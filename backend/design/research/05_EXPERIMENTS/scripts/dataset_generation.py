"""
B1a — Dataset Generation Script (Phase 2 진입)

SSIEA 다회 실행 → 매스 (gene vector → outputs) 데이터 수집.
Surrogate (B1) 학습용. 자가 생성, 외부 데이터셋 의존 없음.

사용법:
    cd ARR/backend
    DJANGO_SETTINGS_MODULE=backend.settings python -c "
        import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
        import django; django.setup()
        import dataset_generation
        dataset_generation.run(target_size=3000)
    "

저장 위치: design/research/04_DATASETS/data/ds01_self_generated_ga.json
형식: {"schema_version": 1, "samples": [{...}], "metadata": {...}}

Schema (각 sample):
    {
        "site_key": "gangnam_yeoksam_677",
        "site_area_m2": 2440.5,
        "site_bcr_limit": 80.0,
        "site_far_limit": 1300.0,
        "site_height_limit_m": 50.0,
        "gene_vector": [29 floats],  # additive algorithm
        "outputs": {
            "floor_area": ..., "daylight_score": ..., "bcr": ..., "far": ...,
            "height": ..., "min_setback": ..., "open_pct": ...,
            "compactness": ..., "stepback_factor": ...,
        },
        "feasible": True/False,
        "penalty": float,
    }
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def run(target_size: int = 3000, output_path: str | None = None) -> dict:
    """
    SSIEA를 여러번 실행해서 target_size 개 sample 수집.

    각 SSIEA run = 1050 designs (75 pop × 14 gen 평균). 3 부지 fixture 사용.
    target_size=3000 이면 약 3 runs (1 site each) 또는 1 run × 3 sites (총 3150 samples) 정도.
    """
    import sys
    if str(Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).parent))
    import benchmark
    from shapely.geometry import Polygon
    from design.engine.objects import SSIEAJob
    from design.services.mass_evaluator import evaluate_designs, _compute_metrics
    from design.services.site_geometry import wgs84_to_utm

    samples = []
    sites_used = []
    t_start = time.perf_counter()

    # Round-robin sites — 각 부지 1 SSIEA run 씩 순환 (다양성 확보)
    site_keys = list(benchmark.TEST_SITES.keys())
    site_run_counter = {k: 0 for k in site_keys}
    rr_idx = 0
    from design.services.mass_evaluator import _build_repair_limits_from_outputs

    while len(samples) < target_size:
        site_key = site_keys[rr_idx % len(site_keys)]
        rr_idx += 1
        site = benchmark.TEST_SITES[site_key]
        site_run_counter[site_key] += 1

        site_polygon = Polygon(site["polygon_wgs84"])
        site_utm = wgs84_to_utm(site_polygon)
        site_area_m2 = site_utm.area
        spec = benchmark._build_spec({**site, "area_m2": site_area_m2},
                                      algorithm="additive",
                                      penalty_mode="normalized",
                                      n_objectives=2)
        repair_limits = _build_repair_limits_from_outputs(spec["outputs"], "공동주택")

        logger.info(f"[{site_key}] SSIEA run {site_run_counter[site_key]}, samples_so_far={len(samples)}")

        job = SSIEAJob(spec)
        job.init_designs()
        eval_fn = lambda ds: evaluate_designs(
            ds, site_polygon, site_area_m2,
            outputs_def=spec["outputs"], building_type="공동주택",
            algorithm="additive", enable_repair=True,
        )
        cont = True
        while cont:
            cont, _, _ = job.step(eval_fn)

        for d in job.all_designs:
            inp = d.get_inputs()
            metrics = _compute_metrics(inp, site_utm, site_area_m2,
                                        building_type="공동주택",
                                        algorithm="additive",
                                        enable_repair=True,
                                        repair_limits=repair_limits)
            gene_vec = [v[0] for v in inp]
            samples.append({
                "site_key": site_key,
                "site_area_m2": round(site_area_m2, 2),
                "site_bcr_limit": site["bcr_limit"],
                "site_far_limit": site["far_limit"],
                "site_height_limit_m": site["height_limit"],
                "gene_vector": gene_vec,
                "outputs": metrics,
                "feasible": d.feasible,
                "penalty": round(d.penalty, 4),
            })
            if len(samples) >= target_size:
                break

        sites_used.append(f"{site_key}_run{site_run_counter[site_key]}")

    elapsed = time.perf_counter() - t_start

    feasibles = sum(1 for s in samples if s["feasible"])
    metadata = {
        "schema_version": 1,
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "target_size": target_size,
        "actual_size": len(samples),
        "feasible_pct": round(feasibles / max(len(samples), 1) * 100, 2),
        "elapsed_sec": round(elapsed, 1),
        "engine": "SSIEAJob (5 islands × 15)",
        "algorithm": "additive (29 genes)",
        "enable_repair": True,
        "penalty_mode": "normalized",
        "sites_used": sites_used,
        "schema": {
            "site_key": "string (fixture name)",
            "site_area_m2": "float (UTM area)",
            "site_bcr_limit/far_limit/height_limit_m": "float (regulation)",
            "gene_vector": "list[float] (29-D for additive)",
            "outputs": "dict {floor_area, daylight_score, bcr, far, height, min_setback, open_pct, compactness, stepback_factor}",
            "feasible": "bool",
            "penalty": "float (0.0=feasible, >0=violation distance)",
        },
    }

    result = {"metadata": metadata, "samples": samples}

    if output_path is None:
        out_dir = Path(__file__).parent.parent.parent / "04_DATASETS" / "data"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "ds01_self_generated_ga.json"
    else:
        out_path = Path(output_path)

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved {len(samples)} samples ({feasibles} feasible, {round(feasibles/max(len(samples),1)*100, 1)}%) → {out_path}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(target_size=3000)
