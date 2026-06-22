"""Visualize source vs SDF-reconstructed mesh side by side."""

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
    verts = mesh.vertices
    faces = mesh.faces
    triangles = verts[faces]
    pc = Poly3DCollection(triangles, alpha=0.85, facecolor=color,
                          edgecolor="white", linewidth=0.15)
    ax.add_collection3d(pc)

    bb_min = verts.min(0)
    bb_max = verts.max(0)
    span = (bb_max - bb_min).max() / 2
    ctr = (bb_min + bb_max) / 2
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(ctr[2] - span, ctr[2] + span)
    ax.set_box_aspect([1, 1, 1])
    ax.set_title(f"{title}\n{len(verts)} verts, {len(faces)} faces", fontsize=11)
    ax.view_init(elev=20, azim=35)
    ax.grid(True, alpha=0.3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--recon", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    src = trimesh.load(args.source)
    rec = trimesh.load(args.recon)

    fig = plt.figure(figsize=(14, 7))
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    render_mesh(ax1, src, color="#22c55e", title="Source mass (extruded box)")
    render_mesh(ax2, rec, color="#a855f7", title="DeepSDF reconstruction (marching cubes)")
    fig.suptitle("Phase 3 C1 SDF — single mass overfit (1500 iter, 1.8s on B200)",
                 fontsize=13, y=1.0)
    fig.tight_layout()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
