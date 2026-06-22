"""
B5 — Typology Benchmark (exp010)

10 typology × 3 fixture site × 2 reps SSIEA 실행 → HV 매트릭스 생성.
typology_recommender.TypologyRanking 으로 저장.

사용법:
    cd ARR/backend
    DJANGO_SETTINGS_MODULE=backend.settings python -c "
        import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
        import django; django.setup()
        import typology_benchmark
        typology_benchmark.run()
    "
"""

import json
import logging
import time
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

logger = logging.getLogger(__name__)


TYPOLOGIES = [
    "additive", "subtractive", "grid",
    "lshape", "ushape", "cross", "courtyard",
    "tower_podium", "hshape", "radial",
]


# Code review fix (2026-05-06): 공유 util 로 분리. bayesian_optimization 과 중복 제거.
from design.services.hv_utils import hypervolume_2obj_max as _hv_max


def benchmark_typology(site_key: str, typology: str, reps: int = 2) -> dict:
    """단일 site × typology × reps SSIEA. HV 평균 반환."""
    import sys
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    import benchmark
    from design.engine.objects import SSIEAJob
    from design.services.mass_evaluator import evaluate_designs
    from design.services.site_geometry import wgs84_to_utm

    site = benchmark.TEST_SITES[site_key]
    site_polygon = Polygon(site["polygon_wgs84"])
    site_utm = wgs84_to_utm(site_polygon)
    site_area_m2 = site_utm.area
    spec = benchmark._build_spec({**site, "area_m2": site_area_m2},
                                  algorithm=typology,
                                  penalty_mode="normalized",
                                  n_objectives=2)

    hvs = []
    feasibles = []
    runtimes = []
    for r in range(reps):
        t0 = time.perf_counter()
        try:
            job = SSIEAJob(spec)
            job.init_designs()
            eval_fn = lambda ds: evaluate_designs(
                ds, site_polygon, site_area_m2, outputs_def=spec["outputs"],
                building_type="공동주택", algorithm=typology, enable_repair=True,
            )
            cont = True
            while cont:
                cont, _, _ = job.step(eval_fn)

            obj_pts = []
            for d in job.all_designs:
                if d.objectives and len(d.objectives) >= 2:
                    obj_pts.append([d.objectives[0], d.objectives[1]])
            obj_pts = np.asarray(obj_pts) if obj_pts else np.zeros((0, 2))
            if len(obj_pts) > 0:
                ref = obj_pts.min(axis=0) - 1.0
                hv = _hv_max(obj_pts, ref)
            else:
                hv = 0.0
            hvs.append(hv)
            n_feasible = sum(1 for d in job.all_designs if d.penalty == 0)
            feasibles.append(n_feasible / max(len(job.all_designs), 1) * 100)
            runtimes.append(time.perf_counter() - t0)
        except Exception as e:
            logger.warning(f"  {typology} {site_key} rep{r+1} failed: {e}")
            hvs.append(0.0)
            feasibles.append(0.0)
            runtimes.append(time.perf_counter() - t0)

    return {
        "typology": typology,
        "site": site_key,
        "reps": reps,
        "hv_mean": round(float(np.mean(hvs)), 1) if hvs else 0,
        "hv_std": round(float(np.std(hvs)), 1) if hvs else 0,
        "feasible_pct_mean": round(float(np.mean(feasibles)), 2) if feasibles else 0,
        "runtime_mean_sec": round(float(np.mean(runtimes)), 2) if runtimes else 0,
    }


def run(reps: int = 2, output_path: str | None = None) -> dict:
    """10 typology × 3 fixture × reps."""
    import sys
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    import benchmark
    from design.services.site_geometry import wgs84_to_utm
    from design.services.typology_recommender import (
        SiteFeatures, TypologyRanking, set_ranking,
    )

    results_matrix = {}  # site → typology → result
    fixture_features = []
    fixture_names = []
    typology_hv = []

    t_start = time.perf_counter()

    for site_key, site in benchmark.TEST_SITES.items():
        results_matrix[site_key] = {}
        site_polygon = Polygon(site["polygon_wgs84"])
        site_utm = wgs84_to_utm(site_polygon)
        minx, miny, maxx, maxy = site_utm.bounds
        aspect = (maxx - minx) / max(maxy - miny, 1e-3)

        feats = SiteFeatures(
            area_m2=site_utm.area,
            bcr_limit=site["bcr_limit"],
            far_limit=site["far_limit"],
            height_limit_m=site["height_limit"],
            aspect_ratio=aspect,
        )
        fixture_features.append(feats.to_vector())
        fixture_names.append(site["name"])

        site_typo_hv = {}
        for typo in TYPOLOGIES:
            logger.info(f"[{site_key}] typology={typo} ...")
            r = benchmark_typology(site_key, typo, reps=reps)
            results_matrix[site_key][typo] = r
            site_typo_hv[typo] = r["hv_mean"]
        typology_hv.append(site_typo_hv)

    elapsed = time.perf_counter() - t_start

    # Save TypologyRanking
    ranking = TypologyRanking(
        fixture_features=fixture_features,
        typology_hv=typology_hv,
        fixture_names=fixture_names,
    )
    set_ranking(ranking)

    # JSON output
    summary = {
        "exp_id": "exp010",
        "title": "Typology Benchmark — 10 typology × 3 fixture × reps",
        "date_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "reps_per_cell": reps,
        "elapsed_sec": round(elapsed, 1),
        "matrix": results_matrix,
        "ranking": {
            "fixture_features": [list(f) for f in fixture_features],
            "fixture_names": fixture_names,
            "typology_hv": typology_hv,
        },
        "winners": {
            site_key: max(results_matrix[site_key].items(),
                          key=lambda x: x[1]["hv_mean"])[0]
            for site_key in results_matrix
        },
    }

    if output_path is None:
        out = Path(__file__).parent.parent / "exp010_data.json"
    else:
        out = Path(output_path)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved → {out}")

    # Save ranking pickle for runtime use
    import pickle
    pkl_path = Path(__file__).parent.parent.parent / "04_DATASETS" / "data" / "typology_ranking.pkl"
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    with pkl_path.open("wb") as f:
        pickle.dump({
            "fixture_features": fixture_features,
            "fixture_names": fixture_names,
            "typology_hv": typology_hv,
        }, f)
    logger.info(f"Saved ranking pickle → {pkl_path}")

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
