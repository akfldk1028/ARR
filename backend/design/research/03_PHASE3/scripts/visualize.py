"""
C4 시각화 — PPO 결과를 두 가지 형식으로 export.

1. matplotlib Pareto plot (PNG): PPO N samples vs SSIEA exp001 baseline + exp003 repair
   per 3 sites — 9-panel figure showing floor_area vs daylight scatter.
2. GeoJSON FeatureCollection per site — for ARR Frontend Cesium 3D loading.

Usage:
    PYTHONPATH=. python design/research/03_PHASE3/scripts/visualize.py \\
        --model /NHNHOME/.../outputs/ppo_v1.zip --tag v1 --n-samples 32
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
from stable_baselines3 import PPO

from mass_env import SITE_POOL, _build_site_context, _action_to_gene
from design.engine.objects import Design
from design.services.mass_evaluator import evaluate_designs
from design.services.mass_renderer import design_to_geojson


SITE_LABELS = {
    "gangnam_yeoksam_677": "강남 역삼 677 (일반상업, BCR80% FAR1300% H50m)",
    "bundang_test": "분당 (2종 일반주거, BCR60% FAR250% H25m)",
    "chuncheon_test": "춘천 (1종 일반주거, BCR60% FAR200% H20m)",
}


def sample_ppo(model: PPO, ctx: dict, n_samples: int, enable_repair: bool):
    obs = np.array([
        ctx["area_m2"] / 2000.0,
        ctx["bcr_limit"] / 100.0,
        ctx["far_limit"] / 2000.0,
        ctx["height_limit"] / 60.0,
        1.0,
    ], dtype=np.float32)
    obs_batch = np.tile(obs, (n_samples, 1))
    actions, _ = model.predict(obs_batch, deterministic=False)
    designs = []
    for i, a in enumerate(actions):
        d = Design(_id=i, des_num=i, gen_num=0)
        d.inputs = _action_to_gene(np.asarray(a, dtype=np.float32), ctx["inputs_def"])
        designs.append(d)
    outs = evaluate_designs(
        designs, ctx["polygon_wgs84"], ctx["area_m2"],
        outputs_def=ctx["outputs_def"],
        building_type="공동주택",
        algorithm="additive",
        enable_repair=enable_repair,
    )
    for d, o in zip(designs, outs):
        d.set_outputs(o, ctx["outputs_def"], penalty_mode="normalized")
    return designs


def load_ssiea_data(exp_data_path: Path, site_key: str) -> dict | None:
    """Load SSIEA rep summary for one site from exp001/exp003 JSON."""
    if not exp_data_path.exists():
        return None
    with open(exp_data_path, encoding="utf-8") as f:
        data = json.load(f)
    for site in data.get("sites", []):
        if site.get("site") == site_key:
            return {
                "hv": site.get("hypervolume_mean", 0),
                "feasible_pct": site.get("feasible_pct_mean", 0),
                "avg_objectives": site.get("rep_details", [{}])[0].get("avg_objectives", []),
            }
    return None


def make_pareto_plot(model: PPO, n_samples: int, enable_repair: bool,
                     experiments_dir: Path, output_path: Path, tag: str):
    """3 부지 × 3 행 (PPO scatter, SSIEA exp001, SSIEA exp003) Pareto plot."""
    site_keys = list(SITE_POOL.keys())
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    for ax, site_key in zip(axes, site_keys):
        ctx = _build_site_context(site_key)
        designs = sample_ppo(model, ctx, n_samples, enable_repair)

        feas = [d for d in designs if d.feasible and d.penalty == 0 and d.objectives]
        infeas = [d for d in designs if not (d.feasible and d.penalty == 0)]

        if feas:
            x_feas = [d.objectives[0] for d in feas]
            y_feas = [d.objectives[1] for d in feas]
            ax.scatter(x_feas, y_feas, c="#2563eb", s=60, alpha=0.75,
                       edgecolors="white", linewidth=0.7, zorder=3,
                       label=f"PPO {tag} (feasible, n={len(feas)})")
        if infeas:
            x_inf = [d.objectives[0] if d.objectives else 0 for d in infeas]
            y_inf = [d.objectives[1] if len(d.objectives) > 1 else 0 for d in infeas]
            ax.scatter(x_inf, y_inf, c="#dc2626", s=40, alpha=0.4,
                       marker="x", zorder=2,
                       label=f"PPO {tag} (infeasible, n={len(infeas)})")

        # SSIEA exp001 (no repair) + exp003 (with repair) summary points
        exp001 = load_ssiea_data(experiments_dir / "exp001_baseline_data.json", site_key)
        exp003 = load_ssiea_data(experiments_dir / "exp003_data.json", site_key)
        if exp001 and exp001.get("avg_objectives"):
            x, y = exp001["avg_objectives"][:2]
            ax.scatter([x], [y], c="#fbbf24", s=200, marker="*",
                       edgecolors="black", linewidth=1.2, zorder=4,
                       label=f"SSIEA exp001 (no repair, feas {exp001['feasible_pct']:.1f}%)")
        if exp003 and exp003.get("avg_objectives"):
            x, y = exp003["avg_objectives"][:2]
            ax.scatter([x], [y], c="#16a34a", s=200, marker="*",
                       edgecolors="black", linewidth=1.2, zorder=4,
                       label=f"SSIEA exp003 (+repair, feas {exp003['feasible_pct']:.1f}%)")

        ax.set_xlabel("floor_area (m²) — Maximize →", fontsize=10)
        ax.set_ylabel("daylight_score — Maximize ↑", fontsize=10)
        ax.set_title(SITE_LABELS.get(site_key, site_key), fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")

    fig.suptitle(f"PPO {tag} (zero-shot, n={n_samples}) vs SSIEA baseline — 3 sites",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Pareto plot → {output_path}")


def make_geojson_export(model: PPO, n_samples: int, enable_repair: bool,
                        out_dir: Path, tag: str) -> dict:
    """Export PPO 매스 32개 × 3 부지 → GeoJSON FeatureCollection per site."""
    summary = {"tag": tag, "n_samples": n_samples, "sites": {}}

    for site_key in SITE_POOL.keys():
        ctx = _build_site_context(site_key)
        designs = sample_ppo(model, ctx, n_samples, enable_repair)

        features = []
        for i, d in enumerate(designs):
            try:
                feat = design_to_geojson(
                    d.inputs, ctx["polygon_wgs84"], ctx["area_m2"],
                    building_type="공동주택", algorithm="additive",
                )
            except Exception as e:
                feat = None
            if feat is None:
                continue
            feat["properties"]["sample_id"] = i
            feat["properties"]["feasible"] = bool(d.feasible)
            feat["properties"]["penalty"] = round(float(d.penalty), 4)
            if d.objectives:
                feat["properties"]["objectives"] = [round(float(x), 2) for x in d.objectives]
            features.append(feat)

        # site polygon as separate feature for context
        from shapely.geometry import mapping
        site_feat = {
            "type": "Feature",
            "geometry": mapping(ctx["polygon_wgs84"]),
            "properties": {
                "kind": "site",
                "site_key": site_key,
                "label": SITE_LABELS.get(site_key, site_key),
                "area_m2": round(ctx["area_m2"], 2),
                "bcr_limit": ctx["bcr_limit"],
                "far_limit": ctx["far_limit"],
                "height_limit": ctx["height_limit"],
            },
        }

        fc = {
            "type": "FeatureCollection",
            "features": [site_feat] + features,
            "metadata": {
                "site_key": site_key,
                "model_tag": tag,
                "n_designs": len(features),
                "n_feasible": sum(1 for f in features if f["properties"].get("feasible")),
            },
        }
        out_path = out_dir / f"ppo_{tag}_{site_key}.geojson"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        summary["sites"][site_key] = {
            "n_designs": len(features),
            "n_feasible": fc["metadata"]["n_feasible"],
            "path": str(out_path),
        }
        print(f"  GeoJSON {site_key} → {out_path} ({len(features)} designs)")

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--n-samples", type=int, default=32)
    parser.add_argument("--tag", type=str, default="v1")
    parser.add_argument("--workspace", type=str,
                        default="/NHNHOME/WORKSPACE/0526040060_A/DHKim/arr-mass")
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--experiments-dir", type=str,
                        default="design/research/05_EXPERIMENTS")
    args = parser.parse_args()

    enable_repair = not args.no_repair
    workspace = Path(args.workspace)
    out_dir = workspace / "outputs" / f"viz_{args.tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== visualize PPO {args.tag} ===")
    print(f"  model: {args.model}")
    print(f"  out dir: {out_dir}")

    model = PPO.load(args.model)

    # 1. Pareto plot
    pareto_path = out_dir / f"ppo_{args.tag}_pareto.png"
    make_pareto_plot(model, args.n_samples, enable_repair,
                     Path(args.experiments_dir), pareto_path, args.tag)

    # 2. GeoJSON export
    summary = make_geojson_export(model, args.n_samples, enable_repair,
                                  out_dir, args.tag)
    summary_path = out_dir / f"ppo_{args.tag}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n=== done — see {out_dir} ===")


if __name__ == "__main__":
    main()
