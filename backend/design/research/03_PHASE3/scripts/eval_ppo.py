"""
C4 DRL Bootstrap — PPO held-out evaluation.

Per site, sample N designs from learned policy (stochastic) → measure HV
and feasible % → compare to SSIEA baseline (exp001/exp003 data).

Usage:
    PYTHONPATH=. python design/research/03_PHASE3/scripts/eval_ppo.py \\
        --model /NHNHOME/.../outputs/ppo_v1.zip --n-samples 32 --tag v1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import numpy as np
from stable_baselines3 import PPO

from mass_env import MassEnv, SITE_POOL, _build_site_context, _action_to_gene
from design.engine.objects import Design
from design.services.mass_evaluator import evaluate_designs


def _eval_design_batch(actions: np.ndarray, ctx: dict, enable_repair: bool = True) -> list[Design]:
    """Apply actions → evaluate → return Design objects with set_outputs."""
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


def _measure_hv(designs: list[Design], outputs_def: list[dict]) -> float:
    """pymoo HV (negate Maximize, ref point from worst feasible)."""
    try:
        from pymoo.indicators.hv import HV
    except ImportError:
        return -1.0

    feas = [d for d in designs if d.feasible and d.penalty == 0 and d.objectives]
    if not feas:
        return 0.0

    n_obj = len(feas[0].objectives)
    # Goal=Maximize: pymoo HV uses minimization → negate
    F = np.array([[-d.objectives[i] for i in range(n_obj)] for d in feas])
    # Reference = max of negated (worst) + small margin
    ref = F.max(axis=0) + 1e-6
    hv = HV(ref_point=ref)(F)
    return float(hv)


def _site_state_for_obs(ctx: dict) -> np.ndarray:
    return np.array([
        ctx["area_m2"] / 2000.0,
        ctx["bcr_limit"] / 100.0,
        ctx["far_limit"] / 2000.0,
        ctx["height_limit"] / 60.0,
        1.0,
    ], dtype=np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True, help="path to ppo_*.zip")
    parser.add_argument("--n-samples", type=int, default=32,
                        help="stochastic samples per site")
    parser.add_argument("--tag", type=str, default="v1")
    parser.add_argument("--workspace", type=str,
                        default="/NHNHOME/WORKSPACE/0526040060_A/DHKim/arr-mass")
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    enable_repair = not args.no_repair

    print(f"=== eval PPO {args.tag} (samples={args.n_samples}) ===")
    print(f"  model: {args.model}")

    model = PPO.load(args.model)

    results = {
        "tag": args.tag,
        "model_path": args.model,
        "n_samples": args.n_samples,
        "enable_repair": enable_repair,
        "seed": args.seed,
        "sites": [],
    }

    rng = np.random.default_rng(args.seed)

    for site_key in SITE_POOL.keys():
        ctx = _build_site_context(site_key)
        obs = _site_state_for_obs(ctx)

        # Sample N stochastic actions from policy
        obs_batch = np.tile(obs, (args.n_samples, 1))
        actions, _ = model.predict(obs_batch, deterministic=False)

        # Also one deterministic
        det_action, _ = model.predict(obs, deterministic=True)
        det_action = np.atleast_2d(det_action)

        all_actions = np.concatenate([actions, det_action], axis=0)

        t0 = time.perf_counter()
        designs = _eval_design_batch(all_actions, ctx, enable_repair=enable_repair)
        dt = time.perf_counter() - t0

        feas = [d for d in designs if d.feasible and d.penalty == 0]
        feas_pct = 100.0 * len(feas) / len(designs)

        if feas:
            avg_floor = float(np.mean([d.objectives[0] for d in feas]))
            avg_daylight = float(np.mean([d.objectives[1] for d in feas]))
            best_floor = float(max(d.objectives[0] for d in feas))
            best_daylight = float(max(d.objectives[1] for d in feas))
        else:
            avg_floor = avg_daylight = best_floor = best_daylight = 0.0

        hv = _measure_hv(designs, ctx["outputs_def"])

        # Deterministic single
        det_design = designs[-1]
        det_obj = {
            "feasible": bool(det_design.feasible),
            "penalty": float(det_design.penalty),
            "objectives": [float(x) for x in det_design.objectives] if det_design.objectives else [],
        }

        site_result = {
            "site": site_key,
            "feasible_pct": round(feas_pct, 2),
            "n_total": len(designs),
            "n_feasible": len(feas),
            "hypervolume": round(hv, 4),
            "avg_floor_area": round(avg_floor, 2),
            "avg_daylight": round(avg_daylight, 2),
            "best_floor_area": round(best_floor, 2),
            "best_daylight": round(best_daylight, 2),
            "deterministic": det_obj,
            "eval_time_sec": round(dt, 3),
        }
        results["sites"].append(site_result)
        print(json.dumps(site_result, ensure_ascii=False))

    # Save
    out_path = Path(args.workspace) / "outputs" / f"ppo_{args.tag}_eval.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n=== eval saved → {out_path} ===")


if __name__ == "__main__":
    main()
