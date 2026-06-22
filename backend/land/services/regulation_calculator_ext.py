"""
Extended Regulation Calculator - computes items 11-41 (31 additional building regulations).

Group A (5): Zone-dependent, loaded from zoning_limits_extended.json
Group B (10): Scale-dependent, fixed thresholds
Group C (16): Text-only, law article references
"""

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@lru_cache(maxsize=1)
def _load_extended_data() -> dict:
    path = os.path.join(_DATA_DIR, "zoning_limits_extended.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────
# Group B: Scale-dependent regulations (10)
# ──────────────────────────────────────────────────────
_SCALE_REGULATIONS = {
    "site_safety": {
        "name": "대지의 안전",
        "rule": "성토·절토 시 옹벽 설치, 배수 확보 등 대지 안전 조치 의무",
        "applies_when": "모든 건축물",
        "article": "건축법 §40",
    },
    "public_open_space": {
        "name": "공개공지",
        "rule": "일반인이 이용할 수 있는 공개 공간 확보 의무",
        "applies_when": "연면적 합계 5,000m² 이상 (문화·집회·판매·업무·숙박시설 등)",
        "article": "건축법 §43, 시행령 §27의2",
    },
    "on_site_open_space": {
        "name": "대지 안의 공지",
        "rule": "건축선 및 인접 대지경계선으로부터 건축물까지 일정 거리 이격",
        "applies_when": "용도·규모별 조례 기준 적용",
        "article": "건축법 §58, 시행령 §80의2",
    },
    "structural_safety": {
        "name": "구조안전 확인/내진설계",
        "rule": "구조안전 확인서 제출 의무, 내진설계 적용",
        "applies_when": "3층 이상 또는 연면적 500m² 이상, 내진: 2층 이상 또는 200m² 이상",
        "article": "건축법 §48, 시행령 §32",
    },
    "fire_resistant": {
        "name": "내화구조",
        "rule": "주요 구조부를 내화구조로 설계",
        "applies_when": "3층 이상 또는 연면적 200m² 이상 (용도별 차이)",
        "article": "건축법 §50, 시행령 §56",
    },
    "fire_compartment": {
        "name": "방화구획",
        "rule": "바닥면적 일정 규모 이상 시 방화구획 설치",
        "applies_when": "내화구조 건축물로서 연면적 기준 초과 시",
        "article": "건축법 §49, 시행령 §46",
    },
    "fire_district": {
        "name": "방화지구 건축제한",
        "rule": "방화지구 내 건축물은 내화구조, 불연재료 사용 의무",
        "applies_when": "방화지구 내 위치 시",
        "article": "건축법 §51, 시행령 §58",
    },
    "elevator": {
        "name": "승강기 설치",
        "rule": "승용 승강기 설치 의무",
        "applies_when": "6층 이상 또는 연면적 2,000m² 이상",
        "article": "건축법 §64, 시행령 제89조",
    },
    "development_permit": {
        "name": "개발행위허가",
        "rule": "건축물 건축, 토지 형질변경 등 시 허가 필요",
        "applies_when": "용도지역별 면적 기준 초과 시",
        "article": "국토계획법 §56, 시행령 §51",
    },
    "infrastructure_fee": {
        "name": "기반시설부담금",
        "rule": "기반시설 설치비용의 일부를 부담",
        "applies_when": "건축연면적 200m² 초과하는 건축행위",
        "article": "국토계획법 §67, 시행령 §64",
    },
}

# ──────────────────────────────────────────────────────
# Group C: Text-only regulations (16)
# ──────────────────────────────────────────────────────
_TEXT_REGULATIONS = {
    "fire_protection": {
        "name": "소방시설",
        "rule": "용도·규모별 소방시설 설치 의무 (소화기, 스프링클러, 자동화재탐지설비 등)",
        "article": "소방시설법 §7, §12",
    },
    "accessibility": {
        "name": "장애인 편의시설",
        "rule": "장애인등이 이용 가능한 편의시설 설치 의무 (경사로, 승강기, 점자블록 등)",
        "article": "장애인등편의법 §8, 시행령 §4",
    },
    "energy_saving": {
        "name": "에너지절약설계",
        "rule": "에너지절약계획서 제출 및 건축물 에너지효율등급 인증 (단열, 기밀, 설비효율)",
        "article": "녹색건축물법 §14, §15, 시행령 §10",
    },
    "evacuation": {
        "name": "피난시설",
        "rule": "피난계단, 특별피난계단, 비상구, 피난안전구역 설치 의무",
        "article": "건축법 §49, 시행령 §34-46",
    },
    "finishing_materials": {
        "name": "마감재료",
        "rule": "내부 마감재료의 불연·준불연·난연 등급 적용 (방화, 유독가스 방지)",
        "article": "건축법 §52, 시행령 §61",
    },
    "room_daylighting": {
        "name": "거실 채광·환기",
        "rule": "거실에 채광 및 환기를 위한 창문 면적 확보 (바닥면적의 1/10 이상 등)",
        "article": "건축법 시행령 §51, §51의2",
    },
    "sewage_treatment": {
        "name": "오수처리",
        "rule": "오수를 공공하수도로 유입시키거나 개인하수처리시설 설치",
        "article": "하수도법 §34, 하수도법 시행령",
    },
    "school_buffer_zone": {
        "name": "학교환경위생정화구역",
        "rule": "학교경계선 200m 이내 유해시설 설치 금지 (유흥주점, 도축장 등)",
        "article": "학교보건법 §6, 시행령 §3-4",
    },
    "cultural_heritage_zone": {
        "name": "문화재 보호구역",
        "rule": "지정문화재 외곽 500m 이내 건축행위 허가·신고 시 문화재청 사전심의",
        "article": "문화재보호법 §35, 시행령 §21의2",
    },
    "military_zone": {
        "name": "군사시설 보호구역",
        "rule": "군사시설 보호구역 내 건축 시 국방부 협의 필요 (높이 제한 등)",
        "article": "군사기지법 §13, 시행령",
    },
    "use_district_restriction": {
        "name": "용도지구 건축제한",
        "rule": "경관지구·미관지구·고도지구 등 용도지구별 추가 건축제한",
        "article": "국토계획법 §76②, 시행령 §72-82",
    },
    "party_wall": {
        "name": "맞벽건축",
        "rule": "상업지역 등에서 맞벽건축 허용·의무 (건축선 일치, 방화벽 공유)",
        "article": "건축법 §59, 시행령 §81",
    },
    "cpted": {
        "name": "범죄예방 CPTED",
        "rule": "범죄예방 환경설계 기준 적용 (사각지대 제거, 조명, 감시카메라 등)",
        "article": "건축법 §53의2, 시행령 §61의3",
    },
    "combined_development": {
        "name": "결합건축",
        "rule": "2개 이상 대지를 결합하여 건폐율·용적률 통합 적용 허용",
        "article": "건축법 §56의2, 시행령 §80의3",
    },
    "basement_restriction": {
        "name": "지하층 제한",
        "rule": "지하층 설치 시 방수·환기·채광·비상탈출구 기준 적용",
        "article": "건축법 §53, 시행령 §25",
    },
    "building_systems": {
        "name": "건축설비",
        "rule": "급·배수, 냉난방, 환기, 전기설비 등 건축설비 기준 적용",
        "article": "건축법 §62, 시행령 §87",
    },
}


def calculate_extended(zone_names: list[str], land_info: dict | None = None) -> dict:
    """
    Calculate 31 extended regulations (items 11-41).

    Returns dict keyed by regulation key with name/rule/article/etc per item.
    """
    result = {}
    result.update(_resolve_group_a(zone_names))
    result.update(_resolve_group_b(zone_names, land_info))
    result.update(_resolve_group_c())
    return result


def _resolve_group_a(zone_names: list[str]) -> dict:
    """Group A: Zone-dependent (5 items). Uses strictest values for multiple zones."""
    data = _load_extended_data()
    zones_db = data["zones"]
    common = data["common"]

    # Collect zone-specific data
    matched = [zones_db[z] for z in zone_names if z in zones_db]

    result = {}

    # 11. building_use_restriction - merge from first matched (zone-specific)
    if matched:
        # For multiple zones, show the most restrictive (first match for summary,
        # combine prohibited lists conceptually)
        first = matched[0].get("building_use_restriction", {})
        result["building_use_restriction"] = {
            "name": "건축물 용도 제한",
            "allowed_summary": first.get("allowed_summary", ""),
            "prohibited_summary": first.get("prohibited_summary", ""),
            "reference_table": first.get("reference_table", ""),
            "article": first.get("article", ""),
        }
        if len(matched) > 1:
            result["building_use_restriction"]["note"] = (
                f"복수 용도지역({len(matched)}개) — 각 지역별 허용용도 교차 확인 필요"
            )
    else:
        result["building_use_restriction"] = {
            "name": "건축물 용도 제한",
            "allowed_summary": "",
            "prohibited_summary": "",
            "reference_table": "",
            "article": "국토계획법 §76, 시행령 §71",
        }

    # 12. site_road_requirement (common, zone-independent)
    road = common.get("site_road_requirement", {})
    result["site_road_requirement"] = {
        "name": "접도의무",
        "min_frontage_m": road.get("min_frontage_m", 2),
        "rule": road.get("rule", ""),
        "article": road.get("article", "건축법 §44"),
    }

    # 13. site_subdivision_limit - strictest (largest min_area)
    sub_areas = [
        m.get("site_subdivision_limit", {}).get("min_area_m2")
        for m in matched if m.get("site_subdivision_limit", {}).get("min_area_m2") is not None
    ]
    sub_articles = list(dict.fromkeys(
        m.get("site_subdivision_limit", {}).get("article", "")
        for m in matched if m.get("site_subdivision_limit", {}).get("article")
    ))
    result["site_subdivision_limit"] = {
        "name": "대지 분할 제한",
        "min_area_m2": max(sub_areas) if sub_areas else None,
        "article": "; ".join(sub_articles) if sub_articles else "건축법 §57, 시행령 §80",
    }

    # 14. daylighting_spacing - applies if ANY zone requires it
    daylight_applies = any(
        m.get("daylighting_spacing", {}).get("applies", False)
        for m in matched
    )
    daylight_data = next(
        (m.get("daylighting_spacing", {}) for m in matched
         if m.get("daylighting_spacing", {}).get("applies", False)),
        {},
    )
    result["daylighting_spacing"] = {
        "name": "채광 인동간격",
        "applies": daylight_applies,
        "rule": daylight_data.get("rule", "주거지역 공동주택 인동간격 확보") if daylight_applies else "비주거지역 또는 비공동주택은 적용 제외",
        "article": daylight_data.get("article", "건축법 §61②, 시행령 §86③"),
    }

    # 15. split_zoning_rule (common)
    split = common.get("split_zoning_rule", {})
    result["split_zoning_rule"] = {
        "name": "2개 용도지역 걸침 규정",
        "rule": split.get("rule", ""),
        "article": split.get("article", "건축법 §54, 국토계획법 §84"),
    }

    return result


def _resolve_group_b(zone_names: list[str], land_info: dict | None = None) -> dict:
    """Group B: Scale-dependent (10 items). Returns threshold info."""
    data = _load_extended_data()
    zones_db = data["zones"]
    matched = [zones_db[z] for z in zone_names if z in zones_db]

    result = {}
    for key, reg in _SCALE_REGULATIONS.items():
        item = dict(reg)  # copy

        # Enrich development_permit with zone-specific max_area if available
        if key == "development_permit" and matched:
            dev_areas = [
                m.get("development_permit", {}).get("max_area_m2")
                for m in matched
                if m.get("development_permit", {}).get("max_area_m2") is not None
            ]
            if dev_areas:
                item["max_area_m2"] = min(dev_areas)  # strictest = smallest

        result[key] = item

    return result


def _resolve_group_c() -> dict:
    """Group C: Text-only (16 items). Static law references."""
    return {key: dict(reg) for key, reg in _TEXT_REGULATIONS.items()}
