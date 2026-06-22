"""
A5 — Baseline Benchmark Script

현재 SSIEAJob (5섬 × 15) + 박스 적층 GA의 정량 baseline 측정.
Phase 1/2/3 모든 변경 전후 비교 기준.

사용법 (Django shell):
    cd ARR/backend
    python manage.py shell
    >>> from design.research.scripts.benchmark import run
    >>> run(reps=3)

또는 standalone:
    cd ARR/backend
    python -m design.research.scripts.benchmark

측정 지표:
    - Hypervolume (pymoo HV)
    - Feasible 비율 (penalty=0 매스 비율)
    - 평균 BCR/FAR/daylight
    - Runtime (sec)
    - Pareto front 크기
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────
# Test sites (3종 fixture)
# ───────────────────────────────────────────────────────────

TEST_SITES = {
    "gangnam_yeoksam_677": {
        "name": "강남구 역삼동 677",
        "polygon_wgs84": [
            (127.0392, 37.5012),
            (127.0395, 37.5012),
            (127.0395, 37.5015),
            (127.0392, 37.5015),
            (127.0392, 37.5012),
        ],
        "area_m2": 800.0,
        "zone": "일반상업지역",
        "bcr_limit": 80.0,
        "far_limit": 1300.0,
        "height_limit": 50.0,
    },
    "bundang_test": {
        "name": "분당 테스트 부지",
        "polygon_wgs84": [
            (127.1100, 37.3500),
            (127.1102, 37.3500),
            (127.1102, 37.3502),
            (127.1100, 37.3502),
            (127.1100, 37.3500),
        ],
        "area_m2": 600.0,
        "zone": "제2종일반주거지역",
        "bcr_limit": 60.0,
        "far_limit": 250.0,
        "height_limit": 25.0,
    },
    "chuncheon_test": {
        "name": "춘천 테스트 부지",
        "polygon_wgs84": [
            (127.7290, 37.8810),
            (127.7295, 37.8810),
            (127.7295, 37.8815),
            (127.7290, 37.8815),
            (127.7290, 37.8810),
        ],
        "area_m2": 1200.0,
        "zone": "제1종일반주거지역",
        "bcr_limit": 60.0,
        "far_limit": 200.0,
        "height_limit": 20.0,
    },
}


def _build_spec(site: dict, algorithm: str = "additive",
                penalty_mode: str = "normalized",
                n_objectives: int = 2) -> dict:
    """build_default_job_spec wrapper.

    Args:
        n_objectives: 2 (default, floor_area+daylight) or 4 (+ compactness Min + stepback_factor Max).
    """
    from design.services.constraint_bridge import (
        regulations_to_constraints,
        build_default_job_spec,
    )

    reg_result = {
        "bcr_limit": site["bcr_limit"],
        "far_limit": site["far_limit"],
        "height_limit_m": site["height_limit"],
        "adjacent_setback_m": 1.0,
        "building_line_setback_m": 3.0,
    }
    constraints = regulations_to_constraints(reg_result)
    spec = build_default_job_spec(
        site_area_m2=site["area_m2"],
        constraints=constraints,
        building_type="공동주택",
        algorithm=algorithm,
    )
    spec.setdefault("options", {})["penalty_mode"] = penalty_mode

    # exp006 4-objective: floor_area Max + daylight Max + compactness Min + stepback Max
    if n_objectives == 4:
        # Insert 2 new objectives BEFORE existing constraints
        # Find where Constraints start in outputs
        outputs = spec["outputs"]
        # Default outputs[0], outputs[1] are objectives. Constraints start at outputs[2].
        new_outputs = [
            outputs[0],  # floor_area Max
            outputs[1],  # daylight_score Max
            {"name": "compactness", "type": "Objective", "Goal": "Minimize",
             "label": "매스 단순도 (perimeter²/area, 낮을수록 단순)"},
            {"name": "stepback_factor", "type": "Objective", "Goal": "Maximize",
             "label": "상층 후퇴 비율 (높을수록 도시 친화)"},
        ] + outputs[2:]  # rest = constraints
        spec["outputs"] = new_outputs

    return spec


def _measure_hypervolume(designs, outputs_def: list) -> float:
    """pymoo HV. 미설치 시 -1."""
    try:
        import numpy as np
        from pymoo.indicators.hv import HV
    except ImportError:
        logger.warning("pymoo not installed — skipping HV")
        return -1.0

    feasible = [d for d in designs if d.objectives and d.penalty == 0]
    if len(feasible) < 2:
        return 0.0

    points = []
    for d in feasible:
        objs = []
        obj_idx = 0
        for out_def in outputs_def:
            if out_def.get("type") != "Objective":
                continue
            val = d.objectives[obj_idx]
            if out_def.get("Goal") == "Maximize":
                val = -val
            objs.append(val)
            obj_idx += 1
        points.append(objs)

    points = np.array(points)
    ref_point = points.max(axis=0) + 1.0
    hv = HV(ref_point=ref_point)
    return float(hv(points))


def benchmark_single(site_key: str, algorithm: str = "additive", reps: int = 3,
                     enable_repair: bool = False, engine: str = "ssiea",
                     penalty_mode: str = "normalized",
                     n_objectives: int = 2) -> dict:
    """단일 부지 × 알고리즘 benchmark.

    Args:
        enable_repair: A6 Repair Operator 활성화 (exp003). Default False (baseline).
        engine: 'ssiea' (default, SSIEAJob 5섬×15) | 'nsga3' (NSGA3Job, A1).
        penalty_mode: 'normalized' (default, A3) | 'binary' (legacy, exp004 비교).
        n_objectives: 2 (default) | 4 (exp006, +compactness Min + stepback Max).
    """
    from shapely.geometry import Polygon
    from design.engine.objects import SSIEAJob, NSGA3Job
    from design.services.mass_evaluator import evaluate_designs

    site = TEST_SITES[site_key]
    site_polygon = Polygon(site["polygon_wgs84"])
    # 2026-05-06: UTM 변환 후 *실제 면적* 사용 (fixture area_m2와 mismatch 시 BCR/FAR 일관성 깨짐)
    from design.services.site_geometry import wgs84_to_utm
    site_area_m2 = wgs84_to_utm(site_polygon).area
    spec = _build_spec({**site, "area_m2": site_area_m2},
                       algorithm=algorithm, penalty_mode=penalty_mode,
                       n_objectives=n_objectives)

    JobClass = NSGA3Job if engine == "nsga3" else SSIEAJob

    rep_results = []
    for rep in range(reps):
        suffix = " [+repair]" if enable_repair else ""
        logger.info(f"[{site_key}]{suffix} [{engine}/{penalty_mode}] {algorithm} rep {rep+1}/{reps}")
        t_start = time.perf_counter()

        job = JobClass(spec)
        job.init_designs()
        eval_fn = lambda ds: evaluate_designs(
            ds, site_polygon, site_area_m2,
            outputs_def=spec["outputs"],
            building_type="공동주택",
            algorithm=algorithm,
            enable_repair=enable_repair,
        )

        cont = True
        while cont:
            cont, gen, _pop = job.step(eval_fn)

        runtime = time.perf_counter() - t_start

        all_designs = job.all_designs
        n_total = len(all_designs)
        feasibles = [d for d in all_designs if d.penalty == 0]
        n_feasible = len(feasibles)
        feasible_pct = n_feasible / n_total * 100 if n_total > 0 else 0.0

        if n_feasible > 0:
            avg_objs = []
            n_obj = len(feasibles[0].objectives)
            for i in range(n_obj):
                vals = [d.objectives[i] for d in feasibles]
                avg_objs.append(sum(vals) / len(vals))
        else:
            avg_objs = []

        hv = _measure_hypervolume(all_designs, spec["outputs"])
        pareto_front = job.get_pareto_front()

        rep_results.append({
            "rep": rep + 1,
            "runtime_sec": round(runtime, 2),
            "n_total": n_total,
            "n_feasible": n_feasible,
            "feasible_pct": round(feasible_pct, 2),
            "hypervolume": round(hv, 4),
            "pareto_front_size": len(pareto_front),
            "avg_objectives": [round(v, 2) for v in avg_objs],
        })

    runtimes = [r["runtime_sec"] for r in rep_results]
    hvs = [r["hypervolume"] for r in rep_results]
    feas = [r["feasible_pct"] for r in rep_results]
    pf = [r["pareto_front_size"] for r in rep_results]

    return {
        "site": site_key,
        "site_name": site["name"],
        "algorithm": algorithm,
        "enable_repair": enable_repair,
        "engine": engine,
        "penalty_mode": penalty_mode,
        "reps": reps,
        "runtime_mean_sec": round(sum(runtimes) / len(runtimes), 2),
        "hypervolume_mean": round(sum(hvs) / len(hvs), 4),
        "feasible_pct_mean": round(sum(feas) / len(feas), 2),
        "pareto_front_size_mean": round(sum(pf) / len(pf), 1),
        "rep_details": rep_results,
    }


def run(reps: int = 3, output_path: str | None = None,
        enable_repair: bool = False, exp_id: str = "exp001",
        engine: str = "ssiea", penalty_mode: str = "normalized") -> dict:
    """3개 부지 × additive 알고리즘 benchmark + JSON 저장.

    Args:
        enable_repair: A6 Repair Operator 활성화 (exp003).
        exp_id: 실험 ID — exp001 / exp003 / exp002 / exp004 / etc.
        engine: 'ssiea' (default) | 'nsga3'.
        penalty_mode: 'normalized' (A3) | 'binary' (legacy, exp004).
    """
    title_map = {
        "exp001": "exp001: Baseline (SSIEAJob + 박스 적층)",
        "exp003": "exp003: A6 Repair Operator",
        "exp002": "exp002: NSGA3Job (A1) vs SSIEAJob",
    }
    title = title_map.get(exp_id, f"{exp_id}: {engine} engine")
    results = {
        "exp_id": exp_id,
        "title": title,
        "date_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "config": {
            "engine": engine,
            "max_gen": 120,
            "algorithm": "additive",
            "enable_repair": enable_repair,
            "reps": reps,
        },
        "sites": [],
    }

    for site_key in TEST_SITES.keys():
        try:
            res = benchmark_single(site_key, algorithm="additive", reps=reps,
                                   enable_repair=enable_repair, engine=engine,
                                   penalty_mode=penalty_mode)
            results["sites"].append(res)
        except Exception as e:
            logger.exception(f"[{site_key}] failed: {e}")
            results["sites"].append({"site": site_key, "error": str(e)})

    if output_path is None:
        fname = f"{exp_id}_baseline_data.json" if exp_id == "exp001" else f"{exp_id}_data.json"
        out = Path(__file__).parent.parent / fname
    else:
        out = Path(output_path)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved → {out}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if "--repair" in sys.argv:
        run(reps=3, enable_repair=True, exp_id="exp003")
    else:
        run(reps=3, enable_repair=False, exp_id="exp001")
