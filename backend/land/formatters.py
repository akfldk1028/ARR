"""
Response formatters for land regulation analysis.

Extracted from views.py — pure functions, no Django imports.
"""


def format_regulations(reg: dict, reg_ext: dict | None = None) -> dict:
    """Format regulation_calculator output into API response structure."""
    result = {
        "bcr": {
            "limit_pct": reg.get("bcr_pct"),
            "article": reg.get("bcr_article", ""),
        },
        "far": {
            "limit_pct": reg.get("far_pct"),
            "article": reg.get("far_article", ""),
        },
        "height": {
            "limit_m": reg.get("height_limit_m"),
            "rule": "가로구역별 높이제한 적용",
            "article": reg.get("height_article", ""),
        },
        "sunlight_setback": {
            "applies": reg.get("sunlight_applies", False),
            "direction": "정북방향" if reg.get("sunlight_applies") else None,
            "rules": reg.get("sunlight_rules", []),
            "article": reg.get("sunlight_article", ""),
        },
        "corner_cutoff": {
            "required": reg.get("corner_cutoff_required", False),
            "rule": "8m 미만 도로 모퉁이 (교차각별 2~4m 후퇴)" if reg.get("corner_cutoff_required") else None,
            "article": reg.get("corner_cutoff_article", ""),
        },
        "road_diagonal": {
            "multiplier": reg.get("road_diagonal_multiplier"),
            "rule": reg.get("road_diagonal_rule", ""),
            "article": reg.get("road_diagonal_article", ""),
        },
        "building_line": {
            "setback_m": reg.get("building_line_setback_m"),
            "rule": "도로경계선 후퇴 (조례에 따름)",
            "article": reg.get("building_line_article", ""),
        },
        "adjacent_setback": {
            "min_m": reg.get("adjacent_setback_m"),
            "article": reg.get("adjacent_setback_article", ""),
        },
        "parking": {
            "rule": reg.get("parking_rule", ""),
            "article": reg.get("parking_article", ""),
        },
        "landscaping": {
            "threshold_m2": reg.get("landscaping_threshold_m2"),
            "min_pct": reg.get("landscaping_min_pct"),
            "article": reg.get("landscaping_article", ""),
        },
    }
    if reg_ext:
        result["extended"] = reg_ext
    return result


def build_restrictions(reg: dict, zone_names: list[str],
                       reg_ext: dict | None = None,
                       overlays: list[dict] | None = None,
                       overlay_all_matched: set[str] | None = None) -> list[str]:
    """Build a human-readable list of key restrictions."""
    restrictions = []

    bcr = reg.get("bcr_pct")
    far = reg.get("far_pct")

    if bcr is not None:
        restrictions.append(f"건폐율 상한: {bcr}%")
    if far is not None:
        restrictions.append(f"용적률 상한: {far}%")

    if reg.get("sunlight_applies"):
        restrictions.append("일조사선: 정북방향 H/2 이격")

    if reg.get("road_diagonal_multiplier") is not None:
        restrictions.append(
            f"높이제한: 전면도로폭 × {reg['road_diagonal_multiplier']} "
            f"(가로구역별 높이 미지정 시, 건축법 시행령 §82)"
        )

    if reg.get("corner_cutoff_required"):
        restrictions.append("가각전제: 8m 미만 도로 모퉁이 (시행령 §31)")

    if reg.get("adjacent_setback_m") is not None:
        restrictions.append(f"인접대지 이격: {reg['adjacent_setback_m']}m 이상")

    if reg.get("landscaping_min_pct") is not None:
        restrictions.append(f"조경: 대지면적의 {reg['landscaping_min_pct']}% 이상")

    # Extended restrictions summary (Group A)
    if reg_ext:
        bur = reg_ext.get("building_use_restriction", {})
        if bur.get("prohibited_summary"):
            restrictions.append(f"건축물 용도 제한: {bur['prohibited_summary']}")

        sub = reg_ext.get("site_subdivision_limit", {})
        if sub.get("min_area_m2"):
            restrictions.append(f"대지 분할 제한: 최소 {sub['min_area_m2']}m²")

        dl = reg_ext.get("daylighting_spacing", {})
        if dl.get("applies"):
            restrictions.append("채광 인동간격: 공동주택 높이 기준 이격 (건축법 §61②)")

    if len(zone_names) > 1:
        restrictions.append(
            f"복수 용도지역 적용 ({len(zone_names)}개) - 최엄격 기준 적용 (국토계획법 제76-77조)"
        )

    cat = reg.get("zone_category", "")
    if "녹지" in cat:
        restrictions.append("건축물 용도 제한 (녹지지역) — 시행령 별표 참조")
    elif "공업" in cat:
        restrictions.append("환경오염 관련 규제 주의 (공업지역)")
    elif "자연환경보전" in cat:
        restrictions.append("건축물 용도 극히 제한 (자연환경보전지역)")

    # Overlay zone restrictions
    overlay_matched_zones = set()
    if overlays:
        for ov in overlays:
            vals = ov.get("values", {})
            if vals.get("min_height_m") is not None and vals.get("max_height_m") is not None:
                restrictions.append(
                    f"높이제한: {ov['name']} {vals['min_height_m']}~{vals['max_height_m']}m "
                    f"({ov['article']})"
                )
            elif vals.get("max_height_m") is not None:
                restrictions.append(
                    f"높이제한: {ov['name']} 최고 {vals['max_height_m']}m ({ov['article']})"
                )
            else:
                restrictions.append(f"{ov['description']} ({ov['article']})")
            overlay_matched_zones.add(ov.get("raw_zone", ""))

    # Unmatched zones — exclude all overlay-recognized zones (regulations + info-only)
    all_recognized = overlay_matched_zones
    if overlay_all_matched:
        all_recognized = all_recognized | overlay_all_matched
    unmatched = [
        z for z in reg.get("unmatched_zones", [])
        if z not in all_recognized
    ]
    if unmatched:
        restrictions.append(
            f"미인식 용도지역: {', '.join(unmatched)} (수동 확인 필요)"
        )

    return restrictions
