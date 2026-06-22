"""
Open-Meteo 표고 정확도 검증 — 알려진 한국 landmark과 비교.

90m DEM이 실제 한국 지형 표고를 얼마나 정확히 반영하는지 평가.
대조 기준: Wikipedia / 공식 자료 (해발고도).

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_elevation_accuracy.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from land.services.datum import elevation_api  # noqa: E402


# (이름, lat, lng, 알려진_표고_m, 출처)
LANDMARKS = [
    # 산 정상
    ("한라산 정상",          33.36167, 126.53333, 1947, "Wikipedia"),
    ("지리산 천왕봉",        35.33686, 127.73061, 1915, "Wikipedia"),
    ("설악산 대청봉",        38.11944, 128.46556, 1708, "Wikipedia"),
    ("덕유산 향적봉",        35.86056, 127.74694, 1614, "Wikipedia"),
    ("북한산 백운대",        37.65861, 126.97667,  836, "Wikipedia"),
    ("남산 정상",            37.55139, 126.99056,  262, "Wikipedia"),
    ("관악산 정상",          37.44528, 126.96389,  629, "Wikipedia"),

    # 도시 평지/건물
    ("서울시청",             37.56683, 126.97842,   38, "공식 (광화문 일대 30m)"),
    ("광화문",               37.57569, 126.97689,   30, "광화문 일대"),
    ("강남역",               37.49793, 127.02763,   38, "강남대로 평균"),
    ("롯데월드타워 부근",     37.51256, 127.10209,   28, "잠실동 평지"),
    ("인천공항 부근",         37.46900, 126.45033,    7, "공항 매립지"),

    # 해안/강
    ("부산 해운대 해변",      35.15850, 129.16022,    2, "해변"),
    ("한강 잠실대교",         37.51850, 127.09100,    5, "한강 수위"),
    ("제주 공항",             33.51100, 126.49300,   30, "공항"),

    # 고원/분지
    ("대관령 횡계리",         37.69200, 128.74800,  832, "Wikipedia 평균"),
    ("진안 마이산 입구",      35.78028, 127.40472,  300, "진안고원"),
    ("태백시 태백역",         37.16410, 128.99030,  680, "태백분지"),
]


def main():
    elevation_api.cache_clear()
    print("=== Open-Meteo 90m DEM 정확도 검증 (알려진 landmark) ===\n")

    points = [(lat, lng) for _, lat, lng, _, _ in LANDMARKS]
    elevs = elevation_api.fetch_elevations(points)

    print(f"{'이름':<25} {'좌표':<22} {'알려진':>8} {'Open-Meteo':>12} {'오차':>8} {'%':>6}")
    print("-" * 90)

    errors = []
    for (name, lat, lng, known, src), got in zip(LANDMARKS, elevs):
        diff = got - known
        pct = abs(diff) / known * 100 if known > 0 else 0.0
        mark = "✓" if abs(diff) <= max(20, known * 0.10) else "✗"
        print(f"{name:<25} ({lat:.3f}, {lng:.3f}) {known:>7}m {got:>10.1f}m "
              f"{diff:+8.1f} {pct:5.1f}% {mark}")
        errors.append(abs(diff))

    print("-" * 90)
    print(f"\n통계 (n={len(errors)}):")
    print(f"  평균 절대오차    : {sum(errors)/len(errors):.1f} m")
    print(f"  최대 절대오차    : {max(errors):.1f} m")
    print(f"  ≤10m 일치       : {sum(1 for e in errors if e <= 10)}/{len(errors)}")
    print(f"  ≤20m 일치       : {sum(1 for e in errors if e <= 20)}/{len(errors)}")
    print(f"  ≤50m 일치       : {sum(1 for e in errors if e <= 50)}/{len(errors)}")

    # 카테고리별
    print("\n카테고리별 평균 오차:")
    cat_mountain = [(k, e) for (n, _, _, k, _), e in zip(LANDMARKS, errors) if k > 500]
    cat_city = [(k, e) for (n, _, _, k, _), e in zip(LANDMARKS, errors) if k <= 500 and k > 20]
    cat_low = [(k, e) for (n, _, _, k, _), e in zip(LANDMARKS, errors) if k <= 20]
    if cat_mountain:
        avg = sum(e for _, e in cat_mountain) / len(cat_mountain)
        print(f"  산 (>500m, n={len(cat_mountain)}): 평균 {avg:.1f}m")
    if cat_city:
        avg = sum(e for _, e in cat_city) / len(cat_city)
        print(f"  도시 (20~500m, n={len(cat_city)}): 평균 {avg:.1f}m")
    if cat_low:
        avg = sum(e for _, e in cat_low) / len(cat_low)
        print(f"  해안/저지 (≤20m, n={len(cat_low)}): 평균 {avg:.1f}m")

    print(f"\n결론:")
    avg_err = sum(errors) / len(errors)
    if avg_err < 5:
        print(f"  ✅ 매우 정확 (평균 {avg_err:.1f}m). datum 신뢰 가능.")
    elif avg_err < 15:
        print(f"  ✓ 양호 (평균 {avg_err:.1f}m). 도시 필지에 적합.")
    elif avg_err < 30:
        print(f"  ⚠ 보통 (평균 {avg_err:.1f}m). 산악지 부정확 가능.")
    else:
        print(f"  ✗ 부정확 (평균 {avg_err:.1f}m). NGII 5m 도입 필요.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
