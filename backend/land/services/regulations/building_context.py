"""
Building context — 건축물의 "가상 조건" 파라미터.

정북일조/채광사선 계산이 **건축물 높이 H, 필로티 유무, 도로 고저차**에
의존하므로, 이 값들을 한 곳에 묶어 regulation_calculator, setback_geometry에
일관되게 주입.

법규 근거 (2026-04-20 기준):

- **10m 기준** (건축법 시행령 §86① 2023.9.12 개정): H ≤ 10m → 1.5m 이격,
  H > 10m → H × 0.5 이격. 기존 9m 에서 10m로 완화.
- **필로티 높이 산정** (법제처 해석, 건축법 §61② 관련): 1층 전체에 필로티가
  설치되는 공동주택의 경우 §60(건축물 높이제한) 및 §61②(채광사선) 적용시
  필로티 층고를 제외한 높이로 산정. §61①(정북일조) 적용도 동일 원칙 준용.
- **전면도로 기준면** (건축법 시행령 §119): §60 높이는 전면도로 중심선 기준.
  전면도로 노면에 고저차 있으면 접하는 범위 수평거리 가중평균 높이의 수평면을
  전면도로면으로 봄. 대지가 도로보다 높으면 그만큼 효과적 높이 증가.

Reference:
- midascad.com/cad_archive/buildingact-41 (완화된 일조권 사선제한 높이 기준)
- moleg.go.kr 법령해석 필로티 층고 제외
- law.go.kr 건축법 시행령 §86
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 시행령 §86① 기준 임계값 (2023.9.12 개정)
SUNLIGHT_LOW_THRESHOLD_M = 10.0
SUNLIGHT_LOW_SETBACK_M = 1.5          # H ≤ 10m
SUNLIGHT_HIGH_MULTIPLIER = 0.5        # H > 10m → H × 0.5

# 채광사선 배수 (시행령 §86③)
DAYLIGHT_MULTIPLIER_HIGH_DENSITY = 4.0   # 근린상업·준주거
DAYLIGHT_MULTIPLIER_DEFAULT = 2.0        # 그 외


@dataclass(frozen=True)
class RoadSegment:
    """전면도로 1구간 — 가중평균용 (§119)."""
    width_m: float       # 접하는 범위 수평거리 (m)
    level_m: float       # 해당 구간 도로면 고도 (m, 절대 또는 상대)


@dataclass(frozen=True)
class BuildingContext:
    """
    규제 계산에 영향을 주는 건축물 가상 조건.

    모든 필드 optional. None/default면 기본값 적용 (필로티 없음, 고저차 없음, 최대높이).
    """

    # 대상 건물 전체 높이(m). None이면 용도지역 기본 최대높이 사용.
    target_height_m: float | None = None

    # 1층 전체 필로티 여부 (True면 pilotis_height_m 만큼 유효 높이에서 제외).
    # 건축법 §61, §60 법령해석 기준 — 공동주택 1층 전체 필로티만 해당.
    has_pilotis_1f: bool = False
    pilotis_height_m: float = 3.0           # 표준: 3m (지상층 필로티 층고)

    # 전면도로와 대지면의 고저차(m). 양수 = 대지가 도로보다 높음.
    # 음수 = 대지가 도로보다 낮음. 건축법 시행령 §119 반영.
    # 단일 균일 offset 케이스. 상세 고저차는 road_segments 사용.
    road_level_offset_m: float = 0.0

    # §119 가중평균용 상세 전면도로 구간. 각 구간 (수평거리, 고도) 리스트.
    # 비어있으면 road_level_offset_m만 사용. 지정시 weighted average 계산.
    road_segments: tuple[RoadSegment, ...] = ()

    # §119 대지 고저차 (주위 접하는 지표면 가중평균용).
    # 3m 초과 고저차는 3m 이내로 분할 후 각 영역 지표면 별도 산정.
    ground_segments: tuple[RoadSegment, ...] = ()

    # §119: 대지 지표면이 전면도로보다 높은 경우 (도로면 = 대지 + 고저차/2).
    # 자동 계산 (road_level_offset_m > 0 이면 해당) 시 활성.
    apply_dfe_half_raise: bool = True

    # 공동주택 여부 (건물용도 기반). 채광사선 적용 대상.
    is_multi_family: bool = False

    # 기타 법령 계산에 필요한 메타데이터
    meta: dict[str, Any] = field(default_factory=dict)


def weighted_road_level(segments: tuple[RoadSegment, ...]) -> float | None:
    """§119: 전면도로 구간별 수평거리 가중평균 고도 계산."""
    if not segments:
        return None
    total_w = sum(s.width_m for s in segments)
    if total_w <= 0:
        return None
    weighted = sum(s.level_m * s.width_m for s in segments)
    return weighted / total_w


def effective_height(
    total_height_m: float, ctx: BuildingContext | None
) -> float:
    """
    §60, §61, §119 종합 적용 유효 높이 산정.

    1. 필로티 1층 전체: pilotis_height_m 차감 (법제처 해석).
    2. 도로 고저차 반영 (§119):
       - road_segments 있으면 수평거리 가중평균 → 대지-도로 고저차 결정
       - 없으면 road_level_offset_m 직접 사용
       - 대지가 도로보다 높으면: (고저차 ÷ 2) 만큼 올라온 위치에 도로면 있다고 봄
         (즉 효과적으로 기준 datum이 올라가므로 유효 H는 그만큼 낮아짐)

    Returns:
        유효 높이 (최소 0).
    """
    if ctx is None:
        return total_height_m
    h = float(total_height_m)

    # 1. 필로티 제외
    if ctx.has_pilotis_1f and ctx.pilotis_height_m > 0:
        h -= ctx.pilotis_height_m

    # 2. 도로-대지 고저차 결정
    if ctx.road_segments:
        avg_road_level = weighted_road_level(ctx.road_segments) or 0.0
        # ground level is 0 (대지 기준). 대지가 avg_road_level보다 위면 positive offset
        parcel_above_road = -avg_road_level  # 대지 0 - 도로 level
    else:
        parcel_above_road = ctx.road_level_offset_m  # 양수 = 대지 높음

    # 3. §119: 대지가 도로보다 높으면 "(고저차/2)만큼 올라온 위치"를 도로면으로 봄
    # → 기준 datum ↑ by parcel_above_road/2 → 유효 H ↓ by parcel_above_road/2
    # 대지가 낮으면 반대 (유효 H ↑)
    if parcel_above_road != 0 and ctx.apply_dfe_half_raise:
        h -= parcel_above_road * 0.5
    else:
        h += -parcel_above_road  # fallback: full offset (옛 로직)

    return max(0.0, h)


def sunlight_setback_for_height(
    building_height_m: float, ctx: BuildingContext | None = None
) -> float:
    """
    건축법 시행령 §86① 정북일조 이격거리.

    - 유효 높이 ≤ 10m → 1.5m
    - 유효 높이 > 10m → H × 0.5

    필로티/도로레벨 반영된 유효 높이 기준.
    """
    h = effective_height(building_height_m, ctx)
    if h <= SUNLIGHT_LOW_THRESHOLD_M:
        return SUNLIGHT_LOW_SETBACK_M
    return h * SUNLIGHT_HIGH_MULTIPLIER


def sunlight_rules_for_context(ctx: BuildingContext | None = None) -> list[dict]:
    """
    정북일조 규칙 테이블 (프런트/시각화용). ctx가 있으면 target 높이에서의
    실제 이격거리도 `computed` 키로 포함.

    반환 형식은 기존 `regulation_calculator`의 sunlight_rules 스키마와 호환.
    """
    rules = [
        {
            "condition": f"H ≤ {SUNLIGHT_LOW_THRESHOLD_M:.0f}m",
            "setback_m": SUNLIGHT_LOW_SETBACK_M,
            "basis": "건축법 시행령 §86①제1호 (2023.9.12 개정, 9→10m 완화)",
        },
        {
            "condition": f"H > {SUNLIGHT_LOW_THRESHOLD_M:.0f}m",
            "formula": f"H × {SUNLIGHT_HIGH_MULTIPLIER}",
            "basis": "건축법 시행령 §86①제2호",
        },
    ]
    if ctx and ctx.target_height_m is not None:
        h_eff = effective_height(ctx.target_height_m, ctx)
        rules.append({
            "condition": f"이 건물 (H_입력={ctx.target_height_m:.1f}m, H_유효={h_eff:.1f}m)",
            "setback_m": sunlight_setback_for_height(ctx.target_height_m, ctx),
            "pilotis_excluded": ctx.has_pilotis_1f,
            "road_level_offset_m": ctx.road_level_offset_m,
            "basis": "유효 높이 = 전체 - (필로티 1F 층고) + 도로레벨 offset",
        })
    return rules


def daylight_multiplier_for_zone(zone: str | None) -> float:
    """채광사선 배수 (시행령 §86③): 근린상업/준주거=4배, 그 외=2배."""
    if zone in ("근린상업지역", "준주거지역"):
        return DAYLIGHT_MULTIPLIER_HIGH_DENSITY
    return DAYLIGHT_MULTIPLIER_DEFAULT


def daylight_distance(
    building_height_m: float, zone: str | None,
    ctx: BuildingContext | None = None,
) -> float:
    """채광사선 수평거리 = H ÷ multiplier. 공동주택 인접경계 이격 기준."""
    h = effective_height(building_height_m, ctx)
    mult = daylight_multiplier_for_zone(zone)
    return h / mult if mult > 0 else 0.0


def summarize(ctx: BuildingContext | None) -> dict:
    """CLI/디버그용 단일 요약."""
    if ctx is None:
        return {"has_context": False}
    return {
        "has_context": True,
        "target_height_m": ctx.target_height_m,
        "has_pilotis_1f": ctx.has_pilotis_1f,
        "pilotis_height_m": ctx.pilotis_height_m,
        "road_level_offset_m": ctx.road_level_offset_m,
        "is_multi_family": ctx.is_multi_family,
        "effective_height_at_target": (
            effective_height(ctx.target_height_m, ctx)
            if ctx.target_height_m is not None else None
        ),
    }
