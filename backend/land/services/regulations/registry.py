"""
Registry: 모든 건축법규 규제선/규제수치의 메타데이터.

참고 문헌 (2026-04-20 기준):
- 건축법 (법률) — §46 건축선, §47 건축선에 따른 건축제한, §58 대지 안의 공지,
                §60 건축물 높이제한, §61 일조 등의 확보를 위한 높이제한
- 건축법 시행령 — §31 건축선 지정, §80의2 대지 안의 공지, §82 건축물 높이제한,
                §86 일조 등의 확보
- 국토의 계획 및 이용에 관한 법률 — §49~§52 지구단위계획
- 지구단위계획 수립지침 (국토교통부) — 건축선 4분류
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class LineType(str, Enum):
    """규제선 geometry 종류."""
    POLYGON_2D = "polygon_2d"          # 건축가능영역 (면)
    LINE_2D = "line_2d"                # 이격선/후퇴선 (선)
    CLIP_2D = "clip_2d"                # 가각전제 (잘리는 삼각면)
    ENVELOPE_3D = "envelope_3d"        # 일조/채광 사선 경사면 (Cesium wall)
    OVERLAY_ONLY = "overlay_only"      # 법문만 표시, geometry 없음


# 용도지역 분류 헬퍼
_RESIDENTIAL_EXCLUSIVE = {"제1종전용주거지역", "제2종전용주거지역"}
_RESIDENTIAL_GENERAL = {
    "제1종일반주거지역", "제2종일반주거지역", "제3종일반주거지역",
}
_RESIDENTIAL_SEMI = {"준주거지역"}
_COMMERCIAL = {"중심상업지역", "일반상업지역", "근린상업지역", "유통상업지역"}


def _is_residential(zone: str | None) -> bool:
    """전용주거 + 일반주거만 (준주거 제외 — 정북일조 미적용)."""
    return bool(zone and zone in (_RESIDENTIAL_EXCLUSIVE | _RESIDENTIAL_GENERAL))


def _is_commercial(zone: str | None) -> bool:
    return bool(zone and zone in _COMMERCIAL)


@dataclass(frozen=True)
class RegulationSpec:
    """규제 하나의 메타데이터."""
    key: str                              # 프런트/백엔드 공통 key (예: "north_setback")
    name_ko: str                          # 한글 표시명
    line_type: LineType                   # geometry 종류
    law_basis: str                        # 법근거 조문 (짧은 표기)
    description: str                      # 한 줄 설명
    # applies(zone, ctx) → bool. ctx는 regulation_calculator.calculate_all() 결과.
    applies: Callable[[str | None, dict], bool] = field(
        default=lambda z, c: True, repr=False,
    )
    # 법상 N/A 사유 (applies가 False일 때 사용자에게 보여줄 설명)
    na_reason: str = ""
    # overlay에서만 오는 규제는 True (geometry 계산 없이 overlay_resolver가 세팅)
    overlay_only: bool = False
    # True면 applies=True여도 실제 geometry 감지가 실패하면 N/A로 처리 (bug 아님).
    # 예: 가각전제는 zone 허용 + 도로 모퉁이 "실제 형상"이 있어야 draw됨.
    geometry_dependent: bool = False
    # 부재시 기본 설명 (geometry_dependent=True일 때)
    geometry_missing_reason: str = ""


# ───────────────────────────────────────────────────────────────
# 핵심 규제 (건축법 본법)
# ───────────────────────────────────────────────────────────────

BUILDABLE_AREA = RegulationSpec(
    key="buildable_area",
    name_ko="건축가능영역",
    line_type=LineType.POLYGON_2D,
    law_basis="통합 (이격/후퇴/사선 전체 적용 후)",
    description="인접이격·건축선 후퇴·가각전제 등 모든 제한을 반영한 실제 건축 가능 폴리곤",
    applies=lambda z, c: True,
)

ADJACENT_SETBACK = RegulationSpec(
    key="adjacent_setback",
    name_ko="인접대지 이격선",
    line_type=LineType.LINE_2D,
    law_basis="건축법 §58, 시행령 §80의2",
    description="대지 경계선에서 띄워야 하는 최소 거리 (기본 0.5m)",
    applies=lambda z, c: (c.get("adjacent_setback_m") or 0) > 0,
)

ROAD_SETBACK = RegulationSpec(
    key="road_setback",
    name_ko="건축선 후퇴",
    line_type=LineType.LINE_2D,
    law_basis="건축법 §46, §47",
    description="도로 접면 쪽 건축선 후퇴 (소요너비 미달 도로의 경우 중심선에서 대칭 후퇴)",
    applies=lambda z, c: (c.get("building_line_setback_m") or 0) > 0,
)

CORNER_CUTOFF = RegulationSpec(
    key="corner_cutoff",
    name_ko="가각전제 (도로 모퉁이 잘라냄)",
    line_type=LineType.CLIP_2D,
    law_basis="건축법 시행령 §31",
    description="8m 미만 도로가 만나는 모퉁이에서 교차각에 따라 삼각 컷오프 (90°미만→3~4m, 90~120°→2~3m, 120°이상 미적용)",
    applies=lambda z, c: c.get("corner_cutoff_required", False),
    na_reason="도로 모퉁이 필지가 아니거나 도로폭 8m 이상",
    geometry_dependent=True,
    geometry_missing_reason="필지에서 두 도로변이 만나는 모퉁이 꼭지점 감지 안 됨 (내측 필지 또는 단일 도로면)",
)

NORTH_SUNLIGHT_SETBACK = RegulationSpec(
    key="north_setback",
    name_ko="정북 일조사선",
    line_type=LineType.LINE_2D,
    law_basis="건축법 §61①, 시행령 §86① (2023.9.12 개정)",
    description="정북 인접대지 경계선에서의 수평 이격 (H≤10m: 1.5m, H>10m: H×0.5)",
    applies=lambda z, c: c.get("sunlight_applies", False) and _is_residential(z),
    na_reason="상업/준주거/녹지 등 정북일조 미적용 용도지역",
)

NORTH_SUNLIGHT_ENVELOPE = RegulationSpec(
    key="sunlight_envelope",
    name_ko="정북 일조 경사면 (3D)",
    line_type=LineType.ENVELOPE_3D,
    law_basis="건축법 §61①, 시행령 §86①",
    description="북측 인접경계에서 올라가는 3D 일조사선 envelope (Cesium wall로 시각화)",
    applies=lambda z, c: c.get("sunlight_applies", False) and _is_residential(z),
    na_reason="상업/준주거 등 정북일조 미적용 용도지역",
)

DAYLIGHT_DIAGONAL_ENVELOPE = RegulationSpec(
    key="daylight_diagonal_envelope",
    name_ko="채광사선 경사면 (3D)",
    line_type=LineType.ENVELOPE_3D,
    law_basis="건축법 §61②, 시행령 §86③",
    description="공동주택 인접경계에서 채광방향 H/수평거리 비율 사선 (근상/준주거 4배, 그외 2배)",
    applies=lambda z, c: bool(c.get("daylight_diagonal_multiplier")),
    na_reason="공동주택 아니거나 채광 적용 대상 아님",
)

# ───────────────────────────────────────────────────────────────
# 지구단위계획 건축선 4분류 (국토의 계획 및 이용에 관한 법률 §49~52)
# ───────────────────────────────────────────────────────────────

BUILDING_DESIGNATION_LINE = RegulationSpec(
    key="building_designation_line",
    name_ko="건축지정선",
    line_type=LineType.LINE_2D,
    law_basis="국토계획법 §52, 지구단위계획 수립지침",
    description="지정 위치에 외벽면이 접해야 하는 선 (가로경관 연속성, 상업가로 벽면 가지런화)",
    applies=lambda z, c: c.get("building_designation_applies", False),
    na_reason="지구단위계획구역 아니거나 건축지정선 미지정",
)

BUILDING_LIMIT_LINE = RegulationSpec(
    key="building_limit_line",
    name_ko="건축한계선",
    line_type=LineType.LINE_2D,
    law_basis="국토계획법 §52, 지구단위계획 수립지침",
    description="이 선의 수직면을 넘어서 건축물 지상부 외벽이 돌출 불가 (도로 개방감 확보용 후퇴선)",
    applies=lambda z, c: c.get("building_limit_applies", False),
    na_reason="지구단위계획구역 아니거나 건축한계선 미지정",
    overlay_only=True,  # overlay 데이터가 있어야 computable (현재 stub)
)

WALL_DESIGNATION_LINE = RegulationSpec(
    key="wall_designation_line",
    name_ko="벽면지정선",
    line_type=LineType.LINE_2D,
    law_basis="국토계획법 §52, 지구단위계획 수립지침",
    description="특정층 외벽면이 일정 비율 이상 접해야 하는 선 (1층 상점가 벽면 정렬, 고층부 벽면 위치 규제)",
    applies=lambda z, c: c.get("wall_designation_applies", False),
    na_reason="지구단위계획구역 아니거나 벽면지정선 미지정",
    overlay_only=True,
)

WALL_LIMIT_LINE = RegulationSpec(
    key="wall_limit_line",
    name_ko="벽면한계선",
    line_type=LineType.LINE_2D,
    law_basis="국토계획법 §52, 지구단위계획 수립지침",
    description="특정층에서 보행공간(공공보행통로 등) 확보를 위해 벽면이 넘을 수 없는 선",
    applies=lambda z, c: c.get("wall_limit_applies", False),
    na_reason="지구단위계획구역 아니거나 벽면한계선 미지정",
    overlay_only=True,
)

# ───────────────────────────────────────────────────────────────
# Registry (순서 = CLI 출력 순서)
# ───────────────────────────────────────────────────────────────

REGISTRY: list[RegulationSpec] = [
    BUILDABLE_AREA,
    # 건축법 본법 이격/사선
    NORTH_SUNLIGHT_SETBACK,
    ADJACENT_SETBACK,
    ROAD_SETBACK,
    CORNER_CUTOFF,
    NORTH_SUNLIGHT_ENVELOPE,
    DAYLIGHT_DIAGONAL_ENVELOPE,
    # 지구단위계획 건축선 4분류
    BUILDING_DESIGNATION_LINE,
    BUILDING_LIMIT_LINE,
    WALL_DESIGNATION_LINE,
    WALL_LIMIT_LINE,
]


def find(key: str) -> RegulationSpec | None:
    """Lookup a spec by key."""
    for spec in REGISTRY:
        if spec.key == key:
            return spec
    return None


def applicable_for(zone: str | None, ctx: dict) -> list[RegulationSpec]:
    """현재 용도지역+플래그에서 적용되는 규제 목록."""
    return [s for s in REGISTRY if s.applies(zone, ctx)]
