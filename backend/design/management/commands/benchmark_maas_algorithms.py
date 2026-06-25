from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from statistics import mean
from typing import Any

from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from design.maas import generate_legal_mass_variants
from design.maas.research_backends import d4descent_design_evidence, run_maas_clone_reference_baseline
from design.services.site_geometry import geojson_to_polygon, wgs84_to_utm


DEFAULT_OPERATORS = [
    "grammar_diagonal_step_connector",
    "grammar_terrace_ribbon_stepback",
    "grammar_sloped_roof_envelope",
    "diagonal_connect_step_x",
    "terrace_link_north",
    "sloped_roof_mass",
]

SECTION_CONNECTOR_VERBS = {"diagonal_connect", "terrace_link", "sloped_roof_mass"}
SECTION_CONNECTOR_SHAPE_TOKENS = (
    "diagonal_connect",
    "terrace_link",
    "sloped_roof",
    "step_connector",
    "ribbon_stepback",
)


def _constraints() -> list[dict[str, Any]]:
    return [
        {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "%"},
        {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
        {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 35, "unit": "m"},
    ]


def _is_section_connector_summary(summary: dict[str, Any]) -> bool:
    mass_shape = str(summary.get("mass_shape") or "")
    if any(token in mass_shape for token in SECTION_CONNECTOR_SHAPE_TOKENS):
        return True
    return any(verb in SECTION_CONNECTOR_VERBS for verb in summary.get("sequence_verbs", []))


def _fixture_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "rect_legal_envelope",
            "site_polygon": {
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0010, 37.0000],
                    [127.0010, 37.0010],
                    [127.0000, 37.0010],
                    [127.0000, 37.0000],
                ]],
            },
            "mass_geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [127.0002, 37.0002],
                        [127.0008, 37.0002],
                        [127.0008, 37.0008],
                        [127.0002, 37.0008],
                        [127.0002, 37.0002],
                    ]],
                },
                "properties": {"height": 28.0, "num_floors": 10, "floor_height": 2.8},
            },
        },
        {
            "case_id": "long_bar_repair",
            "site_polygon": {
                "type": "Polygon",
                "coordinates": [[
                    [127.0100, 37.0000],
                    [127.0114, 37.0000],
                    [127.0114, 37.00055],
                    [127.0100, 37.00055],
                    [127.0100, 37.0000],
                ]],
            },
            "mass_geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [127.01015, 37.00008],
                        [127.01125, 37.00008],
                        [127.01125, 37.00047],
                        [127.01015, 37.00047],
                        [127.01015, 37.00008],
                    ]],
                },
                "properties": {"height": 24.0, "num_floors": 8, "floor_height": 3.0},
            },
        },
    ]


def _feature_summary(feature: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    quality = props.get("design_quality") if isinstance(props.get("design_quality"), dict) else {}
    parking = props.get("parking_precheck") if isinstance(props.get("parking_precheck"), dict) else {}
    layout = parking.get("layout_candidate") if isinstance(parking.get("layout_candidate"), dict) else {}
    required_count = parking.get("required_count") if isinstance(parking.get("required_count"), dict) else {}
    parking_evidence_enabled = required_count.get("required_spaces") is not None
    legal_pass = (
        float(props.get("bcr") or 0.0) <= float(limits["bcr_limit"]) + 0.1
        and float(props.get("far") or 0.0) <= float(limits["far_limit"]) + 0.1
        and float(props.get("height") or 0.0) <= float(limits["height_limit"]) + 0.1
    )
    summary = {
        "variant_id": props.get("variant_id"),
        "mass_shape": props.get("mass_shape"),
        "maas_concept": props.get("maas_concept"),
        "bcr": props.get("bcr"),
        "far": props.get("far"),
        "height": props.get("height"),
        "legal_pass": legal_pass,
        "maas_score": props.get("maas_score"),
        "design_quality_score": props.get("design_quality_score"),
        "sequence_verbs": [
            call.get("verb")
            for call in props.get("maas_verb_sequence", [])
            if isinstance(call, dict) and call.get("verb")
        ],
        "optimizer_backend_status": (
            quality.get("optimizer_backend", {}).get("status")
            if isinstance(quality.get("optimizer_backend"), dict)
            else None
        ),
        "parking_evidence_enabled": parking_evidence_enabled,
        "parking_requirement_status": required_count.get("status") if parking_evidence_enabled else None,
        "parking_layout_status": layout.get("status"),
        "parking_status": (
            required_count.get("status") or layout.get("status")
            if parking_evidence_enabled
            else None
        ),
        "parking_required": required_count.get("required_spaces"),
        "parking_provided": layout.get("provided_spaces"),
    }
    summary["is_section_connector"] = _is_section_connector_summary(summary)
    return summary


def _feature_volumes(feature: dict[str, Any]) -> list[dict[str, Any]]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    model = props.get("maas_model") if isinstance(props.get("maas_model"), dict) else {}
    raw = model.get("volumes") or props.get("mass_volumes") or []
    volumes: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("geometry"), dict):
                continue
            volumes.append({
                "geometry": item["geometry"],
                "bottom": float(item.get("bottom_height") or 0.0),
                "top": float(item.get("top_height") or props.get("height") or 0.0),
            })
    if volumes:
        return volumes
    if isinstance(feature.get("geometry"), dict):
        return [{
            "geometry": feature["geometry"],
            "bottom": 0.0,
            "top": float(props.get("height") or 0.0),
        }]
    return []


def _volume_local_points(volumes: list[dict[str, Any]]) -> list[tuple[list[tuple[float, float]], float, float]]:
    converted = []
    for volume in volumes:
        try:
            polygon = wgs84_to_utm(geojson_to_polygon(volume["geometry"]))
            ring = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
            converted.append((ring, float(volume["bottom"]), float(volume["top"])))
        except Exception:
            continue
    if not converted:
        return []
    minx = min(x for ring, _, _ in converted for x, _ in ring)
    miny = min(y for ring, _, _ in converted for _, y in ring)
    return [(
        [(x - minx, y - miny) for x, y in ring],
        bottom,
        top,
    ) for ring, bottom, top in converted]


def _feature_section_profile(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    profile = props.get("section_profile")
    if isinstance(profile, dict):
        return profile
    model = props.get("maas_model") if isinstance(props.get("maas_model"), dict) else {}
    profile = model.get("section_profile")
    return profile if isinstance(profile, dict) else {}


def _render_variant_grid(
    *,
    features: list[dict[str, Any]],
    output_path: Path,
    title: str,
    limit: int,
) -> None:
    cells = max(1, min(limit, len(features)))
    cols = 5
    rows = (cells + cols - 1) // cols
    cell_w = 320
    cell_h = 260
    header_h = 74
    image = Image.new("RGB", (cols * cell_w, header_h + rows * cell_h), "#f8fafc")
    draw = ImageDraw.Draw(image)
    font = _load_font(13)
    small_font = _load_font(11)
    draw.rectangle((0, 0, image.width, header_h), fill="#0f172a")
    draw.text((18, 14), title, fill="#e2e8f0", font=font)
    draw.text((18, 42), f"legal MAAS alternatives: {cells} shown / {len(features)} generated", fill="#38bdf8", font=font)

    for index, feature in enumerate(features[:cells]):
        col = index % cols
        row = index // cols
        x0 = col * cell_w
        y0 = header_h + row * cell_h
        panel = (x0 + 10, y0 + 10, x0 + cell_w - 10, y0 + cell_h - 10)
        draw.rounded_rectangle(panel, radius=6, fill="#ffffff", outline="#cbd5e1")
        _draw_feature_axon(draw, panel, feature)
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        label = str(props.get("mass_shape") or "-")
        concept = str(props.get("maas_concept") or "")
        metrics = f"FAR {props.get('far', '-')}, BCR {props.get('bcr', '-')}, H {props.get('height', '-')}"
        draw.text((panel[0] + 8, panel[1] + 8), f"{index + 1:02d} {label[:31]}", fill="#0f172a", font=small_font)
        draw.text((panel[0] + 8, panel[1] + 26), concept[:32], fill="#2563eb", font=small_font)
        draw.text((panel[0] + 8, panel[3] - 22), metrics[:44], fill="#475569", font=small_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_feature_axon(
    draw: ImageDraw.ImageDraw,
    panel: tuple[int, int, int, int],
    feature: dict[str, Any],
) -> None:
    volumes = _volume_local_points(_feature_volumes(feature))
    if not volumes:
        return
    all_x = [x for ring, _, _ in volumes for x, _ in ring]
    all_y = [y for ring, _, _ in volumes for _, y in ring]
    all_z = [z for _, bottom, top in volumes for z in (bottom, top)]
    min_px, min_py, max_px, max_py = panel
    pad_x = 28
    pad_y = 48

    def raw_project(point: tuple[float, float], z: float) -> tuple[float, float]:
        x, y = point
        return (x - y * 0.45, y * 0.42 - z * 2.4)

    raw_points = [
        raw_project((x, y), z)
        for ring, bottom, top in volumes
        for x, y in ring
        for z in (bottom, top)
    ]
    raw_min_x = min(x for x, _ in raw_points)
    raw_max_x = max(x for x, _ in raw_points)
    raw_min_y = min(y for _, y in raw_points)
    raw_max_y = max(y for _, y in raw_points)
    span_x = max(raw_max_x - raw_min_x, 1.0)
    span_y = max(raw_max_y - raw_min_y, 1.0)
    scale = min((max_px - min_px - pad_x * 2) / span_x, (max_py - min_py - pad_y * 2) / span_y)

    def project(point: tuple[float, float], z: float) -> tuple[float, float]:
        rx, ry = raw_project(point, z)
        return (
            min_px + pad_x + (rx - raw_min_x) * scale,
            min_py + pad_y + (ry - raw_min_y) * scale,
        )

    palette = ["#f59e0b", "#fb7185", "#38bdf8", "#a78bfa", "#34d399"]
    ordered_volumes = sorted(volumes, key=lambda item: item[1])
    for volume_index, (ring, bottom, top) in enumerate(ordered_volumes):
        top_ring = [project(point, top) for point in ring]
        bottom_ring = [project(point, bottom) for point in ring]
        color = palette[volume_index % len(palette)]
        for a, b, c, d in zip(bottom_ring, bottom_ring[1:] + bottom_ring[:1], top_ring[1:] + top_ring[:1], top_ring):
            draw.polygon([a, b, c, d], fill="#e2e8f0", outline="#94a3b8")
        draw.polygon(top_ring, fill=color, outline="#0f172a")
        draw.line(top_ring + [top_ring[0]], fill="#0f172a", width=2)
    _draw_section_profile_overlay(draw, project, ordered_volumes, _feature_section_profile(feature))


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    return (
        sum(x for x, _ in points) / len(points),
        sum(y for _, y in points) / len(points),
    )


def _draw_section_profile_overlay(
    draw: ImageDraw.ImageDraw,
    project,
    volumes: list[tuple[list[tuple[float, float]], float, float]],
    profile: dict[str, Any],
) -> None:
    if not volumes or not profile:
        return
    kind = str(profile.get("kind") or "")
    all_x = [x for ring, _, _ in volumes for x, _ in ring]
    all_y = [y for ring, _, _ in volumes for _, y in ring]
    minx, maxx = min(all_x), max(all_x)
    miny, maxy = min(all_y), max(all_y)
    bottom = min(value for _, value, _ in volumes)
    top = max(value for _, _, value in volumes)
    accent = "#ec4899"

    if kind in {"diagonal_connector", "diagonal_connect"} and len(volumes) >= 2:
        lower_ring, _, lower_top = volumes[0]
        upper_ring, upper_bottom, upper_top = volumes[-1]
        a = project(_centroid(lower_ring), lower_top)
        b = project(_centroid(upper_ring), (upper_bottom + upper_top) / 2)
        draw.line([a, b], fill=accent, width=7)
        draw.line([a, b], fill="#fdf2f8", width=3)
        return

    if kind == "terrace_ribbon":
        side = str(profile.get("side") or "north")
        count = 4
        for index in range(count):
            t = (index + 1) / (count + 1)
            y = miny + (maxy - miny) * (1.0 - t * 0.55 if side == "north" else t * 0.55)
            z = bottom + (top - bottom) * (0.35 + index * 0.13)
            p1 = project((minx, y), z)
            p2 = project((maxx, y), z)
            draw.line([p1, p2], fill=accent, width=4)
        return

    if kind in {"sloped_roof", "sloped_roof_mass"}:
        high = top
        low = bottom + (top - bottom) * 0.52
        roof = [
            project((minx, miny), high),
            project((maxx, miny), high),
            project((maxx, maxy), low),
            project((minx, maxy), low),
        ]
        draw.polygon(roof, fill="#fed7aa", outline=accent)
        draw.line(roof + [roof[0]], fill=accent, width=4)
        for t in (0.33, 0.66):
            p1 = project((minx + (maxx - minx) * t, miny), high)
            p2 = project((minx + (maxx - minx) * t, maxy), low)
            draw.line([p1, p2], fill="#fb7185", width=2)


def _scenario_summary(
    *,
    case: dict[str, Any],
    label: str,
    preferred_operator: str | None,
    building_type: str,
    pnu: str | None,
    max_variants: int,
    render_dir: Path | None = None,
    render_limit: int = 20,
) -> dict[str, Any]:
    result = generate_legal_mass_variants(
        mass_geojson=case["mass_geojson"],
        site_polygon_geojson=case["site_polygon"],
        constraints=_constraints(),
        building_type=building_type,
        max_variants=max_variants,
        preferred_operator=preferred_operator,
        pnu=pnu,
    )
    limits = result["constraints"]
    features = result["feature_collection"]["features"]
    summaries = [_feature_summary(feature, limits) for feature in features]
    png_path = None
    if render_dir is not None:
        png_path = render_dir / f"{case['case_id']}__{label}.png"
        _render_variant_grid(
            features=features,
            output_path=png_path,
            title=f"{case['case_id']} / {label}",
            limit=render_limit,
        )
    top = summaries[0] if summaries else {}
    preferred_survived = (
        preferred_operator is None
        or any(item.get("mass_shape") == preferred_operator for item in summaries)
    )
    preferred_top = preferred_operator is not None and top.get("mass_shape") == preferred_operator
    unique_mass_shapes = sorted({
        str(item.get("mass_shape"))
        for item in summaries
        if item.get("mass_shape")
    })
    unique_concepts = sorted({
        str(item.get("maas_concept"))
        for item in summaries
        if item.get("maas_concept")
    })
    unique_verbs = sorted({
        str(verb)
        for item in summaries
        for verb in item.get("sequence_verbs", [])
        if verb
    })
    section_connectors = [
        item for item in summaries
        if item.get("is_section_connector")
    ]
    return {
        "case_id": case["case_id"],
        "scenario": label,
        "preferred_operator": preferred_operator,
        "status": "ok",
        "feature_count": len(summaries),
        "unique_mass_shape_count": len(unique_mass_shapes),
        "unique_concept_count": len(unique_concepts),
        "unique_verb_count": len(unique_verbs),
        "unique_mass_shapes": unique_mass_shapes,
        "unique_concepts": unique_concepts,
        "unique_verbs": unique_verbs,
        "section_connector_count": len(section_connectors),
        "section_connector_shapes": sorted({
            str(item.get("mass_shape"))
            for item in section_connectors
            if item.get("mass_shape")
        }),
        "rejected_count": len(result.get("rejected") or []),
        "preferred_survived": preferred_survived,
        "preferred_top": preferred_top,
        "top": top,
        "features": summaries,
        "alt_grid_png": str(png_path) if png_path else None,
    }


def _original_baseline_verbs(original_baseline: dict[str, Any] | None) -> list[str]:
    if not isinstance(original_baseline, dict):
        return []
    case_baseline = original_baseline.get("case_baseline")
    if isinstance(case_baseline, dict) and isinstance(case_baseline.get("unique_gold_verbs"), list):
        return [str(verb) for verb in case_baseline["unique_gold_verbs"] if verb]
    metric_summary = original_baseline.get("metric_summary")
    if isinstance(metric_summary, dict) and isinstance(metric_summary.get("pred_verbs"), list):
        return [str(verb) for verb in metric_summary["pred_verbs"] if verb]
    sequence = original_baseline.get("sequence")
    calls = sequence.get("calls") if isinstance(sequence, dict) else []
    return [
        str(call.get("verb"))
        for call in calls
        if isinstance(call, dict) and call.get("verb") and call.get("verb") != "base"
    ]


def _aggregate(
    scenarios: list[dict[str, Any]],
    *,
    original_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok = [item for item in scenarios if item.get("status") == "ok"]
    features = [feature for item in ok for feature in item.get("features", [])]
    mass_shape_counts = Counter(
        str(feature.get("mass_shape"))
        for feature in features
        if feature.get("mass_shape")
    )
    concept_counts = Counter(
        str(feature.get("maas_concept"))
        for feature in features
        if feature.get("maas_concept")
    )
    verb_counts = Counter(
        str(verb)
        for feature in features
        for verb in feature.get("sequence_verbs", [])
        if verb
    )
    parking_evidence_features = [
        feature for feature in features
        if feature.get("parking_evidence_enabled")
    ]
    preferred = [item for item in ok if item.get("preferred_operator")]
    section_connector_features = [
        feature for feature in features
        if feature.get("is_section_connector")
    ]
    section_connector_shapes = Counter(
        str(feature.get("mass_shape"))
        for feature in section_connector_features
        if feature.get("mass_shape")
    )
    original_verbs = sorted(set(_original_baseline_verbs(original_baseline)))
    arr_verbs = sorted(str(verb) for verb in verb_counts if verb)
    return {
        "scenario_count": len(scenarios),
        "successful_scenarios": len(ok),
        "feature_count": len(features),
        "unique_mass_shape_count": len(mass_shape_counts),
        "unique_concept_count": len(concept_counts),
        "unique_verb_count": len(verb_counts),
        "average_unique_shapes_per_scenario": round(
            mean(float(item.get("unique_mass_shape_count") or 0.0) for item in ok),
            4,
        ) if ok else 0.0,
        "mass_shape_histogram": dict(mass_shape_counts.most_common()),
        "concept_histogram": dict(concept_counts.most_common()),
        "verb_histogram": dict(verb_counts.most_common()),
        "original_maas_baseline_status": (
            original_baseline.get("status")
            if isinstance(original_baseline, dict)
            else None
        ),
        "original_maas_case_baseline_status": (
            original_baseline.get("case_baseline", {}).get("status")
            if isinstance(original_baseline, dict)
            else None
        ),
        "original_maas_case_count": (
            original_baseline.get("case_baseline", {}).get("case_count")
            if isinstance(original_baseline, dict)
            else None
        ),
        "original_maas_compiled_case_count": (
            original_baseline.get("case_baseline", {}).get("compiled_case_count")
            if isinstance(original_baseline, dict)
            else None
        ),
        "original_maas_reference_verbs": original_verbs,
        "arr_original_shared_verbs": sorted(set(arr_verbs) & set(original_verbs)),
        "missing_original_verbs": sorted(set(original_verbs) - set(arr_verbs)),
        "arr_extra_legal_verbs": sorted(set(arr_verbs) - set(original_verbs)),
        "section_connector_feature_count": len(section_connector_features),
        "section_connector_scenario_count": sum(
            1 for item in ok
            if int(item.get("section_connector_count") or 0) > 0
        ),
        "section_connector_shape_count": len(section_connector_shapes),
        "section_connector_shape_histogram": dict(section_connector_shapes.most_common()),
        "legal_pass_rate": round(
            sum(1 for feature in features if feature.get("legal_pass")) / len(features),
            4,
        ) if features else 0.0,
        "parking_evidence_feature_count": len(parking_evidence_features),
        "parking_pass_rate": (
            round(
                sum(1 for feature in parking_evidence_features if feature.get("parking_status") == "pass") / len(parking_evidence_features),
                4,
            )
            if parking_evidence_features else None
        ),
        "preferred_survival_rate": round(
            sum(1 for item in preferred if item.get("preferred_survived")) / len(preferred),
            4,
        ) if preferred else 1.0,
        "preferred_top_rate": round(
            sum(1 for item in preferred if item.get("preferred_top")) / len(preferred),
            4,
        ) if preferred else 1.0,
        "average_design_quality": round(
            mean(float(feature.get("design_quality_score") or 0.0) for feature in features),
            4,
        ) if features else 0.0,
    }


class Command(BaseCommand):
    help = "Run a deterministic MAAS algorithm benchmark over ARR-native grammar/design operators."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out-dir",
            default="docs/ai-session-memory/maas-benchmarks",
            help="Output directory relative to workspace root or absolute path.",
        )
        parser.add_argument("--max-variants", type=int, default=6)
        parser.add_argument("--render-alt-png", action="store_true")
        parser.add_argument("--alt-grid-limit", type=int, default=20)
        parser.add_argument("--building-type", default="공동주택")
        parser.add_argument("--pnu", default="1168011800104170004")
        parser.add_argument("--case-id", help="Run only one fixture case id.")
        parser.add_argument(
            "--baseline-only",
            action="store_true",
            help="Run only the baseline scenario for the selected case(s).",
        )
        parser.add_argument(
            "--skip-original-baseline",
            action="store_true",
            help="Skip clone/MAAS reference compilation for fast visual checks.",
        )
        parser.add_argument(
            "--with-parking",
            action="store_true",
            help="Attach parking count/layout evidence. This may query Neo4j or local structured seed rules.",
        )
        parser.add_argument("--operators", nargs="*", default=DEFAULT_OPERATORS)

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[5]
        out_dir = Path(options["out_dir"])
        if not out_dir.is_absolute():
            out_dir = repo_root / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        building_type = str(options["building_type"])
        raw_pnu = str(options["pnu"] or "").strip()
        pnu = (raw_pnu or None) if options["with_parking"] else None
        max_variants = max(1, int(options["max_variants"]))
        operators = [operator for operator in options["operators"] if isinstance(operator, str) and operator]
        render_dir = (out_dir / "alt_grids") if options["render_alt_png"] else None
        render_limit = max(1, int(options["alt_grid_limit"]))
        original_baseline = (
            None
            if options["skip_original_baseline"]
            else run_maas_clone_reference_baseline(enable_import=True)
        )

        scenarios: list[dict[str, Any]] = []
        cases = _fixture_cases()
        case_id = str(options.get("case_id") or "").strip()
        if case_id:
            cases = [case for case in cases if case["case_id"] == case_id]
            if not cases:
                raise ValueError(f"unknown case_id: {case_id}")

        for case in cases:
            runs = [("baseline_legal_envelope", None)]
            if not options["baseline_only"]:
                runs.extend((f"preferred_{operator}", operator) for operator in operators)
            for label, preferred_operator in runs:
                try:
                    scenarios.append(_scenario_summary(
                        case=case,
                        label=label,
                        preferred_operator=preferred_operator,
                        building_type=building_type,
                        pnu=pnu,
                        max_variants=max_variants,
                        render_dir=render_dir,
                        render_limit=render_limit,
                    ))
                except Exception as exc:
                    scenarios.append({
                        "case_id": case["case_id"],
                        "scenario": label,
                        "preferred_operator": preferred_operator,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    })

        payload = {
            "mode": "maas_algorithm_benchmark",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "building_type": building_type,
            "pnu": pnu,
            "parking_mode": "enabled" if pnu else "disabled",
            "operators": operators,
            "source": {
                "grammar": "ARR grammar JSON/operators plus direct clone/MAAS reference baseline",
                "original_maas_baseline": original_baseline or {"status": "skipped"},
                "optimizer_backend": d4descent_design_evidence(enable_import=True),
                "legal_truth": "ARR deterministic legal repair/evaluation",
            },
            "aggregate": _aggregate(scenarios, original_baseline=original_baseline),
            "scenarios": scenarios,
        }

        path = out_dir / f"maas_algorithm_benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        latest = out_dir / "latest.json"
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"wrote {path}"))
        self.stdout.write(json.dumps(payload["aggregate"], ensure_ascii=False, indent=2))
        self.stdout.write(
            "original MAAS baseline: "
            f"status={(original_baseline or {}).get('status', 'skipped')}, "
            f"labels={(original_baseline or {}).get('backend', {}).get('labels_status')}, "
            f"cases={(original_baseline or {}).get('case_baseline', {}).get('compiled_case_count')}/"
            f"{(original_baseline or {}).get('case_baseline', {}).get('case_count')}, "
            f"verbs={','.join(_original_baseline_verbs(original_baseline)) or '-'}"
        )
        if render_dir:
            self.stdout.write(self.style.SUCCESS(f"rendered alt PNG grids under {render_dir}"))
        for scenario in scenarios:
            if scenario.get("status") != "ok":
                continue
            self.stdout.write(
                f"{scenario['case_id']} / {scenario['scenario']}: "
                f"{scenario['feature_count']} variants, "
                f"{scenario['unique_mass_shape_count']} shapes, "
                f"{scenario['unique_verb_count']} verbs, "
                f"connectors={scenario.get('section_connector_count', 0)}, "
                f"top={scenario.get('top', {}).get('mass_shape')}"
            )
