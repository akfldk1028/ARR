"""
CLI: verify dynamic regulation values based on BuildingContext.

Tests the 10m threshold, pilotis exclusion, and road-level offset logic
from `land.services.regulations.building_context` against Korean 건축법
시행령 §86, §60, §61.

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_dynamic.py
    PYTHONIOENCODING=utf-8 python tools/verify_dynamic.py --zone 제3종일반주거지역
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from land.services.regulations import (  # noqa: E402
    BuildingContext,
    effective_height,
    sunlight_setback_for_height,
    sunlight_rules_for_context,
    daylight_distance,
    daylight_multiplier_for_zone,
    summarize,
    SUNLIGHT_LOW_THRESHOLD_M,
    SUNLIGHT_LOW_SETBACK_M,
    SUNLIGHT_HIGH_MULTIPLIER,
)


def header(title: str) -> None:
    bar = "─" * (len(title) + 4)
    print(f"\n{bar}\n  {title}\n{bar}")


def verify_threshold_table() -> int:
    """Table test: 각 높이별 정북일조 이격 법규대로인지."""
    header("§86① 정북일조 이격 — 높이별 법규 대조 (기본 조건, no pilotis, no offset)")
    print(f"{'H (m)':>8}  {'expected (m)':>14}  {'computed (m)':>14}  {'basis':<50}  status")
    cases = [
        (5.0,  1.5, "H ≤ 10m → 1.5m"),
        (9.0,  1.5, "H ≤ 10m → 1.5m (개정 전 9m 기준 완화 확인)"),
        (10.0, 1.5, "H = 10m 경계 → 1.5m (≤ 포함)"),
        (10.1, 5.05, "H > 10m → H × 0.5"),
        (15.0, 7.5, "H > 10m → H × 0.5"),
        (20.0, 10.0, "H > 10m → H × 0.5"),
        (30.0, 15.0, "H > 10m → H × 0.5"),
    ]
    fails = 0
    for h, expected, basis in cases:
        computed = sunlight_setback_for_height(h, None)
        ok = abs(computed - expected) < 0.001
        mark = "✓" if ok else "✗"
        if not ok:
            fails += 1
        print(f"{h:>8.1f}  {expected:>14.2f}  {computed:>14.2f}  {basis:<50}  {mark}")
    return fails


def verify_pilotis() -> int:
    """필로티 1F 층고 제외 — H_유효 = H − pilotis_h."""
    header("필로티 1F 전체 설치 — 유효 높이 산정 (법제처 해석)")
    fails = 0
    cases = [
        # (total_h, pilotis_on, pilotis_h, expected_effective_h, expected_setback_m)
        (12.0, False, 3.0, 12.0, 6.0),     # 필로티 없음, H>10m → 6m
        (12.0, True,  3.0,  9.0, 1.5),     # 필로티 있음, H_유효=9m ≤10 → 1.5m
        (13.0, True,  3.0, 10.0, 1.5),     # H_유효=10m 경계 → 1.5m
        (14.0, True,  3.0, 11.0, 5.5),     # H_유효=11m > 10 → 5.5m
        (20.0, True,  4.0, 16.0, 8.0),     # 필로티 4m 제외, H_유효=16 → 8m
    ]
    print(f"{'H_total':>8}  {'pilotis':>8}  {'pilotis_h':>10}  {'expected_eff':>12}  "
          f"{'computed_eff':>12}  {'expected_sb':>12}  {'computed_sb':>12}  status")
    for total_h, pilotis_on, pilotis_h, expected_eff, expected_sb in cases:
        ctx = BuildingContext(
            target_height_m=total_h,
            has_pilotis_1f=pilotis_on,
            pilotis_height_m=pilotis_h,
        )
        eff = effective_height(total_h, ctx)
        sb = sunlight_setback_for_height(total_h, ctx)
        ok = abs(eff - expected_eff) < 0.001 and abs(sb - expected_sb) < 0.001
        if not ok:
            fails += 1
        mark = "✓" if ok else "✗"
        print(f"{total_h:>8.1f}  {str(pilotis_on):>8}  {pilotis_h:>10.1f}  {expected_eff:>12.1f}  "
              f"{eff:>12.1f}  {expected_sb:>12.2f}  {sb:>12.2f}  {mark}")
    return fails


def verify_road_level() -> int:
    """§119: 대지-도로 고저차 → 도로면 = 대지 + (고저차/2) 위치. 유효 H는 1/2만큼 감소."""
    header("§119 전면도로 고저차 (대지 높음 → 도로면을 1/2만큼 올림)")
    fails = 0
    cases = [
        # (total_h, offset, expected_eff, expected_sb)
        #   offset > 0: 대지가 도로보다 높음 → 유효 H -= offset/2
        (8.0, 0.0,   8.0, 1.5),    # 평평: H=8 ≤ 10 → 1.5m
        (8.0, 4.0,   6.0, 1.5),    # 대지 +4m → H_유효 = 8 - 2 = 6, ≤10 → 1.5m
        (12.0, 2.0, 11.0, 5.5),    # H_유효 = 12 - 1 = 11 > 10 → 5.5m
        (20.0, 0.0, 20.0, 10.0),   # 고저차 없음
        (20.0, 4.0, 18.0, 9.0),    # H_유효 = 20 - 2 = 18 → 9m
    ]
    print(f"{'H_total':>8}  {'offset':>8}  {'expected_eff':>12}  {'computed_eff':>12}  "
          f"{'expected_sb':>12}  {'computed_sb':>12}  status")
    for total_h, offset, expected_eff, expected_sb in cases:
        ctx = BuildingContext(target_height_m=total_h, road_level_offset_m=offset)
        eff = effective_height(total_h, ctx)
        sb = sunlight_setback_for_height(total_h, ctx)
        ok = abs(eff - expected_eff) < 0.001 and abs(sb - expected_sb) < 0.001
        if not ok:
            fails += 1
        mark = "✓" if ok else "✗"
        print(f"{total_h:>8.1f}  {offset:>+8.1f}  {expected_eff:>12.1f}  {eff:>12.1f}  "
              f"{expected_sb:>12.2f}  {sb:>12.2f}  {mark}")
    return fails


def verify_daylight(zone: str) -> int:
    """채광사선 거리 — H ÷ multiplier."""
    header(f"§86③ 채광사선 수평거리 — H ÷ multiplier (zone={zone})")
    mult = daylight_multiplier_for_zone(zone)
    print(f"  multiplier for '{zone}': {mult}× (근린상업·준주거=4, 그 외=2)")
    fails = 0
    cases = [
        (10.0, 10.0 / mult),
        (20.0, 20.0 / mult),
        (30.0, 30.0 / mult),
    ]
    print(f"{'H (m)':>8}  {'expected_dist':>14}  {'computed_dist':>14}  status")
    for h, expected in cases:
        d = daylight_distance(h, zone, None)
        ok = abs(d - expected) < 0.001
        if not ok:
            fails += 1
        mark = "✓" if ok else "✗"
        print(f"{h:>8.1f}  {expected:>14.2f}  {d:>14.2f}  {mark}")
    return fails


def verify_combined_scenario() -> int:
    """실무 조합: 공동주택 20층, 필로티, 대지 +1m (§119 반영)."""
    header("실무 시나리오: 20층 공동주택, 필로티, 대지가 도로보다 1m 높음")
    fails = 0
    total_h = 20 * 2.8  # 56m
    ctx = BuildingContext(
        target_height_m=total_h,
        has_pilotis_1f=True,
        pilotis_height_m=3.0,
        road_level_offset_m=1.0,
        is_multi_family=True,
    )
    print(f"  입력: H_전체={total_h}m, 필로티={ctx.has_pilotis_1f}, offset={ctx.road_level_offset_m}m")
    # §119: H_유효 = 56 - 3 (필로티) - 0.5 (offset/2) = 52.5m
    expected_eff = total_h - 3.0 - (1.0 * 0.5)
    eff = effective_height(total_h, ctx)
    if abs(eff - expected_eff) > 0.001:
        fails += 1
    print(f"  유효 높이: {eff}m (기대 {expected_eff}m)  {'✓' if abs(eff-expected_eff)<0.001 else '✗'}")

    expected_sb = expected_eff * SUNLIGHT_HIGH_MULTIPLIER
    sb = sunlight_setback_for_height(total_h, ctx)
    if abs(sb - expected_sb) > 0.001:
        fails += 1
    print(f"  정북일조 이격: {sb}m (기대 {expected_sb}m)  {'✓' if abs(sb-expected_sb)<0.001 else '✗'}")

    # sunlight_rules_for_context 스키마
    rules = sunlight_rules_for_context(ctx)
    print(f"\n  sunlight_rules_for_context() — {len(rules)} items:")
    for r in rules:
        print(f"    {r}")
    return fails


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zone", default="제3종일반주거지역",
                   help="채광사선 multiplier 테스트용 zone (기본: 제3종일반주거지역)")
    args = p.parse_args()

    total_fails = 0
    total_fails += verify_threshold_table()
    total_fails += verify_pilotis()
    total_fails += verify_road_level()
    total_fails += verify_daylight(args.zone)
    total_fails += verify_daylight("근린상업지역")  # 4배 케이스
    total_fails += verify_combined_scenario()

    header("종합")
    if total_fails == 0:
        print("  ✓ 전부 PASS (법규 수치 대조 완료)")
    else:
        print(f"  ✗ {total_fails} 개 케이스 실패")
    return 0 if total_fails == 0 else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
