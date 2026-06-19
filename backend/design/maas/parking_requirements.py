"""Graph-backed parking requirement resolver for MAAS candidates."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from law.scripts.check_parking_counts import (
    _load_rules,
    _select_rule,
    calculate_accessible_spaces,
    calculate_required_spaces,
)


DEFAULT_NEO4J_URI = "bolt://172.27.80.1:7687"


def resolve_candidate_parking_requirement(
    *,
    pnu: str | None,
    building_type: str,
    facility_area_m2: float | None,
    options: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve required parking count for a candidate from Graph DB rules.

    This function is intentionally conservative: if the graph is unavailable,
    the use is delegated to an external rule, or the use cannot be mapped to a
    structured row, it returns a status explaining the missing evidence instead
    of fabricating a legal count.
    """
    if not pnu:
        return _unresolved("needs_pnu", "PNU is required to choose local parking ordinance overrides.")
    if facility_area_m2 is None or facility_area_m2 < 0:
        return _unresolved("needs_metric", "Candidate facility area is required for parking count.")

    opts = options or {}
    rule_id = _string_or_none(opts.get("parking_rule_id")) or _rule_id_for_building_type(building_type)
    if not rule_id:
        return _unresolved(
            "needs_use_mapping",
            f"No parking appendix row mapping is configured for building_type={building_type!r}.",
        )

    metric = _string_or_none(opts.get("parking_metric")) or _default_metric_for_rule(rule_id)
    metric_value = _float_or_none(opts.get("parking_metric_value"))
    if metric_value is None:
        metric_value = facility_area_m2

    if rules is None:
        loaded = load_parking_requirement_rules(options=opts)
        if loaded.get("status") != "loaded":
            return _unresolved(loaded.get("status") or "graph_unavailable", loaded.get("reason") or "Parking law graph is unavailable.")
        rules = loaded["rules"]

    rule = _select_rule(rules, pnu, rule_id)

    if not rule:
        return _unresolved("needs_graph_rule", f"Parking rule {rule_id} is not loaded for PNU {pnu}.")

    try:
        if rule.get("requires_external_rule") and (rule.get("base_rule_id") or rule.get("rule_id")) == "parking_appendix1_row_05":
            calc = _calculate_housing_required_spaces(rule, opts, float(metric_value))
        else:
            calc = calculate_required_spaces(rule, metric, float(metric_value))
        accessible = calculate_accessible_spaces(calc.get("required_spaces"))
    except Exception as exc:
        return _unresolved("calculation_failed", f"Parking requirement calculation failed: {exc}")

    return {
        "status": calc.get("status"),
        "pnu": pnu,
        "jurisdiction_code": pnu[:5],
        "building_type": building_type,
        "selected_rule_id": rule.get("rule_id"),
        "base_rule_id": rule.get("base_rule_id") or rule_id,
        "metric": metric,
        "metric_value": round(float(metric_value), 2),
        "required_spaces": calc.get("required_spaces"),
        "raw_spaces": calc.get("raw_spaces"),
        "rounding_rule": calc.get("rounding_rule"),
        "formula_detail": calc.get("formula_detail"),
        "unit_schedule": calc.get("unit_schedule"),
        "accessible": accessible,
        "source": {
            "rule_kind": "local_override" if rule.get("base_rule_id") else "national",
            "source_appendix": rule.get("source_appendix"),
            "source_ordinance": rule.get("source_ordinance"),
            "source_parse_status": rule.get("source_parse_status"),
        },
        "reason": calc.get("reason"),
    }


def _calculate_housing_required_spaces(rule: dict[str, Any], opts: dict[str, Any], fallback_area_m2: float) -> dict[str, Any]:
    schedule = _housing_unit_schedule(opts.get("housing_unit_schedule"))
    if not schedule:
        return {
            "status": "needs_external_rule",
            "required_spaces": None,
            "reason": rule.get("external_reference") or "housing unit exclusive-area schedule is required",
        }

    jurisdiction = str(opts.get("jurisdiction_type") or "special_city")
    if jurisdiction == "special_city":
        area_divisor_under_85 = 75.0
        area_divisor_over_85 = 65.0
    else:
        area_divisor_under_85 = 85.0
        area_divisor_over_85 = 70.0

    local_min_default = _float_or_none(rule.get("local_min_spaces_per_household")) or 1.0
    local_min_under_30 = _float_or_none(rule.get("local_min_spaces_under_30m2")) or 0.5
    local_min_under_60 = _float_or_none(rule.get("local_min_spaces_under_60m2")) or 0.8

    area_raw = 0.0
    household_min_raw = 0.0
    normalized = []
    for index, unit in enumerate(schedule, start=1):
        exclusive_area = _float_or_none(unit.get("exclusive_area_m2"))
        count = int(_float_or_none(unit.get("count")) or 1)
        if exclusive_area is None or exclusive_area <= 0 or count <= 0:
            continue
        divisor = area_divisor_under_85 if exclusive_area <= 85.0 else area_divisor_over_85
        area_raw += (exclusive_area * count) / divisor
        if exclusive_area <= 30.0:
            min_per_unit = local_min_under_30
        elif exclusive_area <= 60.0:
            min_per_unit = local_min_under_60
        else:
            min_per_unit = local_min_default
        household_min_raw += min_per_unit * count
        normalized.append({
            "unit_type": unit.get("unit_type") or f"U{index:02d}",
            "count": count,
            "exclusive_area_m2": round(exclusive_area, 2),
            "area_divisor_m2_per_space": divisor,
            "min_spaces_per_unit": min_per_unit,
            "source": unit.get("source") or "user_or_mass_stage",
        })

    if not normalized:
        return {
            "status": "needs_external_rule",
            "required_spaces": None,
            "reason": rule.get("external_reference") or "valid housing unit exclusive-area schedule is required",
        }

    raw_spaces = max(area_raw, household_min_raw)
    required = math.ceil(raw_spaces)
    return {
        "status": "computed_estimate" if any(item.get("source") == "mass_stage_estimate" for item in normalized) else "computed",
        "raw_spaces": raw_spaces,
        "required_spaces": required,
        "rounding_rule": "housing_standard_article_27_ceil_plus_seoul_household_minimum",
        "formula_detail": (
            "공동주택: 전용 85㎡ 이하 75㎡당 1대, 85㎡ 초과 65㎡당 1대와 "
            "서울 조례 세대별 최소값을 비교해 큰 값 적용"
        ),
        "unit_schedule": {
            "source": "mass_stage_estimate" if any(item.get("source") == "mass_stage_estimate" for item in normalized) else "provided",
            "fallback_area_m2": round(float(fallback_area_m2), 2),
            "area_ratio_raw_spaces": round(area_raw, 4),
            "household_min_raw_spaces": round(household_min_raw, 4),
            "units": normalized,
        },
    }


def _housing_unit_schedule(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def load_parking_requirement_rules(*, options: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = options or {}
    uri = _string_or_none(opts.get("neo4j_uri")) or os.getenv("NEO4J_URI") or DEFAULT_NEO4J_URI
    user = _string_or_none(opts.get("neo4j_user")) or os.getenv("NEO4J_USER") or "neo4j"
    password = _string_or_none(opts.get("neo4j_password"))
    if password is None:
        password = os.getenv("NEO4J_PASSWORD", "")

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=2.0)
        with driver.session() as session:
            return {"status": "loaded", "rules": _load_rules(session)}
    except Exception as exc:
        fallback = _load_structured_seed_rules()
        if fallback:
            return {
                "status": "loaded",
                "rules": fallback,
                "source": "local_structured_seed",
                "graph_status": "graph_unavailable",
                "graph_reason": f"Parking law graph is unavailable: {exc}",
            }
        return {"status": "graph_unavailable", "reason": f"Parking law graph is unavailable: {exc}"}
    finally:
        if driver is not None:
            driver.close()


def _load_structured_seed_rules() -> dict[str, Any] | None:
    """Load reviewed local JSON seed rules when Neo4j is unavailable."""
    root = Path(__file__).resolve().parents[2] / "law" / "data" / "structured"
    national_path = root / "parking_appendix_rules.json"
    seoul_path = root / "seoul_parking_ordinance_rules.json"
    try:
        national_raw = json.loads(national_path.read_text(encoding="utf-8"))
        seoul_raw = json.loads(seoul_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    national = {}
    for rule in national_raw.get("parking_rules") or []:
        if not isinstance(rule, dict) or not rule.get("rule_id"):
            continue
        item = dict(rule)
        item.setdefault("source_parse_status", "official_pdf_text_extracted_manual_review")
        national[str(item["rule_id"])] = item

    local = []
    for rule in seoul_raw.get("local_parking_rules") or []:
        if not isinstance(rule, dict) or not rule.get("rule_id"):
            continue
        item = dict(rule)
        item["base_rule_id"] = item.get("base_rule_id") or item.get("overrides_rule_id")
        item["pnu_prefix"] = item.get("pnu_prefix") or "11"
        item.setdefault("source_parse_status", "official_pdf_text_extracted_manual_review")
        local.append(item)

    if not national:
        return None
    return {"national": national, "local": local}


def apply_parking_requirement_to_props(props: dict[str, Any], requirement: dict[str, Any]) -> None:
    """Copy a resolved parking requirement into MAAS candidate properties."""
    props["parking_required_count"] = requirement
    required_spaces = requirement.get("required_spaces")
    if isinstance(required_spaces, int):
        props["required_parking_spaces"] = required_spaces
        accessible = requirement.get("accessible") if isinstance(requirement.get("accessible"), dict) else {}
        accessible_min = accessible.get("accessible_min")
        if isinstance(accessible_min, int):
            props["required_accessible_parking_spaces"] = accessible_min


def _rule_id_for_building_type(building_type: str) -> str | None:
    text = building_type or ""
    if any(token in text for token in ("위락",)):
        return "parking_appendix1_row_01"
    if any(token in text for token in ("근린생활", "생활시설", "숙박")):
        return "parking_appendix1_row_03"
    if any(token in text for token in ("단독", "다가구")):
        return "parking_appendix1_row_04"
    if any(token in text for token in ("공동주택", "아파트", "연립", "다세대", "오피스텔")):
        return "parking_appendix1_row_05"
    if any(token in text for token in ("창고",)):
        return "parking_appendix1_row_08"
    if any(token in text for token in ("공장", "수련")):
        return "parking_appendix1_row_07"
    if any(token in text for token in ("판매", "업무", "의료", "문화", "종교", "운동", "운수", "방송", "장례")):
        return "parking_appendix1_row_02"
    if any(token in text for token in ("제1종", "제2종")):
        return "parking_appendix1_row_03"
    if text:
        return "parking_appendix1_row_11"
    return None


def _default_metric_for_rule(rule_id: str) -> str:
    if rule_id == "parking_appendix1_row_06":
        return "spectator_capacity"
    if rule_id == "parking_appendix1_row_05":
        return "household_or_unit_area"
    return "facility_area_m2"


def _unresolved(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "required_spaces": None,
        "accessible": {"status": status, "accessible_min": None, "accessible_max": None},
        "reason": reason,
    }


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "apply_parking_requirement_to_props",
    "load_parking_requirement_rules",
    "resolve_candidate_parking_requirement",
]
