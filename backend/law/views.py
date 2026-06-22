"""
Law Search Proxy API

Proxies search requests to law-domain-agents (port 8011) and logs them to Django DB.
"""

import json
import logging
import os
import time

import atexit

import httpx
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from law.models import SearchLog

try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

logger = logging.getLogger(__name__)

LAW_AGENTS_URL = os.environ.get("LAW_BACKEND_URL", "http://localhost:8011")
AG_LIGHT_URL = os.environ.get("AG_LIGHT_URL", "https://law-light-api.clickaround8.workers.dev")
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Module-level httpx client singletons (connection pooling)
_law_client = httpx.Client(base_url=LAW_AGENTS_URL, timeout=_TIMEOUT)
_light_client = httpx.Client(base_url=AG_LIGHT_URL, timeout=_TIMEOUT)

# Module-level Neo4j driver singleton (connection pooling)
_neo4j_driver = None


def _cleanup():
    """Cleanup resources on shutdown."""
    _law_client.close()
    _light_client.close()
    if _neo4j_driver is not None:
        _neo4j_driver.close()


atexit.register(_cleanup)


def _light_search(query: str, limit: int) -> dict:
    """Fallback search via AG-light Worker (Vectorize hybrid)."""
    resp = _light_client.post(
        "/search",
        json={"query": query, "limit": limit, "mode": "hybrid"},
    )
    resp.raise_for_status()
    data = resp.json()
    # Map AG-light results → LawArticle format expected by frontend
    results = []
    for r in data.get("results", []):
        results.append({
            "hang_id": r.get("id", ""),
            "content": r.get("content", ""),
            "similarity": r.get("score", 0),
            "stages": ["ag-light"],
            "source": "ag-light-worker",
            "law_name": r.get("law_name", ""),
            "law_type": r.get("law_type", ""),
            "article": r.get("article", ""),
        })
    return {
        "results": results,
        "total_count": len(results),
        "stats": data.get("stats", {}),
        "source": "ag-light",
    }


def _get_neo4j_driver():
    """Return a shared Neo4j driver (lazy singleton)."""
    global _neo4j_driver
    if _neo4j_driver is None and HAS_NEO4J:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        pw = os.environ.get("NEO4J_PASSWORD", "11111111")
        _neo4j_driver = GraphDatabase.driver(uri, auth=("neo4j", pw))
    return _neo4j_driver


def _proxy_get(path: str) -> JsonResponse:
    """Forward a GET request to law-domain-agents."""
    try:
        resp = _law_client.get(path)
        resp.raise_for_status()
        return JsonResponse(resp.json(), safe=False)
    except httpx.ConnectError:
        return JsonResponse(
            {"error": "law-domain-agents server unavailable"},
            status=502,
        )
    except Exception as e:
        logger.error(f"Proxy GET {path} failed: {e}")
        return JsonResponse({"error": "Internal proxy error"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def search(request):
    """
    POST /law/search/

    Proxies to law-domain-agents POST /api/search, logs to DB.

    Body: {"q": "도시계획", "limit": 10}
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query = body.get("q", "")
    try:
        limit = int(body.get("limit", 10))
    except (TypeError, ValueError):
        return JsonResponse({"error": '"limit" must be an integer'}, status=400)

    if not query:
        return JsonResponse({"error": 'Field "q" is required'}, status=400)

    start = time.time()
    source = "proxy"
    try:
        resp = _law_client.post(
            "/api/search",
            json={"query": query, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Fallback to AG-light Worker
        try:
            data = _light_search(query, limit)
            source = "ag-light"
        except Exception as e2:
            logger.error(f"AG-light fallback also failed: {e2}")
            return JsonResponse(
                {"error": "검색 서버에 연결할 수 없습니다"},
                status=502,
            )
    except Exception as e:
        logger.error(f"Proxy search failed: {e}")
        return JsonResponse({"error": "Search request failed"}, status=500)

    elapsed_ms = (time.time() - start) * 1000
    result_count = len(data.get("results", []))

    try:
        SearchLog.objects.create(
            query=query,
            limit=limit,
            result_count=result_count,
            response_time_ms=round(elapsed_ms, 2),
            source=source,
        )
    except Exception as e:
        logger.warning(f"SearchLog save failed (non-fatal): {e}")

    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def search_domain(request, domain_id: str):
    """
    POST /law/domain/<domain_id>/search/

    Proxies to law-domain-agents POST /api/domain/<domain_id>/search.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query = body.get("q", "")
    try:
        limit = int(body.get("limit", 10))
    except (TypeError, ValueError):
        return JsonResponse({"error": '"limit" must be an integer'}, status=400)

    if not query:
        return JsonResponse({"error": 'Field "q" is required'}, status=400)

    start = time.time()
    source = "proxy"
    try:
        resp = _law_client.post(
            f"/api/domain/{domain_id}/search",
            json={"query": query, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Fallback: AG-light has no domain filtering, search globally
        try:
            data = _light_search(query, limit)
            source = "ag-light"
        except Exception as e2:
            logger.error(f"AG-light fallback also failed: {e2}")
            return JsonResponse(
                {"error": "검색 서버에 연결할 수 없습니다"},
                status=502,
            )
    except Exception as e:
        logger.error(f"Proxy domain search failed: {e}")
        return JsonResponse({"error": "Search request failed"}, status=500)

    elapsed_ms = (time.time() - start) * 1000
    result_count = len(data.get("results", []))

    try:
        SearchLog.objects.create(
            query=query,
            domain_id=domain_id,
            limit=limit,
            result_count=result_count,
            response_time_ms=round(elapsed_ms, 2),
            source=source,
        )
    except Exception as e:
        logger.warning(f"SearchLog save failed (non-fatal): {e}")

    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
def search_stream(request):
    """
    GET /law/search/stream?query=건폐율&limit=10&domain_id=xxx

    SSE endpoint that streams search progress events, then the final results.
    Proxies to law-domain-agents POST /api/search synchronously but wraps
    progress stages as Server-Sent Events for the frontend.
    """
    query = request.GET.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "query parameter required"}, status=400)

    try:
        limit = int(request.GET.get("limit", 10))
    except (TypeError, ValueError):
        return JsonResponse({"error": "limit must be an integer"}, status=400)

    domain_id = request.GET.get("domain_id", "").strip() or None

    def _sse(event_data: dict) -> str:
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def event_stream():
        # Stage 1: started
        yield _sse({
            "status": "started",
            "stage": "exact_match",
            "stage_name": "정확 일치 검색",
            "progress": 0.0,
            "agent": "law-domain-agent",
        })

        start = time.time()

        # Stage 2: searching — vector
        yield _sse({
            "status": "searching",
            "stage": "vector_search",
            "stage_name": "벡터 시맨틱 검색",
            "progress": 0.2,
            "agent": "law-domain-agent",
        })

        # Actual API call — try law-domain-agents, fallback to AG-light
        source = "stream"
        try:
            search_path = (
                f"/api/domain/{domain_id}/search" if domain_id
                else "/api/search"
            )

            # Stage 3: relationship search
            yield _sse({
                "status": "searching",
                "stage": "relationship_search",
                "stage_name": "관계 그래프 검색",
                "progress": 0.4,
                "agent": "law-domain-agent",
            })

            resp = _law_client.post(
                search_path,
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Fallback to AG-light Worker
            yield _sse({
                "status": "searching",
                "stage": "vector_search",
                "stage_name": "AG-light 하이브리드 검색",
                "progress": 0.5,
                "agent": "ag-light-worker",
            })
            try:
                data = _light_search(query, limit)
                source = "ag-light-stream"
            except Exception as e2:
                logger.error(f"SSE AG-light fallback failed: {e2}")
                yield _sse({
                    "status": "error",
                    "message": "검색 서버에 연결할 수 없습니다",
                })
                return
        except Exception as e:
            logger.error(f"SSE proxy search failed: {e}")
            yield _sse({
                "status": "error",
                "message": "검색 요청 처리 중 오류가 발생했습니다",
            })
            return

        # Stage 4: RNE expansion
        yield _sse({
            "status": "processing",
            "stage": "rne_expansion",
            "stage_name": "RNE 그래프 확장",
            "progress": 0.7,
            "agent": "law-domain-agent",
            "node_count": data.get("stats", {}).get("total", 0),
        })

        # Stage 5: enrichment
        yield _sse({
            "status": "processing",
            "stage": "enrichment",
            "stage_name": "결과 강화 및 정렬",
            "progress": 0.9,
            "agent": "law-domain-agent",
        })

        elapsed_ms = round((time.time() - start) * 1000, 2)
        results = data.get("results", [])
        stats = data.get("stats", {})

        # Log to DB (non-fatal)
        try:
            SearchLog.objects.create(
                query=query,
                domain_id=domain_id or "",
                limit=limit,
                result_count=len(results),
                response_time_ms=elapsed_ms,
                source=source,
            )
        except Exception as e:
            logger.warning(f"SearchLog save failed (non-fatal): {e}")

        # Stage 6: complete with results
        yield _sse({
            "status": "complete",
            "results": results,
            "result_count": len(results),
            "response_time": elapsed_ms,
            "domain_id": data.get("domain_id"),
            "domain_name": data.get("domain_name"),
            "stats": stats,
        })

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_http_methods(["GET"])
def domains(request):
    """GET /law/domains/ - list available law domains (empty if agents unavailable)."""
    try:
        resp = _law_client.get("/api/domains")
        resp.raise_for_status()
        return JsonResponse(resp.json(), safe=False)
    except Exception:
        return JsonResponse({"domains": []}, safe=False)


@require_http_methods(["GET"])
def health(request):
    """GET /law/health/ - Django is healthy; optionally check law-domain-agents."""
    result = {"status": "ok", "django": True, "law_agents": False}
    try:
        resp = _law_client.get("/api/health")
        resp.raise_for_status()
        result["law_agents"] = True
        result["law_agents_detail"] = resp.json()
    except Exception:
        pass  # law-domain-agents down is non-fatal
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Article — Worker fallback (Neo4j 미가용 시 법제처 API 경유)
# ---------------------------------------------------------------------------

_search_client = httpx.Client(timeout=15)


def _extract_jo_number(parts: list[str]) -> str | None:
    """full_id parts에서 '제N조' 패턴 찾기."""
    import re
    for p in parts:
        if re.match(r"제\d+조", p):
            return p
    return None


def _article_via_worker(full_id: str, parts: list[str], jo_prefix: str) -> JsonResponse:
    """Neo4j 없을 때 AG-light Worker API로 조문 조회."""
    # full_id: "건축법::제60조::①" → law_part="건축법", jo="제60조"
    law_part = parts[0]
    law_name = law_part.split("(")[0] if "(" in law_part else law_part
    law_type = law_part.split("(")[1].rstrip(")") if "(" in law_part else ""

    jo_str = _extract_jo_number(parts)
    if not jo_str:
        return JsonResponse({"error": f"조문 번호를 찾을 수 없습니다: {full_id}"}, status=400)

    try:
        # 1) 법령 검색 → mst 획득
        search_resp = _search_client.post(
            f"{AG_LIGHT_URL}/law/search",
            json={"query": law_part, "display": 5},
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
        results = search_data.get("results", [])
        if not results:
            return JsonResponse({"error": f"법령 '{law_part}'을 찾을 수 없습니다"}, status=404)

        mst = results[0].get("mst")
        if not mst:
            return JsonResponse({"error": "법령일련번호(mst)를 찾을 수 없습니다"}, status=404)

        # 2) 조문 전문 조회
        text_resp = _search_client.post(
            f"{AG_LIGHT_URL}/law/text",
            json={"mst": mst, "jo": jo_str},
        )
        text_resp.raise_for_status()
        text_data = text_resp.json()
        article_text = text_data.get("text", "")

        if not article_text:
            return JsonResponse({"error": "조문 내용을 찾을 수 없습니다"}, status=404)

        # 3) 텍스트를 ArticleDetail 형식으로 변환
        #    Worker 반환 텍스트를 항별로 파싱
        import re
        lines = article_text.strip().split("\n")
        hangs = []
        current_content = []
        current_num = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 항 번호 패턴: ① ② ③ ... 또는 <1> <2> 등
            hang_match = re.match(r"^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*(.*)", line)
            if hang_match:
                if current_num:
                    hangs.append({
                        "full_id": f"{jo_prefix}::{current_num}",
                        "number": current_num,
                        "content": "\n".join(current_content),
                        "unit_path": None,
                        "hos": [],
                    })
                current_num = hang_match.group(1)
                current_content = [hang_match.group(2)] if hang_match.group(2) else []
            elif current_num:
                current_content.append(line)

        # 마지막 항 추가
        if current_num:
            hangs.append({
                "full_id": f"{jo_prefix}::{current_num}",
                "number": current_num,
                "content": "\n".join(current_content),
                "unit_path": None,
                "hos": [],
            })

        # 항 파싱 실패 시 전체 텍스트를 단일 항으로
        if not hangs:
            hangs = [{
                "full_id": jo_prefix,
                "number": "",
                "content": article_text,
                "unit_path": None,
                "hos": [],
            }]

        return JsonResponse({
            "jo_prefix": jo_prefix,
            "law_name": law_name,
            "law_type": law_type,
            "jo": {
                "full_id": jo_prefix,
                "number": jo_str,
                "title": None,
                "content": None,
                "law_name": law_name,
                "unit_path": None,
            },
            "hangs": hangs,
            "hang_count": len(hangs),
            "ho_count": 0,
            "source": "worker_api",
        })

    except httpx.HTTPError as e:
        logger.error(f"Worker article fallback failed: {e}")
        return JsonResponse({"error": f"조문 조회 실패: {e}"}, status=502)
    except Exception as e:
        logger.error(f"Worker article fallback error: {e}")
        return JsonResponse({"error": f"조문 조회 중 오류: {e}"}, status=500)


def _article_by_vectorize_id(vec_id: str) -> JsonResponse:
    """Vectorize ID ('건축법_제60조') → Neo4j JO 검색 → ArticleDetail 반환."""
    import re

    # "건축법_제60조" → law_name="건축법", jo_number="제60조"
    parts = vec_id.split("_", 1)
    if len(parts) < 2:
        return _article_via_worker(vec_id, [vec_id], vec_id)

    law_name = parts[0]
    jo_number = parts[1]  # "제60조"
    # Neo4j JO.number는 "60조" (제 없음), full_id에는 "제60조"
    jo_num_bare = re.sub(r"^제", "", jo_number)  # "제60조" → "60조"

    driver = _get_neo4j_driver()
    if driver is None:
        return _article_via_worker(vec_id, [law_name, jo_number], f"{law_name}::{jo_number}")

    try:
        with driver.session() as session:
            # JO 노드 검색: 법률 우선 (법률→시행령→시행규칙)
            jo_result = session.run(
                "MATCH (j:JO) WHERE j.law_name = $law AND "
                "(j.number = $num1 OR j.number = $num2 OR j.full_id ENDS WITH $suffix) "
                "RETURN j.full_id AS fid, j.number AS number, j.title AS title, "
                "j.content AS content, j.law_name AS law_name, j.unit_path AS unit_path "
                "ORDER BY CASE WHEN j.full_id CONTAINS '(법률)' THEN 0 "
                "WHEN j.full_id CONTAINS '(시행령)' THEN 1 ELSE 2 END "
                "LIMIT 1",
                law=law_name, num1=jo_number, num2=jo_num_bare,
                suffix="::" + jo_number,
            )
            jo_rec = jo_result.single()
            if not jo_rec:
                return _article_via_worker(vec_id, [law_name, jo_number], f"{law_name}::{jo_number}")

            jo_fid = jo_rec["fid"]
            jo_info = {
                "full_id": jo_fid,
                "number": jo_rec["number"],
                "title": jo_rec["title"],
                "content": jo_rec["content"],
                "law_name": jo_rec["law_name"],
                "unit_path": jo_rec["unit_path"],
            }

            # HANG 조회
            hang_result = session.run(
                "MATCH (h:HANG) WHERE h.full_id STARTS WITH $prefix "
                "RETURN h.full_id AS full_id, h.number AS number, "
                "h.content AS content, h.order AS ord, h.unit_path AS unit_path "
                "ORDER BY coalesce(h.order, 9999)",
                prefix=jo_fid + "::",
            )
            seen = set()
            hangs = []
            for rec in hang_result:
                key = (rec["number"], (rec["content"] or "")[:50])
                if key in seen:
                    continue
                seen.add(key)
                hangs.append({
                    "full_id": rec["full_id"],
                    "number": rec["number"],
                    "content": rec["content"] or "",
                    "unit_path": rec["unit_path"],
                })

            # HO 조회
            ho_result = session.run(
                "MATCH (h:HANG)-[:CONTAINS]->(ho:HO) "
                "WHERE h.full_id STARTS WITH $prefix "
                "RETURN h.number AS hang_num, ho.number AS ho_num, "
                "ho.content AS content, ho.order AS ord, ho.full_id AS full_id "
                "ORDER BY coalesce(h.order, 9999), coalesce(ho.order, 9999)",
                prefix=jo_fid + "::",
            )
            ho_by_hang: dict[str, list] = {}
            for rec in ho_result:
                ho_by_hang.setdefault(rec["hang_num"], []).append({
                    "hang_number": rec["hang_num"],
                    "number": rec["ho_num"],
                    "content": rec["content"] or "",
                    "full_id": rec["full_id"],
                })

            structured_hangs = [{**h, "hos": ho_by_hang.get(h["number"], [])} for h in hangs]

            actual_law = jo_rec["law_name"] or law_name
            law_type_match = re.search(r"\(([^)]+)\)", actual_law)
            law_type = law_type_match.group(1) if law_type_match else ""
            clean_name = actual_law.split("(")[0] if "(" in actual_law else actual_law

            return JsonResponse({
                "jo_prefix": jo_fid,
                "law_name": clean_name,
                "law_type": law_type,
                "jo": jo_info,
                "hangs": structured_hangs,
                "hang_count": len(structured_hangs),
                "ho_count": sum(len(h["hos"]) for h in structured_hangs),
            })

    except Exception as e:
        logger.warning(f"Neo4j vectorize-id lookup failed, falling back to Worker: {e}")
        return _article_via_worker(vec_id, [law_name, jo_number], f"{law_name}::{jo_number}")


@require_http_methods(["GET"])
def article(request):
    """
    GET /law/article/?full_id=국토의 계획 및 이용에 관한 법률(시행령)::제6장::제84조::①

    Fetches the full article (all 항/호/목) from Neo4j given any HANG full_id.
    Returns structured article with JO info + all children.
    """
    full_id = request.GET.get("full_id", "").strip()
    if not full_id:
        return JsonResponse({"error": "full_id parameter required"}, status=400)

    # Vectorize ID 형식 ("건축법_제60조") → Neo4j 조회로 변환
    if "::" not in full_id and "_" in full_id:
        return _article_by_vectorize_id(full_id)

    # Neo4j full_id 형식 ("건축법(시행령)::제6장::제60조::①")
    parts = full_id.split("::")
    if len(parts) < 3:
        return JsonResponse({"error": "Invalid full_id format"}, status=400)

    # Find the JO-level prefix (law::chapter::article)
    # The last part is the HANG number, so JO prefix is everything before it
    jo_prefix = "::".join(parts[:-1])

    # Neo4j 미가용 → AG-light Worker API fallback (법제처 API 경유)
    driver = _get_neo4j_driver()
    if driver is None:
        return _article_via_worker(full_id, parts, jo_prefix)

    try:
        with driver.session() as session:
            # Get JO node info
            jo_result = session.run(
                "MATCH (j:JO) WHERE j.full_id = $fid RETURN j",
                fid=jo_prefix,
            )
            jo_record = jo_result.single()
            jo_info = None
            if jo_record:
                jo_node = jo_record["j"]
                jo_info = {
                    "full_id": jo_node.get("full_id"),
                    "number": jo_node.get("number"),
                    "title": jo_node.get("title"),
                    "content": jo_node.get("content"),
                    "law_name": jo_node.get("law_name"),
                    "unit_path": jo_node.get("unit_path"),
                }

            # Get all HANGs under this JO (deduplicate by number)
            hang_result = session.run(
                """
                MATCH (h:HANG) WHERE h.full_id STARTS WITH $prefix
                RETURN h.full_id AS full_id, h.number AS number,
                       h.content AS content, h.order AS ord,
                       h.unit_path AS unit_path, h.law_name AS law_name
                ORDER BY coalesce(h.order, 9999)
                """,
                prefix=jo_prefix + "::",
            )
            seen_numbers = set()
            hangs = []
            for rec in hang_result:
                num = rec["number"]
                # Deduplicate (some JOs have duplicate 항 entries)
                key = (num, (rec["content"] or "")[:50])
                if key in seen_numbers:
                    continue
                seen_numbers.add(key)
                hangs.append({
                    "full_id": rec["full_id"],
                    "number": num,
                    "content": rec["content"] or "",
                    "unit_path": rec["unit_path"],
                })

            # Get HOs under these HANGs
            ho_result = session.run(
                """
                MATCH (h:HANG)-[:CONTAINS]->(ho:HO)
                WHERE h.full_id STARTS WITH $prefix
                RETURN h.number AS hang_num, ho.number AS ho_num,
                       ho.content AS content, ho.order AS ord,
                       ho.full_id AS full_id
                ORDER BY coalesce(h.order, 9999), coalesce(ho.order, 9999)
                """,
                prefix=jo_prefix + "::",
            )
            seen_ho = set()
            hos = []
            for rec in ho_result:
                key = (rec["hang_num"], rec["ho_num"], (rec["content"] or "")[:50])
                if key in seen_ho:
                    continue
                seen_ho.add(key)
                hos.append({
                    "hang_number": rec["hang_num"],
                    "number": rec["ho_num"],
                    "content": rec["content"] or "",
                    "full_id": rec["full_id"],
                })
    except Exception as e:
        logger.warning(f"Neo4j article query failed, falling back to Worker API: {e}")
        return _article_via_worker(full_id, parts, jo_prefix)

    # Build structured response
    # Group HOs by hang number
    ho_by_hang: dict[str, list] = {}
    for ho in hos:
        ho_by_hang.setdefault(ho["hang_number"], []).append(ho)

    structured_hangs = []
    for h in hangs:
        structured_hangs.append({
            **h,
            "hos": ho_by_hang.get(h["number"], []),
        })

    # Extract law info from full_id
    law_part = parts[0]  # e.g. "국토의 계획 및 이용에 관한 법률(시행령)"
    law_name = law_part.split("(")[0] if "(" in law_part else law_part
    law_type = law_part.split("(")[1].rstrip(")") if "(" in law_part else ""

    return JsonResponse({
        "jo_prefix": jo_prefix,
        "law_name": law_name,
        "law_type": law_type,
        "jo": jo_info,
        "hangs": structured_hangs,
        "hang_count": len(structured_hangs),
        "ho_count": len(hos),
    })


@require_http_methods(["GET"])
def stats(request):
    """
    GET /law/stats/

    Returns search log statistics from Django DB.
    """
    from django.db.models import Avg, Count

    logs = SearchLog.objects.all()
    total = logs.count()
    avg_time = logs.aggregate(avg=Avg("response_time_ms"))["avg"] or 0
    top_queries = (
        logs.values("query")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    return JsonResponse({
        "total_searches": total,
        "avg_response_time_ms": round(avg_time, 2),
        "top_queries": list(top_queries),
    })
