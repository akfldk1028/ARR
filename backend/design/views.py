"""
Design Optimization API

8 endpoints for building mass optimization with GA + SSE streaming.
SSE pattern mirrors land/views.py agent_analyze_stream.
"""

import json
import logging
import queue
import threading
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from design.engine.runner import JobRunner, MultiAlgoRunner
from design.formatters import format_job_response, format_design_response, format_pareto_front
from design.models import OptimizationJob, DesignResult
from design.persistence import save_job, save_results, update_job_status
from design.services.constraint_bridge import (
    regulations_to_constraints, build_default_job_spec, compute_setback_geometry,
    build_floor_plan_spec,
)
from design.services.mass_evaluator import evaluate_designs
from design.services.mass_renderer import design_to_geojson
from design.services.regulation_validator import (
    validate_design, validate_best_designs, auto_correct_constraints,
)
from design.services.site_geometry import (
    fetch_parcel_boundary, geojson_to_polygon, validate_site,
)
from design.services.interactive_patch import build_interactive_patch_plan
from design.services.interactive_apply import build_interactive_preview
from design.services.mass_operations import apply_mass_operation
from design.maas import build_maas_evidence_bundle, export_mass_geojson_to_scad, generate_legal_mass_variants
from design.maas.aesthetic import build_aesthetic_pipeline_result
from design.maas.aesthetic.adapters import NanoBananaAdapter, OpenAIImageAdapter
from design.maas.aesthetic.renderers import MultiViewReferencePackRenderer

logger = logging.getLogger(__name__)

# Active runners keyed by job_id for cancellation
_active_runners: dict[str, JobRunner] = {}


def _all_mode_budget_options(options: dict | None) -> dict[str, int]:
    """Budget used for each algorithm when algorithm='all'."""
    options = options or {}
    return {
        "Number of generations": int(options.get("Number of generations", 80)),
        "num_islands": int(options.get("num_islands", 5)),
        "pop_per_island": int(options.get("pop_per_island", 20)),
    }


def _daylight_diagonal_multiplier(zone_names: list[str], building_type: str) -> float | None:
    """건축법 §61②/시행령 §86③ 채광사선 적용 배수."""
    residential_types = ("공동주택", "아파트", "다세대", "연립", "다가구")
    if not any(t in (building_type or "") for t in residential_types):
        return None
    # 법 §61②: 일반상업지역ㆍ중심상업지역에 건축하는 공동주택은 제외.
    if any(z in ("일반상업지역", "중심상업지역") for z in zone_names):
        return None
    if any(z in ("근린상업지역", "준주거지역") for z in zone_names):
        return 4.0
    return 2.0


def _precompute_sunlight_envelope(job) -> dict | None:
    """
    Phase B (2026-05-08) — job_stream에서 NSGA-II 시작 전에 sunlight envelope 계산.

    Repair operator(`design.services.repair_operator.clip_to_sunlight_envelope`)가
    envelope corners polygon으로 footprint를 clip할 때 사용. PNU에서 zones 받아
    sunlight_applies 여부 판정 후 적용 zone(전용/일반주거)이면 envelope 생성.

    sunlight 미적용 zone(상업/공업 등)이면 None 반환 → Repair clip 단계 skip.

    실패시 None — Repair는 envelope 없이도 BCR/FAR/height 작동.
    """
    if not job.pnu and not job.site_polygon:
        return None
    try:
        from land.services import land_api, regulation_calculator, road_frontage, zoning_mapper
        from land.services.setback_geometry import compute_setback_lines
        from land import config as land_config

        zones = []
        if job.pnu:
            try:
                land_info = land_api.get_land_use_info(job.pnu)
                zones = land_info.get("zones", []) or []
            except Exception as e:
                logger.warning(f"land_api zones lookup failed for {job.pnu}: {e}")

        if not zones:
            return None
        limits = zoning_mapper.resolve_limits(zones)
        zone_names = [z["zone_name"] for z in (limits or {}).get("zones", [])] or zones
        reg = regulation_calculator.calculate_all(
            zone_names,
            use_llm_extraction=False,
        )

        if not reg.get("sunlight_applies"):
            logger.info(f"[sunlight_clip] zone={zone_names} sunlight_applies=False → clip skip")
            return None
        road_frontages = []
        neighbor_parcels = []
        if job.site_polygon:
            try:
                roads_result = road_frontage.fetch_neighbor_roads(job.site_polygon)
                if roads_result.get("success"):
                    road_frontages = roads_result.get("roads") or []
            except Exception as e:
                logger.warning(f"[sunlight_clip] road frontage lookup failed: {e}")
            try:
                neighbors_result = road_frontage.fetch_neighbor_parcels(job.site_polygon)
                if neighbors_result.get("success"):
                    neighbor_parcels = neighbors_result.get("neighbors") or []
            except Exception as e:
                logger.warning(f"[sunlight_clip] neighbor parcel lookup failed: {e}")

        lines = compute_setback_lines(
            job.site_polygon, reg,
            compute_datum=land_config.ENABLE_DATUM_ELEVATION,
            road_frontages=road_frontages,
            neighbor_parcels=neighbor_parcels,
        )
        env = lines.get("sunlight_envelope")
        if env:
            corners = (env.get("slanted_polygons") or [{}])[0].get("corners") or []
            heights = [c[2] for c in corners] if corners else []
            logger.info(
                f"[sunlight_clip] zone={zone_names} envelope: "
                f"corners={len(corners)}, H={min(heights) if heights else 0:.1f}~"
                f"{max(heights) if heights else 0:.1f}m → Repair clip 활성"
            )
        else:
            logger.warning(f"[sunlight_clip] zone={zone_names} envelope=None")
        return env
    except Exception as e:
        logger.warning(f"_precompute_sunlight_envelope failed: {e}")
        return None


@csrf_exempt
@require_http_methods(["POST"])
def create_job(request):
    """POST /design/jobs/ — Create and start an optimization job."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    site_polygon_geojson = body.get("site_polygon")
    if not site_polygon_geojson:
        return JsonResponse({"error": "site_polygon is required"}, status=400)

    try:
        site_polygon = geojson_to_polygon(site_polygon_geojson)
    except Exception as e:
        return JsonResponse({"error": f"Invalid site_polygon: {e}"}, status=400)

    validation = validate_site(site_polygon)
    if not validation["valid"]:
        return JsonResponse({"error": "Invalid site", "details": validation["errors"]}, status=400)

    job_spec = body.get("job_spec")
    constraints = body.get("constraints", [])
    pnu = body.get("pnu", "")
    address = body.get("address", "")

    # Build default spec if not provided or incomplete (missing inputs/outputs)
    user_options = job_spec.get("options", {}) if job_spec else {}
    building_type = user_options.get("building_type", "공동주택")
    algorithm = user_options.get("algorithm", "additive")
    if not job_spec or "inputs" not in job_spec:
        job_spec = build_default_job_spec(validation["area_m2"], constraints, building_type, algorithm)
        # Override defaults with any user-provided options
        if user_options:
            job_spec["options"].update(user_options)
    else:
        # Full spec provided — inject constraints into outputs if missing
        existing_names = {o["name"] for o in job_spec.get("outputs", [])}
        for c in constraints:
            if c["name"] not in existing_names:
                job_spec.setdefault("outputs", []).append(c)

    max_gen = int(job_spec.get("options", {}).get("Number of generations", 50))
    opts = job_spec.get("options", {})
    pop_size = int(opts.get("num_islands", 7)) * int(opts.get("pop_per_island", 30))

    # Create DB record
    job = save_job({
        "pnu": pnu,
        "address": address,
        "site_polygon": site_polygon_geojson,
        "site_area_m2": validation["area_m2"],
        "job_spec": job_spec,
        "constraints": constraints,
        "max_generations": max_gen,
        "population_size": pop_size,
    })

    if not job:
        return JsonResponse({"error": "Failed to create job"}, status=500)

    return JsonResponse(format_job_response(job), status=202)


@require_http_methods(["GET"])
def get_job(request, job_id):
    """GET /design/jobs/<id>/ — Get job status."""
    try:
        job = OptimizationJob.objects.get(id=job_id)
    except OptimizationJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    return JsonResponse(format_job_response(job))


@csrf_exempt
@require_http_methods(["POST"])
def cancel_job(request, job_id):
    """POST /design/jobs/<id>/cancel/ — Cancel a running job."""
    runner = _active_runners.get(str(job_id))
    if runner:
        runner.cancel()

    update_job_status(job_id, "cancelled")
    return JsonResponse({"status": "cancelled"})


@require_http_methods(["GET"])
def job_stream(request, job_id):
    """GET /design/jobs/<id>/stream — SSE stream of optimization progress."""
    try:
        job = OptimizationJob.objects.get(id=job_id)
    except OptimizationJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    if job.status in ("complete", "failed", "cancelled"):
        return JsonResponse({"error": f"Job already {job.status}"}, status=400)

    site_polygon = geojson_to_polygon(job.site_polygon)
    site_area_m2 = job.site_area_m2 or 0

    job_options = job.job_spec.get("options", {})
    building_type = job_options.get("building_type", "공동주택")
    algorithm = job_options.get("algorithm", "additive")

    # Phase B (2026-05-08) — sunlight envelope 즉석 계산. Repair operator가 envelope
    # corners polygon으로 footprint clip할 때 사용. PNU 없거나 정북일조 미적용 zone
    # (상업지역)이면 None — Repair는 envelope=None 시 clip 단계 skip.
    sunlight_envelope = _precompute_sunlight_envelope(job)

    event_queue = queue.Queue()

    maas_mode = algorithm == "maas_legal_envelope"

    if algorithm == "all" or maas_mode:
        # Multi-algorithm mode: run all 10 algorithms in parallel
        from design.services.constraint_bridge import ALL_ALGORITHMS, build_default_job_spec as build_spec
        constraints = job.constraints or []
        base_options = job.job_spec.get("options", {})
        budget_options = _all_mode_budget_options(base_options)

        algo_specs = {}
        evaluate_fns = {}
        for algo in ALL_ALGORITHMS:
            spec = build_spec(site_area_m2, constraints, building_type, algo)
            # Respect caller/UI budget in "all" mode. Previously this was hard-coded
            # to 80x5x20 per algorithm, making short test runs unexpectedly heavy.
            spec["options"].update(base_options)
            spec["options"].update(budget_options)
            spec["options"]["algorithm"] = algo
            algo_specs[algo] = spec

            def make_eval(a, outputs_def):
                def fn(designs):
                    return evaluate_designs(
                        designs, site_polygon, site_area_m2,
                        outputs_def, building_type, a,
                        enable_repair=True,
                        sunlight_envelope=sunlight_envelope,
                    )
                return fn
            evaluate_fns[algo] = make_eval(algo, spec.get("outputs"))

        runner = MultiAlgoRunner(algo_specs, evaluate_fns, event_queue)
    else:
        # Single algorithm mode
        def evaluate_fn(designs):
            return evaluate_designs(designs, site_polygon, site_area_m2,
                                    job.job_spec.get("outputs"), building_type,
                                    algorithm,
                                    enable_repair=True,
                                    sunlight_envelope=sunlight_envelope)
        runner = JobRunner(job.job_spec, evaluate_fn, event_queue)

    _active_runners[str(job_id)] = runner

    update_job_status(job_id, "running")

    def run_optimization():
        try:
            runner.run()
        finally:
            _active_runners.pop(str(job_id), None)

    thread = threading.Thread(target=run_optimization, daemon=True)
    thread.start()

    def event_stream():
        try:
            while True:
                try:
                    event = event_queue.get(timeout=1.0)
                except queue.Empty:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    if not thread.is_alive():
                        break
                    continue

                event_type = event.get("type", "update")

                # Enrich with GeoJSON for 3D mass visualization
                # Throttle: only every 10th generation + complete (geometry pipeline is expensive)
                gen_num = event.get("generation", 0)
                if event_type == "complete" or (event_type == "generation" and gen_num % 10 == 0):
                    # In all/MAAS mode, each seed design has its own legacy
                    # algorithm tag. MAAS mode then replaces the client-facing
                    # final front with legal-envelope variants.
                    render_algo = "per_design" if (algorithm == "all" or maas_mode) else algorithm
                    render_outputs = job.job_spec.get("outputs")
                    if algorithm == "all" or maas_mode:
                        render_outputs = list(algo_specs.values())[0].get("outputs")
                    _enrich_event_geojson(
                        event,
                        site_polygon,
                        site_area_m2,
                        building_type,
                        render_algo,
                        outputs_def=render_outputs,
                        enable_repair=True,
                        sunlight_envelope=sunlight_envelope,
                    )

                client_event = event
                if event_type == "complete" and maas_mode:
                    client_event = _maas_client_event(
                        event,
                        site_polygon_geojson=job.site_polygon,
                        constraints=job.constraints or [],
                        building_type=building_type,
                        sunlight_envelope=sunlight_envelope,
                        pnu=job.pnu or None,
                        job_options=job_options,
                    )

                if event_type in ("complete", "error", "cancelled"):
                    # Save/update before yielding the terminal event. EventSource
                    # clients commonly close as soon as they receive "complete";
                    # doing this after yield can skip persistence on disconnect.
                    if event_type == "complete":
                        save_algo = "per_design" if (algorithm == "all" or maas_mode) else algorithm
                        save_outputs = job.job_spec.get("outputs")
                        if algorithm == "all" or maas_mode:
                            save_outputs = list(algo_specs.values())[0].get("outputs")
                        _save_final_results(
                            job,
                            client_event if maas_mode else event,
                            site_polygon,
                            site_area_m2,
                            building_type,
                            save_algo,
                            outputs_def=save_outputs,
                            enable_repair=True,
                            sunlight_envelope=sunlight_envelope,
                        )
                        update_job_status(
                            job_id, "complete",
                            generation_count=event.get("generations", 0),
                            completed_at=timezone.now(),
                        )
                    elif event_type == "error":
                        update_job_status(
                            job_id, "failed",
                            error=event.get("message", "Unknown error"),
                        )
                    yield f"event: {event_type}\ndata: {json.dumps(client_event, default=str)}\n\n"
                    break

                yield f"event: {event_type}\ndata: {json.dumps(client_event, default=str)}\n\n"

                # Update generation count (throttled to every 10th)
                if event_type == "generation" and gen_num % 10 == 0:
                    update_job_status(
                        job_id, "running",
                        generation_count=gen_num,
                    )

        except GeneratorExit:
            runner.cancel()
        finally:
            _active_runners.pop(str(job_id), None)

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@require_http_methods(["POST"])
def run_job(request, job_id):
    """POST /design/jobs/<id>/run/ — start optimization without holding SSE open.

    This exists for browser automation/dev E2E where a long-lived SSE/fetch stream
    can block page evaluation. Normal UI clients should keep using job_stream.
    """
    try:
        job = OptimizationJob.objects.get(id=job_id)
    except OptimizationJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    if job.status in ("running", "complete", "failed", "cancelled"):
        return JsonResponse({"id": str(job.id), "status": job.status}, status=202)

    if str(job_id) in _active_runners:
        return JsonResponse({"id": str(job.id), "status": "running"}, status=202)

    site_polygon = geojson_to_polygon(job.site_polygon)
    site_area_m2 = job.site_area_m2 or 0
    job_options = job.job_spec.get("options", {})
    building_type = job_options.get("building_type", "공동주택")
    algorithm = job_options.get("algorithm", "additive")
    sunlight_envelope = _precompute_sunlight_envelope(job)
    event_queue = queue.Queue()
    maas_mode = algorithm == "maas_legal_envelope"

    if algorithm == "all" or maas_mode:
        from design.services.constraint_bridge import ALL_ALGORITHMS, build_default_job_spec as build_spec
        constraints = job.constraints or []
        base_options = job.job_spec.get("options", {})
        budget_options = _all_mode_budget_options(base_options)
        algo_specs = {}
        evaluate_fns = {}
        for algo in ALL_ALGORITHMS:
            spec = build_spec(site_area_m2, constraints, building_type, algo)
            spec["options"].update(base_options)
            spec["options"].update(budget_options)
            spec["options"]["algorithm"] = algo
            algo_specs[algo] = spec

            def make_eval(a, outputs_def):
                def fn(designs):
                    return evaluate_designs(
                        designs, site_polygon, site_area_m2,
                        outputs_def, building_type, a,
                        enable_repair=True,
                        sunlight_envelope=sunlight_envelope,
                    )
                return fn
            evaluate_fns[algo] = make_eval(algo, spec.get("outputs"))
        runner = MultiAlgoRunner(algo_specs, evaluate_fns, event_queue)
    else:
        algo_specs = None

        def evaluate_fn(designs):
            return evaluate_designs(
                designs, site_polygon, site_area_m2,
                job.job_spec.get("outputs"), building_type, algorithm,
                enable_repair=True,
                sunlight_envelope=sunlight_envelope,
            )
        runner = JobRunner(job.job_spec, evaluate_fn, event_queue)

    _active_runners[str(job_id)] = runner
    update_job_status(job_id, "running")

    def run_and_persist():
        terminal_seen = False
        try:
            runner_thread = threading.Thread(target=runner.run, daemon=True)
            runner_thread.start()
            while True:
                try:
                    event = event_queue.get(timeout=1.0)
                except queue.Empty:
                    if not runner_thread.is_alive():
                        if not terminal_seen:
                            update_job_status(
                                job_id,
                                "failed",
                                error="Optimization ended without a terminal event",
                            )
                        break
                    continue

                event_type = event.get("type", "update")
                gen_num = event.get("generation", 0)
                if event_type == "generation" and gen_num % 10 == 0:
                    update_job_status(job_id, "running", generation_count=gen_num)

                if event_type in ("complete", "error", "cancelled"):
                    terminal_seen = True
                    if event_type == "complete":
                        save_algo = "per_design" if (algorithm == "all" or maas_mode) else algorithm
                        save_outputs = job.job_spec.get("outputs")
                        if algorithm == "all" or maas_mode:
                            save_outputs = list(algo_specs.values())[0].get("outputs")
                        render_algo = "per_design" if (algorithm == "all" or maas_mode) else algorithm
                        _enrich_event_geojson(
                            event,
                            site_polygon,
                            site_area_m2,
                            building_type,
                            render_algo,
                            outputs_def=save_outputs,
                            enable_repair=True,
                            sunlight_envelope=sunlight_envelope,
                        )
                        client_event = event
                        if maas_mode:
                            client_event = _maas_client_event(
                                event,
                                site_polygon_geojson=job.site_polygon,
                                constraints=job.constraints or [],
                                building_type=building_type,
                                sunlight_envelope=sunlight_envelope,
                                pnu=job.pnu or None,
                                job_options=job_options,
                            )
                        _save_final_results(
                            job,
                            client_event,
                            site_polygon,
                            site_area_m2,
                            building_type,
                            save_algo,
                            outputs_def=save_outputs,
                            enable_repair=True,
                            sunlight_envelope=sunlight_envelope,
                        )
                        update_job_status(
                            job_id, "complete",
                            generation_count=event.get("generations", 0),
                            completed_at=timezone.now(),
                        )
                    elif event_type == "error":
                        update_job_status(job_id, "failed", error=event.get("message", "Unknown error"))
                    else:
                        update_job_status(job_id, "cancelled")
                    break
        finally:
            _active_runners.pop(str(job_id), None)

    threading.Thread(target=run_and_persist, daemon=True).start()
    return JsonResponse({"id": str(job.id), "status": "running"}, status=202)


def _enrich_event_geojson(event, site_polygon, site_area_m2,
                          building_type="공동주택", algorithm="additive",
                          *,
                          outputs_def=None,
                          enable_repair: bool = False,
                          sunlight_envelope: dict | None = None):
    """Add best_geojson and pareto_geojson to SSE events for 3D visualization.

    When algorithm="per_design", each design dict must have an "algorithm" key.
    """
    def _algo_for(d: dict) -> str:
        if algorithm == "per_design":
            return d.get("algorithm", "additive")
        return algorithm

    best = event.get("best")
    if best and best.get("inputs"):
        try:
            a = _algo_for(best)
            feat = design_to_geojson(best["inputs"], site_polygon, site_area_m2,
                                     building_type, a,
                                     enable_repair=enable_repair,
                                     outputs_def=outputs_def,
                                     sunlight_envelope=sunlight_envelope)
            if feat:
                feat["properties"]["design_id"] = best.get("id")
                feat["properties"]["design_uid"] = best.get("uid")
                feat["properties"]["algorithm"] = a
                event["best_geojson"] = feat
        except Exception:
            pass

    pareto = event.get("pareto_front", [])
    if pareto:
        geojson_list = []
        for d in pareto:
            if not d.get("inputs"):
                continue
            try:
                a = _algo_for(d)
                feat = design_to_geojson(d["inputs"], site_polygon, site_area_m2,
                                         building_type, a,
                                         enable_repair=enable_repair,
                                         outputs_def=outputs_def,
                                         sunlight_envelope=sunlight_envelope)
                if feat:
                    feat["properties"]["design_id"] = d.get("id")
                    feat["properties"]["design_uid"] = d.get("uid")
                    feat["properties"]["objectives"] = d.get("objectives", [])
                    feat["properties"]["algorithm"] = a
                    geojson_list.append(feat)
            except Exception:
                pass
        if geojson_list:
            event["pareto_geojson"] = geojson_list


def _maas_design_from_feature(feature: dict, index: int, generation: int) -> dict:
    props = feature.get("properties", {}) or {}
    floor_area = float(props.get("floor_area") or 0.0)
    open_pct = float(props.get("open_pct") or max(0.0, 100.0 - float(props.get("bcr") or 0.0)))
    maas_score = float(props.get("maas_score") or 0.0)
    variant_id = props.get("variant_id") or f"maas_{index + 1:02d}"
    design_id = 900000 + index
    return {
        "id": design_id,
        "uid": f"maas:{variant_id}",
        "generation": generation,
        "parents": [None, None],
        "feasible": True,
        "inputs": [],
        "objectives": [floor_area, open_pct],
        "penalty": 0.0,
        "rank": maas_score,
        "elite": 1,
        "algorithm": "maas_legal_envelope",
    }


def _maas_client_event(
    event: dict,
    *,
    site_polygon_geojson: dict,
    constraints: list[dict],
    building_type: str,
    sunlight_envelope: dict | None = None,
    pnu: str | None = None,
    job_options: dict | None = None,
) -> dict:
    """Replace the final client Pareto front with legal-envelope MAAS variants.

    The optimization runner still uses the legacy 10 algorithms as a seed
    search. The user-facing MAAS mode must not expose those raw repaired boxes
    as the final answer; it exposes floor-by-floor legal envelope variants.
    """
    seed_features = event.get("pareto_geojson") or []
    seed = event.get("best_geojson") or (seed_features[0] if seed_features else None)
    if not seed:
        return event

    try:
        result = generate_legal_mass_variants(
            mass_geojson=seed,
            site_polygon_geojson=site_polygon_geojson,
            constraints=constraints,
            building_type=building_type,
            max_variants=18,
            sunlight_envelope=sunlight_envelope,
            pnu=pnu,
            parking_options=_parking_options_from_job_options(job_options, site_polygon_geojson=site_polygon_geojson),
        )
        features = result.get("feature_collection", {}).get("features", []) or []
    except Exception as exc:
        logger.warning(f"MAAS client event generation failed: {exc}")
        return event

    if not features:
        return event

    generation = int(event.get("generations") or event.get("generation") or 0)
    pareto_front = []
    pareto_geojson = []
    for idx, feature in enumerate(features):
        design = _maas_design_from_feature(feature, idx, generation)
        feature.setdefault("properties", {})
        feature["properties"]["design_id"] = design["id"]
        feature["properties"]["design_uid"] = design["uid"]
        feature["properties"]["objectives"] = design["objectives"]
        feature["properties"]["algorithm"] = "maas_legal_envelope"
        pareto_front.append(design)
        pareto_geojson.append(feature)

    def parking_candidate_score(item):
        idx, feature = item
        props = feature.get("properties") if isinstance(feature, dict) else {}
        precheck = props.get("parking_precheck") if isinstance(props, dict) else {}
        layout = precheck.get("layout_candidate") if isinstance(precheck, dict) else {}
        if not isinstance(layout, dict):
            return (0, 0, 0, 0, 0, 0, -idx)
        status = str(layout.get("status") or "")
        adjacency = layout.get("adjacency") if isinstance(layout.get("adjacency"), dict) else {}
        turning = layout.get("turning_clearance") if isinstance(layout.get("turning_clearance"), dict) else {}
        grid = layout.get("grid_solver") if isinstance(layout.get("grid_solver"), dict) else {}
        required = int(layout.get("required_spaces") or 0)
        provided = int(layout.get("provided_spaces") or 0)
        frontage = int(turning.get("frontage_connected_stalls") or 0)
        return (
            1 if required > 0 and provided > 0 else 0,
            1 if status == "pass" else 0,
            1 if provided >= required else 0,
            1 if required <= 1 or adjacency.get("contiguous_ok") else 0,
            1 if grid.get("entrance_verified") else 0,
            frontage,
            -idx,
        )

    best_idx = max(range(len(pareto_geojson)), key=lambda idx: parking_candidate_score((idx, pareto_geojson[idx])))
    client_event = dict(event)
    client_event["pareto_front"] = pareto_front
    client_event["pareto_geojson"] = pareto_geojson
    client_event["best"] = pareto_front[best_idx]
    client_event["best_geojson"] = pareto_geojson[best_idx]
    client_event["pareto_count"] = len(pareto_front)
    client_event["maas_result"] = {
        "mode": result.get("mode"),
        "algorithm": result.get("algorithm"),
        "constraints": result.get("constraints"),
        "rejected_count": len(result.get("rejected") or []),
        "notes": result.get("notes") or [],
    }
    return client_event


def _parking_options_from_job_options(job_options: dict | None, *, site_polygon_geojson: dict | None = None) -> dict:
    options = job_options or {}
    result = {}
    for key in ("parking_rule_id", "parking_metric", "parking_metric_value"):
        if options.get(key) is not None:
            result[key] = options.get(key)
    road_context = options.get("parking_road_context")
    if isinstance(road_context, dict):
        result["road_context"] = road_context
    elif isinstance(site_polygon_geojson, dict):
        inferred = _infer_parking_road_context(site_polygon_geojson)
        if inferred:
            result["road_context"] = inferred
    return result


def _infer_parking_road_context(site_polygon_geojson: dict) -> dict | None:
    try:
        from land.services import road_frontage
        roads_result = road_frontage.fetch_neighbor_roads(site_polygon_geojson)
        road_frontages = roads_result.get("roads") if isinstance(roads_result, dict) else None
    except Exception:
        return None
    if not isinstance(road_frontages, list) or not road_frontages:
        return None
    widths = []
    for road in road_frontages:
        if not isinstance(road, dict):
            continue
        try:
            width = float(road.get("roadWidthM") or road.get("road_width_m") or 0.0)
        except (TypeError, ValueError):
            width = 0.0
        if width > 0:
            widths.append(width)
    return {
        "road_width_m": max(widths) if widths else None,
        "road_frontages": [
            {
                "geometry": road.get("geometry"),
                "roadWidthM": road.get("roadWidthM") or road.get("road_width_m"),
                "sharedEdge": road.get("sharedEdge") or road.get("shared_edge"),
                "roadCenterline": road.get("roadCenterline") or road.get("road_centerline"),
                "landCategory": road.get("landCategory") or road.get("land_category"),
            }
            for road in road_frontages
            if isinstance(road, dict)
        ][:5],
    }


def _save_final_results(job, event, site_polygon, site_area_m2,
                        building_type="공동주택", algorithm="additive",
                        *,
                        outputs_def=None,
                        enable_repair: bool = False,
                        sunlight_envelope: dict | None = None):
    """Save Pareto-optimal designs to database."""
    pareto = event.get("pareto_front", [])
    geojson_by_uid = {}
    geojson_by_id = {}
    for feature in event.get("pareto_geojson", []) or []:
        props = feature.get("properties", {}) or {}
        if props.get("design_uid") is not None:
            geojson_by_uid[str(props.get("design_uid"))] = feature
        if props.get("design_id") is not None:
            geojson_by_id[str(props.get("design_id"))] = feature
    designs_to_save = []
    for d in pareto:
        a = d.get("algorithm", algorithm) if algorithm == "per_design" else algorithm
        mass_geojson = (
            geojson_by_uid.get(str(d.get("uid")))
            or geojson_by_id.get(str(d.get("id")))
        )
        if mass_geojson is None and d.get("inputs"):
            mass_geojson = design_to_geojson(d.get("inputs", []), site_polygon, site_area_m2,
                                             building_type, a,
                                             enable_repair=enable_repair,
                                             outputs_def=outputs_def,
                                             sunlight_envelope=sunlight_envelope)
        designs_to_save.append({
            "generation": d.get("generation", 0),
            "design_id": d.get("id", 0),
            "inputs": d.get("inputs", []),
            "outputs": {
                "objectives": d.get("objectives", []),
                "penalty": d.get("penalty", 0),
            },
            "ranking": 1.0,
            "crowding_distance": 0.0,
            "is_feasible": d.get("feasible", True),
            "is_pareto_optimal": True,
            "mass_geojson": mass_geojson,
        })
    save_results(job, designs_to_save)


@require_http_methods(["GET"])
def job_results(request, job_id):
    """GET /design/jobs/<id>/results/ — Get all results for a job."""
    try:
        job = OptimizationJob.objects.get(id=job_id)
    except OptimizationJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    designs = job.results.all()
    pareto = job.results.filter(is_pareto_optimal=True)

    return JsonResponse({
        "job": format_job_response(job),
        "total_designs": designs.count(),
        "pareto_front": format_pareto_front(pareto),
        "designs": [format_design_response(d) for d in designs],
    })


@require_http_methods(["GET"])
def design_detail(request, job_id, design_id):
    """GET /design/jobs/<id>/results/<design_id>/ — Get single design."""
    try:
        design = DesignResult.objects.get(job_id=job_id, design_id=design_id)
    except DesignResult.DoesNotExist:
        return JsonResponse({"error": "Design not found"}, status=404)

    return JsonResponse(format_design_response(design))


@require_http_methods(["GET"])
def design_evidence(request, job_id, design_id):
    """GET /design/jobs/<id>/results/<design_id>/evidence/ — canonical MAAS evidence bundle."""
    try:
        design = DesignResult.objects.select_related("job").get(job_id=job_id, design_id=design_id)
    except DesignResult.DoesNotExist:
        return JsonResponse({"error": "Design not found"}, status=404)

    return JsonResponse(build_maas_evidence_bundle(job=design.job, design=design))


@csrf_exempt
@require_http_methods(["POST"])
def design_aesthetic(request, job_id, design_id):
    """POST /design/jobs/<id>/results/<design_id>/aesthetic/ — render locked mass then call image provider."""
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    try:
        design = DesignResult.objects.select_related("job").get(job_id=job_id, design_id=design_id)
    except DesignResult.DoesNotExist:
        return JsonResponse({"error": "Design not found"}, status=404)

    provider = body.get("provider") if isinstance(body.get("provider"), str) else "placeholder"
    if provider not in {"placeholder", "gpt-image", "nano-banana"}:
        return JsonResponse({"error": "provider must be one of: placeholder, gpt-image, nano-banana"}, status=400)

    style = body.get("style") if isinstance(body.get("style"), str) else None
    evidence = build_maas_evidence_bundle(job=design.job, design=design)
    media_root = Path(settings.BASE_DIR) / "media" / "maas" / "aesthetic"
    renderer = MultiViewReferencePackRenderer(media_root / "references")
    adapter = None
    if provider == "gpt-image":
        adapter = OpenAIImageAdapter(output_dir=media_root / "generated")
    elif provider == "nano-banana":
        adapter = NanoBananaAdapter(output_dir=media_root / "generated")

    try:
        result = build_aesthetic_pipeline_result(
            evidence,
            provider=provider,
            style=style,
            renderer=renderer,
            adapter=adapter,
            attach_to_evidence=bool(body.get("attach_to_evidence", True)),
        )
    except Exception as e:
        return JsonResponse({"error": f"MAAS aesthetic generation failed: {e}"}, status=400)
    return JsonResponse(_with_aesthetic_asset_urls(result))


@require_http_methods(["GET"])
def maas_aesthetic_asset(request, asset_path):
    """Serve local MAAS aesthetic reference/generated assets in development."""
    media_root = (Path(settings.BASE_DIR) / "media" / "maas" / "aesthetic").resolve()
    target = (media_root / asset_path).resolve()
    if media_root not in target.parents and target != media_root:
        raise Http404("Asset not found")
    if not target.exists() or not target.is_file():
        raise Http404("Asset not found")
    return FileResponse(target.open("rb"), content_type=_image_content_type(target))


def _image_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gltf":
        return "model/gltf+json"
    if suffix == ".json":
        return "application/json"
    return "image/png"


def _with_aesthetic_asset_urls(result: dict) -> dict:
    media_root = (Path(settings.BASE_DIR) / "media" / "maas" / "aesthetic").resolve()

    def public_url(uri):
        if not isinstance(uri, str):
            return None
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
        try:
            path = Path(uri).resolve()
        except Exception:
            return None
        if media_root in path.parents or path == media_root:
            rel = path.relative_to(media_root).as_posix()
            return f"/design/maas/aesthetic-assets/{rel}"
        return None

    reference = result.get("reference")
    if isinstance(reference, dict):
        url = public_url(reference.get("uri"))
        if url:
            reference["url"] = url
        _add_nested_aesthetic_urls(reference.get("metadata"), public_url)

    provider_result = result.get("provider_result")
    if isinstance(provider_result, dict):
        for asset in provider_result.get("assets") or []:
            if isinstance(asset, dict):
                url = public_url(asset.get("uri"))
                if url:
                    asset["url"] = url

    evidence = result.get("evidence")
    aesthetic_assets = ((evidence or {}).get("assets") or {}).get("aesthetic") if isinstance(evidence, dict) else None
    if isinstance(aesthetic_assets, list):
        for item in aesthetic_assets:
            if not isinstance(item, dict):
                continue
            ref = item.get("reference")
            if isinstance(ref, dict):
                url = public_url(ref.get("uri"))
                if url:
                    ref["url"] = url
            provider = item.get("provider_result")
            if isinstance(provider, dict):
                for asset in provider.get("assets") or []:
                    if isinstance(asset, dict):
                        url = public_url(asset.get("uri"))
                        if url:
                            asset["url"] = url
    return result


def _add_nested_aesthetic_urls(value, public_url):
    if isinstance(value, dict):
        url = public_url(value.get("uri"))
        if url:
            value["url"] = url
        for child in value.values():
            _add_nested_aesthetic_urls(child, public_url)
    elif isinstance(value, list):
        for child in value:
            _add_nested_aesthetic_urls(child, public_url)


@csrf_exempt
@require_http_methods(["POST"])
def interactive_patch(request):
    """POST /design/interactive/patch/ — Dry-run natural language mass edit plan."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    user_text = body.get("message", "")
    selected_design = body.get("selected_design")
    mass_geojson = body.get("mass_geojson")
    constraints = body.get("constraints", [])

    if not isinstance(user_text, str) or not user_text.strip():
        return JsonResponse({"error": "message is required"}, status=400)

    plan = build_interactive_patch_plan(
        user_text=user_text,
        selected_design=selected_design if isinstance(selected_design, dict) else None,
        mass_geojson=mass_geojson if isinstance(mass_geojson, dict) else None,
        constraints=constraints if isinstance(constraints, list) else [],
    )
    return JsonResponse(plan)


@csrf_exempt
@require_http_methods(["POST"])
def interactive_preview(request):
    """POST /design/interactive/preview/ — Apply dry-run patch candidates to geometry."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    patch_plan = body.get("patch_plan")
    selected_design = body.get("selected_design")
    site_polygon = body.get("site_polygon")
    site_area_m2 = body.get("site_area_m2")
    constraints = body.get("constraints", [])
    building_type = body.get("building_type", "공동주택")
    algorithm = body.get("algorithm")

    if not isinstance(patch_plan, dict):
        return JsonResponse({"error": "patch_plan is required"}, status=400)
    if not isinstance(selected_design, dict):
        return JsonResponse({"error": "selected_design is required"}, status=400)
    if not isinstance(site_polygon, dict):
        return JsonResponse({"error": "site_polygon is required"}, status=400)
    try:
        site_area_m2 = float(site_area_m2)
    except (TypeError, ValueError):
        return JsonResponse({"error": "site_area_m2 is required"}, status=400)

    result = build_interactive_preview(
        patch_plan=patch_plan,
        selected_design=selected_design,
        site_polygon_geojson=site_polygon,
        site_area_m2=site_area_m2,
        constraints=constraints if isinstance(constraints, list) else [],
        building_type=building_type if isinstance(building_type, str) else "공동주택",
        algorithm=algorithm if isinstance(algorithm, str) else None,
    )
    if "error" in result:
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def interactive_operation(request):
    """POST /design/interactive/operation/ — Apply push/pull-style mass operation."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    mass_geojson = body.get("mass_geojson")
    site_polygon = body.get("site_polygon")
    operation = body.get("operation")
    if not isinstance(mass_geojson, dict):
        return JsonResponse({"error": "mass_geojson is required"}, status=400)
    if not isinstance(site_polygon, dict):
        return JsonResponse({"error": "site_polygon is required"}, status=400)
    if not isinstance(operation, dict):
        return JsonResponse({"error": "operation is required"}, status=400)

    try:
        result = apply_mass_operation(
            mass_geojson=mass_geojson,
            site_polygon_geojson=site_polygon,
            operation=operation,
            constraints=body.get("constraints") if isinstance(body.get("constraints"), list) else [],
            building_type=body.get("building_type") if isinstance(body.get("building_type"), str) else "공동주택",
            sunlight_envelope=body.get("sunlight_envelope") if isinstance(body.get("sunlight_envelope"), dict) else None,
            setback_geometries=body.get("setback_geometries") if isinstance(body.get("setback_geometries"), dict) else None,
        )
    except Exception as e:
        return JsonResponse({"error": f"Interactive operation failed: {e}"}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def maas_export_scad(request):
    """POST /design/maas/export-scad/ — Export ARR mass GeoJSON to OpenSCAD."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    mass_geojson = body.get("mass_geojson")
    name = body.get("name")
    if not isinstance(mass_geojson, dict):
        return JsonResponse({"error": "mass_geojson is required"}, status=400)

    try:
        result = export_mass_geojson_to_scad(
            mass_geojson,
            name=name if isinstance(name, str) else None,
        )
    except Exception as e:
        return JsonResponse({"error": f"MAAS SCAD export failed: {e}"}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def maas_legal_variants(request):
    """POST /design/maas/legal-variants/ — Generate legal/diverse MAAS mass variants."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    mass_geojson = body.get("mass_geojson")
    site_polygon = body.get("site_polygon")
    if not isinstance(mass_geojson, dict):
        return JsonResponse({"error": "mass_geojson is required"}, status=400)
    if not isinstance(site_polygon, dict):
        return JsonResponse({"error": "site_polygon is required"}, status=400)

    try:
        result = generate_legal_mass_variants(
            mass_geojson=mass_geojson,
            site_polygon_geojson=site_polygon,
            constraints=body.get("constraints") if isinstance(body.get("constraints"), list) else [],
            building_type=body.get("building_type") if isinstance(body.get("building_type"), str) else "공동주택",
            max_variants=int(body.get("max_variants") or 6),
            sunlight_envelope=body.get("sunlight_envelope") if isinstance(body.get("sunlight_envelope"), dict) else None,
            setback_geometries=body.get("setback_geometries") if isinstance(body.get("setback_geometries"), dict) else None,
        )
    except Exception as e:
        return JsonResponse({"error": f"MAAS legal variants failed: {e}"}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(["POST"])
def site_boundary(request):
    """POST /design/site-boundary/ — Get parcel polygon from PNU."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    pnu = (body.get("pnu") or "").strip()
    if not pnu:
        return JsonResponse({"error": "pnu is required"}, status=400)

    # 19자리 숫자 아니면 주소로 간주 → Vworld geocode로 PNU 자동 추출
    # (사용자 편의: ControlPanel placeholder "PNU 코드 (19자리) 또는 주소")
    if not (pnu.isdigit() and len(pnu) == 19):
        try:
            from land.services.pnu_resolver import resolve_address
            resolved = resolve_address(pnu)
            if resolved and resolved.get("pnu"):
                pnu = resolved["pnu"]
            else:
                return JsonResponse(
                    {"error": f"주소 '{pnu}' → PNU 변환 실패"}, status=404
                )
        except Exception as e:
            return JsonResponse(
                {"error": f"주소 변환 오류: {e}"}, status=500
            )

    geometry = fetch_parcel_boundary(pnu)
    if not geometry:
        return JsonResponse({"error": f"No boundary found for PNU {pnu}"}, status=404)

    # Validate the polygon
    polygon = geojson_to_polygon(geometry)
    validation = validate_site(polygon)

    return JsonResponse({
        "pnu": pnu,
        "geometry": geometry,
        "area_m2": validation["area_m2"],
        "valid": validation["valid"],
        "errors": validation["errors"],
    })


@csrf_exempt
@require_http_methods(["POST"])
def auto_constraints(request):
    """POST /design/auto-constraints/ — Generate constraints from land regulations."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    pnu = body.get("pnu", "")
    zones = body.get("zones", [])
    address = body.get("address", "")
    building_type = body.get("building_type", "")
    include_law_articles = bool(body.get("include_law_articles", True))

    if not pnu and not zones and not address:
        return JsonResponse({"error": "pnu, zones, or address required"}, status=400)

    # Call land/analyze internally
    try:
        from land.services import regulation_calculator
        from land.services import zoning_mapper, land_api, road_frontage

        # If PNU given but no zones, look up zones via Vworld Data API
        if not zones and pnu:
            land_info = land_api.get_land_use_info(pnu)
            zones = land_info.get("zones", [])

        # resolve_limits handles exact matching + strictest-zone logic
        limits = zoning_mapper.resolve_limits(zones) if zones else {}
        zone_names = [z["zone_name"] for z in limits.get("zones", [])] if limits else zones

        reg = regulation_calculator.calculate_all(
            zone_names,
            use_llm_extraction=include_law_articles,
        )

        daylight_multiplier = _daylight_diagonal_multiplier(zone_names, building_type)
        if daylight_multiplier is not None:
            reg["daylight_diagonal_multiplier"] = daylight_multiplier

        constraints = regulations_to_constraints(reg)

        # Query law articles for building-type-specific regulations
        law_articles = {}
        if include_law_articles and building_type and zone_names:
            try:
                from land.services.law_enricher import search_for_building_type
                law_result = search_for_building_type(building_type, zone_names)
                law_articles = law_result
            except Exception as e:
                logger.warning(f"Law search for building type failed: {e}")
                law_articles = {"articles": [], "total_count": 0,
                                "errors": [str(e)]}

        # Compute setback geometry for map visualization
        setback_geometries = {}
        site_geojson = body.get("site_polygon")
        if site_geojson:
            try:
                from land.services.setback_geometry import compute_setback_lines
                from land import config as land_config
                road_frontages = []
                neighbor_parcels = []
                try:
                    roads_result = road_frontage.fetch_neighbor_roads(site_geojson)
                    if roads_result.get("success"):
                        road_frontages = roads_result.get("roads") or []
                except Exception as e:
                    logger.warning(f"road frontage lookup failed: {e}")
                try:
                    neighbors_result = road_frontage.fetch_neighbor_parcels(site_geojson)
                    if neighbors_result.get("success"):
                        neighbor_parcels = neighbors_result.get("neighbors") or []
                except Exception as e:
                    logger.warning(f"neighbor parcel lookup failed: {e}")

                lines = compute_setback_lines(
                    site_geojson, reg,
                    compute_datum=land_config.ENABLE_DATUM_ELEVATION,
                    road_frontages=road_frontages,
                    neighbor_parcels=neighbor_parcels,
                )
                adj_m = reg.get("adjacent_setback_m") or 0.5
                sunlight_m = 1.5
                if lines.get("buildable_area"):
                    setback_geometries["buildable_area"] = {
                        "geometry": lines["buildable_area"],
                        "distance_m": float(adj_m),
                        "label": f"건축가능영역 (이격 {adj_m}m)",
                    }
                if lines.get("north_setback"):
                    setback_geometries["north_setback"] = {
                        "geometry": lines["north_setback"],
                        "distance_m": sunlight_m,
                        "label": f"정북 일조사선 {sunlight_m}m",
                    }
                if lines.get("adjacent_setback"):
                    setback_geometries["adjacent_setback"] = {
                        "geometry": lines["adjacent_setback"],
                        "distance_m": float(adj_m),
                        "label": f"인접대지 이격 {adj_m}m",
                    }
                road_m = 0.0
                if lines.get("road_setback"):
                    road_setback_meta = lines.get("road_setback") or {}
                    road_m = road_setback_meta.get("setback_m")
                    if road_m is None:
                        road_m = reg.get("building_line_setback_m") or 1.0
                if lines.get("road_setback"):
                    setback_geometries["road_setback"] = {
                        "geometry": lines["road_setback"],
                        "distance_m": float(road_m),
                        "label": f"건축선 후퇴 {road_m}m",
                    }
                cutoff_val = reg.get("corner_cutoff_m") or 3.0
                if lines.get("corner_cutoff"):
                    setback_geometries["corner_cutoff"] = {
                        "geometry": lines["corner_cutoff"],
                        "distance_m": float(cutoff_val),
                        "label": f"가각전제 {cutoff_val}m",
                    }
                desig_m = reg.get("building_designation_setback_m")
                if lines.get("building_designation_line"):
                    setback_geometries["building_designation_line"] = {
                        "geometry": lines["building_designation_line"],
                        "distance_m": float(desig_m) if desig_m else 2.0,
                        "label": f"건축지정선 {desig_m or 2.0}m",
                    }
                if lines.get("sunlight_envelope"):
                    setback_geometries["sunlight_envelope"] = lines["sunlight_envelope"]
                if lines.get("daylight_diagonal_envelope"):
                    setback_geometries["daylight_diagonal_envelope"] = lines["daylight_diagonal_envelope"]
                # Phase 2D: datum_result는 envelope과 독립적으로 노출
                # (정북일조 미적용 zone(상업 등)에서도 datum 표시 가능)
                if lines.get("datum_result"):
                    setback_geometries["datum_result"] = lines["datum_result"]
                    datum = lines["datum_result"]
                    road_widths = [
                        float(r.get("roadWidthM") or r.get("road_width_m") or 0.0)
                        for r in road_frontages
                        if float(r.get("roadWidthM") or r.get("road_width_m") or 0.0) > 0
                    ]
                    if road_widths:
                        road_width = max(road_widths)
                        road_diag_mult = reg.get("road_diagonal_multiplier")
                        setback_geometries["front_road_diagonal_profile"] = {
                            "road_width_m": road_width,
                            "slope": float(road_diag_mult or 1.5),
                            "applies": road_diag_mult is not None,
                            "law_basis": reg.get("road_diagonal_article") or "건축법 시행령 §82 도로사선 기준 참고",
                            "note": reg.get("road_diagonal_rule") or "현행 도로사선은 삭제/가로구역별 높이제한으로 대체. 1:1.5는 참고 단면.",
                            "road_datum_m": datum.get("road_datum_m"),
                            "parcel_datum_m": datum.get("parcel_datum_m"),
                        }
                    setback_geometries["road_frontages"] = [
                        {
                            "geometry": r.get("geometry"),
                            "roadWidthM": float(r.get("roadWidthM") or r.get("road_width_m") or 0.0),
                            "sharedEdge": r.get("sharedEdge") or r.get("shared_edge"),
                            "roadCenterline": r.get("roadCenterline") or r.get("road_centerline"),
                            "landCategory": r.get("landCategory") or r.get("land_category"),
                        }
                        for r in road_frontages
                    ][:5]
                    setback_geometries["neighbor_parcels"] = [
                        {
                            "geometry": n.get("geometry"),
                            "sharedEdge": n.get("sharedEdge") or n.get("shared_edge"),
                            "landCategory": n.get("landCategory") or n.get("land_category"),
                            "pnu": n.get("pnu"),
                        }
                        for n in neighbor_parcels
                    ][:10]
            except Exception as e:
                logger.warning(f"setback_geometry failed, falling back: {e}")
                # Fallback: simple buffer
                setback_m = reg.get("adjacent_setback_m")
                if setback_m:
                    geom = compute_setback_geometry(site_geojson, float(setback_m))
                    if geom:
                        setback_geometries["adjacent_setback"] = {
                            "geometry": geom,
                            "distance_m": float(setback_m),
                            "label": f"인접대지 이격 {setback_m}m",
                        }

        return JsonResponse({
            "zones": zone_names,
            "regulations": {
                "bcr_pct": reg.get("bcr_pct"),
                "far_pct": reg.get("far_pct"),
                "height_limit_m": reg.get("height_limit_m"),
                "adjacent_setback_m": reg.get("adjacent_setback_m"),
                "sunlight_applies": reg.get("sunlight_applies"),
                "sunlight_rules": reg.get("sunlight_rules"),
                "corner_cutoff_required": reg.get("corner_cutoff_required"),
                "road_diagonal_multiplier": reg.get("road_diagonal_multiplier"),
                "road_diagonal_rule": reg.get("road_diagonal_rule"),
                "road_diagonal_article": reg.get("road_diagonal_article"),
                "daylight_diagonal_multiplier": reg.get("daylight_diagonal_multiplier"),
                "zone_category": reg.get("zone_category"),
            },
            "constraints": constraints,
            "setback_geometries": setback_geometries,
            "law_articles": law_articles,
            "building_type": building_type,
        })

    except ImportError:
        logger.warning("land app not available for constraint generation")
        return JsonResponse({
            "zones": zones,
            "regulations": {},
            "constraints": [],
            "warning": "land app not available",
        })
    except Exception as e:
        logger.error(f"Auto-constraints failed: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def validate_job(request, job_id):
    """
    POST /design/jobs/<id>/validate/ — Validate designs against building regulations.

    Body: {
        "regulation_result": {bcr_pct, far_pct, height_limit_m, adjacent_setback_m, ...}
    }

    Returns validation results + tightened constraints if violations found.
    """
    try:
        job = OptimizationJob.objects.get(id=job_id)
    except OptimizationJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    regulation_result = body.get("regulation_result", {})
    if not regulation_result:
        return JsonResponse({"error": "regulation_result is required"}, status=400)

    # Get top pareto designs
    pareto_designs = job.results.filter(is_pareto_optimal=True)
    if not pareto_designs.exists():
        return JsonResponse({"error": "No pareto designs found. Run optimization first."}, status=400)

    # Extract metrics from stored design outputs
    designs_metrics = []
    for d in pareto_designs[:5]:
        outputs = d.outputs or {}
        objectives = outputs.get("objectives", [])
        # Map from job_spec output order to named metrics
        output_defs = job.job_spec.get("outputs", [])
        metrics = {}
        for i, obj_def in enumerate(output_defs):
            if i < len(objectives):
                metrics[obj_def["name"]] = objectives[i]
        designs_metrics.append(metrics)

    # Validate
    result = validate_best_designs(designs_metrics, regulation_result)

    # If violations exist, suggest tightened constraints
    tightened = None
    if not result["all_valid"] and result["worst_violations"]:
        current_constraints = list(job.constraints or [])
        tightened = auto_correct_constraints(result["worst_violations"], current_constraints)

    return JsonResponse({
        "job_id": str(job_id),
        "all_valid": result["all_valid"],
        "violations": result["violations"],
        "worst_violations": result["worst_violations"],
        "tightened_constraints": tightened,
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_floor_plan(request):
    """
    POST /design/floor-plan/

    Generate floor plan within a building footprint.

    Body: {
        "footprint_geojson": {GeoJSON Polygon},
        "rooms": [{"name": "Living", "area": 200, "adjacency": ["Entry"]}],
        "cell_size": 3.0,
        "algorithm": "ga" | "subdivision" | "mcts" | "packing" | "graph2plan",
        "options": {"num_generations": 50, "population_size": 30}
    }
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    footprint_geojson = body.get("footprint_geojson")
    rooms = body.get("rooms", [])
    cell_size = body.get("cell_size", 3.0)
    algorithm = body.get("algorithm", "ga")
    options = body.get("options", {})

    if not footprint_geojson:
        return JsonResponse({"error": "footprint_geojson is required"}, status=400)
    if not rooms:
        return JsonResponse({"error": "rooms list is required"}, status=400)

    try:
        from shapely.geometry import shape
        footprint = shape(footprint_geojson)
        if not footprint.is_valid or footprint.is_empty:
            return JsonResponse({"error": "Invalid footprint geometry"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Cannot parse footprint: {e}"}, status=400)

    try:
        if algorithm == "subdivision":
            from design.services.floor_subdivision import subdivide_floor_plan
            result = subdivide_floor_plan(footprint, rooms, cell_size, options)
        elif algorithm == "mcts":
            from design.services.floor_mcts import mcts_floor_plan
            result = mcts_floor_plan(footprint, rooms, cell_size, options)
        elif algorithm == "packing":
            from design.services.floor_packing import packing_floor_plan
            result = packing_floor_plan(footprint, rooms, cell_size, options)
        elif algorithm == "graph2plan":
            from design.services.floor_graph2plan import generate_graph2plan
            result = generate_graph2plan(footprint, rooms, options)
        else:
            result = _ga_floor_plan(footprint, rooms, cell_size, options)
    except Exception as e:
        logger.exception("Floor plan generation failed: %s", e)
        return JsonResponse({"error": f"Generation failed: {e}"}, status=500)

    result["algorithm"] = algorithm
    return JsonResponse(result)


def _ga_floor_plan(footprint, rooms, cell_size, options):
    """GA + Series gene floor plan generation (original algorithm)."""
    from design.services.floor_packer import create_grid, evaluate_floor_plan, assignment_to_geojson
    from design.engine.objects import SSIEAJob

    grid_info = create_grid(footprint, cell_size)
    num_cells = grid_info["rows"] * grid_info["cols"]
    num_rooms = len(rooms)

    num_gen = options.get("num_generations", 50)
    pop_size = options.get("population_size", 30)

    job_spec = {
        "inputs": [{
            "type": "Series",
            "Set length": num_cells,
            "Depth": num_rooms + 1,
            "Mutation rate": 0.3,
        }],
        "outputs": [
            {"name": "adjacency_score", "type": "Objective", "Goal": "Max"},
            {"name": "area_error", "type": "Objective", "Goal": "Min"},
            {"name": "compactness", "type": "Objective", "Goal": "Max"},
        ],
        "options": {
            "Number of generations": num_gen,
            "num_islands": 3,
            "pop_per_island": max(pop_size // 3, 5),
        },
    }

    def evaluate_fn(designs):
        results = []
        for d in designs:
            assignment = d.get_inputs()[0]
            m = evaluate_floor_plan(assignment, grid_info, rooms)
            results.append([m["adjacency_score"], m["area_error"], m["compactness"]])
        return results

    job = SSIEAJob(job_spec)
    job.init_designs()
    while True:
        cont, gen, pop = job.step(evaluate_fn)
        if not cont:
            break

    pareto = job.get_pareto_front()
    results = []
    for d in pareto:
        assignment = d.get_inputs()[0]
        metrics = evaluate_floor_plan(assignment, grid_info, rooms)
        geojson = assignment_to_geojson(assignment, grid_info, rooms)
        results.append({
            "design_id": d.get_id(),
            "metrics": metrics,
            "floor_plan": geojson,
        })

    return {
        "grid_info": {
            "rows": grid_info["rows"],
            "cols": grid_info["cols"],
            "cell_size": grid_info["cell_size"],
            "active_cells": grid_info["active_count"],
        },
        "rooms": rooms,
        "num_results": len(results),
        "results": results,
    }


@csrf_exempt
@require_http_methods(["POST"])
def constraints_visualize(request):
    """POST /design/constraints/visualize/ — site polygon + 법규 한도 → envelope/setback GeoJSON.

    Flexity 광고 스타일: 대지경계선 + 대지 안의 공지(빨간 점선) + 정북 일조 base(녹색 점선) +
    sunlight slope metadata + 법규 한도 라벨.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    site_polygon_geojson = body.get("site_polygon")
    if not site_polygon_geojson:
        return JsonResponse({"error": "site_polygon is required"}, status=400)

    try:
        site_polygon = geojson_to_polygon(site_polygon_geojson)
    except Exception as e:
        return JsonResponse({"error": f"Invalid site_polygon: {e}"}, status=400)

    from design.services.mass_renderer import constraint_envelope_geojson

    kwargs = {
        k: body[k] for k in (
            "bcr_limit_pct", "far_limit_pct", "height_limit_m",
            "adjacent_setback_m", "north_setback_m", "road_setback_m",
            "sunlight_slope", "sunlight_base_height_m",
        ) if k in body
    }

    try:
        result = constraint_envelope_geojson(site_polygon, **kwargs)
    except Exception as e:
        logger.exception("constraint_envelope_geojson failed")
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse(result)
