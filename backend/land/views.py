"""
Land Regulation Analysis API v3

Analyzes land parcels for 41 building regulations:
- Items 1-10 (core): BCR, FAR, height, sunlight, corner cutoff, road diagonal,
  building line, adjacent setback, parking, landscaping
- Items 11-41 (extended): zone-dependent (5), scale-dependent (10), text-only (16)
All with legal article references.
"""

import json
import logging
import queue
import threading
import time

import httpx
import websocket

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from land import config
from land.formatters import format_regulations, build_restrictions
from land.persistence import save_analysis_result, log_query
from land.services import pnu_resolver, zoning_mapper, land_api, law_enricher
from land.services import regulation_calculator, regulation_calculator_ext
from land.services import overlay_resolver
from land.services import road_frontage, setback_geometry

logger = logging.getLogger(__name__)


def _flatten_law_articles(law_articles: dict) -> dict:
    """Flatten nested {query, results} articles into flat list for frontend.

    Backend format: {"articles": [{"query": "...", "results": [item, ...]}]}
    Frontend format: {"articles": [item, ...], "total_count": int}
    """
    nested = law_articles.get("articles", [])
    seen_ids = set()
    flat = []
    for group in nested:
        if isinstance(group, dict) and "results" in group:
            for item in group["results"]:
                hang_id = item.get("hang_id", "")
                if hang_id and hang_id in seen_ids:
                    continue
                seen_ids.add(hang_id)
                flat.append(item)
        else:
            # Already flat item
            flat.append(group)
    return {
        "articles": flat,
        "total_count": len(flat),
        "errors": law_articles.get("errors", []),
    }


@csrf_exempt
@require_http_methods(["POST"])
def analyze(request):
    """
    POST /land/analyze/

    Main analysis endpoint. Accepts PNU, address, or raw zone list.
    Returns 41 building regulations (10 core + 31 extended) with legal article references.

    Body: {
        "input": "1168011200101280003" | "서울시 강남구 ...",
        "input_type": "pnu" | "address" | "raw",
        "zones": ["제1종일반주거지역"],     # required if input_type=raw, optional override
        "include_law": true                 # default true, fetch law articles
    }
    """
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    raw_input = body.get("input", "")
    input_type = body.get("input_type", "pnu")
    manual_zones = body.get("zones", [])
    include_law = body.get("include_law", True)
    parcel_geometry = body.get("geometry")  # GeoJSON from reverse geocode

    # Input validation
    if not isinstance(raw_input, str):
        return JsonResponse({"error": '"input" must be a string'}, status=400)
    if len(raw_input) > 500:
        return JsonResponse({"error": '"input" too long (max 500)'}, status=400)
    if not isinstance(manual_zones, list) or not all(isinstance(z, str) for z in manual_zones):
        return JsonResponse({"error": '"zones" must be a list of strings'}, status=400)

    if not raw_input and not manual_zones:
        return JsonResponse(
            {"error": 'Either "input" or "zones" is required'},
            status=400,
        )

    if input_type not in ("pnu", "address", "raw"):
        return JsonResponse(
            {"error": f'Invalid input_type: {input_type}. Use pnu/address/raw'},
            status=400,
        )

    start = time.time()
    errors = []
    pnu_info = None
    land_info = None
    zone_names = list(manual_zones)

    # Step 1: Resolve PNU
    if input_type == "pnu" and raw_input:
        if not pnu_resolver.validate_pnu(raw_input):
            return JsonResponse(
                {"error": f"Invalid PNU format (expected 19 digits): {raw_input}"},
                status=400,
            )
        pnu_info = pnu_resolver.parse_pnu(raw_input)
    elif input_type == "address" and raw_input:
        result = pnu_resolver.resolve_address(raw_input)
        if not result["success"]:
            errors.append(result["error"])
        else:
            pnu_info = pnu_resolver.parse_pnu(result["pnu"])

    # Step 2: Fetch land use info
    if pnu_info:
        land_info = land_api.get_land_use_info(pnu_info["pnu"])
        if land_info["success"] and land_info["zones"]:
            if not zone_names:
                zone_names = land_info["zones"]
        if not parcel_geometry:
            geom_result = pnu_resolver.fetch_parcel_geometry(pnu_info["pnu"])
            if geom_result.get("success") and geom_result.get("geometry"):
                parcel_geometry = geom_result["geometry"]
            elif geom_result.get("error"):
                errors.append(geom_result["error"])

    # Step 3: No zones → warning
    if not zone_names:
        elapsed_ms = (time.time() - start) * 1000
        log_query(input_type, raw_input, pnu_info, None, land_info, 0, elapsed_ms,
                  error="No zones provided or resolved")
        return JsonResponse({
            "pnu": pnu_info,
            "regulations": None,
            "zone_info": None,
            "land_info": land_info,
            "law_articles": None,
            "restrictions": [],
            "warning": "No zoning zones provided or resolved. "
                       "Pass 'zones' array or wait for data.go.kr API integration.",
        })

    # Steps 4-7: Core analysis (shared with agent_analyze_stream)
    response, reg, analysis_result, analysis_errors = _core_analysis(
        pnu_info, zone_names, land_info, include_law=include_law,
        parcel_geometry=parcel_geometry,
    )
    errors.extend(analysis_errors)

    elapsed_ms = (time.time() - start) * 1000

    law_count = 0
    if response.get("law_articles"):
        law_count = response["law_articles"].get("total_count", 0)

    log_query(
        input_type, raw_input, pnu_info, reg,
        land_info, law_count,
        elapsed_ms, error="; ".join(errors) if errors else "",
        analysis_result=analysis_result,
    )

    if errors:
        response["errors"] = errors

    return JsonResponse(response)


@csrf_exempt
@require_http_methods(["POST"])
def resolve(request):
    """
    POST /land/resolve/

    Resolve address to PNU or validate/parse PNU.

    Body: {"input": "...", "input_type": "pnu" | "address"}
    """
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    raw_input = body.get("input", "")
    input_type = body.get("input_type", "pnu")

    if not raw_input:
        return JsonResponse({"error": '"input" is required'}, status=400)

    if input_type == "pnu":
        if not pnu_resolver.validate_pnu(raw_input):
            return JsonResponse({"error": "Invalid PNU format", "valid": False}, status=400)
        return JsonResponse({
            "valid": True,
            "parsed": pnu_resolver.parse_pnu(raw_input),
        })
    elif input_type == "address":
        result = pnu_resolver.resolve_address(raw_input)
        return JsonResponse(result)
    else:
        return JsonResponse({"error": f"Unknown input_type: {input_type}"}, status=400)


@require_http_methods(["GET"])
def zones(request):
    """
    GET /land/zones/

    Return all zoning zone definitions with BCR/FAR limits.
    """
    all_zones = zoning_mapper.get_all_zones()
    return JsonResponse({"zones": all_zones, "count": len(all_zones)})


@require_http_methods(["GET"])
def map_config(request):
    """
    GET /land/map-config/

    Return Vworld API key and WMS config for 3D map initialization.
    The frontend loads Vworld WebGL 3D script with this key.
    """
    if not config.VWORLD_API_KEY:
        return JsonResponse(
            {
                "error": "VWORLD_API_KEY is not configured",
                "configured": False,
            },
            status=503,
        )
    return JsonResponse({
        "api_key": config.VWORLD_API_KEY,
        "configured": True,
        "wms_layers": "lp_pa_cbnd_bonbun,lp_pa_cbnd_bubun",
    })


@require_http_methods(["GET"])
def elevation_grid(request):
    """
    GET /land/elevation-grid/?lng=&lat=&radius_m=50&n=5

    parcel 중심 기준 n×n 격자 점들의 표고 (Open-Meteo or NGII LiDAR via
    config.ELEVATION_PROVIDER). "주변 몇m 표고" 시각화용.

    Returns:
        {"points": [{"lng": ..., "lat": ..., "elev_m": ...}, ...]}
    """
    import math
    from land.services.datum import elevation_api

    try:
        lng = float(request.GET.get("lng", ""))
        lat = float(request.GET.get("lat", ""))
    except ValueError:
        return JsonResponse({"error": "lng/lat required (float)"}, status=400)

    try:
        radius_m = float(request.GET.get("radius_m", "50"))
        n = int(request.GET.get("n", "5"))
    except ValueError:
        return JsonResponse({"error": "radius_m (float) and n (int) required"}, status=400)

    # DoS guard
    n = max(2, min(n, 11))   # 2~11 → 4~121 점
    radius_m = max(5.0, min(radius_m, 500.0))

    deg_per_m_lat = 1.0 / 111000.0
    deg_per_m_lng = 1.0 / (111000.0 * max(0.1, math.cos(math.radians(lat))))
    step_m = (2 * radius_m) / (n - 1) if n > 1 else 0.0

    points_latlng: list[tuple[float, float]] = []
    points_meta: list[tuple[float, float]] = []   # (lng, lat) for response
    for i in range(n):
        for j in range(n):
            dx = (j - (n - 1) / 2.0) * step_m
            dy = ((n - 1) / 2.0 - i) * step_m   # i=0이 북쪽
            pt_lat = lat + dy * deg_per_m_lat
            pt_lng = lng + dx * deg_per_m_lng
            points_latlng.append((pt_lat, pt_lng))
            points_meta.append((pt_lng, pt_lat))

    try:
        elevs = elevation_api.fetch_elevations(points_latlng)
    except elevation_api.ElevationFetchError as e:
        return JsonResponse({"error": f"elevation fetch failed: {e}"}, status=502)

    return JsonResponse({
        "center": {"lng": lng, "lat": lat},
        "radius_m": radius_m,
        "n": n,
        "step_m": round(step_m, 3),
        "provider": config.ELEVATION_PROVIDER,
        "points": [
            {"lng": round(pl[0], 6), "lat": round(pl[1], 6), "elev_m": round(float(e), 3)}
            for pl, e in zip(points_meta, elevs)
        ],
    })


@require_http_methods(["GET"])
def stats(request):
    """
    GET /land/stats/

    Return query statistics from LandQuery audit log.
    """
    from django.db.models import Avg, Count

    from land.models import LandQuery

    logs = LandQuery.objects.all()
    total = logs.count()
    avg_time = logs.aggregate(avg=Avg("response_time_ms"))["avg"] or 0
    by_type = (
        logs.values("input_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    error_count = logs.exclude(error="").count()

    return JsonResponse({
        "total_queries": total,
        "avg_response_time_ms": round(avg_time, 2),
        "by_input_type": list(by_type),
        "error_count": error_count,
    })


# ---------------------------------------------------------------------------
# Agent analysis SSE endpoint — 빠른 분석 + AutoGen Studio 에이전트 협업
# ---------------------------------------------------------------------------


def _sse(event_data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"


def _resolve_team() -> tuple[str, dict] | None:
    """Find Land Swarm Analysis Team (ID + component) from AutoGen Studio."""
    try:
        resp = httpx.get(
            f"{config.AUTOGEN_STUDIO_URL}/api/teams/",
            params={"user_id": config.AUTOGEN_STUDIO_USER},
            timeout=10.0,
        )
        resp.raise_for_status()
        body = resp.json()
        # API returns {"status": true, "data": [...]} or bare list
        teams = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(teams, list):
            return None
        needle = config.LAND_TEAM_LABEL.lower()
        for t in teams:
            if isinstance(t, dict):
                label = (t.get("component", {}) or {}).get("label", "")
                if label and needle in label.lower():
                    return str(t.get("id", "")), t.get("component", {})
        return None
    except Exception as e:
        logger.warning(f"Failed to resolve team: {e}")
        return None


def _core_analysis(pnu_info, zone_names, land_info, include_law=True,
                    parcel_geometry=None):
    """Shared analysis pipeline used by both analyze() and agent_analyze_stream().

    Returns (result_dict, reg, analysis_result, errors).
    """
    errors = []

    if not zone_names:
        return {
            "pnu": pnu_info, "regulations": None, "zone_info": None,
            "land_info": land_info, "law_articles": None,
            "restrictions": [], "warning": "No zones resolved",
        }, None, None, errors

    sigungu_code = pnu_info.get("sigungu", "") if pnu_info else ""
    reg = regulation_calculator.calculate_all(zone_names, land_info, sigungu_code=sigungu_code)
    reg_ext = regulation_calculator_ext.calculate_extended(zone_names, land_info)
    overlays = overlay_resolver.resolve_overlays(zone_names)

    law_articles = None
    if include_law:
        law_articles = law_enricher.search_for_zones(zone_names, include_extended=True)
        if law_articles["errors"]:
            errors.extend(law_articles["errors"])

    analysis_result = save_analysis_result(
        pnu_info, zone_names, reg, law_articles, land_info, reg_ext=reg_ext,
    )

    overlay_all_matched = overlay_resolver.get_all_matched_zones(zone_names)
    restrictions = build_restrictions(
        reg, zone_names, reg_ext,
        overlays=overlays, overlay_all_matched=overlay_all_matched,
    )

    zone_info = zoning_mapper.resolve_limits(zone_names)
    if zone_info and zone_info.get("zones"):
        zone_info["zones"] = [
            z["zone_name"] if isinstance(z, dict) else z for z in zone_info["zones"]
        ]

    flat_articles = _flatten_law_articles(law_articles) if law_articles else None

    # Setback lines geometry (규제선 시각화)
    # Phase 2B: ENABLE_DATUM_ELEVATION=true 일 때 envelope에 §119 datum 주입
    setback_lines = None
    if parcel_geometry:
        road_frontages = None
        neighbor_parcels = None
        roads_result = road_frontage.fetch_neighbor_roads(parcel_geometry)
        if roads_result.get("success"):
            road_frontages = roads_result.get("roads") or None
        elif roads_result.get("error"):
            errors.append(roads_result["error"])
        neighbors_result = road_frontage.fetch_neighbor_parcels(parcel_geometry)
        if neighbors_result.get("success"):
            neighbor_parcels = neighbors_result.get("neighbors") or None
        elif neighbors_result.get("error"):
            errors.append(neighbors_result["error"])
        setback_lines = setback_geometry.compute_setback_lines(
            parcel_geometry, reg,
            compute_datum=config.ENABLE_DATUM_ELEVATION,
            road_frontages=road_frontages,
            neighbor_parcels=neighbor_parcels,
        )

    result = {
        "pnu": pnu_info,
        "regulations": format_regulations(reg, reg_ext=reg_ext),
        "zone_info": zone_info,
        "land_info": land_info,
        "law_articles": flat_articles,
        "restrictions": restrictions,
        "overlay_regulations": overlays if overlays else [],
        "setback_lines": setback_lines,
    }
    if errors:
        result["errors"] = errors
    return result, reg, analysis_result, errors


def _resolve_input(pnu: str, address: str, zones_override: list[str] | None):
    """Resolve PNU/address to (pnu_info, zone_names, land_info, errors)."""
    errors = []
    pnu_info = None
    land_info = None
    zone_names = list(zones_override) if zones_override else []

    if pnu and pnu_resolver.validate_pnu(pnu):
        pnu_info = pnu_resolver.parse_pnu(pnu)
    elif address:
        result = pnu_resolver.resolve_address(address)
        if result["success"]:
            pnu_info = pnu_resolver.parse_pnu(result["pnu"])
        else:
            errors.append(result.get("error", "Address resolution failed"))

    if pnu_info:
        land_info = land_api.get_land_use_info(pnu_info["pnu"])
        if land_info["success"] and land_info["zones"] and not zone_names:
            zone_names = land_info["zones"]

    return pnu_info, zone_names, land_info, errors


def _run_quick_analysis(pnu: str, address: str, zones_override: list[str] | None):
    """Run the standard analysis pipeline, returning (result_dict, errors)."""
    pnu_info, zone_names, land_info, resolve_errors = _resolve_input(
        pnu, address, zones_override,
    )

    result, reg, analysis_result, analysis_errors = _core_analysis(
        pnu_info, zone_names, land_info,
    )
    all_errors = resolve_errors + analysis_errors
    if all_errors:
        result["errors"] = all_errors

    # Audit log (non-fatal)
    try:
        input_type = "pnu" if pnu else "address"
        raw_input = pnu or address
        log_query(
            input_type, raw_input, pnu_info,
            reg, land_info, 0, 0,
            error="; ".join(all_errors) if all_errors else "",
            analysis_result=analysis_result,
        )
    except Exception as e:
        logger.warning(f"agent_analyze log_query failed (non-fatal): {e}")

    return result, all_errors


@require_http_methods(["GET"])
def agent_analyze_stream(request):
    """
    GET /land/agent-analyze/stream?pnu=...&address=...&zones=...

    SSE endpoint: Phase 1 (quick analysis) + Phase 2 (agent collaboration).
    Phase 1 yields progress events then quick_done with full regulations.
    Phase 2 connects to AutoGen Studio WS and relays agent messages.
    Falls back gracefully if AutoGen Studio is unavailable.
    """
    pnu = request.GET.get("pnu", "").strip()
    address = request.GET.get("address", "").strip()
    zones_raw = request.GET.get("zones", "").strip()
    zones_override = [z.strip() for z in zones_raw.split(",") if z.strip()] if zones_raw else None

    if not pnu and not address:
        return JsonResponse({"error": "pnu or address required"}, status=400)

    def event_stream():
        # ── Phase 1: Quick analysis (0–30%) ──────────────────────
        yield _sse({"status": "analyzing", "phase": "reverse",
                     "phase_name": "필지 조회", "progress": 0.05})

        yield _sse({"status": "analyzing", "phase": "land_use",
                     "phase_name": "토지이용 조회", "progress": 0.10})

        yield _sse({"status": "analyzing", "phase": "regulations",
                     "phase_name": "규제 계산", "progress": 0.20})

        try:
            result, errors = _run_quick_analysis(pnu, address, zones_override)
        except Exception as e:
            logger.error(f"Quick analysis failed: {e}")
            yield _sse({"status": "error", "message": "빠른 분석 중 오류가 발생했습니다.", "fallback_to_quick": False})
            return

        yield _sse({"status": "analyzing", "phase": "law_search",
                     "phase_name": "법조항 검색", "progress": 0.25})

        yield _sse({"status": "quick_done", "regulations": result, "progress": 0.30})

        # ── Phase 2: Agent collaboration (30–95%) ────────────────
        team_result = _resolve_team()
        if not team_result:
            yield _sse({
                "status": "error",
                "message": "AutoGen Studio 팀을 찾을 수 없습니다. 빠른 분석 결과만 표시합니다.",
                "fallback_to_quick": True,
            })
            return

        team_id, team_component = team_result

        # Build task prompt — agents have tools to fetch their own data
        pnu_val = result.get("pnu", {})
        pnu_str = pnu_val.get("pnu", pnu) if isinstance(pnu_val, dict) else (pnu or address)
        addr_str = ""
        if isinstance(pnu_val, dict):
            addr_str = pnu_val.get("address", "")
        if not addr_str:
            addr_str = address or ""

        task = (
            f"다음 토지를 분석하세요.\n\n"
            f"PNU: {pnu_str}\n"
            f"주소: {addr_str or '(미확인)'}\n\n"
            f"land_analyst는 analyze_land 도구로 규제 데이터를 조회하고, "
            f"legal_interpreter는 search_laws 도구로 관련 법조항을 검색하세요."
        )

        def _unwrap(body):
            """Unwrap AutoGen Studio {status, data} envelope."""
            if isinstance(body, dict) and "data" in body:
                return body["data"]
            return body

        try:
            # Create session
            sess_resp = httpx.post(
                f"{config.AUTOGEN_STUDIO_URL}/api/sessions/",
                json={"team_id": int(team_id), "user_id": config.AUTOGEN_STUDIO_USER},
                timeout=10.0,
            )
            sess_resp.raise_for_status()
            session = _unwrap(sess_resp.json())
            session_id = session.get("id") if isinstance(session, dict) else session

            # Create run
            run_resp = httpx.post(
                f"{config.AUTOGEN_STUDIO_URL}/api/runs/",
                json={"session_id": session_id, "user_id": config.AUTOGEN_STUDIO_USER},
                timeout=10.0,
            )
            run_resp.raise_for_status()
            run = _unwrap(run_resp.json())
            run_id = run.get("run_id") if isinstance(run, dict) else run

        except Exception as e:
            logger.warning(f"AutoGen Studio session/run creation failed: {e}")
            yield _sse({
                "status": "error",
                "message": "AutoGen Studio 연결 실패. 빠른 분석 결과만 표시합니다.",
                "fallback_to_quick": True,
            })
            return

        # Connect WS and relay agent messages
        ws_base = config.AUTOGEN_STUDIO_URL.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_base}/api/ws/runs/{run_id}"

        yield _sse({"status": "analyzing", "phase": "agent_connect",
                     "phase_name": "에이전트 팀 연결", "progress": 0.32})

        msg_queue = queue.Queue()
        _SENTINEL = object()
        completion_data = None
        ws_error = None
        ws_done = threading.Event()

        def _ws_thread():
            nonlocal completion_data, ws_error
            ws = None
            try:
                ws = websocket.create_connection(ws_url, timeout=config.AUTOGEN_WS_TIMEOUT)
                ws.send(json.dumps({
                    "type": "start",
                    "task": task,
                    "files": [],
                    "team_config": team_component,
                }, ensure_ascii=False))

                while True:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        break

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type", "")
                    data = msg.get("data") or {}

                    if msg_type == "message" and isinstance(data, dict):
                        source = data.get("source", "")
                        content = data.get("content", "")
                        if source and content:
                            msg_queue.put({
                                "source": source,
                                "content": content,
                            })

                    elif msg_type == "input_request":
                        ws.send(json.dumps({
                            "type": "input_response",
                            "response": "continue",
                        }))

                    elif msg_type in ("completion", "result"):
                        completion_data = data if isinstance(data, dict) else msg
                        break

                    elif msg_type == "error":
                        ws_error = msg.get("error", "Unknown execution error")
                        break

            except Exception as e:
                ws_error = str(e)
            finally:
                if ws:
                    try:
                        ws.close()
                    except Exception:
                        pass
                msg_queue.put(_SENTINEL)
                ws_done.set()

        t = threading.Thread(target=_ws_thread, daemon=True)
        t.start()

        # Consume from queue and relay as SSE
        turn = 0
        all_messages = []
        t0 = time.time()

        while not ws_done.is_set():
            try:
                msg = msg_queue.get(timeout=1.0)
            except queue.Empty:
                # Timeout guard
                if time.time() - t0 > config.AUTOGEN_WS_TIMEOUT:
                    yield _sse({
                        "status": "error",
                        "message": "에이전트 실행 시간 초과",
                        "fallback_to_quick": True,
                    })
                    return
                continue

            if msg is _SENTINEL:
                break
            turn += 1
            all_messages.append(msg)
            progress = min(0.35 + turn * 0.08, 0.92)
            yield _sse({
                "status": "agent",
                "agent": msg["source"],
                "content": msg["content"],
                "progress": round(progress, 2),
                "turn": turn,
            })

        # Drain remaining messages after ws_done
        while True:
            try:
                msg = msg_queue.get_nowait()
            except queue.Empty:
                break
            if msg is _SENTINEL:
                break
            turn += 1
            all_messages.append(msg)
            progress = min(0.35 + turn * 0.08, 0.92)
            yield _sse({
                "status": "agent",
                "agent": msg["source"],
                "content": msg["content"],
                "progress": round(progress, 2),
                "turn": turn,
            })

        if ws_error:
            logger.warning(f"Agent execution error: {ws_error}")
            yield _sse({
                "status": "error",
                "message": "에이전트 실행 중 오류가 발생했습니다. 빠른 분석 결과만 표시합니다.",
                "fallback_to_quick": True,
            })
            return

        # Build final report
        duration = round(time.time() - t0, 2)
        agent_turns = [m for m in all_messages if m["source"] != "user"]
        last_content = agent_turns[-1]["content"] if agent_turns else ""

        yield _sse({
            "status": "complete",
            "report": last_content,
            "run_summary": {
                "duration": duration,
                "total_tokens": 0,
                "turn_count": len(all_messages),
            },
        })

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ---------------------------------------------------------------------------
# Map proxy endpoints — Vworld 타일/WMS/WFS 프록시 (API 키 은닉 + CORS 회피)
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def tile_proxy(request, z, y, x):
    """GET /land/tiles/{z}/{y}/{x}.png — Vworld WMTS 배경지도 타일 프록시."""
    url = (
        f"https://api.vworld.kr/req/wmts/1.0.0/{config.VWORLD_API_KEY}/Base"
        f"/{z}/{y}/{x}.png"
    )
    try:
        resp = config.proxy_client.get(url)
        resp.raise_for_status()
        response = HttpResponse(
            resp.content,
            content_type=resp.headers.get("content-type", "image/png"),
        )
        response["Cache-Control"] = "public, max-age=86400"  # 1 day
        return response
    except Exception as e:
        logger.warning(f"Tile proxy failed ({z}/{y}/{x}): {e}")
        return HttpResponse(status=502)


@require_http_methods(["GET"])
def wms_proxy(request):
    """GET /land/wms?... — Vworld WMS 지적도 프록시 (key 서버 주입)."""
    params = request.GET.dict()
    params["key"] = config.VWORLD_API_KEY
    try:
        resp = config.proxy_client.get("https://api.vworld.kr/req/wms", params=params)
        resp.raise_for_status()
        response = HttpResponse(
            resp.content,
            content_type=resp.headers.get("content-type", "image/png"),
        )
        response["Cache-Control"] = "public, max-age=300"  # 5 min
        return response
    except Exception as e:
        logger.warning(f"WMS proxy failed: {e}")
        return HttpResponse(status=502)


@csrf_exempt
@require_http_methods(["POST"])
def reverse(request):
    """
    POST /land/reverse/ — 좌표 → PNU + 필지 polygon (Vworld 2D Data API).

    Body: {"x": 127.0365, "y": 37.5013}
    Returns: {success, pnu, address, geometry(GeoJSON), coordinates}
    """
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    x = body.get("x")
    y = body.get("y")
    if x is None or y is None:
        return JsonResponse({"error": '"x" and "y" are required'}, status=400)

    try:
        x = float(x)
        y = float(y)
    except (ValueError, TypeError):
        return JsonResponse({"error": '"x" and "y" must be numbers'}, status=400)

    # Korea bounding box validation
    if not (124.0 <= x <= 133.0 and 33.0 <= y <= 44.0):
        return JsonResponse({"error": "좌표가 대한민국 범위 밖입니다 (x: 124-133, y: 33-44)"}, status=400)

    result = pnu_resolver.reverse_geocode(x, y)
    return JsonResponse(result)
