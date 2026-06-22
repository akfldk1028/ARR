"""
CLI: envelope 변경 후 자동 시각 검증 플로우.

1. Django 응답에서 envelope + parcel ring 좌표 추출
2. envelope corners가 parcel 내부에 있는지 (shapely contains)
3. envelope min/max H 법규 일치 (10~50m)
4. envelope footprint == parcel ring 일치 (좌표 매칭)
5. 결과 JSON + 요약 출력 — 사용자가 브라우저 열 필요 없음

사용자 요구: "이거 자동플로우 안 되겠니 도저히"

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/auto_visual_check.py <PNU> [--building-type 공동주택]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

from shapely.geometry import shape, MultiPolygon, Polygon, Point  # noqa: E402


CHECKS = []


def check(name: str, passed: bool, detail: str = ""):
    CHECKS.append((name, passed, detail))
    mark = "✓" if passed else "✗"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pnu")
    ap.add_argument("--building-type", default="공동주택")
    ap.add_argument("--backend", default="http://localhost:8000")
    args = ap.parse_args()

    client = httpx.Client(base_url=args.backend, timeout=90.0)
    print(f"=== 자동 시각 검증 (PNU {args.pnu}) ===\n")

    try:
        sb = client.post("/design/site-boundary/", json={"pnu": args.pnu}).json()
    except Exception as e:
        print(f"✗ site-boundary 실패: {e}")
        return 1

    parcel = shape(sb["geometry"])
    if isinstance(parcel, MultiPolygon):
        parcel = max(parcel.geoms, key=lambda g: g.area)
    parcel_ring = list(parcel.exterior.coords)[:-1]
    pb = parcel.bounds

    try:
        ac = client.post("/design/auto-constraints/", json={
            "pnu": args.pnu, "site_polygon": sb["geometry"],
            "building_type": args.building_type,
        }).json()
    except Exception as e:
        print(f"✗ auto-constraints 실패: {e}")
        return 1

    zones = ac.get("zones") or []
    reg = ac.get("regulations") or {}
    sg = ac.get("setback_geometries") or {}

    print(f"Parcel: area={parcel.area * 111000 * 111000 * 0.8:.0f}m²")
    print(f"Zones: {zones}")
    print(f"BCR: {reg.get('bcr_pct')}%, FAR: {reg.get('far_pct')}%")
    print(f"Parcel ring: {len(parcel_ring)} vertices\n")

    # ─── 1. envelope 존재 여부
    env = sg.get("sunlight_envelope")
    print("─── envelope 존재 ───")
    if env is None:
        applies = reg.get("sunlight_applies", False)
        if not applies:
            check("정북일조 미적용 zone", True, "envelope 없음 (정상)")
            print("\n→ 상업/녹지 등 정북일조 법상 미적용. 검증 종료.")
            return 0
        check("envelope 존재", False, "sunlight_applies=True인데 envelope 없음")
        return 2
    check("envelope 존재", True)

    slants = env.get("slanted_polygons") or []
    check("slanted_polygons ≥ 1", len(slants) >= 1, f"{len(slants)}개")
    if not slants:
        return 2

    # ─── 2. envelope 좌표가 parcel 내부 (각 corner contains)
    print("\n─── 2. envelope corners ⊂ parcel ───")
    for pi, poly in enumerate(slants):
        corners = poly["corners"]
        outside_count = 0
        for c in corners:
            if not parcel.contains(Point(c[0], c[1])):
                # boundary 허용 (10cm margin)
                if parcel.boundary.distance(Point(c[0], c[1])) > 0.000001:
                    outside_count += 1
        ok = outside_count == 0
        check(f"slanted[{pi}] ({poly['kind']}) corners parcel 내부",
              ok, f"{len(corners)}개 중 {outside_count}개 OUT")

    # ─── 3. H 법규 일치 (10~50m)
    print("\n─── 3. envelope H 법규 §86① ───")
    for pi, poly in enumerate(slants):
        heights = [c[2] for c in poly["corners"]]
        min_h, max_h = min(heights), max(heights)
        ok_min = 9.9 <= min_h <= 10.1
        ok_max = 49.9 <= max_h <= 50.1
        check(f"slanted[{pi}] min H = 10m", ok_min, f"{min_h:.1f}m")
        check(f"slanted[{pi}] max H = 50m", ok_max, f"{max_h:.1f}m")

    # ─── 4. envelope footprint == parcel ring
    print("\n─── 4. envelope footprint = parcel ring ───")
    env_ring = [(c[0], c[1]) for c in slants[0]["corners"]]
    parcel_ring_set = {(round(p[0], 6), round(p[1], 6)) for p in parcel_ring}
    env_ring_set = {(round(p[0], 6), round(p[1], 6)) for p in env_ring}
    overlap = parcel_ring_set & env_ring_set
    pct = len(overlap) / max(len(parcel_ring_set), 1) * 100
    check(f"parcel vertices 매칭", pct >= 90,
          f"{len(overlap)}/{len(parcel_ring_set)} ({pct:.0f}%)")

    # ─── 5. 기타 규제선
    print("\n─── 5. 2D 규제선 존재 ───")
    for key in ("adjacent_setback", "road_setback", "buildable_area"):
        v = sg.get(key)
        check(f"{key} 존재", v is not None)

    # ─── 종합
    print("\n─── 종합 ───")
    total = len(CHECKS)
    passed = sum(1 for _, p, _ in CHECKS if p)
    print(f"{passed}/{total} 통과")
    print()
    print("✓ 자동 플로우 완료 (브라우저 열 필요 없음)")
    return 0 if passed == total else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
