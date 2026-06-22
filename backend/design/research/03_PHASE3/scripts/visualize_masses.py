"""
C4 매스 시각화 — top-down + axonometric per site, single PNG.

Renders site polygon + N PPO masses on a 2-row figure (top: footprint, bottom: 3D iso).
Each mass colored by floor_area (viridis cmap), labeled [floor / daylight].
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from shapely.geometry import shape, Polygon as ShPolygon
import pyproj


def latlon_to_local(coords: list, origin_lat: float, origin_lon: float) -> np.ndarray:
    """Convert WGS84 to local meters (centered at origin)."""
    proj = pyproj.Transformer.from_crs(
        "EPSG:4326",
        f"+proj=tmerc +lat_0={origin_lat} +lon_0={origin_lon} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs",
        always_xy=True,
    )
    pts = np.array([proj.transform(lon, lat) for lon, lat in coords])
    return pts


def load_site_geojson(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_site_panel(ax_top, ax_3d, fc: dict, top_n: int = 8):
    """Render a single site: top-down (left) and 3D iso (right)."""
    site_feat = next((f for f in fc["features"] if f["properties"].get("kind") == "site"), None)
    masses = [f for f in fc["features"] if f["properties"].get("kind") != "site"]

    if not site_feat:
        ax_top.text(0.5, 0.5, "no site", ha="center", va="center", transform=ax_top.transAxes)
        return

    site_coords_wgs = site_feat["geometry"]["coordinates"][0]
    centroid_lon = sum(c[0] for c in site_coords_wgs) / len(site_coords_wgs)
    centroid_lat = sum(c[1] for c in site_coords_wgs) / len(site_coords_wgs)

    site_local = latlon_to_local(site_coords_wgs, centroid_lat, centroid_lon)

    label = site_feat["properties"].get("label", site_feat["properties"].get("site_key", "?"))
    bcr_lim = site_feat["properties"].get("bcr_limit", 0)
    far_lim = site_feat["properties"].get("far_limit", 0)
    h_lim = site_feat["properties"].get("height_limit", 0)

    # Sort masses by floor_area desc, take top_n
    masses_with_area = [
        (m, m["properties"].get("objectives", [0])[0] if m["properties"].get("objectives") else 0)
        for m in masses
    ]
    masses_with_area.sort(key=lambda x: -x[1])
    top_masses = [m for m, _ in masses_with_area[:top_n]]

    floor_areas = [m["properties"].get("objectives", [0])[0] if m["properties"].get("objectives") else 0
                   for m in top_masses]
    daylights = [m["properties"].get("objectives", [0, 0])[1] if m["properties"].get("objectives") else 0
                 for m in top_masses]

    fa_min = min(floor_areas) if floor_areas else 0
    fa_max = max(floor_areas) if floor_areas else 1
    fa_range = max(fa_max - fa_min, 1.0)

    # Top-down plot
    site_patch = MplPolygon(site_local, closed=True, edgecolor="black", facecolor="none",
                             linewidth=2.0, zorder=2)
    ax_top.add_patch(site_patch)

    cmap = plt.cm.viridis
    for i, mass in enumerate(top_masses):
        coords_wgs = mass["geometry"]["coordinates"][0]
        coords_local = latlon_to_local(coords_wgs, centroid_lat, centroid_lon)
        norm_fa = (floor_areas[i] - fa_min) / fa_range
        color = cmap(0.2 + 0.7 * norm_fa)
        patch = MplPolygon(coords_local, closed=True, edgecolor=color,
                           facecolor=color, alpha=0.4, linewidth=1.0, zorder=3)
        ax_top.add_patch(patch)

    ax_top.set_aspect("equal")
    margin = 5.0
    ax_top.set_xlim(site_local[:, 0].min() - margin, site_local[:, 0].max() + margin)
    ax_top.set_ylim(site_local[:, 1].min() - margin, site_local[:, 1].max() + margin)
    ax_top.set_title(f"{label}\nTop-down (top {top_n} by floor_area)", fontsize=10)
    ax_top.set_xlabel("x (m)")
    ax_top.set_ylabel("y (m)")
    ax_top.grid(True, alpha=0.3)

    # 3D iso plot
    # Site footprint (z=0)
    site_z = np.column_stack([site_local, np.zeros(len(site_local))])
    site_poly3d = Poly3DCollection([site_z], facecolors="lightgray", edgecolor="black",
                                    linewidth=1.5, alpha=0.3, zorder=1)
    ax_3d.add_collection3d(site_poly3d)

    max_h = 0.0
    for i, mass in enumerate(top_masses):
        coords_wgs = mass["geometry"]["coordinates"][0]
        coords_local = latlon_to_local(coords_wgs, centroid_lat, centroid_lon)
        height = mass["properties"].get("height", 10.0)
        max_h = max(max_h, height)

        # Lower mass (footprint extruded)
        norm_fa = (floor_areas[i] - fa_min) / fa_range
        color = cmap(0.2 + 0.7 * norm_fa)

        bot = np.column_stack([coords_local, np.zeros(len(coords_local))])
        top = np.column_stack([coords_local, np.full(len(coords_local), height)])

        # Top face
        ax_3d.add_collection3d(Poly3DCollection([top], facecolors=color, edgecolor="white",
                                                 linewidth=0.3, alpha=0.7, zorder=3))
        # Side faces (quads between bot and top)
        for j in range(len(coords_local) - 1):
            quad = [bot[j], bot[j + 1], top[j + 1], top[j]]
            ax_3d.add_collection3d(Poly3DCollection([quad], facecolors=color, edgecolor="white",
                                                     linewidth=0.2, alpha=0.6, zorder=2))

        # Step-back upper if exists
        upper = mass["properties"].get("upper_geometry")
        if upper:
            upper_coords_wgs = upper["coordinates"][0]
            upper_local = latlon_to_local(upper_coords_wgs, centroid_lat, centroid_lon)
            step_floor = mass["properties"].get("step_floor", 0)
            floor_h = mass["properties"].get("floor_height", 3.0)
            lower_h = step_floor * floor_h

            up_bot = np.column_stack([upper_local, np.full(len(upper_local), lower_h)])
            up_top = np.column_stack([upper_local, np.full(len(upper_local), height)])
            ax_3d.add_collection3d(Poly3DCollection([up_top], facecolors=color, edgecolor="white",
                                                     linewidth=0.3, alpha=0.85, zorder=4))
            for j in range(len(upper_local) - 1):
                quad = [up_bot[j], up_bot[j + 1], up_top[j + 1], up_top[j]]
                ax_3d.add_collection3d(Poly3DCollection([quad], facecolors=color, edgecolor="white",
                                                         linewidth=0.2, alpha=0.75, zorder=3))

    margin3d = 5.0
    ax_3d.set_xlim(site_local[:, 0].min() - margin3d, site_local[:, 0].max() + margin3d)
    ax_3d.set_ylim(site_local[:, 1].min() - margin3d, site_local[:, 1].max() + margin3d)
    ax_3d.set_zlim(0, max_h * 1.2 if max_h > 0 else 30)
    ax_3d.set_title(f"3D iso (avg floor={np.mean(floor_areas):.0f} day={np.mean(daylights):.1f}, "
                    f"BCR<={bcr_lim:.0f} FAR<={far_lim:.0f} H<={h_lim:.0f})", fontsize=9)
    ax_3d.set_xlabel("x (m)", fontsize=8)
    ax_3d.set_ylabel("y (m)", fontsize=8)
    ax_3d.set_zlabel("z (m)", fontsize=8)
    ax_3d.view_init(elev=25, azim=45)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True,
                        help="dir containing ppo_*_<site>.geojson files")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--tag", type=str, default="v1")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    site_keys = ["gangnam_yeoksam_677", "bundang_test", "chuncheon_test"]
    paths = [in_dir / f"ppo_{args.tag}_{sk}.geojson" for sk in site_keys]

    fig = plt.figure(figsize=(20, 11))
    for col, sk in enumerate(site_keys):
        path = in_dir / f"ppo_{args.tag}_{sk}.geojson"
        if not path.exists():
            print(f"  SKIP missing: {path}")
            continue
        fc = load_site_geojson(path)
        ax_top = fig.add_subplot(2, 3, col + 1)
        ax_3d = fig.add_subplot(2, 3, col + 4, projection="3d")
        render_site_panel(ax_top, ax_3d, fc, top_n=args.top_n)

    fig.suptitle(f"PPO {args.tag} masses — top {args.top_n} per site (sorted by floor_area)",
                 fontsize=13, y=0.995)
    fig.tight_layout()
    out = Path(args.output)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out}")


if __name__ == "__main__":
    main()
