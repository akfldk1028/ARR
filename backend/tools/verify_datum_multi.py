"""
Multi-PNU 땅 레벨 데이터 검증 — Vworld + Open-Meteo 라이브.

평탄지/경사지/산기슭 PNU 여러개에서:
1. Vworld API로 polygon 가져오기
2. Open-Meteo로 표고 sample
3. §119 가중평균 datum 계산
4. 합리성 체크 (한국 표고 -10 ~ 1947m, 도시 필지 0~200m)

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_datum_multi.py
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

from shapely.geometry import shape, MultiPolygon, Polygon  # noqa: E402

from design.services.site_geometry import fetch_parcel_boundary  # noqa: E402
from land.services.pnu_resolver import resolve_address  # noqa: E402
from land.services.datum import (  # noqa: E402
    compute_datum_elevation, DatumContext, elevation_api,
)


# 검증 대상 — 주소 (Vworld geocode → PNU 자동)
TEST_ADDRESSES = [
    # (주소, 예상_타입, 예상_표고)
    ("서울특별시 강남구 역삼동 677",          "도시 평지",  "30~80m"),
    ("서울특별시 성북구 성북동 33",            "산기슭",    "100~200m"),
    ("서울특별시 용산구 한남동 686",          "경사지",    "30~150m"),
    ("서울특별시 마포구 합정동 369",          "한강변 평지", "10~40m"),
    ("서울특별시 종로구 평창동 350",          "산기슭",    "100~250m"),
    ("서울특별시 영등포구 여의도동 35-1",     "한강변 평지", "10~30m"),
    ("부산광역시 해운대구 우동 1394",          "해안 도시",  "5~50m"),
    ("강원특별자치도 평창군 대관령면 횡계리",  "산악",      "700~900m"),
]


def verify_address(address: str, expected_type: str, expected_elev: str) -> dict:
    """주소 → PNU → polygon → datum 검증."""
    print(f"\n─── {address} ───")
    print(f"  expected: {expected_type}, ~{expected_elev}")

    # 1. 주소 → PNU
    pnu_result = resolve_address(address)
    if not pnu_result.get("success"):
        print(f"  ✗ Vworld geocode 실패: {pnu_result.get('error', 'unknown')}")
        return {"address": address, "ok": False, "reason": "geocode_failed"}
    pnu = pnu_result.get("pnu")
    if not pnu:
        print(f"  ✗ PNU 추출 실패")
        return {"address": address, "ok": False, "reason": "no_pnu"}
    print(f"  PNU: {pnu}")

    # 2. PNU → polygon
    geom = fetch_parcel_boundary(pnu)
    if geom is None:
        print(f"  ✗ Vworld polygon 가져오기 실패 (PNU {pnu})")
        return {"address": address, "ok": False, "reason": "vworld_failed"}

    parcel = shape(geom)
    if isinstance(parcel, MultiPolygon):
        parcel = max(parcel.geoms, key=lambda g: g.area)
    if not isinstance(parcel, Polygon):
        print(f"  ✗ Polygon 아님: {type(parcel).__name__}")
        return {"address": address, "ok": False, "reason": "not_polygon"}

    bb = parcel.bounds
    n_vertices = len(parcel.exterior.coords) - 1
    area_deg2 = parcel.area
    print(f"  polygon: {n_vertices} vertices, bbox lng {bb[0]:.5f}~{bb[2]:.5f}")

    # 3. datum 계산
    try:
        result = compute_datum_elevation(DatumContext(parcel_wgs=parcel))
    except Exception as e:
        print(f"  ✗ datum 계산 실패: {e}")
        return {"address": address, "ok": False, "reason": f"datum_error: {e}"}

    elevs = (
        [s["midpoint_elev_m"] for s in result.parcel_segments]
        if result.parcel_segments else []
    )
    if not elevs:
        print(f"  ✗ edge 표고 sample 없음")
        return {"address": address, "ok": False, "reason": "no_segments"}

    elev_min, elev_max = min(elevs), max(elevs)
    elev_range = elev_max - elev_min

    # 3. 합리성 체크
    OK = True
    issues = []

    # 한국 표고 범위 (해수면 ~ 백두산 2744m)
    if elev_min < -50 or elev_max > 2000:
        OK = False
        issues.append(f"표고 범위 비정상 ({elev_min:.0f}~{elev_max:.0f}m)")

    # 평탄지인데 변동 큼 (90m DEM 한계 후보)
    if "평지" in expected_type and elev_range > 5.0:
        issues.append(f"⚠ 평지 가정인데 변동 {elev_range:.1f}m 큼 (90m DEM 노이즈 의심)")

    # source 확인
    if result.elevation_source != "open_meteo":
        OK = False
        issues.append(f"source={result.elevation_source!r} (expected 'open_meteo')")

    print(f"  case      : {result.case.value}")
    print(f"  datum_m   : {result.elevation_m:.2f}")
    print(f"  source    : {result.elevation_source}")
    print(f"  elev range: {elev_min:.1f}~{elev_max:.1f}m (변동 {elev_range:.2f}m)")
    print(f"  edges     : {len(elevs)} sample")

    mark = "✓" if OK else "✗"
    print(f"  {mark} {expected_type}")
    for issue in issues:
        print(f"    {issue}")

    return {
        "address": address,
        "expected_type": expected_type,
        "ok": OK,
        "case": result.case.value,
        "datum_m": result.elevation_m,
        "elev_min": elev_min,
        "elev_max": elev_max,
        "elev_range": elev_range,
        "n_edges": len(elevs),
        "issues": issues,
    }


def main():
    elevation_api.cache_clear()
    print("=== 땅 레벨 데이터 검증 (Multi-Address) ===")
    print(f"target: {len(TEST_ADDRESSES)} addresses")

    results = []
    for addr, ex_type, ex_elev in TEST_ADDRESSES:
        r = verify_address(addr, ex_type, ex_elev)
        results.append(r)

    # 요약
    print("\n=== 요약 ===")
    ok = sum(1 for r in results if r["ok"])
    print(f"성공: {ok}/{len(results)}")

    print("\n케이스 분포:")
    cases = {}
    for r in results:
        if r["ok"]:
            cases.setdefault(r["case"], []).append(r["address"])
    for case, addrs in cases.items():
        labels = [a.split()[-2] if " " in a else a for a in addrs]
        print(f"  {case}: {len(labels)} ({', '.join(labels)})")

    # 평지/경사지 분포
    print("\n표고 변동 분포 (90m DEM 노이즈 평가):")
    for r in results:
        if not r["ok"]:
            continue
        addr_short = " ".join(r["address"].split()[1:3])  # 시구
        print(f"  {addr_short:<25} | {r['expected_type']:<12} | "
              f"변동 {r['elev_range']:5.1f}m | case={r['case']:<12} | "
              f"datum={r['datum_m']:7.2f}m")

    # 임계값 권고
    print("\n임계값 분석:")
    flat_results = [r for r in results
                    if r["ok"] and "평지" in r["expected_type"]]
    if flat_results:
        max_flat = max(r["elev_range"] for r in flat_results)
        print(f"  평지 expected PNU 최대 변동: {max_flat:.1f}m (n={len(flat_results)})")
        if max_flat <= 3.0:
            print(f"  → 현재 SLOPE_LE3M 분류 적절. 임계값 조정 불필요.")
        elif max_flat <= 5.0:
            print(f"  → SLOPE_3M_THRESHOLD_M 3.0 → {round(max_flat + 1.0, 1)} 권장")
        else:
            print(f"  → 90m DEM 노이즈 큼. NGII 5m 도입 검토.")

    print(f"\n캐시 사이즈: {elevation_api.cache_size()}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
