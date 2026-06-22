"""Playwright verification of envelope plateau visualization.

Tests Step 13 fix: plateau_polygon should cover only the north 5m strip,
not the full box top.

PNU: 1168011800104170004 (강남 도곡동 417-4, 264m^2, 제2종일반주거)
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Request, Response

PNU = "1168011800104170004"
OUT_DIR = Path(r"D:/Data/25_ACE/docs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Camera control: locate viewer + entity-centroid anchor, then setView.
# Each rotate_* expression is a single arrow IIFE returning a status string.
ROTATE_JS = """
((heading, pitchDeg, distEastDeg, distSouthDeg, altMeters) => {
  const viewer =
    (window.ws3d && window.ws3d.viewer && window.ws3d.viewer.scene && window.ws3d.viewer) ||
    (window.viewer && window.viewer.scene && window.viewer) ||
    null;
  if (!viewer) return 'NO_VIEWER';

  // Entity-centroid anchor (sunlight envelope walls/polygons)
  let sumLng = 0, sumLat = 0, count = 0;
  for (const e of (viewer.entities.values || [])) {
    try {
      let positions = null;
      if (e.wall && e.wall.positions) {
        positions = e.wall.positions.getValue && e.wall.positions.getValue();
      } else if (e.polygon && e.polygon.hierarchy) {
        const h = e.polygon.hierarchy.getValue && e.polygon.hierarchy.getValue();
        positions = h && h.positions;
      }
      if (!positions) continue;
      for (const p of positions) {
        const c = Cesium.Cartographic.fromCartesian(p);
        if (c) { sumLng += c.longitude; sumLat += c.latitude; count++; }
      }
    } catch (err) {}
  }
  if (count === 0) return 'NO_ENTITIES';
  const lng = sumLng / count;
  const lat = sumLat / count;
  const pitch = -Math.abs(pitchDeg) * Math.PI / 180;
  const headingRad = heading * Math.PI / 180;
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromRadians(
      lng + distEastDeg * Math.PI / 180,
      lat + (-distSouthDeg) * Math.PI / 180,
      altMeters
    ),
    orientation: { heading: headingRad, pitch: pitch, roll: 0 }
  });
  viewer.scene.requestRender();
  return JSON.stringify({
    lng_deg: lng * 180 / Math.PI,
    lat_deg: lat * 180 / Math.PI,
    entity_count: count
  });
}).call(null, ${heading}, ${pitch_deg}, ${east_deg}, ${south_deg}, ${alt})
"""


def rotate(page: Page, heading: float, pitch_deg: float,
           east_deg: float, south_deg: float, alt: float) -> str:
    expr = (ROTATE_JS
            .replace("${heading}", str(heading))
            .replace("${pitch_deg}", str(pitch_deg))
            .replace("${east_deg}", str(east_deg))
            .replace("${south_deg}", str(south_deg))
            .replace("${alt}", str(alt)))
    return page.evaluate(expr)


def main() -> int:
    plateau_data: dict = {}
    auto_constraints_payload: dict = {}
    all_design_urls: list[str] = []
    all_api_urls: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page: Page = ctx.new_page()

        def on_request(req: Request) -> None:
            url = req.url
            if "/src/" in url or url.endswith((".ts", ".tsx", ".js")):
                return
            if "/design/" in url or "/land/" in url or "localhost:8000" in url:
                all_api_urls.append(f"REQ {req.method} {url}")

        page.on("request", on_request)

        def on_response(resp: Response) -> None:
            url = resp.url
            if "/src/" in url:
                return
            if "/design/" in url or "/land/" in url:
                all_design_urls.append(f"{resp.status} {resp.request.method} {url}")
            if "/auto-constraints" in url or "/land/analyze" in url:
                try:
                    body = resp.json()
                except Exception:
                    return
                sb = (body.get("setback_geometries")
                      if "/auto-constraints" in url else body.get("setback_lines")) or {}
                if not isinstance(sb, dict):
                    return
                env = sb.get("sunlight_envelope")
                if env:
                    auto_constraints_payload["envelope"] = env
                    pp = env.get("plateau_polygon")
                    if pp:
                        plateau_data["from"] = url.split("/")[-2]
                        plateau_data["polygon"] = pp

        page.on("response", on_response)

        page.on("console", lambda msg: print(f"[console.{msg.type}] {msg.text}")
                if msg.type == "error" else None)
        page.on("pageerror", lambda exc: print(f"[pageerror] {exc}"))

        print(f"[1/7] Navigating to http://localhost:5173/design ...")
        page.goto("http://localhost:5173/design",
                  wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        print(f"[2/7] Filling PNU: {PNU}")
        pnu_input = page.locator('input[placeholder*="PNU"]').first
        pnu_input.wait_for(state="visible", timeout=10000)
        pnu_input.click()
        pnu_input.fill("")
        pnu_input.type(PNU, delay=15)

        print("[3/7] Clicking 조회 button ...")
        page.get_by_role("button", name="조회").click()

        print("[4/7] Waiting up to 90s for auto-constraints + envelope render ...")
        for i in range(90):
            page.wait_for_timeout(1000)
            if auto_constraints_payload:
                print(f"        envelope response observed at t={i+1}s")
                break
        page.wait_for_timeout(5000)

        # View A: front (camera south of site, look north, pitch 30deg, alt 30m)
        print("[5/7] Front view (south->north) ...")
        r = rotate(page, heading=0, pitch_deg=30,
                   east_deg=0, south_deg=0.00035, alt=30)
        print(f"        anchor: {r}")
        page.wait_for_timeout(2500)
        path_front = OUT_DIR / "img_45_front.png"
        page.screenshot(path=str(path_front), full_page=False)
        print(f"        -> {path_front}")

        # View B: top-down (alt 100m, pitch 90deg)
        print("[6/7] Top-down view ...")
        r = rotate(page, heading=0, pitch_deg=89.5,
                   east_deg=0, south_deg=0, alt=100)
        print(f"        anchor: {r}")
        page.wait_for_timeout(2500)
        path_top = OUT_DIR / "img_45_top.png"
        page.screenshot(path=str(path_top), full_page=False)
        print(f"        -> {path_top}")

        # View C: side (east of site, look west, low pitch)
        print("[7/7] Side view (east->west) ...")
        r = rotate(page, heading=270, pitch_deg=12,
                   east_deg=0.00040, south_deg=0, alt=20)
        print(f"        anchor: {r}")
        page.wait_for_timeout(2500)
        path_side = OUT_DIR / "img_45_side.png"
        page.screenshot(path=str(path_side), full_page=False)
        print(f"        -> {path_side}")

        browser.close()

    # Report
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    print(f"PNU              : {PNU}  (강남 도곡동 417-4, 264m^2, 제2종일반주거)")
    if plateau_data:
        pp = plateau_data["polygon"]
        corners = pp.get("corners", [])
        heights = [c[2] for c in corners] if corners else []
        all_10 = all(abs(h - 10.0) < 0.01 for h in heights) if heights else False
        print(f"source           : {plateau_data['from']}")
        print(f"plateau_polygon  : PRESENT")
        print(f"corners count    : {len(corners)}")
        print(f"label            : {pp.get('label')}")
        print(f"kind             : {pp.get('kind')}")
        print(f"heights          : {heights}")
        print(f"all H=10m        : {all_10}")
    else:
        env = auto_constraints_payload.get("envelope")
        if env:
            print(f"envelope keys    : {list(env.keys())}")
            print(f"plateau_polygon  : MISSING")
            print(f"plateau_end_m    : {env.get('plateau_end_m')}")
        else:
            print(f"plateau_polygon  : MISSING (no envelope response captured)")
    print(f"\nScreenshots saved to: {OUT_DIR}")
    print(f"  img_45_front.png  (south->north, pitch 30deg)")
    print(f"  img_45_top.png    (top-down)")
    print(f"  img_45_side.png   (east->west, pitch 12deg)")
    print(f"\nAPI requests ({len(all_api_urls)}):")
    for u in all_api_urls[:20]:
        print(f"  {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
