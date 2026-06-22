"""
B2 — Bayesian Optimization over Surrogate (Phase 2)

Surrogate model (B1b의 MLP) 을 acquisition function 으로 활용해
*적은 평가 횟수* 로 좋은 매스 발견 시도.

비교: SSIEA 1500 평가 vs BO 50 평가 의 hypervolume.

전략:
    1. 50개 초기 random sample (real evaluator)
    2. surrogate (MLP) 학습/업데이트
    3. acquisition: 다음 평가할 매스 = 모든 후보 중 surrogate predicted score 최고점
       (Expected Improvement 단순화)
    4. 10 round 반복 → 총 50 + 10×k 평가
    5. SSIEA HV 와 비교

본 스크립트는 *직접 SSIEA 와 BO 호출* — 외부 BO 라이브러리(BOTorch 등) 미사용.
간이 EI 대신 *surrogate top-K* 사용 (k=5 후보).

사용법:
    cd ARR/backend
    DJANGO_SETTINGS_MODULE=backend.settings python -c "
        import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
        import django; django.setup()
        import bayesian_optimization
        bayesian_optimization.run()
    "
"""

import json
import logging
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


TARGET_METRICS = ["floor_area", "daylight_score", "bcr", "far"]


def _load_real_evaluator():
    """SSIEA의 실제 평가 (mass_evaluator._compute_metrics)."""
    from design.services.mass_evaluator import _compute_metrics, _build_repair_limits_from_outputs
    from design.services.site_geometry import wgs84_to_utm
    return _compute_metrics, _build_repair_limits_from_outputs, wgs84_to_utm


def _build_input_vector(gene_vector: list, site_ctx: dict) -> np.ndarray:
    """gene_vector (29) + 3 site limits → (32,)."""
    return np.asarray(gene_vector + [site_ctx["bcr_limit"], site_ctx["far_limit"], site_ctx["height_limit_m"]],
                      dtype=np.float64)


def random_gene_vector(rng: np.random.RandomState, inputs_def: list) -> list[list[float]]:
    """spec inputs_def → random gene vector (Design.generate_random과 호환).

    Spec 형식: each input dict 에 type=Continuous/Categorical/Series + Min/Max + Set length.
    여기서는 Continuous (Set length=1) 만 가정 (additive algorithm 의 기본 형식).
    """
    gene = []
    for inp in inputs_def:
        t = inp.get("type", "Continuous")
        set_len = int(inp.get("Set length", 1))
        if t == "Continuous":
            p = [float(rng.uniform(inp["Min"], inp["Max"])) for _ in range(set_len)]
        elif t == "Categorical":
            n_opts = int(inp["Num options"])
            p = [float(rng.randint(0, n_opts)) for _ in range(set_len)]
        elif t == "Series":
            depth = int(inp["Depth"])
            p = [float(rng.randint(0, depth)) for _ in range(set_len)]
        else:
            p = [float(rng.uniform(inp.get("Min", 0), inp.get("Max", 1)))]
        gene.append(p)
    return gene


def evaluate_real(gene_vector: list[list[float]], site_polygon, site_utm, site_area_m2,
                  spec, repair_limits) -> dict:
    """gene_vector 한 개 → real metrics."""
    from design.services.mass_evaluator import _compute_metrics
    return _compute_metrics(
        gene_vector, site_utm, site_area_m2,
        building_type="공동주택",
        algorithm="additive",
        enable_repair=True,
        repair_limits=repair_limits,
    )


# Code review fix (2026-05-06): 공유 util 로 분리. typology_benchmark 와 중복 제거.
from design.services.hv_utils import hypervolume_2obj_max


def run(site_key: str = "gangnam_yeoksam_677",
        n_initial: int = 50, n_rounds: int = 10, candidates_per_round: int = 200,
        evals_per_round: int = 5,
        output_dir: str | None = None) -> dict:
    """
    BO loop:
    1. n_initial random evaluations
    2. for n_rounds: train MLP on history, sample candidates_per_round random,
       pick top-evals_per_round by surrogate score, evaluate real
    3. compare HV with SSIEA baseline (read from exp001/exp003)
    """
    import sys
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    import benchmark
    from shapely.geometry import Polygon
    from design.services.site_geometry import wgs84_to_utm
    from design.services.mass_evaluator import _build_repair_limits_from_outputs

    site = benchmark.TEST_SITES[site_key]
    site_polygon = Polygon(site["polygon_wgs84"])
    site_utm = wgs84_to_utm(site_polygon)
    site_area_m2 = site_utm.area
    spec = benchmark._build_spec({**site, "area_m2": site_area_m2},
                                  algorithm="additive",
                                  penalty_mode="normalized",
                                  n_objectives=2)
    repair_limits = _build_repair_limits_from_outputs(spec["outputs"], "공동주택")
    site_ctx = {
        "bcr_limit": site["bcr_limit"],
        "far_limit": site["far_limit"],
        "height_limit_m": site["height_limit"],
    }

    rng = np.random.RandomState(42)
    history_X, history_Y = [], []
    history_metrics = []  # full metrics for HV calc

    t_start = time.perf_counter()

    # 1. Initial random sampling
    logger.info(f"[{site_key}] BO initial sampling n={n_initial}")
    for i in range(n_initial):
        gene = random_gene_vector(rng, spec["inputs"])
        m = evaluate_real(gene, site_polygon, site_utm, site_area_m2, spec, repair_limits)
        gene_flat = [v[0] for v in gene]
        history_X.append(gene_flat + [site_ctx["bcr_limit"], site_ctx["far_limit"], site_ctx["height_limit_m"]])
        history_Y.append([m[k] for k in TARGET_METRICS])
        history_metrics.append(m)

    rounds_log = []

    # 2. BO rounds
    for r in range(n_rounds):
        X = np.asarray(history_X)
        Y = np.asarray(history_Y)
        sx = StandardScaler().fit(X)
        sy = StandardScaler().fit(Y)
        Xs = sx.transform(X)
        Ys = sy.transform(Y)

        # Train MLP
        mlp = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=300,
                           random_state=42, early_stopping=True, validation_fraction=0.1)
        mlp.fit(Xs, Ys)

        # Sample candidates
        cand_genes = [random_gene_vector(rng, spec["inputs"]) for _ in range(candidates_per_round)]
        cand_X = np.asarray([
            [v[0] for v in g] + [site_ctx["bcr_limit"], site_ctx["far_limit"], site_ctx["height_limit_m"]]
            for g in cand_genes
        ])
        cand_Xs = sx.transform(cand_X)
        cand_Ys_pred = mlp.predict(cand_Xs)
        cand_Y_pred = sy.inverse_transform(cand_Ys_pred)

        # Acquisition: maximize floor_area (idx 0) + daylight (idx 1)
        # 단순 score = predicted floor_area + daylight (normalized)
        score = cand_Y_pred[:, 0] / max(np.abs(cand_Y_pred[:, 0]).max(), 1) \
              + cand_Y_pred[:, 1] / max(np.abs(cand_Y_pred[:, 1]).max(), 1)
        top_idx = np.argsort(-score)[:evals_per_round]

        for idx in top_idx:
            gene = cand_genes[idx]
            m = evaluate_real(gene, site_polygon, site_utm, site_area_m2, spec, repair_limits)
            gene_flat = [v[0] for v in gene]
            history_X.append(gene_flat + [site_ctx["bcr_limit"], site_ctx["far_limit"], site_ctx["height_limit_m"]])
            history_Y.append([m[k] for k in TARGET_METRICS])
            history_metrics.append(m)

        # current Pareto/HV (2 obj: floor_area Max, daylight Max)
        Y_now = np.asarray(history_Y)
        obj_pts = Y_now[:, [0, 1]]
        # Reference: worst corner (min - 1) for maximization HV
        ref = obj_pts.min(axis=0) - 1.0
        hv = hypervolume_2obj_max(obj_pts, ref)
        rounds_log.append({"round": r + 1, "n_total_evals": len(history_X),
                            "best_floor_area": round(float(obj_pts[:, 0].max()), 1),
                            "best_daylight": round(float(obj_pts[:, 1].max()), 2),
                            "hv": round(float(hv), 1)})
        logger.info(f"  round {r+1}: total_evals={len(history_X)} hv={hv:.0f}")

    elapsed = time.perf_counter() - t_start

    summary = {
        "exp_id": "exp009",
        # Code review fix (2026-05-06): naive surrogate-mean acquisition (uncertainty 무시)
        # 은 진짜 BO 가 아니라 Surrogate-Guided Search (SGS). 정직한 명명.
        "title": "Surrogate-Guided Search (SGS) vs SSIEA — naive acquisition (uncertainty 무시)",
        "method_clarification": "Not true Bayesian Optimization (no Expected Improvement, no GP "
                                  "uncertainty). MLP surrogate + top-K mean prediction. Real BO "
                                  "follow-up: BoTorch + qEHVI + GP.",
        "date_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "site": site_key,
        "n_initial": n_initial,
        "n_rounds": n_rounds,
        "candidates_per_round": candidates_per_round,
        "evals_per_round": evals_per_round,
        "total_real_evals": len(history_X),
        "elapsed_sec": round(elapsed, 2),
        "rounds": rounds_log,
        "final_best_floor_area": rounds_log[-1]["best_floor_area"],
        "final_best_daylight": rounds_log[-1]["best_daylight"],
        "final_hv": rounds_log[-1]["hv"],
    }

    if output_dir is None:
        out = Path(__file__).parent.parent / "exp009_data.json"
    else:
        out = Path(output_dir) / "exp009_data.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved → {out}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
