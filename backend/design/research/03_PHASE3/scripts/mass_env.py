"""
C4 DRL Bootstrap — Gymnasium Env for mass generation.

State (5-D): site features (area, BCR limit, FAR limit, height limit, aspect_ratio=1.0)
Action (29-D): normalized [-1, 1] gene vector (additive box-stacking)
Reward: feasible × normalized utility (floor_area + daylight). Infeasible = -penalty.

1-step episode (contextual bandit). Each reset samples one site from pool.
A6 repair (C7 Layer 3) applied via evaluate_designs(enable_repair=True) for hard constraint.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from shapely.geometry import Polygon

from design.engine.objects import Design
from design.services.constraint_bridge import (
    regulations_to_constraints,
    build_default_job_spec,
)
from design.services.mass_evaluator import evaluate_designs
from design.services.site_geometry import wgs84_to_utm


# ───────────────────────────────────────────────────────────
# Site pool (same as benchmark.py — 3 fixtures)
# ───────────────────────────────────────────────────────────

SITE_POOL = {
    "gangnam_yeoksam_677": {
        "polygon_wgs84": [
            (127.0392, 37.5012), (127.0395, 37.5012),
            (127.0395, 37.5015), (127.0392, 37.5015),
            (127.0392, 37.5012),
        ],
        "bcr_limit": 80.0, "far_limit": 1300.0, "height_limit": 50.0,
        "adjacent_setback_m": 1.0, "building_line_setback_m": 3.0,
    },
    "bundang_test": {
        "polygon_wgs84": [
            (127.1042, 37.3812), (127.1045, 37.3812),
            (127.1045, 37.3815), (127.1042, 37.3815),
            (127.1042, 37.3812),
        ],
        "bcr_limit": 60.0, "far_limit": 250.0, "height_limit": 25.0,
        "adjacent_setback_m": 1.0, "building_line_setback_m": 3.0,
    },
    "chuncheon_test": {
        "polygon_wgs84": [
            (127.7242, 37.8742), (127.7245, 37.8742),
            (127.7245, 37.8745), (127.7242, 37.8745),
            (127.7242, 37.8742),
        ],
        "bcr_limit": 60.0, "far_limit": 200.0, "height_limit": 20.0,
        "adjacent_setback_m": 1.0, "building_line_setback_m": 3.0,
    },
}


def _build_site_context(site_key: str) -> dict[str, Any]:
    """Build cached site context with spec + UTM polygon."""
    site = SITE_POOL[site_key]
    poly_wgs = Polygon(site["polygon_wgs84"])
    poly_utm = wgs84_to_utm(poly_wgs)
    area_m2 = poly_utm.area

    constraints = regulations_to_constraints({
        "bcr_limit": site["bcr_limit"],
        "far_limit": site["far_limit"],
        "height_limit_m": site["height_limit"],
        "adjacent_setback_m": site["adjacent_setback_m"],
        "building_line_setback_m": site["building_line_setback_m"],
    })
    spec = build_default_job_spec(
        site_area_m2=area_m2,
        constraints=constraints,
        building_type="공동주택",
        algorithm="additive",
    )
    spec.setdefault("options", {})["penalty_mode"] = "normalized"
    return {
        "site_key": site_key,
        "polygon_wgs84": poly_wgs,
        "area_m2": area_m2,
        "bcr_limit": site["bcr_limit"],
        "far_limit": site["far_limit"],
        "height_limit": site["height_limit"],
        "spec": spec,
        "inputs_def": spec["inputs"],
        "outputs_def": spec["outputs"],
    }


# ───────────────────────────────────────────────────────────
# Action / state encoding
# ───────────────────────────────────────────────────────────

OBS_DIM = 5     # [area_m2/2000, bcr/100, far/2000, height/60, aspect=1.0]
ACTION_DIM = 29  # additive box-stacking gene_vector

# Reward shaping coefficients
W_FLOOR = 1.0    # floor_area normalized weight
W_DAYLIGHT = 0.5  # daylight (0~100) weight
INFEASIBLE_PENALTY_SCALE = 0.5


def _action_to_gene(action: np.ndarray, inputs_def: list[dict]) -> list[list[float]]:
    """Map action ∈ [-1, 1]^29 → Design.inputs (list of [scalar] lists, length=29)."""
    inputs = []
    for i, inp_def in enumerate(inputs_def):
        lo, hi = float(inp_def["Min"]), float(inp_def["Max"])
        # remap [-1, 1] → [lo, hi]
        a = float(np.clip(action[i], -1.0, 1.0))
        val = lo + (a + 1.0) * 0.5 * (hi - lo)
        inputs.append([val])  # Set length=1 for additive
    return inputs


def _site_state(ctx: dict[str, Any]) -> np.ndarray:
    """Site context → 5-D observation (normalized)."""
    return np.array([
        ctx["area_m2"] / 2000.0,
        ctx["bcr_limit"] / 100.0,
        ctx["far_limit"] / 2000.0,
        ctx["height_limit"] / 60.0,
        1.0,  # placeholder aspect ratio
    ], dtype=np.float32)


def _reward_from_outputs(design: Design, ctx: dict[str, Any]) -> tuple[float, dict]:
    """Compute reward from evaluated design (with set_outputs already called)."""
    # design.objectives = [floor_area, daylight_score] (after set_outputs filters Objective only)
    if not design.objectives:
        return -1.0, {"feasible": False, "penalty": float(design.penalty), "reason": "no_objectives"}

    floor_area = design.objectives[0]
    daylight = design.objectives[1] if len(design.objectives) > 1 else 0.0

    # Normalize: max floor_area ~= site_area * (FAR_limit / 100); cap at FAR-equivalent
    max_floor = ctx["area_m2"] * (ctx["far_limit"] / 100.0)
    floor_norm = float(min(floor_area / max(max_floor, 1.0), 1.5))
    daylight_norm = float(daylight) / 100.0

    if design.feasible and design.penalty == 0:
        reward = W_FLOOR * floor_norm + W_DAYLIGHT * daylight_norm
    else:
        # Penalty already normalized (~ 0~3 range typical)
        reward = -INFEASIBLE_PENALTY_SCALE * float(min(design.penalty, 2.0))

    info = {
        "feasible": bool(design.feasible),
        "penalty": float(design.penalty),
        "floor_area": float(floor_area),
        "daylight": float(daylight),
        "floor_norm": floor_norm,
        "daylight_norm": daylight_norm,
    }
    return reward, info


# ───────────────────────────────────────────────────────────
# Env
# ───────────────────────────────────────────────────────────

class MassEnv(gym.Env):
    """Single-step contextual bandit env for additive mass generation."""

    metadata = {"render_modes": []}

    def __init__(self,
                 site_keys: list[str] | None = None,
                 enable_repair: bool = True,
                 building_type: str = "공동주택",
                 seed: int | None = None):
        super().__init__()
        self.site_keys = site_keys or list(SITE_POOL.keys())
        self.enable_repair = enable_repair
        self.building_type = building_type

        # Pre-build site contexts (spec is expensive)
        self._contexts = {k: _build_site_context(k) for k in self.site_keys}

        self.observation_space = spaces.Box(
            low=0.0, high=2.0, shape=(OBS_DIM,), dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32,
        )

        self._rng = random.Random(seed)
        self._step_id = 0
        self._current_ctx: dict | None = None

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = random.Random(seed)
        site_key = self._rng.choice(self.site_keys)
        self._current_ctx = self._contexts[site_key]
        obs = _site_state(self._current_ctx)
        info = {"site_key": site_key}
        return obs, info

    def step(self, action):
        assert self._current_ctx is not None, "call reset() first"
        ctx = self._current_ctx
        self._step_id += 1

        # action → Design
        design = Design(_id=self._step_id, des_num=0, gen_num=0)
        design.inputs = _action_to_gene(np.asarray(action, dtype=np.float32), ctx["inputs_def"])

        # evaluate (single design batch)
        try:
            outs = evaluate_designs(
                [design], ctx["polygon_wgs84"], ctx["area_m2"],
                outputs_def=ctx["outputs_def"],
                building_type=self.building_type,
                algorithm="additive",
                enable_repair=self.enable_repair,
            )
            design.set_outputs(outs[0], ctx["outputs_def"], penalty_mode="normalized")
            reward, info = _reward_from_outputs(design, ctx)
        except Exception as e:
            reward = -1.0
            info = {"error": str(e), "feasible": False}

        info["site_key"] = ctx["site_key"]
        obs = _site_state(ctx)  # same site (1-step)
        terminated = True
        truncated = False
        return obs, float(reward), terminated, truncated, info


def make_env(site_keys: list[str] | None = None,
             enable_repair: bool = True,
             seed: int | None = None):
    """Factory for SB3 vec env."""
    def _thunk():
        return MassEnv(site_keys=site_keys, enable_repair=enable_repair, seed=seed)
    return _thunk


if __name__ == "__main__":
    # Smoke test
    env = MassEnv(seed=42)
    obs, info = env.reset(seed=42)
    print("obs:", obs, "site:", info["site_key"])
    for i in range(5):
        a = env.action_space.sample()
        obs, r, term, trunc, info = env.step(a)
        print(f"  step {i}: r={r:.3f} feasible={info.get('feasible')} penalty={info.get('penalty', 0):.3f} site={info['site_key']}")
        if term or trunc:
            obs, info = env.reset()
