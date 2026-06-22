"""
C4 DRL Bootstrap — PPO training entry.

Usage (from ARR/backend):
    PYTHONPATH=. python design/research/03_PHASE3/scripts/train_ppo.py \\
        --steps 100000 --n-envs 16 --tag v1

The script adds its own directory to sys.path because '03_PHASE3' is not a valid
Python module name (digits-leading), so we cannot do `from design.research.03_PHASE3...`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make sibling mass_env.py importable
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback

from mass_env import make_env, SITE_POOL  # noqa: E402  (after sys.path tweak)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=100_000)
    parser.add_argument("--n-envs", type=int, default=16)
    parser.add_argument("--tag", type=str, default="v1")
    parser.add_argument("--workspace", type=str,
                        default="/NHNHOME/WORKSPACE/0526040060_A/DHKim/arr-mass")
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--n-steps-per-rollout", type=int, default=128,
                        help="PPO n_steps per env")
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    log_dir = workspace / "logs" / f"ppo_{args.tag}"
    out_dir = workspace / "outputs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    enable_repair = not args.no_repair
    site_keys = list(SITE_POOL.keys())

    print(f"=== PPO training (tag={args.tag}) ===")
    print(f"  total steps: {args.steps}")
    print(f"  n envs: {args.n_envs}")
    print(f"  enable_repair: {enable_repair}")
    print(f"  device: {args.device}")
    print(f"  log dir: {log_dir}")
    print(f"  sites: {site_keys}")

    # Vectorized env
    env_fns = [make_env(site_keys=site_keys, enable_repair=enable_repair, seed=i)
               for i in range(args.n_envs)]
    vec_env = SubprocVecEnv(env_fns, start_method="fork")
    vec_env = VecMonitor(vec_env, filename=str(log_dir / "monitor.csv"))

    model = PPO(
        "MlpPolicy",
        vec_env,
        n_steps=args.n_steps_per_rollout,
        batch_size=min(64 * args.n_envs, args.n_steps_per_rollout * args.n_envs),
        gae_lambda=0.95,
        gamma=0.99,
        learning_rate=3e-4,
        clip_range=0.2,
        ent_coef=0.01,
        n_epochs=10,
        verbose=1,
        device=args.device,
        tensorboard_log=str(log_dir),
    )

    print(f"  policy params: {sum(p.numel() for p in model.policy.parameters()):,}")

    # Checkpoint every 10k steps
    cp_cb = CheckpointCallback(
        save_freq=max(10_000 // args.n_envs, 1),
        save_path=str(out_dir / f"checkpoints_{args.tag}"),
        name_prefix=f"ppo_{args.tag}",
    )

    t0 = time.perf_counter()
    model.learn(total_timesteps=args.steps, callback=cp_cb,
                tb_log_name="ppo", progress_bar=False)
    runtime = time.perf_counter() - t0

    final_path = out_dir / f"ppo_{args.tag}.zip"
    model.save(str(final_path))
    print(f"=== done in {runtime:.1f}s — saved {final_path} ===")

    # Summary stats
    summary = {
        "tag": args.tag,
        "total_steps": args.steps,
        "n_envs": args.n_envs,
        "enable_repair": enable_repair,
        "runtime_sec": round(runtime, 1),
        "device": args.device,
        "sites": site_keys,
        "model_path": str(final_path),
    }
    with open(out_dir / f"ppo_{args.tag}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
