"""Pick best recons (recon_verts/src_verts ratio close to 1) and render side-by-side.

Source on left, recon on right per mesh, 6 rows x 2 cols per dataset.
Compares v1 (LVIS birdhouse, blue) vs v3 (Sketchfab arch <30k, purple).
"""

from __future__ import annotations

import argparse
import json
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
    ax.set_title(title, fontsize=7)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax.view_init(elev=20, azim=-60)


def pick_best(results, n=6):
    scored = []
    for r in results:
        sv = r["src_verts"]
        rv = r["recon_verts"]
        if rv == 0 or sv == 0:
            continue
        ratio = min(rv, sv) / max(rv, sv)
        scored.append((ratio, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:n]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-results", type=str, required=True)
    parser.add_argument("--v3-results", type=str, required=True)
    parser.add_argument("--filter-v3", type=str, required=True)
    parser.add_argument("--n", type=int, default=6)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    with open(args.filter_v3, encoding="utf-8") as f:
        v3_meta = json.load(f)
    uid_to_name = {s["uid"]: s.get("name", "") for s in v3_meta["selected"]}

    with open(args.v1_results, encoding="utf-8") as f:
        v1_results = json.load(f)
    with open(args.v3_results, encoding="utf-8") as f:
        v3_results = json.load(f)

    v1_best = pick_best(v1_results, args.n)
    v3_best = pick_best(v3_results, args.n)

    n = args.n
    fig = plt.figure(figsize=(3.5 * n, 11))

    for i, r in enumerate(v1_best):
        ax = fig.add_subplot(4, n, i + 1, projection="3d")
        m = trimesh.load(r["source_path"], force="mesh")
        render_mesh(ax, m, "#42a5f5",
                    f"v1 src #{i}\nbirdhouse/tower\n{r['src_verts']}v")
        ax = fig.add_subplot(4, n, i + 1 + n, projection="3d")
        m = trimesh.load(r["recon_path"], force="mesh")
        render_mesh(ax, m, "#1976d2",
                    f"v1 recon #{i}\n{r['recon_verts']}v")

    for i, r in enumerate(v3_best):
        nm = uid_to_name.get(r["uid"], "")[:25]
        ax = fig.add_subplot(4, n, i + 1 + 2 * n, projection="3d")
        m = trimesh.load(r["source_path"], force="mesh")
        render_mesh(ax, m, "#ab47bc",
                    f"v3 src #{i}\n{nm}\n{r['src_verts']}v")
        ax = fig.add_subplot(4, n, i + 1 + 3 * n, projection="3d")
        m = trimesh.load(r["recon_path"], force="mesh")
        render_mesh(ax, m, "#7b1fa2",
                    f"v3 recon #{i}\n{r['recon_verts']}v")

    fig.suptitle(
        f"BEST {args.n} (recon/src vert ratio): v1 LVIS birdhouse/tower vs v3 Sketchfab architecture (<30k verts)\n"
        f"VecSetX 424M pretrained AE, marching cubes resolution 128",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(args.out, dpi=110, bbox_inches="tight")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
