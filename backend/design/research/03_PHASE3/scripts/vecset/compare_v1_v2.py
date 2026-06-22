"""Compare v1 (birdhouse/tower, 192) vs v2 (architecture category, 1000) reconstructions.

Renders 6 source/recon pairs from each dataset side-by-side with mesh name + verts.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def render_mesh(ax, mesh, color, title=""):
    if mesh is None or len(mesh.vertices) == 0:
        ax.set_title(title + "\n(empty)", fontsize=8)
        ax.axis("off")
        return
    v = np.asarray(mesh.vertices)
    f = np.asarray(mesh.faces)
    if len(f) > 8000:
        idx = np.random.default_rng(0).choice(len(f), 8000, replace=False)
        f = f[idx]
    coll = Poly3DCollection(v[f], alpha=0.85, facecolor=color, edgecolor="none")
    ax.add_collection3d(coll)
    mn, mx = v.min(0), v.max(0)
    ctr = (mn + mx) / 2
    sz = (mx - mn).max() / 2 * 1.05
    ax.set_xlim(ctr[0] - sz, ctr[0] + sz)
    ax.set_ylim(ctr[1] - sz, ctr[1] + sz)
    ax.set_zlim(ctr[2] - sz, ctr[2] + sz)
    ax.set_title(title, fontsize=8)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-dir", type=str, required=True,
                        help="dir with v1 recons (e.g. trackB_vecset/recon_v1/)")
    parser.add_argument("--v2-dir", type=str, required=True,
                        help="dir with v2 recons (e.g. trackB_vecset/recon_v2/)")
    parser.add_argument("--filter-v2", type=str, required=True,
                        help="filter_v2.json (for names)")
    parser.add_argument("--n", type=int, default=6)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    with open(args.filter_v2, encoding="utf-8") as f:
        v2_meta = json.load(f)
    uid_to_name = {s["uid"]: s.get("name", "") for s in v2_meta["selected"]}

    v1_pairs = []
    for src in sorted(Path(args.v1_dir).glob("*_source.obj"))[:args.n]:
        idx = src.stem.split("_")[0]
        rec = src.parent / f"{idx}_recon.obj"
        if rec.exists():
            v1_pairs.append((src, rec, "birdhouse/tower"))

    v2_pairs = []
    v2_results = Path(args.v2_dir) / "results.json"
    if v2_results.exists():
        with open(v2_results, encoding="utf-8") as f:
            v2_data = json.load(f)
        # Pick interesting (non-failed) results
        for r in v2_data[:args.n]:
            src = Path(r["source_path"])
            rec = Path(r["recon_path"])
            if src.exists() and rec.exists():
                v2_pairs.append((src, rec, uid_to_name.get(r["uid"], "")[:30]))

    n = max(len(v1_pairs), len(v2_pairs))
    fig = plt.figure(figsize=(3 * n, 12))

    for i, (src, rec, name) in enumerate(v1_pairs):
        ax = fig.add_subplot(4, n, i + 1, projection="3d")
        m = trimesh.load(src, force="mesh")
        render_mesh(ax, m, "#42a5f5",
                    f"v1 src #{i}\n{name}\n{len(m.vertices)}v")
        ax = fig.add_subplot(4, n, i + 1 + n, projection="3d")
        m = trimesh.load(rec, force="mesh")
        render_mesh(ax, m, "#1976d2",
                    f"v1 recon #{i}\n{len(m.vertices)}v")

    for i, (src, rec, name) in enumerate(v2_pairs):
        ax = fig.add_subplot(4, n, i + 1 + 2 * n, projection="3d")
        m = trimesh.load(src, force="mesh")
        render_mesh(ax, m, "#ab47bc",
                    f"v2 src #{i}\n{name}\n{len(m.vertices)}v")
        ax = fig.add_subplot(4, n, i + 1 + 3 * n, projection="3d")
        m = trimesh.load(rec, force="mesh")
        render_mesh(ax, m, "#7b1fa2",
                    f"v2 recon #{i}\n{len(m.vertices)}v")

    fig.suptitle(
        f"v1 (LVIS birdhouse/tower, 192 meshes) vs v2 (Sketchfab architecture, 1000 meshes)\n"
        f"Both reconstructed by VecSetX 424M pretrained AE",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(args.out, dpi=110, bbox_inches="tight")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
