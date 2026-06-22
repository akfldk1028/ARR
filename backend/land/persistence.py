"""
Persistence helpers for land regulation analysis.

Extracted from views.py — handles LandAnalysisResult and LandQuery saves.
All saves are non-fatal (wrapped in try/except).
"""

import logging

from land.models import LandQuery, LandAnalysisResult

logger = logging.getLogger(__name__)


def save_analysis_result(pnu_info, zone_names, reg, law_articles, land_info,
                         reg_ext=None):
    """Save LandAnalysisResult (non-fatal on failure)."""
    try:
        return LandAnalysisResult.objects.create(
            pnu=pnu_info["pnu"] if pnu_info else "",
            address=pnu_info.get("address", "") if pnu_info else "",
            coordinate_x=pnu_info.get("coordinate_x") if pnu_info else None,
            coordinate_y=pnu_info.get("coordinate_y") if pnu_info else None,
            zones=zone_names,
            zone_category=reg.get("zone_category", ""),
            land_area_m2=land_info.get("land_area_m2") if land_info else None,
            official_land_price=land_info.get("official_land_price") if land_info else None,
            land_use_situation=land_info.get("land_use_situation", "") if land_info else "",
            bcr_pct=reg.get("bcr_pct"),
            bcr_article=reg.get("bcr_article", ""),
            far_pct=reg.get("far_pct"),
            far_article=reg.get("far_article", ""),
            height_limit_m=reg.get("height_limit_m"),
            height_article=reg.get("height_article", ""),
            sunlight_applies=reg.get("sunlight_applies", False),
            sunlight_rules=reg.get("sunlight_rules", []),
            sunlight_article=reg.get("sunlight_article", ""),
            corner_cutoff_required=reg.get("corner_cutoff_required", False),
            corner_cutoff_article=reg.get("corner_cutoff_article", ""),
            road_diagonal_multiplier=reg.get("road_diagonal_multiplier"),
            road_diagonal_rule=reg.get("road_diagonal_rule", ""),
            road_diagonal_article=reg.get("road_diagonal_article", ""),
            building_line_setback_m=reg.get("building_line_setback_m"),
            building_line_article=reg.get("building_line_article", ""),
            adjacent_setback_m=reg.get("adjacent_setback_m"),
            adjacent_setback_article=reg.get("adjacent_setback_article", ""),
            parking_rule=reg.get("parking_rule", ""),
            parking_article=reg.get("parking_article", ""),
            landscaping_threshold_m2=reg.get("landscaping_threshold_m2"),
            landscaping_min_pct=reg.get("landscaping_min_pct"),
            landscaping_article=reg.get("landscaping_article", ""),
            regulations_extended=reg_ext or {},
            law_articles_json=law_articles.get("articles", []) if law_articles else [],
            law_article_count=law_articles.get("total_count", 0) if law_articles else 0,
            data_source=land_info.get("source", "static") if land_info else "static",
        )
    except Exception as e:
        logger.warning(f"LandAnalysisResult save failed (non-fatal): {e}")
        return None


def log_query(input_type, raw_input, pnu_info, reg, land_info,
              law_count, elapsed_ms, error="", analysis_result=None):
    """Save audit log (non-fatal on failure)."""
    try:
        LandQuery.objects.create(
            input_type=input_type,
            raw_input=raw_input[:500],
            resolved_pnu=pnu_info["pnu"] if pnu_info else "",
            zoning_zones=reg.get("matched_zones", []) if reg else [],
            building_coverage_limit=reg.get("bcr_pct") if reg else None,
            floor_area_limit=reg.get("far_pct") if reg else None,
            land_area_m2=land_info.get("land_area_m2") if land_info else None,
            official_land_price=land_info.get("official_land_price") if land_info else None,
            law_article_count=law_count,
            analysis_result=analysis_result,
            response_time_ms=round(elapsed_ms, 2),
            error=error,
        )
    except Exception as e:
        logger.warning(f"LandQuery save failed (non-fatal): {e}")
