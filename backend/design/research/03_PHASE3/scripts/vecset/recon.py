"""F6 — VecSetX pretrained AE reconstruction on Objaverse meshes.

Loads pretrained `point_vec1024x32_dim1024_depth24_nb` AE → encodes Objaverse mesh
surface → decodes SDF on grid → marching cubes → output mesh.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import types
from pathlib import Path

# ── Flash-attn stub (PyTorch native fallback) ──
# B200 + nightly env can't easily build flash-attn; substitute with native SDPA.
import torch as _torch_for_stub

if 'flash_attn' not in sys.modules:
    _fa = types.ModuleType('flash_attn')

    def _flash_attn_kvpacked_func(q, kv, window_size=(-1, -1), **kwargs):
        # q: (B, Nq, h, d), kv: (B, Nk, 2, h, d)
        k, v = kv.unbind(dim=2)
        # transpose to (B, h, N, d) for SDPA
        q_ = q.transpose(1, 2)
        k_ = k.transpose(1, 2)
        v_ = v.transpose(1, 2)
        out = _torch_for_stub.nn.functional.scaled_dot_product_attention(q_, k_, v_)
        return out.transpose(1, 2)  # back to (B, Nq, h, d)

    _fa.flash_attn_kvpacked_func = _flash_attn_kvpacked_func
    sys.modules['flash_attn'] = _fa

import numpy as np
import torch
import trimesh
import mcubes


def load_model(vecset_dir: Path, model_name: str, ckpt_path: Path, pc_size: int = 8192,
               device: str = "cuda"):
    sys.path.insert(0, str(vecset_dir / "vecset"))
    from models import autoencoder  # noqa: E402

    print(f"  Building model {model_name} (pc_size={pc_size})...")
    model = autoencoder.__dict__[model_name](pc_size=pc_size)
    print(f"  Loading checkpoint {ckpt_path}...")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state = ckpt.get("model", ckpt)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print(f"  WARN missing keys: {len(missing)} (first 3: {missing[:3]})")
    if unexpected:
        print(f"  WARN unexpected keys: {len(unexpected)} (first 3: {unexpected[:3]})")
    model.eval().to(device)
    print(f"  param count: {sum(p.numel() for p in model.parameters())/1e6:.1f}M")
    return model


def normalize_surface(verts: np.ndarray) -> np.ndarray:
    ctr = (verts.max(0) + verts.min(0)) / 2.0
    verts = verts - ctr
    dist = np.linalg.norm(verts, axis=1)
    if dist.max() < 1e-6:
        return verts
    return (verts / dist.max()) * 0.999


def reconstruct(model, glb_path: Path, pc_size: int, resolution: int, device: str = "cuda"):
    m = trimesh.load(glb_path, force="mesh")
    if not hasattr(m, "vertices") or len(m.vertices) < 10:
        return None, None

    # Sample N surface points (use mesh.sample for even coverage)
    surface_pts, _ = trimesh.sample.sample_surface(m, max(pc_size * 2, 16384))
    surface_pts = np.asarray(surface_pts, dtype=np.float32)
    surface_pts = normalize_surface(surface_pts)
    if len(surface_pts) >= pc_size:
        ind = np.random.default_rng().choice(len(surface_pts), pc_size, replace=False)
    else:
        ind = np.random.default_rng().choice(len(surface_pts), pc_size, replace=True)
    surface_pts = surface_pts[ind]

    surface_t = torch.from_numpy(surface_pts).to(device).unsqueeze(0)  # (1, N, 3)

    # Build grid for SDF query
    g = np.linspace(-1, 1, resolution + 1, dtype=np.float32)
    xv, yv, zv = np.meshgrid(g, g, g, indexing="ij")
    grid = np.stack([xv, yv, zv], axis=-1).reshape(-1, 3)
    grid_t = torch.from_numpy(grid).to(device).unsqueeze(0)  # (1, M, 3)

    with torch.no_grad():
        out = model(surface_t, grid_t)
        if isinstance(out, dict):
            sdf = out.get("o", out.get("sdf", None))
        else:
            sdf = out
        sdf = sdf[0].view(resolution + 1, resolution + 1, resolution + 1)
        # match infer.py: permute(1, 0, 2)
        volume = sdf.permute(1, 0, 2).cpu().numpy()

    try:
        verts, faces = mcubes.marching_cubes(volume, 0.0)
        if len(verts) == 0:
            return None, None
        gap = 2.0 / resolution
        verts = verts * gap - 1.0
        recon = trimesh.Trimesh(vertices=verts, faces=faces)
        return recon, surface_pts
    except Exception as e:
        print(f"    marching_cubes err: {e}")
        return None, surface_pts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vecset-dir", type=str, required=True)
    parser.add_argument("--model", type=str, default="point_vec1024x32_dim1024_depth24_nb")
    parser.add_argument("--ckpt", type=str, required=True)
    parser.add_argument("--filter-json", type=str, required=True)
    parser.add_argument("--n", type=int, default=9)
    parser.add_argument("--pc-size", type=int, default=8192)
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = load_model(Path(args.vecset_dir), args.model, Path(args.ckpt), pc_size=args.pc_size)

    with open(args.filter_json) as f:
        meta = json.load(f)
    items = [s for s in meta["selected"] if s.get("glb_path")][:args.n]
    print(f"Reconstructing {len(items)} meshes...")

    results = []
    t0 = time.time()
    for i, s in enumerate(items):
        glb = s["glb_path"]
        print(f"  [{i+1}/{len(items)}] {Path(glb).stem[:8]}... ({s['category']})")
        recon, surface = reconstruct(model, Path(glb), args.pc_size, args.resolution)
        if recon is None:
            print(f"    SKIP (no recon)")
            continue
        # Save source + recon
        src_obj = out_dir / f"{i:02d}_source.obj"
        src_m = trimesh.load(glb, force="mesh")
        src_m.vertices = normalize_surface(np.asarray(src_m.vertices, dtype=np.float32))
        src_m.export(src_obj)
        recon_obj = out_dir / f"{i:02d}_recon.obj"
        recon.export(recon_obj)
        results.append({
            "idx": i,
            "uid": s["uid"],
            "category": s["category"],
            "src_verts": int(len(src_m.vertices)),
            "recon_verts": int(len(recon.vertices)),
            "recon_faces": int(len(recon.faces)),
            "source_path": str(src_obj),
            "recon_path": str(recon_obj),
        })
        print(f"    src verts {len(src_m.vertices)} → recon verts {len(recon.vertices)}")

    elapsed = time.time() - t0
    print(f"DONE {len(results)}/{len(items)} in {elapsed:.1f}s")
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
