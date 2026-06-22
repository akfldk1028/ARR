"""
CLI: envelope polygon 좌표가 parcel 내부인지 **자동 검증**.

사용자 피드백: "매번 브라우저로 확인 말고 자동 체크 필요". 이 CLI는
- wall 라인이 parcel 내부 있는지
- slope polygon 꼭지점 H 값이 §86① 범위 [10, 50] 안인지 (per-vertex 분포)
- envelope 방향이 parcel 북쪽 절반인지

LOCKED SPEC (envelope-locked-spec.md, 2026-04-21):
- plateau 별도 polygon 폐기 (경사 지붕이 H=10m에서 시작, 중복)
- slope corners 42개, H ∈ [10, 50] 분포 (vertex별 distance에 따라)

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_envelope_coords.py <PNU>
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

from shapely.geometry import shape, MultiPolygon, Point, Polygon  # noqa: E402


def verify(pnu: str, backend: str) -> int:
    client = httpx.Client(base_url=backend, timeout=60.0)
    sb = client.post("/design/site-boundary/", json={"pnu": pnu}).json()
    parcel = shape(sb["geometry"])
    if isinstance(parcel, MultiPolygon):
        parcel = max(parcel.geoms, key=lambda g: g.area)
    pbb = parcel.bounds
    cx, cy = parcel.centroid.x, parcel.centroid.y

    print(f"=== Envelope 좌표 자동 검증 (PNU {pnu}) ===\n")
    print(f"Parcel bounds: lon {pbb[0]:.6f}~{pbb[2]:.6f}, lat {pbb[1]:.6f}~{pbb[3]:.6f}")
    print(f"Parcel centroid: ({cx:.6f}, {cy:.6f})\n")

    ac = client.post("/design/auto-constraints/", json={
        "pnu": pnu, "site_polygon": sb["geometry"], "building_type": "공동주택"
    }).json()
    env = ac.get("setback_geometries", {}).get("sunlight_envelope")
    if not env:
        print("✗ envelope 없음")
        return 1

    fails = 0

    # Helper: 점이 parcel 내부 (margin 5m 허용)
    margin_deg = 0.00005  # ~5m
    def in_parcel(lon, lat):
        pt = Point(lon, lat)
        if parcel.contains(pt) or parcel.boundary.distance(pt) < margin_deg:
            return True
        return False

    # 1. 수직벽 — parcel 내부 or 경계
    print("─── 1. 수직 직각벽 (walls) ───")
    for wi, w in enumerate(env.get("walls") or []):
        for i, pt in enumerate(w["positions"]):
            ok = in_parcel(pt[0], pt[1])
            mark = "✓" if ok else "✗"
            if not ok:
                fails += 1
            print(f"  {mark} wall[{wi}]pt[{i}]: ({pt[0]:.6f}, {pt[1]:.6f})")

    # 2. Slope corners 모두 parcel 내부 (LOCKED SPEC: parcel.buffer(-1.5m) inner ring)
    print("\n─── 2. Slope corners parcel 내부 ───")
    for pi, p in enumerate(env.get("slanted_polygons") or []):
        if p.get("kind") != "slope":
            continue
        all_in = True
        out_count = 0
        for c in p["corners"]:
            if not in_parcel(c[0], c[1]):
                all_in = False
                out_count += 1
        if all_in:
            print(f"  ✓ slope[{pi}] 모든 {len(p['corners'])} corners parcel 내부")
        else:
            print(f"  ✗ slope[{pi}] {out_count}/{len(p['corners'])} corners OUT of parcel")
            fails += 1

    # 3. Envelope 방향 — slope corners 중 H≈10인 점들이 parcel 북쪽 절반에 위치
    # (정북 경계 부근에서 H=10m로 시작 → 남쪽으로 가면서 H 증가)
    print("\n─── 3. Envelope 방향 (북쪽 H=10 corner) ───")
    for pi, p in enumerate(env.get("slanted_polygons") or []):
        if p.get("kind") != "slope":
            continue
        # H ≈ 10 인 corners (북쪽 부근)
        north_corners = [c for c in p["corners"] if abs(c[2] - 10.0) < 0.5]
        if not north_corners:
            print(f"  ? slope[{pi}] H≈10 corner 없음 (parcel 매우 작거나 형태 특이)")
            continue
        ny = sum(c[1] for c in north_corners) / len(north_corners)
        is_north_half = ny > cy
        mark = "✓" if is_north_half else "✗"
        if not is_north_half:
            fails += 1
        print(f"  {mark} slope[{pi}] H=10 corners 평균 lat={ny:.6f} "
              f"(parcel centroid {cy:.6f}), 북쪽 절반? {is_north_half}")

    # 4. Slope corners H 값이 §86① 범위 [10, 50] (LOCKED SPEC: H = min(50, max(10, d×2)))
    print("\n─── 4. Slope 높이 범위 (§86① 10≤H≤50) ───")
    for pi, p in enumerate(env.get("slanted_polygons") or []):
        if p.get("kind") != "slope":
            continue
        heights = [c[2] for c in p["corners"]]
        h_min = min(heights)
        h_max = max(heights)
        in_range = all(10.0 - 0.5 <= h <= 50.0 + 0.5 for h in heights)
        has_10 = h_min < 10.5  # 북쪽 corner H≈10 (slope 시작점)
        ok = in_range and has_10
        mark = "✓" if ok else "✗"
        if not ok:
            fails += 1
        print(f"  {mark} slope[{pi}] H range=[{h_min:.1f}, {h_max:.1f}] "
              f"({len(p['corners'])} corners), in [10, 50]? {in_range}, has 10? {has_10}")

    # 5. Profile polyline — 수직 → 평탄 → 경사 3단 프로파일
    print("\n─── 5. Profile polyline (3단 꺾임) ───")
    for pi, pl in enumerate(env.get("profile_polylines") or []):
        pts = pl["points"]
        if len(pts) < 4:
            print(f"  ✗ profile[{pi}]: {len(pts)} pts (기대 4)")
            fails += 1
            continue
        # 기대: P1(H=0) → P2(H=10) → P3(H=10) → P4(H>10)
        h = [p[2] for p in pts]
        expected_pattern = (h[0] == 0 and h[1] == 10 and h[2] == 10 and h[3] > 10)
        mark = "✓" if expected_pattern else "✗"
        if not expected_pattern:
            fails += 1
        print(f"  {mark} profile[{pi}] heights={h}")

    # 종합
    print(f"\n=== 종합 ===")
    if fails == 0:
        print("✓ 모든 좌표 검증 통과 (envelope이 parcel과 정렬됨)")
        return 0
    print(f"✗ {fails}개 검증 실패")
    return 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pnu")
    p.add_argument("--backend", default="http://localhost:8000")
    args = p.parse_args()
    return verify(args.pnu, args.backend)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
