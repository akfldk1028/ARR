"""
CLI: verify all regulation lines for a parcel against the REGISTRY.

Iterates `land.services.regulations.REGISTRY` (single source of truth for
regulation metadata: law basis, line type, applies-when rule) and compares
backend `/design/auto-constraints/` output against it.

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_setbacks.py <PNU>
    PYTHONIOENCODING=utf-8 python tools/verify_setbacks.py 1168010100106770000 --building-type 공동주택
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Make Django imports work when running from ARR/backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from land.services.regulations import REGISTRY, LineType  # noqa: E402

DEFAULT_BACKEND = "http://localhost:8000"

# Reference 법 상한 for 주요 zone (국계법 시행령 §84, §85) — verify_setbacks sanity check
ZONE_REFERENCE: dict[str, dict[str, Any]] = {
    "제1종전용주거지역": {"bcr": 50, "far_min": 50, "far_max": 100},
    "제2종전용주거지역": {"bcr": 50, "far_min": 50, "far_max": 150},
    "제1종일반주거지역": {"bcr": 60, "far_min": 100, "far_max": 200},
    "제2종일반주거지역": {"bcr": 60, "far_min": 100, "far_max": 250},
    "제3종일반주거지역": {"bcr": 50, "far_min": 100, "far_max": 300},
    "준주거지역": {"bcr": 70, "far_min": 200, "far_max": 500},
    "중심상업지역": {"bcr": 90, "far_min": 200, "far_max": 1500},
    "일반상업지역": {"bcr": 80, "far_min": 200, "far_max": 1300},
    "근린상업지역": {"bcr": 70, "far_min": 200, "far_max": 900},
    "유통상업지역": {"bcr": 80, "far_min": 200, "far_max": 1100},
}


def describe_geometry(g: dict | None) -> str:
    if not isinstance(g, dict):
        return "no geometry"
    t = g.get("type", "?")
    coords = g.get("coordinates")
    if t == "Polygon" and isinstance(coords, list):
        return f"Polygon ({len(coords[0]) if coords else 0}pt)"
    if t == "MultiPolygon" and isinstance(coords, list):
        return f"MultiPolygon ({len(coords)}part)"
    if t == "LineString" and isinstance(coords, list):
        return f"LineString ({len(coords)}pt)"
    if t == "MultiLineString" and isinstance(coords, list):
        seg_lens = [len(seg) for seg in coords]
        return f"MultiLineString ({len(coords)} segs, pts={seg_lens})"
    return f"{t}"


def describe_walls(walls: list | None) -> str:
    if not isinstance(walls, list) or not walls:
        return "walls 없음"
    heights: list[float] = []
    for w in walls:
        mh = w.get("max_heights") if isinstance(w, dict) else None
        if isinstance(mh, list):
            heights.extend(float(h) for h in mh if isinstance(h, (int, float)))
    if heights:
        return f"{len(walls)}walls, H={min(heights):.1f}~{max(heights):.1f}m"
    return f"{len(walls)}walls (no heights)"


def call_backend(client: httpx.Client, pnu: str, building_type: str) -> dict:
    sb = client.post("/design/site-boundary/", json={"pnu": pnu}, timeout=30.0).json()
    poly = sb.get("geometry")
    if not poly:
        raise RuntimeError(f"no site boundary for {pnu}")
    ac = client.post(
        "/design/auto-constraints/",
        json={"pnu": pnu, "site_polygon": poly, "building_type": building_type},
        timeout=120.0,
    ).json()
    ac["_site_area_m2"] = sb.get("area_m2")
    ac["_site_polygon"] = poly
    return ac


def verify(pnu: str, building_type: str, backend: str) -> int:
    client = httpx.Client(base_url=backend)
    print(f"=== 규제선 검증 (PNU: {pnu}, 용도: {building_type}) ===\n")

    try:
        ac = call_backend(client, pnu, building_type)
    except Exception as e:
        print(f"✗ 백엔드 호출 실패: {e}")
        return 1

    zones = ac.get("zones") or []
    zone = zones[0] if zones else None
    reg = ac.get("regulations") or {}
    sg = ac.get("setback_geometries") or {}
    law = ac.get("law_articles") or {}
    area = ac.get("_site_area_m2")

    # 1) 대지 정보
    print(f"용도지역: {zone or '(미확인)'}")
    print(f"대지면적: {area:.2f} m²" if area else "대지면적: ?")

    # 2) BCR/FAR 법 상한 대조
    print("\n─── BCR / FAR 수치 검증 ───")
    if zone and zone in ZONE_REFERENCE:
        ref = ZONE_REFERENCE[zone]
        bcr = reg.get("bcr_pct")
        far = reg.get("far_pct")
        bcr_ok = bcr == ref["bcr"]
        far_ok = far is not None and ref["far_min"] <= far <= ref["far_max"]
        print(f"  {'✓' if bcr_ok else '✗'} BCR: {bcr}%  (법 상한 {ref['bcr']}%)")
        print(f"  {'✓' if far_ok else '✗'} FAR: {far}%  (법 범위 {ref['far_min']}~{ref['far_max']}%)")
    else:
        print(f"  (레퍼런스 없음) BCR={reg.get('bcr_pct')}%, FAR={reg.get('far_pct')}%")
    print(f"  이격: adjacent={reg.get('adjacent_setback_m')}m, "
          f"cornerCut_req={reg.get('corner_cutoff_required')}, "
          f"daylight_mult={reg.get('daylight_diagonal_multiplier')}")

    # 3) REGISTRY 순회 — 각 규제선 상태
    print(f"\n─── 규제 {len(REGISTRY)}종 상태 ───")
    drawn = 0
    na_expected = 0
    missing_bugs = 0

    # context for applies(): merge regulations + helper flags
    ctx = dict(reg)
    for spec in REGISTRY:
        is_applicable = spec.applies(zone, ctx)
        value = sg.get(spec.key)

        if value is None:
            if is_applicable:
                # Expected to draw but missing — potential bug (unless overlay_only)
                if spec.overlay_only:
                    print(f"  ─ {spec.name_ko} ({spec.key}): overlay stub (데이터 미확보)")
                    na_expected += 1
                else:
                    print(f"  ✗ {spec.name_ko} ({spec.key}): 누락 ⚠️  [{spec.law_basis}]")
                    missing_bugs += 1
            else:
                # Correctly N/A
                reason = spec.na_reason or "법상 미적용"
                print(f"  – {spec.name_ko} ({spec.key}): N/A ({reason})")
                na_expected += 1
            continue

        # Value exists — describe it
        if spec.line_type == LineType.ENVELOPE_3D:
            walls = value.get("walls") if isinstance(value, dict) else None
            desc = describe_walls(walls)
        else:
            geom = value.get("geometry") if isinstance(value, dict) else None
            desc = describe_geometry(geom)
        dist = value.get("distance_m") if isinstance(value, dict) else None
        dist_str = f" [{dist}m]" if dist is not None else ""
        label = value.get("label", "") if isinstance(value, dict) else ""
        print(f"  ✓ {spec.name_ko} ({spec.key}): {desc}{dist_str}  {label}")
        drawn += 1

    # 4) 법조항
    print(f"\n─── 법조항: {law.get('total_count', 0)}건 "
          f"(errors={len(law.get('errors') or [])}) ───")

    # 5) 종합
    print(f"\n─── 종합 ───")
    print(f"그려진 선: {drawn}")
    print(f"N/A (정상): {na_expected}")
    print(f"누락 (버그 의심): {missing_bugs}")
    return 0 if missing_bugs == 0 else 2


def main() -> int:
    p = argparse.ArgumentParser(description="필지 규제선 CLI 검증 (registry 기반)")
    p.add_argument("pnu", help="19자리 PNU")
    p.add_argument("--building-type", default="공동주택")
    p.add_argument("--backend", default=DEFAULT_BACKEND)
    args = p.parse_args()
    return verify(args.pnu, args.building_type, args.backend)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
