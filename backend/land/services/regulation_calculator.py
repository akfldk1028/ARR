"""
Regulation Calculator - computes all 11 building regulations from zone data.

Given zone names, resolves BCR, FAR, height limit, sunlight setback,
road diagonal, corner cutoff, building line, adjacent setback, parking,
landscaping, and building designation regulations.
When multiple zones apply, the strictest values are used.

Supports 3-tier override: zoning_limits.json → ordinance_overrides/{sigungu}.json → LLM extraction.
"""

import json
import logging
import os

from land import config
from land.services import zoning_mapper

logger = logging.getLogger(__name__)


def calculate_all(zone_names: list[str], land_info: dict | None = None,
                   sigungu_code: str = "", use_llm_extraction: bool | None = None) -> dict:
    """
    Compute all 11 regulations from zone names.

    Args:
        zone_names: list of zone names including overlays (e.g. ["제1종일반주거지역", "지구단위계획구역"])
        land_info: optional dict with land_area_m2, etc.
        sigungu_code: 5-digit sigungu code for ordinance override (e.g. "11680" = 강남구)

    Returns dict with keys matching LandAnalysisResult fields.
    """
    zones_data = [
        zd for z in zone_names
        if (zd := zoning_mapper.lookup(z)) is not None
    ]

    if not zones_data:
        return _empty_result()

    # Apply ordinance overrides if available
    if sigungu_code:
        zones_data = _apply_ordinance_overrides(zones_data, sigungu_code)

    result = {}
    result.update(_resolve_bcr_far(zones_data))
    result.update(_resolve_height(zones_data))
    result.update(_resolve_sunlight(zones_data, use_llm_extraction=use_llm_extraction))
    result.update(_resolve_corner_cutoff(zones_data))
    result.update(_resolve_road_diagonal(zones_data))
    result.update(_resolve_building_line(zones_data))
    result.update(_resolve_adjacent_setback(zones_data, use_llm_extraction=use_llm_extraction))
    result.update(_resolve_parking(zones_data))
    result.update(_resolve_landscaping(zones_data, land_info))
    result.update(_resolve_building_designation(zone_names, use_llm_extraction=use_llm_extraction))
    result["zone_category"] = zones_data[0].get("category", "")
    result["matched_zones"] = [z["zone_name"] for z in zones_data]
    result["unmatched_zones"] = [
        z for z in zone_names if z not in result["matched_zones"]
    ]

    return result


def _empty_result() -> dict:
    return {
        "bcr_pct": None, "bcr_article": "",
        "far_pct": None, "far_article": "",
        "height_limit_m": None, "height_article": "",
        "sunlight_applies": False, "sunlight_rules": [], "sunlight_article": "",
        "corner_cutoff_required": False, "corner_cutoff_m": None, "corner_cutoff_article": "",
        "road_diagonal_multiplier": None, "road_diagonal_rule": "",
        "road_diagonal_article": "",
        "building_line_setback_m": None, "building_line_article": "",
        "adjacent_setback_m": None, "adjacent_setback_article": "",
        "parking_rule": "", "parking_article": "",
        "landscaping_threshold_m2": None, "landscaping_min_pct": None,
        "landscaping_article": "",
        "sunlight_source": "",
        "adjacent_setback_source": "",
        "building_designation_applies": False,
        "building_designation_setback_m": None,
        "building_designation_article": "",
        "building_designation_source": "",
        "zone_category": "",
        "matched_zones": [],
        "unmatched_zones": [],
    }


def _resolve_bcr_far(zones_data: list[dict]) -> dict:
    """BCR/FAR: use strictest (lowest) across zones."""
    bcr = min(z["bcr_default"] for z in zones_data)
    far = min(z["far_default"] for z in zones_data)

    bcr_articles = list(dict.fromkeys(z["bcr_article"] for z in zones_data))
    far_articles = list(dict.fromkeys(z["far_article"] for z in zones_data))

    return {
        "bcr_pct": bcr,
        "bcr_article": "; ".join(bcr_articles),
        "far_pct": far,
        "far_article": "; ".join(far_articles),
    }


def _resolve_height(zones_data: list[dict]) -> dict:
    """Height limit: use strictest (lowest non-null)."""
    heights = [z["height_limit_m"] for z in zones_data if z.get("height_limit_m") is not None]
    articles = list(dict.fromkeys(z.get("height_limit_article", "") for z in zones_data if z.get("height_limit_article")))

    return {
        "height_limit_m": min(heights) if heights else None,
        "height_article": "; ".join(articles) if articles else "",
    }


def _use_llm_extraction(override: bool | None) -> bool:
    return config.LLM_EXTRACTION_ENABLED if override is None else bool(override)


def _resolve_sunlight(zones_data: list[dict], use_llm_extraction: bool | None = None) -> dict:
    """Sunlight setback: applies if ANY zone requires it. LLM override when enabled."""
    # Base: static JSON
    base = _resolve_sunlight_from_json(zones_data)
    base["sunlight_source"] = "static_json"

    # LLM override attempt
    if _use_llm_extraction(use_llm_extraction):
        try:
            from land.services import law_enricher
            zone_names = [z["zone_name"] for z in zones_data]
            extracted = law_enricher.extract_regulation_values(zone_names, "sunlight")
            if extracted:
                # Guard: LLM cannot flip applies from False→True
                # (zone applicability is a static legal fact, not LLM judgment)
                if base["sunlight_applies"]:
                    if "sunlight_rules" in extracted and extracted["sunlight_rules"]:
                        base["sunlight_rules"] = extracted["sunlight_rules"]
                    if "sunlight_article" in extracted and extracted["sunlight_article"]:
                        base["sunlight_article"] = extracted["sunlight_article"]
                    base["sunlight_source"] = "law_text"
        except Exception as e:
            logger.warning(f"LLM sunlight extraction failed, using JSON fallback: {e}")

    return base


def _resolve_sunlight_from_json(zones_data: list[dict]) -> dict:
    """Sunlight from static JSON (fallback)."""
    applies = any(
        z.get("sunlight_setback", {}).get("applies", False)
        for z in zones_data
    )

    if not applies:
        articles = list(dict.fromkeys(
            z.get("sunlight_setback", {}).get("article", "")
            for z in zones_data
            if z.get("sunlight_setback", {}).get("article")
        ))
        return {
            "sunlight_applies": False,
            "sunlight_rules": [],
            "sunlight_article": "; ".join(articles) if articles else "",
        }

    for z in zones_data:
        ss = z.get("sunlight_setback", {})
        if ss.get("applies"):
            return {
                "sunlight_applies": True,
                "sunlight_rules": ss.get("rules", []),
                "sunlight_article": ss.get("article", ""),
            }

    return {"sunlight_applies": False, "sunlight_rules": [], "sunlight_article": ""}


def _resolve_corner_cutoff(zones_data: list[dict]) -> dict:
    """Corner cutoff: required if ANY zone requires it. Cutoff distance from zone or ordinance."""
    required = any(
        z.get("corner_cutoff", {}).get("required", False)
        for z in zones_data
    )
    articles = list(dict.fromkeys(
        z.get("corner_cutoff", {}).get("article", "")
        for z in zones_data
        if z.get("corner_cutoff", {}).get("article")
    ))
    # Cutoff distance: ordinance/zone override or None (→ setback_geometry calculates dynamically)
    cutoff_values = [
        z.get("corner_cutoff", {}).get("default_cutoff_m")
        for z in zones_data
        if z.get("corner_cutoff", {}).get("default_cutoff_m") is not None
    ]

    return {
        "corner_cutoff_required": required,
        "corner_cutoff_m": max(cutoff_values) if cutoff_values else None,
        "corner_cutoff_article": "; ".join(articles) if articles else "",
    }


def _resolve_road_diagonal(zones_data: list[dict]) -> dict:
    """Road diagonal: use strictest (lowest multiplier)."""
    multipliers = [
        z.get("road_diagonal", {}).get("multiplier")
        for z in zones_data
        if z.get("road_diagonal", {}).get("multiplier") is not None
    ]
    notes = [
        z.get("road_diagonal", {}).get("note", "")
        for z in zones_data
        if z.get("road_diagonal", {}).get("note")
    ]
    articles = list(dict.fromkeys(
        z.get("road_diagonal", {}).get("article", "")
        for z in zones_data
        if z.get("road_diagonal", {}).get("article")
    ))

    return {
        "road_diagonal_multiplier": min(multipliers) if multipliers else None,
        "road_diagonal_rule": notes[0] if notes else "",
        "road_diagonal_article": "; ".join(articles) if articles else "",
    }


def _resolve_building_line(zones_data: list[dict]) -> dict:
    """Building line: rule text only (site-specific calculation in Phase 3+)."""
    articles = list(dict.fromkeys(
        z.get("building_line_article", "")
        for z in zones_data
        if z.get("building_line_article")
    ))

    return {
        "building_line_setback_m": None,
        "building_line_article": "; ".join(articles) if articles else "",
    }


def _resolve_adjacent_setback(zones_data: list[dict], use_llm_extraction: bool | None = None) -> dict:
    """Adjacent setback: use strictest (largest setback). LLM override when enabled."""
    # Base: static JSON
    setbacks = [
        z.get("adjacent_setback_m")
        for z in zones_data
        if z.get("adjacent_setback_m") is not None
    ]
    articles = list(dict.fromkeys(
        z.get("adjacent_setback_article", "")
        for z in zones_data
        if z.get("adjacent_setback_article")
    ))
    base = {
        "adjacent_setback_m": max(setbacks) if setbacks else None,
        "adjacent_setback_article": "; ".join(articles) if articles else "",
        "adjacent_setback_source": "static_json",
    }

    # LLM override attempt
    if _use_llm_extraction(use_llm_extraction):
        try:
            from land.services import law_enricher
            zone_names = [z["zone_name"] for z in zones_data]
            extracted = law_enricher.extract_regulation_values(zone_names, "adjacent_setback")
            if extracted and extracted.get("adjacent_setback_m") is not None:
                base["adjacent_setback_m"] = extracted["adjacent_setback_m"]
                if extracted.get("adjacent_setback_article"):
                    base["adjacent_setback_article"] = extracted["adjacent_setback_article"]
                base["adjacent_setback_source"] = "law_text"
        except Exception as e:
            logger.warning(f"LLM adjacent_setback extraction failed: {e}")

    return base


def _resolve_parking(zones_data: list[dict]) -> dict:
    """Parking: rule text only (usage-dependent, not zone-dependent)."""
    articles = list(dict.fromkeys(
        z.get("parking_article", "")
        for z in zones_data
        if z.get("parking_article")
    ))

    return {
        "parking_rule": "용도별 주차대수 산정 (주차장법 시행령 별표1)",
        "parking_article": "; ".join(articles) if articles else "",
    }


def _resolve_landscaping(zones_data: list[dict], land_info: dict | None = None) -> dict:
    """Landscaping: use strictest (highest min_pct)."""
    thresholds = []
    pcts = []
    articles_set = set()

    for z in zones_data:
        ls = z.get("landscaping", {})
        if ls.get("threshold_m2") is not None:
            thresholds.append(ls["threshold_m2"])
        if ls.get("min_pct") is not None:
            pcts.append(ls["min_pct"])
        if ls.get("article"):
            articles_set.add(ls["article"])

    return {
        "landscaping_threshold_m2": min(thresholds) if thresholds else None,
        "landscaping_min_pct": max(pcts) if pcts else None,
        "landscaping_article": "; ".join(articles_set) if articles_set else "",
    }


# ──────────────────────────────────────────────────────
# Ordinance Override (지자체 조례)
# ──────────────────────────────────────────────────────

_ordinance_cache: dict[str, dict | None] = {}


def _load_ordinance(sigungu_code: str) -> dict | None:
    """Load ordinance override JSON for a sigungu. Cached."""
    if sigungu_code in _ordinance_cache:
        return _ordinance_cache[sigungu_code]

    path = os.path.join(config.ORDINANCE_DIR, f"{sigungu_code}.json")
    if not os.path.exists(path):
        _ordinance_cache[sigungu_code] = None
        return None

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _ordinance_cache[sigungu_code] = data
        logger.info(f"Loaded ordinance override: {sigungu_code} ({data.get('sigungu_name', '')})")
        return data
    except Exception as e:
        logger.warning(f"Failed to load ordinance {sigungu_code}: {e}")
        _ordinance_cache[sigungu_code] = None
        return None


def _apply_ordinance_overrides(zones_data: list[dict], sigungu_code: str) -> list[dict]:
    """1-level merge ordinance overrides into zones_data. Returns new list (no mutation)."""
    ordinance = _load_ordinance(sigungu_code)
    if not ordinance:
        return zones_data

    overrides = ordinance.get("overrides", {})
    if not overrides:
        return zones_data

    result = []
    for z in zones_data:
        zone_name = z.get("zone_name", "")
        if zone_name in overrides:
            merged = {**z}
            for key, val in overrides[zone_name].items():
                if isinstance(val, dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged[key], **val}
                else:
                    merged[key] = val
            result.append(merged)
        else:
            result.append(z)
    return result


def _resolve_building_designation(
    all_zone_names: list[str], use_llm_extraction: bool | None = None,
) -> dict:
    """Building designation line: applies in 지구단위계획구역. LLM override when enabled."""
    is_district_plan = any("지구단위계획" in z for z in all_zone_names)

    base = {
        "building_designation_applies": is_district_plan,
        "building_designation_setback_m": 2.0 if is_district_plan else None,
        "building_designation_article": (
            "국토계획법 §49-52, 건축법 §46-47" if is_district_plan else ""
        ),
        "building_designation_source": "static_default" if is_district_plan else "",
    }

    if not is_district_plan:
        return base

    # LLM override attempt
    if _use_llm_extraction(use_llm_extraction):
        try:
            from land.services import law_enricher
            standard_zones = [
                z for z in all_zone_names
                if zoning_mapper.lookup(z) is not None
            ]
            if standard_zones:
                extracted = law_enricher.extract_regulation_values(
                    standard_zones, "building_designation",
                )
                if extracted and extracted.get("building_designation_setback_m") is not None:
                    base["building_designation_setback_m"] = extracted["building_designation_setback_m"]
                    if extracted.get("building_designation_article"):
                        base["building_designation_article"] = extracted["building_designation_article"]
                    base["building_designation_source"] = "law_text"
        except Exception as e:
            logger.warning(f"LLM building_designation extraction failed: {e}")

    return base
