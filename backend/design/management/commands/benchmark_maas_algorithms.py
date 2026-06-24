from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from statistics import mean
from typing import Any

from django.core.management.base import BaseCommand

from design.maas import generate_legal_mass_variants
from design.maas.research_backends import d4descent_design_evidence


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


def _scenario_summary(
    *,
    case: dict[str, Any],
    label: str,
    preferred_operator: str | None,
    building_type: str,
    pnu: str | None,
    max_variants: int,
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
    }


def _aggregate(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
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
        parser.add_argument("--building-type", default="공동주택")
        parser.add_argument("--pnu", default="1168011800104170004")
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

        scenarios: list[dict[str, Any]] = []
        for case in _fixture_cases():
            runs = [("baseline_legal_envelope", None)]
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
                "grammar": "clone/MAAS verb-sequence philosophy absorbed as ARR grammar JSON/operators",
                "optimizer_backend": d4descent_design_evidence(enable_import=True),
                "legal_truth": "ARR deterministic legal repair/evaluation",
            },
            "aggregate": _aggregate(scenarios),
            "scenarios": scenarios,
        }

        path = out_dir / f"maas_algorithm_benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        latest = out_dir / "latest.json"
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"wrote {path}"))
        self.stdout.write(json.dumps(payload["aggregate"], ensure_ascii=False, indent=2))
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
