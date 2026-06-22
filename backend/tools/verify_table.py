"""
CLI: 규제선 전체를 **색상별 표**로 출력하여 프런트 렌더와 교차 검증.

Row 하나당 규제 하나 + 색상 + 현재 상태 + 법규 근거. 프런트와 색상이 동기화
되었는지, 어느 선이 실제로 그려졌는지 한눈에 확인.

Usage:
    cd ARR/backend
    PYTHONIOENCODING=utf-8 python tools/verify_table.py <PNU>
    PYTHONIOENCODING=utf-8 python tools/verify_table.py 1168011800104670003
    PYTHONIOENCODING=utf-8 python tools/verify_table.py 1168010100106770000  # 역삼(상업)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

from land.services.regulations import REGISTRY, LineType  # noqa: E402
from land.services.regulations.colors import COLORS, name_ko  # noqa: E402


# 정북일조 envelope은 3 컴포넌트로 분리돼 있어 별도 row 로 표시.
ENVELOPE_COMPONENTS = [
    # (row_key, source_path_in_envelope, expected_kind, display_name, color_key)
    ("sunlight_envelope_wall",
     "walls", None, "정북 일조 수직 직각벽 (x=1.5m, H=0→10m)",
     "sunlight_envelope_wall"),
    ("sunlight_envelope_plateau",
     "slanted_polygons", "plateau", "정북 평탄 지붕 (x=1.5~5m, H=10m)",
     "sunlight_envelope_plateau"),
    ("sunlight_envelope_slope",
     "slanted_polygons", "slope", "정북 경사 지붕 (slope 2:1)",
     "sunlight_envelope_slope"),
]


def build_table_rows(ac: dict) -> list[dict]:
    """표 한 줄당 정보 만들기."""
    sg = ac.get("setback_geometries") or {}
    reg = ac.get("regulations") or {}
    zone = (ac.get("zones") or ["?"])[0]

    rows: list[dict] = []

    for spec in REGISTRY:
        if spec.key == "sunlight_envelope":
            # 3 컴포넌트로 분리
            env = sg.get("sunlight_envelope")
            for row_key, src_path, expected_kind, name, color_key in ENVELOPE_COMPONENTS:
                color = COLORS.get(color_key, "#64748b")
                if env is None:
                    status = "N/A" if not spec.applies(zone, reg) else "MISS"
                    count = 0
                else:
                    items = env.get(src_path) or []
                    if expected_kind is None:
                        count = len(items)
                    else:
                        count = sum(1 for it in items if it.get("kind") == expected_kind)
                    status = "DRAWN" if count > 0 else "MISS"
                rows.append({
                    "key": row_key,
                    "name": name,
                    "color": color,
                    "color_ko": name_ko(color),
                    "status": status,
                    "count": count,
                    "law": spec.law_basis,
                })
            continue

        color = COLORS.get(spec.key, "#64748b")
        value = sg.get(spec.key)
        applies = spec.applies(zone, reg)
        if value is None:
            if not applies:
                status = "N/A"
            elif spec.geometry_dependent:
                status = "N/A*"  # applies but no geometry matched
            elif spec.overlay_only:
                status = "STUB"
            else:
                status = "MISS"
            count = 0
        else:
            status = "DRAWN"
            # Try to count sub-elements
            if spec.line_type == LineType.ENVELOPE_3D:
                count = len(value.get("walls") or [])
            elif isinstance(value, dict) and "geometry" in value:
                g = value["geometry"]
                if g and g.get("type", "").startswith("Multi"):
                    count = len(g.get("coordinates") or [])
                else:
                    count = 1
            else:
                count = 1

        rows.append({
            "key": spec.key,
            "name": spec.name_ko,
            "color": color,
            "color_ko": name_ko(color),
            "status": status,
            "count": count,
            "law": spec.law_basis,
        })

    return rows


def print_table(rows: list[dict]) -> None:
    # Header
    print(f"{'색':<6} {'키':<30} {'이름':<40} {'상태':<7} {'cnt':>4}  법근거")
    print("─" * 130)
    status_color = {
        "DRAWN": "✓",
        "N/A": "–",
        "N/A*": "–",   # geometry_dependent N/A (정상)
        "MISS": "✗",
        "STUB": "…",
    }
    for r in rows:
        mark = status_color.get(r["status"], "?")
        color_cell = f"{r['color_ko']:<4}"
        print(f"{color_cell:<6} {r['key']:<30} {r['name']:<40} {mark} {r['status']:<5} "
              f"{r['count']:>4}  {r['law']}")


def print_legend() -> None:
    print("\n─── 상태 범례 ───")
    print("  ✓ DRAWN  : 실제 그려짐")
    print("  – N/A    : 법상 적용 대상 아님 (정상)")
    print("  – N/A*   : 법상 적용되지만 필지 형상상 없음 (geometry_dependent)")
    print("  … STUB   : 지구단위계획 overlay 필요 (미확보, 정상 stub)")
    print("  ✗ MISS   : 그려져야 하는데 누락 (버그 의심)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pnu")
    p.add_argument("--backend", default="http://localhost:8000")
    p.add_argument("--building-type", default="공동주택")
    args = p.parse_args()

    client = httpx.Client(base_url=args.backend, timeout=120.0)
    try:
        sb = client.post("/design/site-boundary/", json={"pnu": args.pnu}).json()
        ac = client.post("/design/auto-constraints/", json={
            "pnu": args.pnu, "site_polygon": sb["geometry"],
            "building_type": args.building_type,
        }).json()
    except Exception as e:
        print(f"✗ 백엔드 호출 실패: {e}")
        return 1

    zone = (ac.get("zones") or ["?"])[0]
    reg = ac.get("regulations") or {}
    print(f"=== 규제선 색상별 검증 표 ===")
    print(f"PNU: {args.pnu}  |  zone: {zone}  |  BCR: {reg.get('bcr_pct')}%  "
          f"FAR: {reg.get('far_pct')}%  sunlight_applies: {reg.get('sunlight_applies')}\n")

    rows = build_table_rows(ac)
    print_table(rows)

    drawn = sum(1 for r in rows if r["status"] == "DRAWN")
    na = sum(1 for r in rows if r["status"] in ("N/A", "N/A*"))
    stub = sum(1 for r in rows if r["status"] == "STUB")
    miss = sum(1 for r in rows if r["status"] == "MISS")

    print(f"\n종합: drawn={drawn} / na={na} / stub={stub} / miss={miss} "
          f"(총 {len(rows)})")
    print_legend()

    return 0 if miss == 0 else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
