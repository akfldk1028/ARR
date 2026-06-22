"""
Batch verify all regulation lines for curated test parcels, using the REGISTRY.

Registry-driven — automatically tests all 11 regulation types per parcel.
Fixture `test_parcels.json` defines expected zone/BCR/FAR only; applies
for each regulation is determined by the registry spec itself.

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_all.py
    PYTHONIOENCODING=utf-8 python tools/verify_all.py --filter 주거
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from land.services.regulations import REGISTRY  # noqa: E402

FIXTURES = HERE / "test_parcels.json"


def load_fixtures() -> list[dict]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))["parcels"]


def verify_one(client: httpx.Client, parcel: dict, timeout_s: float) -> dict:
    pnu = parcel["pnu"]
    expected = parcel["expected"]

    r = {
        "pnu": pnu,
        "address": parcel["address"],
        "expected_zone": parcel["zone"],
        "error": None,
    }
    try:
        sb = client.post("/design/site-boundary/", json={"pnu": pnu}, timeout=min(timeout_s, 60.0)).json()
        poly = sb.get("geometry")
        if not poly:
            r["error"] = "no boundary"
            return r
        ac = client.post(
            "/design/auto-constraints/",
            json={"pnu": pnu, "site_polygon": poly, "building_type": "공동주택"},
            timeout=timeout_s,
        ).json()
    except Exception as e:
        r["error"] = f"http: {e}"
        return r

    zones = ac.get("zones") or []
    reg = ac.get("regulations") or {}
    sg = ac.get("setback_geometries") or {}
    law = ac.get("law_articles") or {}

    r["actual_zones"] = zones
    r["actual_zone"] = zones[0] if zones else None
    r["zone_match"] = expected_zone_match = parcel["zone"] in zones
    r["bcr_match"] = reg.get("bcr_pct") == expected["bcr_pct"]
    r["far_match"] = reg.get("far_pct") == expected["far_pct"]
    r["sunlight_match"] = reg.get("sunlight_applies") == expected["sunlight_applies"]
    r["actual_bcr"] = reg.get("bcr_pct")
    r["actual_far"] = reg.get("far_pct")
    r["actual_sunlight"] = reg.get("sunlight_applies")

    # Registry-driven line status
    zone = r["actual_zone"]
    bugs = []
    drawn = []
    na = []
    stubs = []
    geom_na = []  # geometry_dependent + applies=True but not detected — not a bug
    for spec in REGISTRY:
        applies = spec.applies(zone, reg)
        has_value = sg.get(spec.key) is not None
        if applies and not has_value:
            if spec.overlay_only:
                stubs.append(spec.key)
            elif spec.geometry_dependent:
                geom_na.append(spec.key)
            else:
                bugs.append(spec.key)
        elif has_value:
            drawn.append(spec.key)
        else:
            na.append(spec.key)

    r["lines_drawn"] = drawn
    r["lines_missing_bugs"] = bugs
    r["lines_na_legal"] = na
    r["lines_overlay_stubs"] = stubs
    r["lines_geom_na"] = geom_na
    r["law_total"] = law.get("total_count", 0)
    return r


def format_result(r: dict) -> str:
    if r["error"]:
        return f"✗ {r['pnu']}  {r['address']}  → {r['error']}"
    zone_ok = bool(r.get("zone_match"))
    mark = lambda ok: "✓" if ok else "✗"
    lines_ok = not r["lines_missing_bugs"]

    lines_part = (
        f"drawn={len(r['lines_drawn'])} "
        f"na={len(r['lines_na_legal'])} "
        f"geom_na={len(r['lines_geom_na'])} "
        f"stubs={len(r['lines_overlay_stubs'])}"
    )
    if r["lines_missing_bugs"]:
        lines_part += f" BUGS={r['lines_missing_bugs']}"

    return (
        f"{r['pnu']}  {r['address']}\n"
        f"    {mark(zone_ok)} zones={r.get('actual_zones') or []}  (기대 포함 {r['expected_zone']})\n"
        f"    {mark(r['bcr_match'])} BCR={r['actual_bcr']}%  "
        f"{mark(r['far_match'])} FAR={r['actual_far']}%  "
        f"{mark(r['sunlight_match'])} sunlight={r['actual_sunlight']}\n"
        f"    {mark(lines_ok)} {lines_part}  law={r['law_total']}건"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="http://localhost:8000")
    p.add_argument("--filter", default=None, help="zone name filter (e.g. 주거)")
    p.add_argument("--timeout", type=float, default=240.0, help="auto-constraints timeout seconds per PNU")
    p.add_argument("--out", default=None, help="optional JSON result output path")
    args = p.parse_args()

    parcels = load_fixtures()
    if args.filter:
        parcels = [p for p in parcels if args.filter in p["zone"]]
    if not parcels:
        print("no parcels matched", file=sys.stderr)
        return 1

    client = httpx.Client(base_url=args.backend)
    print(f"=== 배치 검증: {len(parcels)}개 필지, {len(REGISTRY)}종 규제 ===\n")

    all_pass = True
    zone_stats: dict[str, dict[str, int]] = {}
    results = []
    for parcel in parcels:
        result = verify_one(client, parcel, args.timeout)
        results.append(result)
        print(format_result(result))
        print()
        zone = parcel["zone"]
        stat = zone_stats.setdefault(zone, {"total": 0, "pass": 0})
        stat["total"] += 1
        ok = (
            not result.get("error")
            and result.get("zone_match")
            and result.get("bcr_match")
            and result.get("far_match")
            and result.get("sunlight_match")
            and not result.get("lines_missing_bugs")
        )
        if ok:
            stat["pass"] += 1
        else:
            all_pass = False

    print("─── 용도지역별 요약 ───")
    for zone, stat in sorted(zone_stats.items()):
        m = "✓" if stat["pass"] == stat["total"] else "✗"
        print(f"  {m} {zone}: {stat['pass']}/{stat['total']}")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "backend": args.backend,
                    "timeout": args.timeout,
                    "pass": all_pass,
                    "results": results,
                    "zone_stats": zone_stats,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {out_path}")

    return 0 if all_pass else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
