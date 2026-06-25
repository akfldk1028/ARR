"""Legal MAAS variant generator for ARR mass GeoJSON.

Take one candidate mass, expand/mutate it with deterministic MAAS morphology
operators, then repair and rank the results by legal FAR/BCR utilization and
diversity. The hard rule is simple: never return a variant that fails the
available ARR legal constraints.
"""

from __future__ import annotations

from typing import Any

from shapely.geometry import box, mapping
from shapely.affinity import scale as shapely_scale, translate as shapely_translate

from design.maas.diversity import diversity_score, polygon_iou, shape_signature
from design.maas.design_quality import attach_design_quality_evidence
from design.maas.floor_groups import build_floor_groups
from design.maas.grammar import get_sequence_label
from design.maas.legal_envelope import (
    FloorPlateStack,
    build_floor_plate_stack,
    build_legal_envelope,
    failed_constraint_metrics,
)
from design.maas.morphology_operators import largest_polygon
from design.maas.parking_requirements import (
    apply_parking_requirement_to_props,
    load_parking_requirement_rules,
    resolve_candidate_parking_requirement,
)
from design.maas.parking_strategy import attach_parking_strategy
from design.maas.research_backends import d4descent_design_evidence
from design.maas.seed_library import generate_seed_variants, seed_library_metadata
from design.services.mass_evaluator import get_floor_height
from design.services.repair_operator import repair_design
from design.services.site_geometry import geojson_to_polygon, utm_to_wgs84, wgs84_to_utm


def _operator_family(operator: str) -> str:
    if operator.endswith("_layered"):
        operator = operator[:-8]
    if operator == "legal_layered_max":
        return "legal_layered"
    if operator.startswith("legal_buildable"):
        return "legal_buildable"
    if operator.startswith("bcr_fill"):
        return "bcr_fill"
    if operator.startswith("notch") or operator.startswith("court_open"):
        return "void_notch"
    if operator.startswith("slender_bar"):
        return "slender_bar"
    if operator.startswith("split_bridge"):
        return "split"
    if operator.startswith("branch_y"):
        return "branch"
    if operator.startswith("pinch_waist"):
        return "pinch"
    if operator.startswith("interlock_cross"):
        return "interlock"
    if operator.startswith("overlap_slabs"):
        return "overlap"
    if operator.startswith("diagonal_connect"):
        return "diagonal_connect"
    if operator.startswith("terrace_link"):
        return "terrace_link"
    if operator.startswith("sloped_roof"):
        return "sloped_roof"
    if operator in {"courtyard_void"}:
        return "courtyard"
    if operator.startswith("tapered"):
        return "taper"
    if operator.startswith("grade_terrace"):
        return "grade"
    if operator in {"terrace_stepback", "shifted_tower", "lift_overlap_slabs"}:
        return "stepback_tower"
    if operator.startswith("grammar_"):
        return operator
    if operator.startswith("inset"):
        return "inset"
    return operator


CONCEPT_ORDER = [
    "legal_layered",
    "void_notch",
    "courtyard",
    "slender_bar",
    "split",
    "branch",
    "pinch",
    "interlock",
    "overlap",
    "diagonal_connect",
    "terrace_link",
    "sloped_roof",
    "stepback_tower",
    "taper",
    "grade",
    "inset",
    "bcr_fill",
    "legal_buildable",
]

SECTION_CONCEPTS = {"stepback_tower", "taper", "grade", "diagonal_connect", "terrace_link", "sloped_roof"}
MIN_GRAMMAR_CONCEPTS = 3
SECTION_CONNECTOR_VERBS = {"diagonal_connect", "terrace_link", "sloped_roof_mass"}
SECTION_CONNECTOR_SHAPE_TOKENS = (
    "diagonal_connect",
    "terrace_link",
    "sloped_roof",
    "step_connector",
    "ribbon_stepback",
)

CONCEPT_LABELS = {
    "legal_layered": "법규엔벨로프",
    "legal_buildable": "최대건폐",
    "bcr_fill": "건폐확장",
    "void_notch": "코너/오픈코트",
    "courtyard": "중정형",
    "slender_bar": "바형",
    "split": "분절/브릿지",
    "branch": "브랜치형",
    "pinch": "핀치형",
    "interlock": "인터락",
    "overlap": "오버랩",
    "diagonal_connect": "사선연결",
    "terrace_link": "테라스연결",
    "sloped_roof": "사선지붕형",
    "stepback_tower": "포디움/타워",
    "taper": "테이퍼",
    "grade": "테라스",
    "inset": "인셋",
}


def _concept_label(operator: str) -> str:
    sequence_key = operator[:-8] if operator.endswith("_layered") else operator
    sequence_label = get_sequence_label(sequence_key)
    if sequence_label:
        return sequence_label
    return CONCEPT_LABELS.get(_operator_family(operator), _operator_family(operator))


def _is_section_connector(feature: dict[str, Any]) -> bool:
    props = feature.get("properties", {}) or {}
    mass_shape = str(props.get("mass_shape") or "")
    if any(token in mass_shape for token in SECTION_CONNECTOR_SHAPE_TOKENS):
        return True
    sequence = props.get("maas_verb_sequence")
    if not isinstance(sequence, list):
        model = props.get("maas_model") if isinstance(props.get("maas_model"), dict) else {}
        sequence = model.get("verb_sequence")
    if not isinstance(sequence, list):
        return False
    return any(
        isinstance(call, dict) and call.get("verb") in SECTION_CONNECTOR_VERBS
        for call in sequence
    )


def _has_resolved_parking_requirement(feature: dict[str, Any]) -> bool:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    precheck = props.get("parking_precheck") if isinstance(props.get("parking_precheck"), dict) else {}
    required = precheck.get("required_count") if isinstance(precheck.get("required_count"), dict) else {}
    return isinstance(required.get("required_spaces"), int)


def _preserve_visible_section_connector(
    selected: list[dict[str, Any]],
    *,
    final_limit: int,
    preferred_operator: str | None = None,
) -> list[dict[str, Any]]:
    if preferred_operator or final_limit <= 1:
        return selected
    visible = selected[:final_limit]
    if any(_is_section_connector(feature) for feature in visible):
        return selected
    connector = next((feature for feature in selected if _is_section_connector(feature)), None)
    if connector is None:
        return selected
    has_parking_gate = any(_has_resolved_parking_requirement(feature) for feature in selected)
    if has_parking_gate and _parking_priority_key(connector) < _parking_priority_key(visible[-1]):
        return selected
    return visible[:-1] + [connector] + [
        feature for feature in selected[final_limit:]
        if feature is not connector
    ]


def _volume_profile(feature: dict[str, Any]) -> tuple[tuple[float, float, float], ...]:
    props = feature.get("properties", {}) or {}
    volumes = props.get("mass_volumes") or props.get("maas_model", {}).get("volumes") or []
    profile: list[tuple[float, float, float]] = []
    for volume in volumes:
        try:
            geom = wgs84_to_utm(geojson_to_polygon(volume.get("geometry")))
            profile.append((
                round(float(volume.get("bottom_height") or 0.0), 1),
                round(float(volume.get("top_height") or 0.0), 1),
                round(float(geom.area), 1),
            ))
        except Exception:
            continue
    if profile:
        return tuple(profile)
    try:
        geom = wgs84_to_utm(geojson_to_polygon(feature.get("geometry")))
        return ((0.0, round(float(props.get("height") or 0.0), 1), round(float(geom.area), 1)),)
    except Exception:
        return ()


def _shape_signature_3d(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties", {}) or {}
    model = props.get("maas_model") if isinstance(props.get("maas_model"), dict) else {}
    floor_plates = props.get("floor_plates") or model.get("floor_plates") or []
    plate_areas = [
        round(float(plate.get("area") or plate.get("area_m2") or 0.0), 2)
        for plate in floor_plates
        if isinstance(plate, dict)
    ]
    return {
        "height_m": props.get("height"),
        "num_floors": props.get("num_floors"),
        "volume_count": len(_volume_profile(feature)),
        "volume_profile": [
            {"bottom_height": bottom, "top_height": top, "area_m2": area}
            for bottom, top, area in _volume_profile(feature)
        ],
        "floor_plate_count": len(plate_areas),
        "floor_plate_area_profile": plate_areas,
    }


def _diversity_class(feature: dict[str, Any]) -> str:
    props = feature.get("properties", {}) or {}
    footprint_diversity = float(props.get("diversity_score") or 0.0)
    signature = props.get("shape_signature_3d") if isinstance(props.get("shape_signature_3d"), dict) else {}
    volume_count = int(signature.get("volume_count") or 0)
    floor_plate_count = int(signature.get("floor_plate_count") or 0)
    if footprint_diversity >= 0.2:
        return "plan_diverse"
    if volume_count > 1 or floor_plate_count > 0:
        return "section_diverse"
    return "near_duplicate"


def _attach_3d_diversity(feature: dict[str, Any]) -> None:
    props = feature.setdefault("properties", {})
    signature = _shape_signature_3d(feature)
    props["shape_signature_3d"] = signature
    props["candidate_diversity"] = {
        "class": _diversity_class(feature),
        "footprint_diversity_score": props.get("diversity_score"),
        "source_iou": props.get("source_iou"),
        "shape_signature_3d": signature,
    }


def _attach_design_quality(feature: dict[str, Any], footprint_utm) -> None:
    attach_design_quality_evidence(
        feature,
        footprint_utm=footprint_utm,
        optimizer_backend=d4descent_design_evidence(),
    )


def _stack_has_meaningful_top(stack: FloorPlateStack) -> bool:
    if not stack.floor_plates:
        return False
    top_area = float(stack.floor_plates[-1].get("area") or 0.0)
    ground_area = float(stack.footprint.area or 0.0)
    return top_area >= max(8.0, ground_area * 0.08)


def _should_use_floor_plate_stack(operator: str, preferred_operator: str | None = None) -> bool:
    """Use the expensive legal stack only for genuinely vertical/sectional forms.

    Plan-shape operators such as notch, courtyard, bar, branch, pinch, interlock
    and overlap lose their architectural identity if every candidate is rebuilt
    as the same envelope-derived floor plate stack. Those should keep their
    repaired footprint and be checked by the normal legal repair/metric pass.
    """
    if operator == preferred_operator:
        return True
    if operator.startswith("grammar_"):
        return any(token in operator for token in ("lift", "taper", "step", "terrace", "tower"))
    return _operator_family(operator) in {
        "legal_layered",
        "stepback_tower",
        "taper",
        "grade",
        "diagonal_connect",
        "terrace_link",
        "sloped_roof",
    }


def _capacity_score(props: dict[str, Any]) -> float:
    far = float(props.get("far_utilization") or 0.0)
    bcr = float(props.get("bcr_utilization") or 0.0)
    return far * 0.62 + bcr * 0.38


def _maas_verb_sequence(operator: str) -> list[dict[str, Any]]:
    """Architectural-language tags adapted from the MAAS verb grammar repo."""
    base = [{"verb": "base", "params": {"proportion": "1/1"}}]
    op = operator[:-8] if operator.endswith("_layered") else operator
    recipes: dict[str, list[dict[str, Any]]] = {
        "legal_layered_max": [{"verb": "taper", "params": {"top_ratio": 0.72}}],
        "legal_buildable_max": [{"verb": "taper", "params": {"top_ratio": 0.72}}],
        "notch_north_west": [{"verb": "notch", "params": {"corner": "-x+y"}}],
        "notch_north_east": [{"verb": "notch", "params": {"corner": "+x+y"}}],
        "notch_south_west": [{"verb": "notch", "params": {"corner": "-x-y"}}],
        "notch_south_east": [{"verb": "notch", "params": {"corner": "+x-y"}}],
        "court_open_north": [{"verb": "cave", "params": {"face": "+y"}}],
        "court_open_south": [{"verb": "cave", "params": {"face": "-y"}}],
        "court_open_east": [{"verb": "cave", "params": {"face": "+x"}}],
        "court_open_west": [{"verb": "cave", "params": {"face": "-x"}}],
        "courtyard_void": [{"verb": "puncture", "params": {"axis": "z"}}],
        "split_bridge_x": [{"verb": "split", "params": {"axis": "x"}}],
        "split_bridge_y": [{"verb": "split", "params": {"axis": "y"}}],
        "branch_y_soft": [{"verb": "branch", "params": {"angle": 28.0}}],
        "branch_y_wide": [{"verb": "branch", "params": {"angle": 42.0}}],
        "pinch_waist_x": [{"verb": "pinch", "params": {"axis": "x"}}],
        "pinch_waist_y": [{"verb": "pinch", "params": {"axis": "y"}}],
        "interlock_cross_soft": [{"verb": "interlock", "params": {"cross_axis": "z"}}, {"verb": "rotate_part", "params": {"axis": "z", "angle": 28.0}}],
        "interlock_cross_diagonal": [{"verb": "interlock", "params": {"cross_axis": "z"}}, {"verb": "rotate_part", "params": {"axis": "z", "angle": -34.0}}],
        "overlap_slabs_x": [{"verb": "overlap", "params": {"offset_vec": [0.5, 0.2, 0.0]}}],
        "overlap_slabs_y": [{"verb": "overlap", "params": {"offset_vec": [0.2, 0.5, 0.0]}}],
        "terrace_stepback": [{"verb": "grade", "params": {"axis": "+z"}}, {"verb": "taper", "params": {"top_ratio": 0.68}}],
        "shifted_tower": [{"verb": "lift", "params": {"other": "6/8"}}, {"verb": "shift", "params": {"axis": "x"}}],
        "tapered_slab": [{"verb": "taper", "params": {"top_ratio": 0.58}}],
        "grade_terrace_north": [{"verb": "grade", "params": {"axis": "+y"}}],
        "lift_overlap_slabs": [{"verb": "overlap", "params": {"offset_vec": [0.4, 0.2, 0.0]}}, {"verb": "lift", "params": {"other": "6/8"}}],
        "diagonal_connect_step_x": [{"verb": "diagonal_connect", "params": {"axis": "x", "upper_ratio": 0.72, "distance_ratio": 0.12}}],
        "diagonal_connect_step_y": [{"verb": "diagonal_connect", "params": {"axis": "y", "upper_ratio": 0.72, "distance_ratio": 0.12}}],
        "terrace_link_north": [{"verb": "terrace_link", "params": {"side": "north", "upper_ratio": 0.84}}],
        "sloped_roof_mass": [{"verb": "sloped_roof_mass", "params": {"upper_ratio": 0.90, "x_ratio": 0.70, "y_ratio": 0.92}}],
    }
    if op.startswith("slender_bar"):
        return base + [{"verb": "compress", "params": {"axis": "x" if op.endswith(("east", "west")) else "y", "factor": 0.54}}]
    if op.startswith("bcr_fill"):
        return base + [{"verb": "expand", "params": {"face": "+x"}}, {"verb": "expand", "params": {"face": "+y"}}]
    if op.startswith("inset"):
        return base + [{"verb": "compress", "params": {"axis": "x", "factor": 0.92}}, {"verb": "compress", "params": {"axis": "y", "factor": 0.92}}]
    return base + recipes.get(op, [{"verb": op, "params": {}}])


def _compact_visual_volumes(floor_plates: list[dict[str, Any]], operator: str) -> list[dict[str, Any]]:
    """Build the MAAS volume representation from legal floor plates.

    The volume geometry is not a separate render-only artifact. It is the
    user-facing MAAS mass, and it is derived from floor plates that have already
    been clipped by the legal envelope. Using each band's top plate keeps the
    full volume inside the same legal envelope.
    """
    if not floor_plates:
        return []
    n = len(floor_plates)
    family = _operator_family(operator)
    wants_stepped_display = (
        "step" in operator
        or "terrace" in operator
        or "grade" in operator
        or "diagonal_connect" in operator
        or "sloped_roof" in operator
        or family in {"stepback_tower", "grade"}
    )
    if wants_stepped_display and n >= 4:
        raw_cuts = [
            (0, max(0, n // 4 - 1)),
            (max(0, n // 4), max(0, n // 2 - 1)),
            (max(0, n // 2), max(0, (n * 3) // 4 - 1)),
            (max(0, (n * 3) // 4), n - 1),
        ]
        cuts = []
        for start, end in raw_cuts:
            if start <= end and (not cuts or cuts[-1] != (start, end)):
                cuts.append((start, end))
    elif n <= 2:
        cuts = [(0, n - 1)]
    elif family in {"legal_layered", "stepback_tower", "taper", "grade"}:
        cuts = [(0, max(0, n // 3)), (max(0, n // 3 + 1), n - 1)]
    else:
        cuts = [(0, max(0, n // 2)), (max(0, n // 2 + 1), n - 1)]

    volumes: list[dict[str, Any]] = []
    previous_top = 0.0
    for band_index, (start, end) in enumerate(cuts):
        if start > end or end >= n:
            continue
        top_plate = floor_plates[end]
        top_height = float(top_plate.get("top_height") or 0.0)
        if top_height <= previous_top:
            continue
        volumes.append({
            "band": band_index,
            "bottom_height": round(previous_top, 2),
            "top_height": round(top_height, 2),
            "geometry": top_plate.get("geometry"),
            "role": "morphology_volume",
        })
        previous_top = top_height
    return volumes


def _maas_model(
    *,
    operator: str,
    floor_plates: list[dict[str, Any]],
    props: dict[str, Any],
    site_area_m2: float,
) -> dict[str, Any]:
    """Single integrated object for agents/frontend: morphology + legal audit."""
    return {
        "algorithm": "maas_legal_envelope",
        "operator": operator,
        "verb_sequence": _maas_verb_sequence(operator),
        "volumes": _compact_visual_volumes(floor_plates, operator),
        "floor_plates": floor_plates,
        "floor_groups": build_floor_groups(
            floor_plates,
            site_area_m2=site_area_m2,
            building_type=str(props.get("building_type") or ""),
        ),
        "legal_metrics": {
            "far": props.get("far"),
            "bcr": props.get("bcr"),
            "height": props.get("height"),
            "num_floors": props.get("num_floors"),
            "footprint_area": props.get("footprint_area"),
            "floor_area": props.get("floor_area"),
            "min_setback": props.get("min_setback"),
            "open_pct": props.get("open_pct"),
        },
    }


def _single_volume_model(operator: str, feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties", {}) or {}
    volumes = [{
        "band": 0,
        "bottom_height": 0.0,
        "top_height": props.get("height") or 0.0,
        "geometry": feature.get("geometry"),
        "role": "morphology_volume",
    }]
    if props.get("lower_height") is not None and props.get("upper_geometry") is not None:
        lower_height = float(props.get("lower_height") or 0.0)
        total_height = float(props.get("height") or lower_height)
        if total_height > lower_height > 0:
            volumes = [
                {
                    "band": 0,
                    "bottom_height": 0.0,
                    "top_height": round(lower_height, 2),
                    "geometry": feature.get("geometry"),
                    "role": "morphology_volume",
                },
                {
                    "band": 1,
                    "bottom_height": round(lower_height, 2),
                    "top_height": round(total_height, 2),
                    "geometry": props.get("upper_geometry"),
                    "role": "morphology_volume",
                },
            ]
    return {
        "algorithm": "maas_legal_envelope",
        "operator": operator,
        "verb_sequence": _maas_verb_sequence(operator),
        "volumes": volumes,
        "floor_plates": [],
        "legal_metrics": {
            "far": props.get("far"),
            "bcr": props.get("bcr"),
            "height": props.get("height"),
            "num_floors": props.get("num_floors"),
            "footprint_area": props.get("footprint_area"),
            "floor_area": props.get("floor_area"),
            "min_setback": props.get("min_setback"),
            "open_pct": props.get("open_pct"),
        },
    }


def _apply_variant_verb_sequence(feature: dict[str, Any], variant) -> None:
    sequence = getattr(variant, "verb_sequence", ()) or ()
    if not sequence:
        return
    props = feature.get("properties", {}) or {}
    sequence_list = [dict(item) for item in sequence]
    props["maas_verb_sequence"] = sequence_list
    model = props.get("maas_model")
    if isinstance(model, dict):
        model["verb_sequence"] = sequence_list
        model["grammar_sequence"] = variant.operator
        model["grammar_label"] = _concept_label(variant.operator)


def _select_diverse_features(
    features: list[dict[str, Any]],
    max_variants: int,
    preferred_operator: str | None = None,
) -> list[dict[str, Any]]:
    """Pick the best legal candidate per spatial concept, then fill by score.

    MAAS is useful here only if the user sees different architectural
    strategies, not eighteen tiny variations of the same sunlight stepback.
    The first pass therefore reserves one slot for each concept family.
    """
    limit = max(1, max_variants)
    if len(features) <= 1:
        return features

    by_score = sorted(features, key=lambda f: f["properties"].get("maas_score", 0), reverse=True)
    selected: list[dict[str, Any]] = []

    # Keep an explicit user/agent-preferred operator first; otherwise keep the
    # legal capacity anchor first. Family coverage is applied after that.
    anchor = None
    if preferred_operator:
        anchor = next((f for f in by_score if f["properties"].get("mass_shape") == preferred_operator), None)
    if anchor is None:
        anchor = next((f for f in by_score if f["properties"].get("mass_shape") == "legal_layered_max"), None)
    if anchor is not None:
        selected.append(anchor)

    def is_near_duplicate(feature: dict[str, Any]) -> bool:
        if preferred_operator and feature["properties"].get("mass_shape") == preferred_operator:
            return False
        try:
            family = _operator_family(feature["properties"].get("mass_shape", ""))
            candidate = geojson_to_polygon(feature["geometry"])
            candidate_profile = _volume_profile(feature)
            candidate_is_connector = _is_section_connector(feature)
            for existing in selected:
                existing_family = _operator_family(existing["properties"].get("mass_shape", ""))
                existing_is_connector = _is_section_connector(existing)
                iou = polygon_iou(candidate, geojson_to_polygon(existing["geometry"]))
                if iou >= 0.98 and candidate_profile == _volume_profile(existing):
                    return True
                if family in {"bcr_fill", "legal_buildable"} and iou >= 0.96:
                    return True
                # A podium/tower or taper can legitimately share the same
                # ground footprint with another concept while differing in
                # section. Treat only same-family high-IoU footprints as
                # duplicates; cross-family vertical typologies must survive.
                if family != existing_family:
                    continue
                if iou >= 0.96:
                    return True
            return False
        except Exception:
            return False

    by_family: dict[str, list[dict[str, Any]]] = {}
    for feature in by_score:
        family = _operator_family(feature["properties"].get("mass_shape", ""))
        by_family.setdefault(family, []).append(feature)

    # Keep at least one sectional/stepback strategy when the parcel can support
    # it. The user still needs a legal terrace/step mass as an option; the
    # diversity pass below only prevents that family from dominating the list.
    if limit > len(selected) and not preferred_operator:
        has_section = any(
            _operator_family(s["properties"].get("mass_shape", "")) in SECTION_CONCEPTS
            for s in selected
        )
        if not has_section:
            section_candidates = [
                f for family in ("stepback_tower", "grade", "taper")
                for f in by_family.get(family, [])
            ]
            for feature in section_candidates:
                if feature in selected or is_near_duplicate(feature):
                    continue
                selected.append(feature)
                break

    # A stepped mass alone is not enough for MAAS design exploration. Preserve
    # at least one section connector option so the user can compare step-only
    # forms against diagonal/terrace/sloped linking masses in the default run.
    if limit > len(selected) and not preferred_operator:
        has_connector = any(_is_section_connector(feature) for feature in selected)
        if not has_connector:
            connector_candidates = [f for f in by_score if _is_section_connector(f)]
            for feature in connector_candidates:
                if feature in selected or is_near_duplicate(feature):
                    continue
                selected.append(feature)
                break

    ordered_families = CONCEPT_ORDER + [
        family for family in by_family
        if family not in CONCEPT_ORDER
    ]

    for family in ordered_families:
        if len(selected) >= limit:
            break
        if any(_operator_family(s["properties"].get("mass_shape", "")) == family for s in selected):
            continue
        for feature in by_family.get(family, []):
            if feature in selected or is_near_duplicate(feature):
                continue
            selected.append(feature)
            break

    if limit > len(selected) and not preferred_operator:
        grammar_candidates = [
            f for f in by_score
            if str(f["properties"].get("mass_shape", "")).startswith("grammar_")
        ]
        for feature in grammar_candidates:
            if len(selected) >= limit:
                break
            grammar_count = sum(
                1 for s in selected
                if str(s["properties"].get("mass_shape", "")).startswith("grammar_")
            )
            if grammar_count >= min(MIN_GRAMMAR_CONCEPTS, limit):
                break
            if feature in selected or is_near_duplicate(feature):
                continue
            selected.append(feature)

    # Only backfill same-family variants when the parcel yielded too few
    # concepts. For normal parcels, stop at one representative per spatial
    # concept so the UI does not become a list of near-identical stepbacks.
    min_required = limit
    while len(selected) < min_required:
        remaining = [f for f in by_score if f not in selected and not is_near_duplicate(f)]
        if not remaining:
            break
        selected_polys = [geojson_to_polygon(f["geometry"]) for f in selected]
        best = max(
            remaining,
            key=lambda f: (
                _capacity_score(f["properties"]) * 0.65
                + diversity_score(geojson_to_polygon(f["geometry"]), selected_polys, None) * 0.35
            ),
        )
        selected.append(best)

    if preferred_operator:
        return selected
    return selected[:limit]


def _mass_feature(
    *,
    operator: str,
    footprint_utm,
    upper_footprint_utm,
    num_floors: int,
    lower_floor_fraction: float | None,
    site_utm,
    site_area_m2: float,
    building_type: str,
    notes: tuple[str, ...],
    diversity: float,
    source_iou: float,
) -> dict[str, Any]:
    floor_height = get_floor_height(building_type)
    height = num_floors * floor_height
    footprint_area = footprint_utm.area
    open_pct = max(0.0, 100.0 - (footprint_area / site_area_m2 * 100)) if site_area_m2 > 0 else 0.0

    lower_floors = num_floors
    upper_floors = 0
    lower_height = None
    if upper_footprint_utm is not None and num_floors >= 2:
        fraction = lower_floor_fraction if lower_floor_fraction is not None else 0.5
        lower_floors = max(1, min(num_floors - 1, int(round(num_floors * fraction))))
        upper_floors = num_floors - lower_floors
        lower_height = lower_floors * floor_height
        floor_area = footprint_area * lower_floors + upper_footprint_utm.area * upper_floors
    else:
        floor_area = footprint_area * num_floors

    props = {
        "algorithm": "maas_legal_envelope",
        "mass_shape": operator,
        "maas_concept": _concept_label(operator),
        "height": round(height, 2),
        "num_floors": num_floors,
        "floor_height": floor_height,
        "footprint_area": round(footprint_area, 2),
        "floor_area": round(floor_area, 2),
        "bcr": round(footprint_area / site_area_m2 * 100, 2) if site_area_m2 > 0 else 0,
        "far": round(floor_area / site_area_m2 * 100, 2) if site_area_m2 > 0 else 0,
        "min_setback": round(float(footprint_utm.distance(site_utm.boundary)), 2),
        "open_pct": round(open_pct, 2),
        "diversity_score": diversity,
        "source_iou": source_iou,
        "shape_signature": shape_signature(footprint_utm),
        "notes": list(notes),
    }
    if lower_height is not None and upper_footprint_utm is not None:
        props["lower_height"] = round(lower_height, 2)
        props["step_floor"] = lower_floors
        props["upper_geometry"] = mapping(utm_to_wgs84(upper_footprint_utm))

    feature = {
        "type": "Feature",
        "geometry": mapping(utm_to_wgs84(footprint_utm)),
        "properties": props,
    }
    model = _single_volume_model(operator, feature)
    props["maas_model"] = model
    props["mass_volumes"] = model["volumes"]
    props["maas_verb_sequence"] = model["verb_sequence"]
    attach_parking_strategy(
        props,
        site_area_m2=site_area_m2,
        building_type=building_type,
        footprint_utm=footprint_utm,
        site_utm=site_utm,
    )
    _attach_3d_diversity(feature)
    return feature


def _floor_plate_feature(
    *,
    stack: FloorPlateStack,
    site_utm,
    site_area_m2: float,
    building_type: str,
    diversity: float,
    source_iou: float,
) -> dict[str, Any]:
    floor_height = get_floor_height(building_type)
    footprint_area = stack.footprint.area
    open_pct = max(0.0, 100.0 - (footprint_area / site_area_m2 * 100)) if site_area_m2 > 0 else 0.0
    props = {
        "algorithm": "maas_legal_envelope",
        "mass_shape": stack.operator,
        "maas_concept": _concept_label(stack.operator),
        "building_type": building_type,
        "height": round(stack.height_m, 2),
        "num_floors": stack.num_floors,
        "floor_height": floor_height,
        "footprint_area": round(footprint_area, 2),
        "floor_area": round(stack.total_floor_area_m2, 2),
        "bcr": round(footprint_area / site_area_m2 * 100, 2) if site_area_m2 > 0 else 0,
        "far": round(stack.total_floor_area_m2 / site_area_m2 * 100, 2) if site_area_m2 > 0 else 0,
        "min_setback": round(float(stack.footprint.distance(site_utm.boundary)), 2),
        "open_pct": round(open_pct, 2),
        "diversity_score": diversity,
        "source_iou": source_iou,
        "shape_signature": shape_signature(stack.footprint),
        "notes": list(stack.notes),
    }
    model = _maas_model(
        operator=stack.operator,
        floor_plates=stack.floor_plates,
        props=props,
        site_area_m2=site_area_m2,
    )
    props["maas_model"] = model
    # Compatibility fields for existing UI/tests. The canonical source is
    # properties.maas_model, so agents should read that first.
    props["floor_plates"] = model["floor_plates"]
    props["floor_groups"] = model["floor_groups"]
    props["mass_volumes"] = model["volumes"]
    props["maas_verb_sequence"] = model["verb_sequence"]
    attach_parking_strategy(
        props,
        site_area_m2=site_area_m2,
        building_type=building_type,
        footprint_utm=stack.footprint,
        site_utm=site_utm,
    )
    feature = {
        "type": "Feature",
        "geometry": mapping(utm_to_wgs84(stack.footprint)),
        "properties": props,
    }
    _attach_3d_diversity(feature)
    return feature


def generate_legal_mass_variants(
    *,
    mass_geojson: dict[str, Any],
    site_polygon_geojson: dict[str, Any],
    constraints: list[dict[str, Any]] | None = None,
    building_type: str = "공동주택",
    max_variants: int = 6,
    sunlight_envelope: dict[str, Any] | None = None,
    setback_geometries: dict[str, Any] | None = None,
    include_interactive_seed: bool = False,
    preferred_operator: str | None = None,
    pnu: str | None = None,
    parking_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return legal, diverse variants derived from a selected mass GeoJSON."""
    if mass_geojson.get("type") != "Feature":
        raise ValueError("mass_geojson must be a GeoJSON Feature")

    source_wgs = largest_polygon(geojson_to_polygon(mass_geojson.get("geometry")))
    source_utm = wgs84_to_utm(source_wgs)
    site_wgs = geojson_to_polygon(site_polygon_geojson)
    site_utm = wgs84_to_utm(site_wgs)
    site_area_m2 = site_utm.area

    envelope = build_legal_envelope(
        site_utm=site_utm,
        constraints=constraints,
        building_type=building_type,
        sunlight_envelope=sunlight_envelope,
        setback_geometries=setback_geometries,
    )
    limits = envelope.limits
    max_seed_floors = envelope.max_seed_floors

    repaired_source, repaired_floors, source_actions = repair_design(
        source_utm, site_utm, max_seed_floors, limits,
        sunlight_envelope=sunlight_envelope,
    )
    if repaired_source is None:
        raise ValueError("source mass cannot be repaired into the site/legal envelope")

    selected = []
    selected_polygons = []
    rejected = []

    layered_stack = build_floor_plate_stack(envelope, sunlight_envelope)
    if layered_stack is not None:
        source_iou = round(1.0 - diversity_score(layered_stack.footprint, [], repaired_source), 4)
        diversity = diversity_score(layered_stack.footprint, selected_polygons, repaired_source)
        feature = _floor_plate_feature(
            stack=layered_stack,
            site_utm=site_utm,
            site_area_m2=site_area_m2,
            building_type=building_type,
            diversity=diversity,
            source_iou=source_iou,
        )
        props = feature["properties"]
        failed_metrics = failed_constraint_metrics(props, envelope)
        if failed_metrics:
            rejected.append({
                "operator": layered_stack.operator,
                "reason": "legal_metric_failed_after_layering",
                "failed_metrics": failed_metrics,
            })
        else:
            far_utilization = min(1.0, props["far"] / envelope.far_limit) if envelope.far_limit > 0 else 0.0
            bcr_utilization = min(1.0, props["bcr"] / envelope.bcr_limit) if envelope.bcr_limit > 0 else 0.0
            props["far_utilization"] = round(far_utilization, 4)
            props["bcr_utilization"] = round(bcr_utilization, 4)
            props["maas_score"] = round(far_utilization * 0.52 + bcr_utilization * 0.30 + diversity * 0.18, 4)
            _attach_design_quality(feature, layered_stack.footprint)
            selected.append(feature)
            selected_polygons.append(layered_stack.footprint)

    variants = generate_seed_variants(
        repaired_source,
        envelope,
        include_interactive_seed=include_interactive_seed,
    )

    for variant in variants:
        repaired_fp, floors, actions = repair_design(
            variant.footprint,
            site_utm,
            max_seed_floors,
            limits,
            sunlight_envelope=sunlight_envelope,
        )
        if repaired_fp is None:
            rejected.append({"operator": variant.operator, "reason": "repair_failed"})
            continue

        upper = variant.upper_footprint
        if upper is not None:
            upper = upper.intersection(repaired_fp)
            if upper.is_empty or upper.area < 1.0:
                upper = None

        source_iou = round(1.0 - diversity_score(repaired_fp, [], repaired_source), 4)
        diversity = diversity_score(repaired_fp, selected_polygons, repaired_source)
        variant_stack = None
        if _should_use_floor_plate_stack(variant.operator, preferred_operator):
            variant_stack = build_floor_plate_stack(
                envelope,
                sunlight_envelope,
                operator=variant.operator if variant.operator == preferred_operator else f"{variant.operator}_layered",
                ground_footprint=repaired_fp,
                upper_footprint=upper,
                lower_floor_fraction=variant.lower_floor_fraction,
            )
        if (
            variant_stack is not None
            and variant_stack.total_floor_area_m2 >= repaired_fp.area
            and _stack_has_meaningful_top(variant_stack)
        ):
            feature = _floor_plate_feature(
                stack=variant_stack,
                site_utm=site_utm,
                site_area_m2=site_area_m2,
                building_type=building_type,
                diversity=diversity,
                source_iou=source_iou,
            )
            feature["properties"]["notes"].extend(list(variant.notes + tuple(actions)))
            _apply_variant_verb_sequence(feature, variant)
        else:
            feature = _mass_feature(
                operator=variant.operator,
                footprint_utm=repaired_fp,
                upper_footprint_utm=upper,
                num_floors=floors,
                lower_floor_fraction=variant.lower_floor_fraction,
                site_utm=site_utm,
                site_area_m2=site_area_m2,
                building_type=building_type,
                notes=variant.notes + tuple(actions),
                diversity=diversity,
                source_iou=source_iou,
            )
            _apply_variant_verb_sequence(feature, variant)
        props = feature["properties"]
        if (
            variant.operator == "grammar_sunlight_multi_step"
            and len(props.get("mass_volumes") or []) < 3
        ):
            rejected.append({
                "operator": variant.operator,
                "reason": "not_enough_floor_bands_for_multi_step",
            })
            continue
        failed_metrics = failed_constraint_metrics(props, envelope)
        if failed_metrics:
            rejected.append({
                "operator": variant.operator,
                "reason": "legal_metric_failed_after_repair",
                "failed_metrics": failed_metrics,
            })
            continue

        far_utilization = min(1.0, props["far"] / envelope.far_limit) if envelope.far_limit > 0 else 0.0
        bcr_utilization = min(1.0, props["bcr"] / envelope.bcr_limit) if envelope.bcr_limit > 0 else 0.0
        props["far_utilization"] = round(far_utilization, 4)
        props["bcr_utilization"] = round(bcr_utilization, 4)
        props["maas_score"] = round(far_utilization * 0.45 + bcr_utilization * 0.35 + diversity * 0.20, 4)
        _attach_design_quality(feature, repaired_fp)
        selected.append(feature)
        selected_polygons.append(repaired_fp)

    selected.sort(key=lambda f: f["properties"].get("maas_score", 0), reverse=True)
    legal_candidate_pool = list(selected)
    if preferred_operator:
        preferred_index = next(
            (
                i for i, feature in enumerate(selected)
                if feature["properties"].get("mass_shape") == preferred_operator
            ),
            None,
        )
        if preferred_index is not None:
            selected.insert(0, selected.pop(preferred_index))
    selected = _select_diverse_features(selected, max(1, max_variants), preferred_operator=preferred_operator)
    parking_scan_features = list(selected)
    if not preferred_operator:
        parking_scan_features.extend(
            feature for feature in legal_candidate_pool[:24]
            if feature not in parking_scan_features
        )
    _attach_parking_requirements(
        parking_scan_features,
        pnu=pnu,
        building_type=building_type,
        site_utm=site_utm,
        site_area_m2=site_area_m2,
        parking_options=parking_options,
    )
    parking_viable_extras = [
        feature for feature in parking_scan_features
        if feature not in selected and _parking_priority_key(feature)[0] > 0
    ]
    parking_viable_extras.sort(key=_parking_priority_key, reverse=True)
    for feature in parking_viable_extras[:3]:
        selected.append(feature)
    parking_repairs = _parking_repair_candidates(
        selected,
        envelope=envelope,
        site_utm=site_utm,
        site_area_m2=site_area_m2,
        building_type=building_type,
        parking_options=parking_options,
    )
    if parking_repairs:
        _attach_parking_requirements(
            parking_repairs,
            pnu=pnu,
            building_type=building_type,
            site_utm=site_utm,
            site_area_m2=site_area_m2,
            parking_options=parking_options,
        )
        _sync_parking_repair_metadata(parking_repairs)
        selected.extend(parking_repairs)
    parking_visible = [
        feature for feature in selected
        if _parking_priority_key(feature)[1] > 0
    ]
    parking_visible.sort(key=_parking_priority_key, reverse=True)
    review_candidates = [
        feature for feature in selected
        if feature not in parking_visible
    ]
    review_candidates.sort(key=_review_diversity_priority_key, reverse=True)
    selected = parking_visible + review_candidates
    if preferred_operator:
        preferred_index = next(
            (
                i for i, feature in enumerate(selected)
                if feature["properties"].get("mass_shape") == preferred_operator
            ),
            None,
        )
        if preferred_index is not None:
            selected.insert(0, selected.pop(preferred_index))
    final_limit = max(1, max_variants)
    selected = _preserve_visible_section_connector(
        selected,
        final_limit=final_limit,
        preferred_operator=preferred_operator,
    )
    selected = selected[:final_limit]
    for i, feature in enumerate(selected, start=1):
        feature["properties"]["variant_id"] = f"maas_{i:02d}"

    return {
        "mode": "maas_legal_variants",
        "algorithm": "maas_legal_envelope",
        "count": len(selected),
        "seed_library": seed_library_metadata(),
        "source_repair_actions": source_actions,
        "constraints": {
            "bcr_limit": envelope.bcr_limit,
            "far_limit": envelope.far_limit,
            "height_limit": envelope.height_limit,
            "max_seed_floors": envelope.max_seed_floors,
            "has_buildable_footprint": envelope.buildable_footprint is not None,
            "has_floor_plate_stack": layered_stack is not None,
        },
        "feature_collection": {
            "type": "FeatureCollection",
            "features": selected,
        },
        "rejected": rejected,
        "notes": [
            "Legal envelope is the primary generator boundary.",
            "Layered MAAS candidates clip every floor plate by the legal envelope before FAR/BCR scoring.",
            "Selected ARR/legacy mass is treated as a seed for diversity, not as the capacity source.",
            "Each variant is repaired and checked against BCR/FAR/height/sunlight before return.",
            "Variants are ranked by legal FAR/BCR utilization plus geometric diversity.",
        ],
    }


def _attach_parking_requirements(
    features: list[dict[str, Any]],
    *,
    pnu: str | None,
    building_type: str,
    site_utm,
    site_area_m2: float,
    parking_options: dict[str, Any] | None,
) -> None:
    options = parking_options or {}
    road_context = options.get("road_context") if isinstance(options.get("road_context"), dict) else None
    loaded_rules = load_parking_requirement_rules(options=options) if pnu else None
    rules = loaded_rules.get("rules") if isinstance(loaded_rules, dict) and loaded_rules.get("status") == "loaded" else None
    graph_unavailable = loaded_rules if isinstance(loaded_rules, dict) and loaded_rules.get("status") != "loaded" else None
    for feature in features:
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        if graph_unavailable:
            requirement = {
                "status": graph_unavailable.get("status"),
                "required_spaces": None,
                "accessible": {
                    "status": graph_unavailable.get("status"),
                    "accessible_min": None,
                    "accessible_max": None,
                },
                "reason": graph_unavailable.get("reason"),
            }
        else:
            feature_options = _parking_options_for_feature(options, props, building_type)
            requirement = resolve_candidate_parking_requirement(
                pnu=pnu,
                building_type=building_type,
                facility_area_m2=_float_or_none(props.get("floor_area")),
                options=feature_options,
                rules=rules,
            )
        apply_parking_requirement_to_props(props, requirement)
        try:
            footprint_utm = largest_polygon(wgs84_to_utm(geojson_to_polygon(feature.get("geometry"))))
        except Exception:
            footprint_utm = None
        attach_parking_strategy(
            props,
            site_area_m2=site_area_m2,
            building_type=building_type,
            footprint_utm=footprint_utm,
            site_utm=site_utm,
            road_context=road_context,
        )


def _parking_repair_candidates(
    features: list[dict[str, Any]],
    *,
    envelope,
    site_utm,
    site_area_m2: float,
    building_type: str,
    parking_options: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    options = parking_options or {}
    road_context = options.get("road_context") if isinstance(options.get("road_context"), dict) else None
    repaired: list[dict[str, Any]] = []
    seen_signatures: set[tuple[float, float, float]] = set()
    for feature in features:
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        precheck = props.get("parking_precheck") if isinstance(props.get("parking_precheck"), dict) else {}
        layout = precheck.get("layout_candidate") if isinstance(precheck.get("layout_candidate"), dict) else {}
        required_count = precheck.get("required_count") if isinstance(precheck.get("required_count"), dict) else {}
        required = _int_or_none(required_count.get("required_spaces"))
        if required is None or required <= 0:
            required = _int_or_none(layout.get("required_spaces"))
        if required is None or required <= 0:
            required = _int_or_none(props.get("required_parking_spaces"))
        if required is None or required <= 0:
            continue
        if layout.get("status") == "pass" and int(layout.get("provided_spaces") or 0) >= required:
            continue
        try:
            footprint_utm = largest_polygon(wgs84_to_utm(geojson_to_polygon(feature.get("geometry"))))
        except Exception:
            continue
        repair = _find_parking_repair_footprint(
            footprint_utm,
            site_utm=site_utm,
            required_spaces=required,
            road_context=road_context,
            floors=int(float(props.get("num_floors") or 1)),
            building_type=building_type,
        )
        if repair is None:
            continue
        repaired_fp, repair_layout, repair_meta = repair
        signature = (
            round(float(repaired_fp.area), 1),
            round(float(repaired_fp.centroid.x), 1),
            round(float(repaired_fp.centroid.y), 1),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        floors = int(float(props.get("num_floors") or 1))
        source_score = float(props.get("maas_score") or 0.0)
        source_iou = round(1.0 - diversity_score(repaired_fp, [], footprint_utm), 4)
        diversity = float(props.get("diversity_score") or 0.0)
        candidate = _mass_feature(
            operator="parking_repair_shrink",
            footprint_utm=repaired_fp,
            upper_footprint_utm=None,
            num_floors=max(1, floors),
            lower_floor_fraction=None,
            site_utm=site_utm,
            site_area_m2=site_area_m2,
            building_type=building_type,
            notes=(
                "parking_repair: reshape/translate footprint to fit required small-lot parking",
                f"parking_repair_method={repair_meta.get('method')}",
                f"parking_repair_scale=({repair_meta.get('scale_x')},{repair_meta.get('scale_y')})",
                f"parking_repair_offset_m=({repair_meta.get('dx')},{repair_meta.get('dy')})",
                f"parking_repair_layout_status={repair_layout.get('status')}",
            ),
            diversity=diversity,
            source_iou=source_iou,
        )
        cprops = candidate["properties"]
        if failed_constraint_metrics(cprops, envelope):
            continue
        cprops["maas_score"] = round(max(0.0, source_score - 0.18), 4)
        _attach_design_quality(candidate, repaired_fp)
        cprops["parking_repair"] = {
            "source_variant_id": props.get("variant_id"),
            "source_mass_shape": props.get("mass_shape"),
            "method": repair_meta.get("method"),
            "scale_factor": repair_meta.get("scale_factor"),
            "scale": {"x": repair_meta.get("scale_x"), "y": repair_meta.get("scale_y")},
            "offset_m": {"x": repair_meta.get("dx"), "y": repair_meta.get("dy")},
            "area_retention": repair_meta.get("area_retention"),
            "target_required_spaces": repair_meta.get("candidate_required_spaces", required),
            "preview_layout_status": repair_layout.get("status"),
            "preview_layout_mode": repair_layout.get("placement_mode"),
            "preview_adjacency": repair_layout.get("adjacency"),
            "authority_review": repair_layout.get("status") != "pass",
        }
        repaired.append(candidate)
        if floors >= 2 and footprint_utm.area > repaired_fp.area * 1.2:
            lifted_candidate = _mass_feature(
                operator="parking_repair_ground_void",
                footprint_utm=repaired_fp,
                upper_footprint_utm=footprint_utm,
                num_floors=max(2, floors),
                lower_floor_fraction=1.0 / max(2, floors),
                site_utm=site_utm,
                site_area_m2=site_area_m2,
                building_type=building_type,
                notes=(
                    "parking_repair: keep upper mass while reducing ground footprint for parking",
                    f"parking_repair_method={repair_meta.get('method')}",
                    f"parking_repair_scale=({repair_meta.get('scale_x')},{repair_meta.get('scale_y')})",
                    f"parking_repair_offset_m=({repair_meta.get('dx')},{repair_meta.get('dy')})",
                    f"parking_repair_layout_status={repair_layout.get('status')}",
                ),
                diversity=diversity,
                source_iou=source_iou,
            )
            lifted_props = lifted_candidate["properties"]
            if failed_constraint_metrics(lifted_props, envelope):
                continue
            lifted_props["maas_score"] = round(max(0.0, source_score - 0.08), 4)
            _attach_design_quality(lifted_candidate, repaired_fp)
            lifted_props["parking_repair"] = {
                **cprops["parking_repair"],
                "method": "ground_void_upper_mass",
                "base_method": repair_meta.get("method"),
                "upper_mass_retained": True,
                "upper_source_mass_shape": props.get("mass_shape"),
                "upper_floor_start": lifted_props.get("step_floor"),
            }
            repaired.append(lifted_candidate)
        break
    return repaired


def _sync_parking_repair_metadata(features: list[dict[str, Any]]) -> None:
    for feature in features:
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        repair = props.get("parking_repair") if isinstance(props.get("parking_repair"), dict) else None
        precheck = props.get("parking_precheck") if isinstance(props.get("parking_precheck"), dict) else {}
        requirement = precheck.get("required_count") if isinstance(precheck.get("required_count"), dict) else {}
        layout = precheck.get("layout_candidate") if isinstance(precheck.get("layout_candidate"), dict) else {}
        if repair is None:
            continue
        final_required = _int_or_none(requirement.get("required_spaces"))
        final_provided = _int_or_none(layout.get("provided_spaces"))
        repair["final_required_spaces"] = final_required
        repair["final_provided_spaces"] = final_provided
        repair["final_layout_status"] = layout.get("status")
        repair["final_layout_mode"] = layout.get("placement_mode")
        repair["final_adjacency"] = layout.get("adjacency")
        repair["authority_review"] = bool(
            layout.get("turning_clearance", {}).get("authority_review")
            if isinstance(layout.get("turning_clearance"), dict)
            else layout.get("status") != "pass"
        )


def _find_parking_repair_footprint(
    footprint_utm,
    *,
    site_utm,
    required_spaces: int,
    road_context: dict[str, Any] | None,
    floors: int,
    building_type: str,
) -> tuple[Any, dict[str, Any], dict[str, Any]] | None:
    from design.maas.parking_layout import generate_parking_layout_candidate
    from design.maas.parking_strategy import _parking_drive_envelope, _parking_envelope

    best: tuple[tuple[Any, ...], Any, dict[str, Any], dict[str, Any]] | None = None
    source_area = float(footprint_utm.area or 0.0)
    for candidate_fp, meta in _iter_parking_repair_footprints(footprint_utm):
        if candidate_fp.is_empty or candidate_fp.area < 8.0:
            continue
        if not site_utm.buffer(1e-7).covers(candidate_fp):
            continue
        envelope = _parking_envelope(
            "ground_surface",
            footprint_utm=candidate_fp,
            site_utm=site_utm,
        )
        drive_envelope = _parking_drive_envelope(
            "ground_surface",
            footprint_utm=candidate_fp,
            site_utm=site_utm,
        )
        candidate_required = _estimate_candidate_repair_required_spaces(
            candidate_fp,
            floors=floors,
            building_type=building_type,
            fallback_required_spaces=required_spaces,
        )
        layout = generate_parking_layout_candidate(
            envelope,
            drive_envelope=drive_envelope,
            required_spaces=candidate_required,
            strategy="ground_surface",
            road_context=road_context,
        )
        provided = int(layout.get("provided_spaces") or 0)
        if provided < candidate_required:
            continue
        adjacency = layout.get("adjacency") if isinstance(layout.get("adjacency"), dict) else {}
        status = str(layout.get("status") or "")
        area_retention = float(candidate_fp.area / source_area) if source_area > 0 else 0.0
        meta = {
            **meta,
            "area_retention": round(area_retention, 4),
            "candidate_required_spaces": candidate_required,
        }
        score = (
            3 if status == "pass" else 2 if status in {"needs_drive_connectivity_review", "needs_swept_path_review"} else 0,
            1 if adjacency.get("row_contiguous_ok") else 0,
            1 if adjacency.get("contiguous_ok") else 0,
            round(area_retention, 4),
            1 if meta.get("method") in {"edge_notch", "axis_compress"} else 0,
            -float(meta.get("movement_m") or 0.0),
        )
        if best is None or score > best[0]:
            best = (score, candidate_fp, layout, meta)
    if best is None:
        return None
    _score, candidate_fp, layout, meta = best
    return candidate_fp, layout, meta


def _estimate_candidate_repair_required_spaces(
    footprint_utm,
    *,
    floors: int,
    building_type: str,
    fallback_required_spaces: int,
) -> int:
    if not _is_common_housing(building_type):
        return fallback_required_spaces
    floor_count = max(1, floors)
    footprint_area = float(getattr(footprint_utm, "area", 0.0) or 0.0)
    if footprint_area <= 0:
        return fallback_required_spaces
    exclusive_area_per_unit = footprint_area * 0.75
    total_exclusive_area = exclusive_area_per_unit * floor_count
    area_ratio_spaces = total_exclusive_area / 75.0
    if exclusive_area_per_unit <= 30.0:
        min_per_unit = 0.5
    elif exclusive_area_per_unit <= 60.0:
        min_per_unit = 0.8
    else:
        min_per_unit = 1.0
    household_min_spaces = floor_count * min_per_unit
    return max(1, int(__import__("math").ceil(max(area_ratio_spaces, household_min_spaces))))


def _iter_parking_repair_footprints(footprint_utm) -> list[tuple[Any, dict[str, Any]]]:
    candidates: list[tuple[Any, dict[str, Any]]] = []
    offsets = (0.0, -4.0, 4.0, -8.0, 8.0)

    def add_scaled(method: str, sx: float, sy: float) -> None:
        scaled = shapely_scale(footprint_utm, xfact=sx, yfact=sy, origin="centroid")
        for dx in offsets:
            for dy in offsets:
                moved = shapely_translate(scaled, xoff=dx, yoff=dy)
                candidates.append((moved, {
                    "method": method,
                    "scale_factor": round(min(sx, sy), 4),
                    "scale_x": sx,
                    "scale_y": sy,
                    "dx": dx,
                    "dy": dy,
                    "movement_m": abs(dx) + abs(dy),
                }))

    for factor in (0.74, 0.66, 0.58, 0.50):
        add_scaled("uniform_shrink", factor, factor)
    for factor in (0.82, 0.74, 0.66, 0.58):
        add_scaled("axis_compress", factor, 1.0)
        add_scaled("axis_compress", 1.0, factor)

    minx, miny, maxx, maxy = footprint_utm.bounds
    span_x = maxx - minx
    span_y = maxy - miny
    strip_specs = [
        ("west", minx, miny, minx + width, maxy)
        for width in (2.0, 3.5, 5.0, 6.5, 8.0)
        if width < span_x
    ] + [
        ("east", maxx - width, miny, maxx, maxy)
        for width in (2.0, 3.5, 5.0, 6.5, 8.0)
        if width < span_x
    ] + [
        ("south", minx, miny, maxx, miny + depth)
        for depth in (2.0, 3.5, 5.0, 6.5, 8.0)
        if depth < span_y
    ] + [
        ("north", minx, maxy - depth, maxx, maxy)
        for depth in (2.0, 3.5, 5.0, 6.5, 8.0)
        if depth < span_y
    ]
    for edge, a, b, c, d in strip_specs:
        cut = box(a, b, c, d)
        diff = footprint_utm.difference(cut)
        repaired = largest_polygon(diff)
        if repaired.is_empty:
            continue
        for dx in (0.0, -4.0, 4.0):
            for dy in (0.0, -4.0, 4.0):
                moved = shapely_translate(repaired, xoff=dx, yoff=dy)
                candidates.append((moved, {
                    "method": "edge_notch",
                    "edge": edge,
                    "scale_factor": None,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                    "dx": dx,
                    "dy": dy,
                    "movement_m": abs(dx) + abs(dy),
                }))
    return candidates


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parking_options_for_feature(options: dict[str, Any], props: dict[str, Any], building_type: str) -> dict[str, Any]:
    result = dict(options)
    if result.get("housing_unit_schedule") or not _is_common_housing(building_type):
        return result
    schedule = _estimate_housing_unit_schedule(props)
    if schedule:
        result["housing_unit_schedule"] = schedule
        result.setdefault("jurisdiction_type", "special_city")
    return result


def _is_common_housing(building_type: str) -> bool:
    text = building_type or ""
    return any(token in text for token in ("공동주택", "아파트", "연립", "다세대"))


def _estimate_housing_unit_schedule(props: dict[str, Any]) -> list[dict[str, Any]]:
    plates = props.get("floor_plates")
    if not isinstance(plates, list) or not plates:
        model = props.get("maas_model") if isinstance(props.get("maas_model"), dict) else {}
        plates = model.get("floor_plates") if isinstance(model.get("floor_plates"), list) else []
    if not isinstance(plates, list) or not plates:
        footprint_area = _float_or_none(props.get("footprint_area"))
        floor_area = _float_or_none(props.get("floor_area"))
        floors = int(_float_or_none(props.get("num_floors")) or 0)
        if floors > 0 and floor_area and floor_area > 0:
            average_floor_area = floor_area / floors
            plates = [{"floor": floor, "area_m2": average_floor_area} for floor in range(1, floors + 1)]
        elif footprint_area and footprint_area > 0 and floors > 0:
            plates = [{"floor": floor, "area_m2": footprint_area} for floor in range(1, floors + 1)]
    schedule: list[dict[str, Any]] = []
    exclusive_ratio = 0.75
    for plate in plates:
        if not isinstance(plate, dict):
            continue
        area = _float_or_none(plate.get("area") or plate.get("area_m2"))
        floor = int(_float_or_none(plate.get("floor")) or len(schedule) + 1)
        if area is None or area <= 0:
            continue
        schedule.append({
            "unit_type": f"F{floor:02d}",
            "count": 1,
            "exclusive_area_m2": round(area * exclusive_ratio, 2),
            "gross_floor_plate_area_m2": round(area, 2),
            "exclusive_area_ratio": exclusive_ratio,
            "source": "mass_stage_estimate",
        })
    return schedule


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parking_priority_key(feature: dict[str, Any]) -> tuple[int, int, int, float, float, float]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    precheck = props.get("parking_precheck") if isinstance(props.get("parking_precheck"), dict) else {}
    layout = precheck.get("layout_candidate") if isinstance(precheck.get("layout_candidate"), dict) else {}
    required = layout.get("required_spaces")
    provided = layout.get("provided_spaces")
    unmet = layout.get("unmet_spaces")
    status = layout.get("status")
    if isinstance(required, int) and required > 0 and isinstance(provided, int):
        satisfied = int(provided >= required and (not isinstance(unmet, int) or unmet == 0))
    else:
        satisfied = 0
    status_rank = 3 if status == "pass" and isinstance(required, int) and required > 0 else 2 if status in {"needs_drive_connectivity_review", "needs_aisle_review"} else 0
    repair = props.get("parking_repair") if isinstance(props.get("parking_repair"), dict) else None
    repair_rank = 0 if repair else 1
    floor_area = float(props.get("floor_area") or 0.0)
    footprint_area = float(props.get("footprint_area") or 0.0)
    return (
        satisfied,
        status_rank,
        repair_rank,
        float(props.get("maas_score") or 0.0),
        floor_area,
        footprint_area,
    )


def _review_diversity_priority_key(feature: dict[str, Any]) -> tuple[int, float, float, float]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    diversity = props.get("candidate_diversity") if isinstance(props.get("candidate_diversity"), dict) else {}
    class_rank = {
        "plan_diverse": 3,
        "near_duplicate": 2,
        "section_diverse": 1,
    }.get(diversity.get("class"), 0)
    return (
        class_rank,
        float(props.get("diversity_score") or 0.0),
        float(props.get("maas_score") or 0.0),
        float(props.get("floor_area") or 0.0),
    )


__all__ = ["generate_legal_mass_variants"]
