"""Visualize a grid of SDF-sampled meshes."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh


def render_mesh(ax, mesh: trimesh.Trimesh, color: str = "#3b82f6", title: str = ""):
    if len(mesh.vertices) == 0:
        ax.text(0.5, 0.5, "empty", transform=ax.transAxes, ha="center")
        ax.set_title(title, fontsize=8)
        return
    verts = mesh.vertices
    faces = mesh.faces
    triangles = verts[faces]
    pc = Poly3DCollection(triangles, alpha=0.85, facecolor=color,
                          edgecolor="white", linewidth=0.05)
    ax.add_collection3d(pc)

    bb_min = verts.min(0)
    bb_max = verts.max(0)
    span = max((bb_max - bb_min).max() / 2, 0.1)
    ctr = (bb_min + bb_max) / 2
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(ctr[2] - span, ctr[2] + span)
    ax.set_box_aspect([1, 1, 1])
    ax.set_title(title, fontsize=9)
    ax.view_init(elev=22, azim=35)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True,
                        help="dir with sample_NNN.obj files")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--title", type=str, default="DeepSDF latent sampling")
    parser.add_argument("--cmap", type=str, default="plasma")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    obj_paths = sorted(in_dir.glob("sample_*.obj"))
    if not obj_paths:
        print(f"  no sample_*.obj in {in_dir}")
        return

    n = min(args.rows * args.cols, len(obj_paths))
    fig = plt.figure(figsize=(args.cols * 3.0, args.rows * 3.0))
    cmap = plt.get_cmap(args.cmap)
    for i in range(n):
        ax = fig.add_subplot(args.rows, args.cols, i + 1, projection="3d")
        try:
            mesh = trimesh.load(obj_paths[i])
            color = cmap(0.2 + 0.7 * (i / max(n - 1, 1)))
            color = "#%02x%02x%02x" % (int(color[0]*255), int(color[1]*255), int(color[2]*255))
            render_mesh(ax, mesh, color=color,
                        title=f"#{i:03d} ({len(mesh.vertices)} v)")
        except Exception as e:
            ax.text(0.5, 0.5, f"err: {e}", transform=ax.transAxes, ha="center", fontsize=7)

    fig.suptitle(args.title, fontsize=14, y=0.995)
    fig.tight_layout()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out}")


if __name__ == "__main__":
    main()
