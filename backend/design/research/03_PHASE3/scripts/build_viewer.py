"""
C4 Cesium 단일 HTML viewer 빌더.

3개 GeoJSON FeatureCollection을 inline embed해서 더블클릭으로 열 수 있는
독립 HTML 파일 생성. file:// 또는 http server 둘 다 OK.

Usage:
    python build_viewer.py --input-dir <path> --output viewer.html --tag v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PPO {TAG} Mass Viewer — ARR Phase 3 C4 DRL Bootstrap</title>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; font-family: -apple-system, "Segoe UI", "Noto Sans KR", sans-serif; background: #1a1a1a; }}
  #cesiumContainer {{ width: 100%; height: calc(100% - 70px); }}
  #controls {{ height: 70px; display: flex; align-items: center; padding: 0 24px; background: linear-gradient(90deg, #0f172a, #1e293b); color: #f8fafc; gap: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }}
  #controls .title {{ font-weight: 700; font-size: 16px; margin-right: 8px; }}
  #controls .subtitle {{ font-size: 11px; opacity: 0.6; margin-right: 16px; }}
  button {{ padding: 8px 14px; border: 1px solid #475569; background: #1e293b; color: #f1f5f9; cursor: pointer; border-radius: 6px; font-size: 13px; transition: all 0.15s; }}
  button:hover {{ background: #334155; border-color: #64748b; }}
  button.active {{ background: #2563eb; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3); }}
  .info {{ margin-left: auto; font-size: 11px; opacity: 0.7; line-height: 1.4; text-align: right; }}
  .legend {{ display: inline-flex; gap: 8px; align-items: center; margin: 0 8px; font-size: 11px; }}
  .swatch {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(255,255,255,0.4); }}
</style>
</head>
<body>
<div id="controls">
  <span class="title">PPO {TAG} 매스 뷰어</span>
  <button data-site="all" class="active">전체 부지</button>
  <button data-site="gangnam_yeoksam_677">강남 역삼 677</button>
  <button data-site="bundang_test">분당</button>
  <button data-site="chuncheon_test">춘천</button>
  <span class="legend">
    <span class="swatch" style="background:#dc2626"></span>부지
    <span class="swatch" style="background:#22c55e"></span>큰 매스
    <span class="swatch" style="background:#3b82f6"></span>작은 매스
  </span>
  <span class="info">
    Phase 3 C4 DRL Bootstrap · PPO 100k step (13.4s on B200)<br>
    부지당 32개 zero-shot 매스 · 매스 클릭 → 상세
  </span>
</div>
<div id="cesiumContainer"></div>

<script type="application/json" id="data-gangnam_yeoksam_677">{JSON_GANGNAM}</script>
<script type="application/json" id="data-bundang_test">{JSON_BUNDANG}</script>
<script type="application/json" id="data-chuncheon_test">{JSON_CHUNCHEON}</script>

<script>
// Cesium ion token unset — use OSM imagery
Cesium.Ion.defaultAccessToken = '';

const viewer = new Cesium.Viewer('cesiumContainer', {{
  imageryProvider: new Cesium.UrlTemplateImageryProvider({{
    url: 'https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
    credit: '© OpenStreetMap contributors'
  }}),
  terrainProvider: new Cesium.EllipsoidTerrainProvider(),
  baseLayerPicker: false, geocoder: false, sceneModePicker: false,
  navigationHelpButton: false, timeline: false, animation: false,
  homeButton: false, fullscreenButton: true, infoBox: true, selectionIndicator: true,
  vrButton: false,
}});
viewer.cesiumWidget.creditContainer.style.display = 'none';
viewer.scene.globe.enableLighting = true;
viewer.scene.skyAtmosphere.show = true;

const SITES = ['gangnam_yeoksam_677', 'bundang_test', 'chuncheon_test'];
const SITE_LABELS = {{
  'gangnam_yeoksam_677': '강남 역삼 677 (일반상업)',
  'bundang_test': '분당 (2종 일반주거)',
  'chuncheon_test': '춘천 (1종 일반주거)'
}};

const dataSources = {{}};

SITES.forEach(siteKey => {{
  const el = document.getElementById('data-' + siteKey);
  const fc = JSON.parse(el.text);
  const ds = new Cesium.CustomDataSource(siteKey);

  // First pass: find max floor_area for color normalization
  let maxFa = 0;
  fc.features.forEach(f => {{
    if (f.properties.kind === 'site') return;
    const obj = f.properties.objectives || [0];
    if (obj[0] > maxFa) maxFa = obj[0];
  }});
  if (maxFa < 1) maxFa = 1;

  fc.features.forEach(feature => {{
    const props = feature.properties;
    const ring = feature.geometry.coordinates[0];
    const flat = [];
    for (const pt of ring) {{ flat.push(pt[0], pt[1]); }}
    const positions = Cesium.Cartesian3.fromDegreesArray(flat);

    if (props.kind === 'site') {{
      ds.entities.add({{
        name: 'Site: ' + (props.label || siteKey),
        polygon: {{
          hierarchy: positions,
          material: Cesium.Color.RED.withAlpha(0.15),
          outline: true, outlineColor: Cesium.Color.RED, outlineWidth: 3,
          height: 0,
        }},
        description: `<table style="font-size:13px;line-height:1.6">
          <tr><td><b>${{props.label || siteKey}}</b></td></tr>
          <tr><td>Area:</td><td>${{props.area_m2}} m²</td></tr>
          <tr><td>BCR limit:</td><td>≤ ${{props.bcr_limit}}%</td></tr>
          <tr><td>FAR limit:</td><td>≤ ${{props.far_limit}}%</td></tr>
          <tr><td>Height limit:</td><td>≤ ${{props.height_limit}} m</td></tr></table>`,
      }});
    }} else {{
      const height = props.height || 10;
      const obj = props.objectives || [0, 0];
      const fa = obj[0] || 0;
      const day = obj[1] || 0;
      const feasible = props.feasible !== false;

      const norm = Math.min(fa / maxFa, 1);
      const hue = 0.65 - norm * 0.35;  // blue (low fa) → green (high fa)
      const color = feasible
        ? Cesium.Color.fromHsl(hue, 0.75, 0.55, 0.7)
        : Cesium.Color.fromCssColorString('#dc2626').withAlpha(0.5);

      const stepFloor = props.step_floor || 0;
      const floorH = props.floor_height || 3.0;
      const lowerH = stepFloor > 0 ? stepFloor * floorH : height;

      ds.entities.add({{
        name: `Mass #${{props.sample_id}}`,
        polygon: {{
          hierarchy: positions,
          material: color,
          extrudedHeight: lowerH,
          height: 0,
          outline: true, outlineColor: Cesium.Color.WHITE.withAlpha(0.5),
        }},
        description: `<table style="font-size:13px;line-height:1.7">
          <tr><th colspan="2" style="text-align:left;background:#0f172a;color:#f8fafc;padding:6px 10px">PPO Mass #${{props.sample_id}}</th></tr>
          <tr><td>Site:</td><td>${{SITE_LABELS[siteKey] || siteKey}}</td></tr>
          <tr><td>Feasible:</td><td>${{feasible ? '✅ pass' : '❌ violate'}}</td></tr>
          <tr><td><b>Floor area:</b></td><td><b>${{fa.toFixed(0)}} m²</b></td></tr>
          <tr><td><b>Daylight:</b></td><td><b>${{day.toFixed(1)}}</b></td></tr>
          <tr><td>Height:</td><td>${{height}} m (${{props.num_floors}} floors)</td></tr>
          <tr><td>BCR:</td><td>${{props.bcr}}%</td></tr>
          <tr><td>FAR:</td><td>${{props.far}}%</td></tr>
          <tr><td>Penalty:</td><td>${{props.penalty}}</td></tr>
          ${{props.step_floor ? `<tr><td>Stepback:</td><td>floor ${{props.step_floor}} → upper scale ${{props.upper_scale}}</td></tr>` : ''}}
        </table>`,
      }});

      if (props.upper_geometry) {{
        const upperRing = props.upper_geometry.coordinates[0];
        const upperFlat = [];
        for (const pt of upperRing) {{ upperFlat.push(pt[0], pt[1]); }}
        const upperPos = Cesium.Cartesian3.fromDegreesArray(upperFlat);
        ds.entities.add({{
          name: `Mass #${{props.sample_id}} upper`,
          polygon: {{
            hierarchy: upperPos,
            material: color,
            extrudedHeight: height,
            height: lowerH,
            outline: true, outlineColor: Cesium.Color.WHITE.withAlpha(0.5),
          }},
        }});
      }}
    }}
  }});

  viewer.dataSources.add(ds);
  dataSources[siteKey] = ds;
}});

setTimeout(() => {{
  viewer.flyTo(dataSources['gangnam_yeoksam_677'], {{ duration: 1.0 }});
}}, 200);

document.querySelectorAll('#controls button').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('#controls button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const site = btn.dataset.site;
    if (site === 'all') {{
      SITES.forEach(s => dataSources[s].show = true);
      const all = SITES.map(s => dataSources[s]);
      viewer.flyTo(all, {{ duration: 1.5 }});
    }} else {{
      SITES.forEach(s => dataSources[s].show = (s === site));
      viewer.flyTo(dataSources[site], {{ duration: 1.2 }});
    }}
  }});
}});
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--tag", type=str, default="v1")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    geojsons = {}
    for site in ["gangnam_yeoksam_677", "bundang_test", "chuncheon_test"]:
        path = in_dir / f"ppo_{args.tag}_{site}.geojson"
        with open(path, encoding="utf-8") as f:
            geojsons[site] = f.read().strip()

    html = HTML_TEMPLATE.format(
        TAG=args.tag,
        JSON_GANGNAM=geojsons["gangnam_yeoksam_677"],
        JSON_BUNDANG=geojsons["bundang_test"],
        JSON_CHUNCHEON=geojsons["chuncheon_test"],
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Built viewer: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
