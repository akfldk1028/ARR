"""
C1 SDF Phase 3 — End-to-end pipeline: mass → mesh → SDF samples → DeepSDF train → reconstruct.

Stages:
  prep      : 박스 매스 N개 → trimesh extrusion → mesh_to_sdf 샘플링 → npz 저장
  recon-one : 단일 매스 SDF auto-decoder overfit → marching cubes 복원 → mesh 비교
  train     : 100 매스 DeepSDF 학습 (latent codes + decoder)
  sample    : 학습된 latent space에서 새 latent → mesh 생성

Usage:
    python sdf_pipeline.py prep --n-shapes 100 --output /path/data.npz
    python sdf_pipeline.py recon-one --output /path/recon
    python sdf_pipeline.py train --data /path/data.npz --output /path/model
    python sdf_pipeline.py sample --model /path/model --n 16 --output /path/samples
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ─────────────────────────────────────────────────────────
# Stage 1: mass → mesh
# ─────────────────────────────────────────────────────────

def mass_to_trimesh(footprint_xy: np.ndarray, height: float,
                    upper_xy: np.ndarray | None = None,
                    lower_height: float = 0.0):
    """Build a 3D mesh from polygon(s) + heights using trimesh extrusion."""
    import trimesh
    from shapely.geometry import Polygon as ShPoly

    poly = ShPoly(footprint_xy)
    if not poly.is_valid or poly.area < 0.1:
        return None

    if upper_xy is not None and len(upper_xy) >= 3:
        # Lower (footprint × lower_height) + Upper (upper_xy × (height - lower_height))
        lower_mesh = trimesh.creation.extrude_polygon(poly, lower_height)
        upper_poly = ShPoly(upper_xy)
        if upper_poly.is_valid and upper_poly.area > 0.1:
            upper_mesh = trimesh.creation.extrude_polygon(upper_poly, height - lower_height)
            upper_mesh.apply_translation([0, 0, lower_height])
            mesh = trimesh.util.concatenate([lower_mesh, upper_mesh])
        else:
            mesh = lower_mesh
    else:
        mesh = trimesh.creation.extrude_polygon(poly, height)

    # Center + normalize to unit sphere (DeepSDF convention)
    centroid = mesh.centroid
    mesh.apply_translation(-centroid)
    radius = float(np.linalg.norm(mesh.vertices, axis=1).max())
    if radius > 0:
        mesh.apply_scale(1.0 / radius)
    return mesh


def generate_mass_meshes(n_shapes: int, seed: int = 42) -> list:
    """Build N mass meshes from random additive (box-stacking) gene vectors."""
    from mass_env import SITE_POOL, _build_site_context, _action_to_gene
    from design.engine.objects import Design
    from design.services.mass_evaluator import evaluate_designs, BUILDERS
    from design.services.site_geometry import wgs84_to_utm

    rng = np.random.default_rng(seed)
    site_keys = list(SITE_POOL.keys())
    contexts = {k: _build_site_context(k) for k in site_keys}

    meshes = []
    metadata = []
    attempts = 0
    while len(meshes) < n_shapes and attempts < n_shapes * 5:
        attempts += 1
        site_key = rng.choice(site_keys)
        ctx = contexts[site_key]
        action = rng.uniform(-1, 1, size=29).astype(np.float32)

        d = Design(_id=attempts, des_num=0, gen_num=0)
        d.inputs = _action_to_gene(action, ctx["inputs_def"])

        try:
            outs = evaluate_designs(
                [d], ctx["polygon_wgs84"], ctx["area_m2"],
                outputs_def=ctx["outputs_def"],
                building_type="공동주택",
                algorithm="additive",
                enable_repair=True,
            )
            d.set_outputs(outs[0], ctx["outputs_def"], penalty_mode="normalized")
            if not d.feasible or d.penalty > 0.1:
                continue

            # Build UTM mass polygon directly
            site_utm = wgs84_to_utm(ctx["polygon_wgs84"])
            builder = BUILDERS["additive"]
            building_utm, _ = builder(d.inputs, site_utm)
            if building_utm is None or building_utm.is_empty:
                continue
            footprint_utm = building_utm.intersection(site_utm)
            if footprint_utm.is_empty or footprint_utm.area < 5.0:
                continue

            # Get exterior coords (handle MultiPolygon)
            from shapely.geometry import Polygon as ShPoly, MultiPolygon
            if isinstance(footprint_utm, MultiPolygon):
                footprint_utm = max(footprint_utm.geoms, key=lambda p: p.area)
            xy = np.array(footprint_utm.exterior.coords[:-1], dtype=np.float32)

            # Height + step-back
            num_floors = max(1, round(d.inputs[5][0]))
            floor_h = 3.0
            height = num_floors * floor_h

            upper_scale_val = max(0.5, min(1.0, d.inputs[7][0])) if len(d.inputs) > 7 else 1.0
            step_frac = max(0.3, min(0.8, d.inputs[8][0])) if len(d.inputs) > 8 else 1.0
            has_stepback = upper_scale_val < 0.98 and step_frac < 0.95

            upper_xy = None
            lower_h = 0.0
            if has_stepback:
                step_floor = max(1, round(num_floors * step_frac))
                lower_h = step_floor * floor_h
                from shapely.affinity import scale as sh_scale
                upper_poly = sh_scale(footprint_utm, xfact=upper_scale_val,
                                      yfact=upper_scale_val, origin="centroid")
                upper_poly = upper_poly.intersection(site_utm)
                if isinstance(upper_poly, MultiPolygon):
                    upper_poly = max(upper_poly.geoms, key=lambda p: p.area)
                if not upper_poly.is_empty and upper_poly.area > 1.0:
                    upper_xy = np.array(upper_poly.exterior.coords[:-1], dtype=np.float32)

            mesh = mass_to_trimesh(xy, height, upper_xy, lower_h)
            if mesh is None or len(mesh.vertices) < 8:
                continue

            meshes.append(mesh)
            metadata.append({
                "shape_id": len(meshes) - 1,
                "site_key": site_key,
                "height_m": float(height),
                "num_floors": num_floors,
                "footprint_area_m2": float(footprint_utm.area),
                "has_stepback": bool(has_stepback),
                "feasible": bool(d.feasible),
            })
        except Exception as e:
            continue

    return meshes, metadata


# ─────────────────────────────────────────────────────────
# Stage 2: mesh → SDF samples
# ─────────────────────────────────────────────────────────

def mesh_to_sdf_samples(mesh, n_samples: int = 100_000):
    """mesh_to_sdf surface sampling — DeepSDF style (75% near surface, 25% uniform)."""
    from mesh_to_sdf import sample_sdf_near_surface

    # 'sample' + 'normal' = CPU only (headless server compatible)
    points, sdf = sample_sdf_near_surface(
        mesh, number_of_points=n_samples,
        surface_point_method="sample",
        sign_method="normal",
    )
    return points.astype(np.float32), sdf.astype(np.float32)


def cmd_prep(args):
    print(f"=== prep: generating {args.n_shapes} masses + SDF samples ===")
    t0 = time.perf_counter()
    meshes, metadata = generate_mass_meshes(args.n_shapes)
    print(f"  {len(meshes)} feasible meshes in {time.perf_counter()-t0:.1f}s")

    all_points = []
    all_sdf = []
    all_shape_ids = []
    n_per = args.n_samples_per_shape

    for i, mesh in enumerate(meshes):
        try:
            pts, sd = mesh_to_sdf_samples(mesh, n_samples=n_per)
            if len(pts) < n_per // 2:
                print(f"  shape {i}: only {len(pts)} samples — skip")
                continue
            all_points.append(pts)
            all_sdf.append(sd)
            all_shape_ids.append(np.full(len(pts), i, dtype=np.int64))
            if (i + 1) % 10 == 0:
                print(f"  shape {i+1}/{len(meshes)}  ({len(pts)} samples)")
        except Exception as e:
            print(f"  shape {i}: error {e}")

    points = np.concatenate(all_points)
    sdfs = np.concatenate(all_sdf)
    shape_ids = np.concatenate(all_shape_ids)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, points=points, sdf=sdfs, shape_ids=shape_ids,
                         metadata=json.dumps(metadata, ensure_ascii=False))
    print(f"  saved {out} | {len(points):,} samples | {points.nbytes/1e6:.1f} MB")

    # Also save first mesh for recon-one
    if meshes:
        recon_path = out.parent / "first_mesh.obj"
        meshes[0].export(recon_path)
        print(f"  saved first_mesh.obj for recon-one")


# ─────────────────────────────────────────────────────────
# Stage 3: DeepSDF model
# ─────────────────────────────────────────────────────────

class DeepSDF(nn.Module):
    """Simplified DeepSDF auto-decoder (ICCV 2019)."""
    def __init__(self, latent_dim: int = 64, hidden_dim: int = 256, n_layers: int = 6):
        super().__init__()
        in_dim = latent_dim + 3
        layers = []
        for i in range(n_layers - 1):
            layers.append(nn.utils.weight_norm(nn.Linear(in_dim, hidden_dim)))
            layers.append(nn.ReLU(inplace=True))
            in_dim = hidden_dim
        layers.append(nn.utils.weight_norm(nn.Linear(hidden_dim, 1)))
        self.net = nn.Sequential(*layers)

    def forward(self, latent: torch.Tensor, xyz: torch.Tensor) -> torch.Tensor:
        h = torch.cat([latent, xyz], dim=-1)
        return self.net(h).squeeze(-1)


# ─────────────────────────────────────────────────────────
# Stage 4: train (single shape overfit OR multi-shape)
# ─────────────────────────────────────────────────────────

class SDFDataset(Dataset):
    def __init__(self, points, sdfs, shape_ids):
        self.points = torch.from_numpy(points)
        self.sdfs = torch.from_numpy(sdfs)
        self.shape_ids = torch.from_numpy(shape_ids)

    def __len__(self):
        return len(self.points)

    def __getitem__(self, idx):
        return self.points[idx], self.sdfs[idx], self.shape_ids[idx]


def cmd_train(args):
    print("=== train: DeepSDF auto-decoder ===")
    data = np.load(args.data, allow_pickle=True)
    points = data["points"]
    sdfs = data["sdf"]
    shape_ids = data["shape_ids"]
    n_shapes = int(shape_ids.max()) + 1
    print(f"  {len(points):,} samples, {n_shapes} shapes")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  device: {device}")

    decoder = DeepSDF(latent_dim=args.latent_dim, hidden_dim=args.hidden_dim,
                      n_layers=args.n_layers).to(device)
    latent_codes = nn.Embedding(n_shapes, args.latent_dim).to(device)
    nn.init.normal_(latent_codes.weight, mean=0.0, std=0.01)

    optim_decoder = torch.optim.Adam(decoder.parameters(), lr=args.lr_decoder)
    optim_latent = torch.optim.Adam(latent_codes.parameters(), lr=args.lr_latent)

    # All tensors GPU-resident. Manual indexing bypasses DataLoader.
    points_t = torch.from_numpy(points).to(device)
    sdfs_t = torch.from_numpy(sdfs).to(device)
    sids_t = torch.from_numpy(shape_ids).to(device)
    n_total = len(points_t)

    delta = 0.1  # SDF clamp threshold
    sigma2 = 1e-2  # latent regularization
    batch = args.batch_size

    decoder.train()
    latent_codes.train()
    t0 = time.perf_counter()
    for ep in range(args.epochs):
        perm = torch.randperm(n_total, device=device)
        ep_loss = 0.0
        n_batches = 0
        for i in range(0, n_total, batch):
            idx = perm[i:i + batch]
            pts = points_t[idx]
            gt = sdfs_t[idx].clamp(-delta, delta)
            sids = sids_t[idx]

            latent = latent_codes(sids)
            pred = decoder(latent, pts).clamp(-delta, delta)
            recon_loss = F.l1_loss(pred, gt)
            reg_loss = sigma2 * (latent.pow(2).sum(-1).mean())
            loss = recon_loss + reg_loss

            optim_decoder.zero_grad(set_to_none=True)
            optim_latent.zero_grad(set_to_none=True)
            loss.backward()
            optim_decoder.step()
            optim_latent.step()

            ep_loss += loss.detach()
            n_batches += 1

        avg_loss = (ep_loss / max(n_batches, 1)).item()
        elapsed = time.perf_counter() - t0
        if (ep + 1) % max(args.epochs // 20, 1) == 0 or ep == 0:
            print(f"  epoch {ep+1}/{args.epochs}  loss={avg_loss:.4f}  elapsed={elapsed:.1f}s", flush=True)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save({
        "decoder_state": decoder.state_dict(),
        "latent_codes": latent_codes.state_dict(),
        "latent_dim": args.latent_dim,
        "hidden_dim": args.hidden_dim,
        "n_layers": args.n_layers,
        "n_shapes": n_shapes,
    }, out_dir / "deepsdf.pt")
    print(f"  saved {out_dir / 'deepsdf.pt'} ({time.perf_counter()-t0:.1f}s)")


# ─────────────────────────────────────────────────────────
# Stage 5: reconstruct (marching cubes from SDF)
# ─────────────────────────────────────────────────────────

def reconstruct_mesh(decoder, latent_code, resolution: int = 128, device="cuda",
                     sdf_thresh: float = 0.0, batch_size: int = 64_000):
    """Sample SDF on a grid + marching cubes → mesh."""
    from skimage.measure import marching_cubes

    grid_size = resolution
    coords = np.linspace(-1.0, 1.0, grid_size, dtype=np.float32)
    xx, yy, zz = np.meshgrid(coords, coords, coords, indexing="ij")
    pts_np = np.stack([xx.ravel(), yy.ravel(), zz.ravel()], axis=-1)
    pts = torch.from_numpy(pts_np).to(device)
    latent_b = latent_code.unsqueeze(0).expand(pts.shape[0], -1)

    decoder.eval()
    sdf_vals = []
    with torch.no_grad():
        for i in range(0, len(pts), batch_size):
            sd = decoder(latent_b[i:i+batch_size], pts[i:i+batch_size])
            sdf_vals.append(sd.cpu().numpy())
    sdf_grid = np.concatenate(sdf_vals).reshape(grid_size, grid_size, grid_size)

    try:
        verts, faces, _, _ = marching_cubes(sdf_grid, level=sdf_thresh)
        # Map verts from [0, grid_size-1] to [-1, 1]
        verts = verts / (grid_size - 1) * 2 - 1
        import trimesh
        mesh = trimesh.Trimesh(vertices=verts, faces=faces)
        return mesh
    except Exception as e:
        return None


def cmd_recon_one(args):
    """Overfit single mesh — sanity check that SDF representation works."""
    print("=== recon-one: single mesh SDF overfit ===")
    import trimesh

    # Build 1 mesh
    meshes, metadata = generate_mass_meshes(1)
    if not meshes:
        print("  no feasible mesh — abort")
        return
    mesh = meshes[0]
    print(f"  source mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    # SDF samples
    print("  sampling SDF...")
    pts, sd = mesh_to_sdf_samples(mesh, n_samples=80_000)
    print(f"  {len(pts):,} samples, sdf range [{sd.min():.3f}, {sd.max():.3f}]")

    # Train tiny decoder + 1 latent
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    latent_dim = 64
    decoder = DeepSDF(latent_dim=latent_dim, hidden_dim=256, n_layers=6).to(device)
    latent = nn.Parameter(torch.randn(latent_dim, device=device) * 0.01)

    optim_dec = torch.optim.Adam(decoder.parameters(), lr=5e-4)
    optim_lat = torch.optim.Adam([latent], lr=1e-3)

    pts_t = torch.from_numpy(pts).to(device)
    sd_t = torch.from_numpy(sd).to(device).clamp(-0.1, 0.1)

    delta = 0.1
    n_iter = args.iters
    batch = 8192
    t0 = time.perf_counter()
    for it in range(n_iter):
        idx = torch.randint(0, len(pts_t), (batch,), device=device)
        p = pts_t[idx]
        s = sd_t[idx]
        lat_b = latent.unsqueeze(0).expand(batch, -1)
        pred = decoder(lat_b, p).clamp(-delta, delta)
        loss = F.l1_loss(pred, s)
        optim_dec.zero_grad(); optim_lat.zero_grad()
        loss.backward()
        optim_dec.step(); optim_lat.step()
        if (it + 1) % max(n_iter // 10, 1) == 0:
            print(f"  iter {it+1}/{n_iter}  loss={loss.item():.4f}  elapsed={time.perf_counter()-t0:.1f}s")

    # Reconstruct
    print("  reconstructing via marching cubes...")
    recon_mesh = reconstruct_mesh(decoder, latent, resolution=args.resolution, device=device)
    if recon_mesh is None:
        print("  marching cubes failed (no surface) — try lower sdf_thresh")
        return

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    mesh.export(out_dir / "source.obj")
    recon_mesh.export(out_dir / "recon.obj")
    print(f"  saved source.obj + recon.obj → {out_dir}")
    print(f"  source: {len(mesh.vertices)} verts | recon: {len(recon_mesh.vertices)} verts")


def cmd_sample(args):
    """Sample new latents + reconstruct meshes."""
    print("=== sample: latent space → new meshes ===")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(args.model + "/deepsdf.pt", map_location=device, weights_only=False)
    decoder = DeepSDF(latent_dim=ckpt["latent_dim"], hidden_dim=ckpt["hidden_dim"],
                      n_layers=ckpt["n_layers"]).to(device)
    decoder.load_state_dict(ckpt["decoder_state"])
    decoder.eval()

    latent_codes = nn.Embedding(ckpt["n_shapes"], ckpt["latent_dim"]).to(device)
    latent_codes.load_state_dict(ckpt["latent_codes"])

    # Sample strategy: interpolate between random pairs from learned latents
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    saved = 0
    for i in range(args.n):
        if args.mode == "interp":
            a = rng.integers(0, ckpt["n_shapes"])
            b = rng.integers(0, ckpt["n_shapes"])
            t = float(rng.uniform(0.2, 0.8))
            latent = (latent_codes.weight[a] * (1-t) + latent_codes.weight[b] * t).detach()
        elif args.mode == "noise":
            mean = latent_codes.weight.mean(0).detach()
            std = latent_codes.weight.std(0).detach()
            latent = mean + torch.randn_like(mean) * std * args.noise_scale
        else:  # random
            latent = torch.randn(ckpt["latent_dim"], device=device) * 0.1
        mesh = reconstruct_mesh(decoder, latent, resolution=args.resolution, device=device)
        if mesh is None:
            continue
        mesh.export(out_dir / f"sample_{i:03d}.obj")
        saved += 1
    print(f"  saved {saved}/{args.n} samples → {out_dir}")


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prep")
    p_prep.add_argument("--n-shapes", type=int, default=100)
    p_prep.add_argument("--n-samples-per-shape", type=int, default=80_000)
    p_prep.add_argument("--output", type=str, required=True)

    p_recon = sub.add_parser("recon-one")
    p_recon.add_argument("--iters", type=int, default=2000)
    p_recon.add_argument("--resolution", type=int, default=96)
    p_recon.add_argument("--output", type=str, required=True)

    p_train = sub.add_parser("train")
    p_train.add_argument("--data", type=str, required=True)
    p_train.add_argument("--output", type=str, required=True)
    p_train.add_argument("--epochs", type=int, default=200)
    p_train.add_argument("--batch-size", type=int, default=16384)
    p_train.add_argument("--latent-dim", type=int, default=64)
    p_train.add_argument("--hidden-dim", type=int, default=256)
    p_train.add_argument("--n-layers", type=int, default=6)
    p_train.add_argument("--lr-decoder", type=float, default=5e-4)
    p_train.add_argument("--lr-latent", type=float, default=1e-3)

    p_sample = sub.add_parser("sample")
    p_sample.add_argument("--model", type=str, required=True)
    p_sample.add_argument("--n", type=int, default=16)
    p_sample.add_argument("--mode", choices=["interp", "noise", "random"], default="interp")
    p_sample.add_argument("--noise-scale", type=float, default=0.5)
    p_sample.add_argument("--resolution", type=int, default=96)
    p_sample.add_argument("--seed", type=int, default=42)
    p_sample.add_argument("--output", type=str, required=True)

    args = parser.parse_args()

    if args.cmd == "prep":
        cmd_prep(args)
    elif args.cmd == "recon-one":
        cmd_recon_one(args)
    elif args.cmd == "train":
        cmd_train(args)
    elif args.cmd == "sample":
        cmd_sample(args)


if __name__ == "__main__":
    main()
