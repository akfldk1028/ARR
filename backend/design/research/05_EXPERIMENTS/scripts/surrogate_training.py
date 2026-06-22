"""
B1b — Surrogate Training (Phase 2)

ds01_self_generated_ga.json (3000 samples) 으로 surrogate 모델 학습.

Input  (32-D): 29-D gene_vector + 3 site limits (bcr/far/height)
Output (4):    floor_area, daylight_score, bcr, far  (가장 중요한 4개 metric)
              나머지 (height, min_setback, open_pct, compactness, stepback)는
              gene_vector + site_area 로 deterministic하게 계산 가능.

비교 모델 3종:
    1. MLPRegressor (sklearn) — 작은 신경망 (64,32)
    2. RandomForestRegressor — baseline (학습 빠름, robust)
    3. GaussianProcessRegressor — 1k 미만 sample에 적합, 3000은 느릴 수 있음

학습 결과:
    - test set R², MAE per output
    - best model pickle → `04_DATASETS/data/surrogate_best.pkl` (gitignore)
    - 결과 → exp008_surrogate.md

사용법:
    cd ARR/backend
    DJANGO_SETTINGS_MODULE=backend.settings python -c "
        import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
        import django; django.setup()
        import surrogate_training
        surrogate_training.run()
    "
"""

import json
import logging
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


TARGET_METRICS = ["floor_area", "daylight_score", "bcr", "far"]


def load_dataset(path: str | None = None) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """
    ds01 dataset 을 (X, Y, feature_names, target_names) 로 변환.

    X: (N, 32) — gene_vector(29) + bcr_limit + far_limit + height_limit
    Y: (N, 4)  — floor_area, daylight_score, bcr, far
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "04_DATASETS" / "data" / "ds01_self_generated_ga.json"
    else:
        path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    samples = data["samples"]

    X_list, Y_list = [], []
    for s in samples:
        gene = s["gene_vector"]
        site_ctx = [s["site_bcr_limit"], s["site_far_limit"], s["site_height_limit_m"]]
        X_list.append(gene + site_ctx)
        Y_list.append([s["outputs"][m] for m in TARGET_METRICS])

    X = np.asarray(X_list, dtype=np.float64)
    Y = np.asarray(Y_list, dtype=np.float64)
    feat_names = [f"gene_{i}" for i in range(29)] + ["bcr_limit", "far_limit", "height_limit"]
    return X, Y, feat_names, TARGET_METRICS


def evaluate_model(model, X_test, Y_test, scaler_y=None) -> dict:
    """Per-output R² and MAE."""
    Y_pred = model.predict(X_test)
    if scaler_y is not None:
        Y_pred = scaler_y.inverse_transform(Y_pred)
        Y_test = scaler_y.inverse_transform(Y_test)
    metrics = {}
    for i, name in enumerate(TARGET_METRICS):
        metrics[name] = {
            "r2": round(float(r2_score(Y_test[:, i], Y_pred[:, i])), 4),
            "mae": round(float(mean_absolute_error(Y_test[:, i], Y_pred[:, i])), 3),
        }
    metrics["mean_r2"] = round(float(np.mean([metrics[n]["r2"] for n in TARGET_METRICS])), 4)
    return metrics


def run(output_dir: str | None = None) -> dict:
    """Train 3 surrogate models + compare."""
    X, Y, feat_names, target_names = load_dataset()
    logger.info(f"Dataset: X{X.shape} Y{Y.shape}")

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42)
    logger.info(f"Train: {len(X_train)} / Test: {len(X_test)}")

    sx = StandardScaler().fit(X_train)
    sy = StandardScaler().fit(Y_train)
    X_train_s, X_test_s = sx.transform(X_train), sx.transform(X_test)
    Y_train_s, Y_test_s = sy.transform(Y_train), sy.transform(Y_test)

    results = {}

    # 1. RandomForest (baseline, robust)
    logger.info("Training RandomForest...")
    t0 = time.perf_counter()
    rf = RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
    rf.fit(X_train, Y_train)  # RF doesn't need scaling
    rf_time = time.perf_counter() - t0
    results["random_forest"] = {
        "train_sec": round(rf_time, 2),
        "metrics": evaluate_model(rf, X_test, Y_test),
    }
    logger.info(f"  done in {rf_time:.2f}s, mean_r2={results['random_forest']['metrics']['mean_r2']}")

    # 2. MLP (small NN)
    logger.info("Training MLP...")
    t0 = time.perf_counter()
    mlp = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500,
                       random_state=42, early_stopping=True, validation_fraction=0.1)
    mlp.fit(X_train_s, Y_train_s)
    mlp_time = time.perf_counter() - t0
    results["mlp"] = {
        "train_sec": round(mlp_time, 2),
        "metrics": evaluate_model(mlp, X_test_s, Y_test_s, scaler_y=sy),
    }
    logger.info(f"  done in {mlp_time:.2f}s, mean_r2={results['mlp']['metrics']['mean_r2']}")

    # 3. GP (subsample for speed)
    logger.info("Training GP (subsample 1000)...")
    t0 = time.perf_counter()
    try:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel
        sub = min(1000, len(X_train_s))
        idx = np.random.RandomState(42).choice(len(X_train_s), sub, replace=False)
        kernel = ConstantKernel(1.0) * RBF(length_scale=1.0)
        gp = GaussianProcessRegressor(kernel=kernel, alpha=1e-2, normalize_y=False, random_state=42)
        gp.fit(X_train_s[idx], Y_train_s[idx])
        gp_time = time.perf_counter() - t0
        results["gp"] = {
            "train_sec": round(gp_time, 2),
            "subsample": sub,
            "metrics": evaluate_model(gp, X_test_s, Y_test_s, scaler_y=sy),
        }
        logger.info(f"  done in {gp_time:.2f}s, mean_r2={results['gp']['metrics']['mean_r2']}")
    except Exception as e:
        logger.warning(f"GP failed: {e}")
        results["gp"] = {"error": str(e)}

    # Pick best by mean R²
    candidates = {k: v for k, v in results.items() if "metrics" in v}
    best_name = max(candidates, key=lambda k: candidates[k]["metrics"]["mean_r2"])
    logger.info(f"Best model: {best_name} (mean_r2={candidates[best_name]['metrics']['mean_r2']})")

    # Save best model
    if output_dir is None:
        out_dir = Path(__file__).parent.parent.parent / "04_DATASETS" / "data"
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if best_name == "random_forest":
        best_obj = {"model": rf, "scaler_x": None, "scaler_y": None}
    elif best_name == "mlp":
        best_obj = {"model": mlp, "scaler_x": sx, "scaler_y": sy}
    elif best_name == "gp":
        best_obj = {"model": gp, "scaler_x": sx, "scaler_y": sy}

    pkl_path = out_dir / "surrogate_best.pkl"
    with pkl_path.open("wb") as f:
        pickle.dump({"name": best_name, "feat_names": feat_names, "target_names": target_names,
                     **best_obj}, f)
    logger.info(f"Saved best model → {pkl_path}")

    summary = {
        "exp_id": "exp008",
        "title": "Surrogate Training (RandomForest / MLP / GP)",
        "date_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "dataset": "ds01_self_generated_ga.json",
        "n_total": len(X), "n_train": len(X_train), "n_test": len(X_test),
        "input_dim": X.shape[1], "output_dim": Y.shape[1],
        "target_names": target_names,
        "best_model": best_name,
        "models": results,
    }
    summary_path = out_dir.parent.parent / "05_EXPERIMENTS" / "exp008_data.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved summary → {summary_path}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
