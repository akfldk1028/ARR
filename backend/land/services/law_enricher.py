"""
Law Enricher - searches law-domain-agents for relevant building/zoning law articles.

Queries :8011/api/search with zone-specific keywords.
Fan-out parallel search via ThreadPoolExecutor (max 5 concurrent).
Includes LLM-based structured extraction: law text → regulation values.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from land import config

# Overall wall-clock budget for all queries (seconds)
_TOTAL_TIMEOUT = 120

# Max concurrent requests to :8011 (prevents overloading the search server)
_MAX_WORKERS = 5

logger = logging.getLogger(__name__)

# Minimum similarity to keep a result (drops low-relevance noise)
_MIN_SIMILARITY = 0.25

# Laws almost never relevant to building/zoning regulation analysis.
# Results from these are filtered out to reduce noise.
_NOISE_LAWS = {"수도법"}

# Base queries applied to every analysis (10 regulation categories)
_BASE_QUERIES = [
    "건폐율",
    "용적률",
    "건축제한",
    "높이제한",
    "일조권",
    "가각전제",
    "건축물 높이제한 전면도로",
    "건축선",
    "인접대지",
    "주차장",
    "조경",
    "건축지정선",
]

# Extended queries for items 11-41 (optional, activated via include_extended)
_EXTENDED_QUERIES = [
    "용도제한",
    "접도의무",
    "대지분할",
    "인동간격",
    "공개공지",
    "내화구조",
    "개발행위허가",
    "소방시설",
    "건축물 에너지절약설계",
]


def search_for_building_type(building_type: str, zone_names: list[str],
                              limit_per_query: int = 5) -> dict:
    """
    Search law articles specific to a building type + zone combination.

    Queries law-domain-agents for building-type-specific regulations.
    Uses fan-out parallel search (ThreadPoolExecutor).
    Returns same structure as search_for_zones.
    """
    queries = [
        f"{building_type} 건폐율",
        f"{building_type} 용적률",
        f"{building_type} 높이제한",
        f"{building_type} 건축제한",
        f"{building_type} 주차",
    ]
    for zone in zone_names[:2]:
        queries.append(f"{zone} {building_type}")

    return _parallel_search(queries, limit_per_query, timeout=60)


def search_for_zones(zone_names: list[str], limit_per_query: int = 5,
                     include_extended: bool = False) -> dict:
    """
    Search law articles relevant to the given zoning zones.

    For each zone, searches base queries + zone-specific keywords.
    Uses fan-out parallel search (ThreadPoolExecutor, max 5 concurrent).
    Fails fast if law-domain-agents is unreachable.

    Returns:
        {
            "articles": [{"query": str, "results": list}],
            "total_count": int,
            "errors": [str]
        }
    """
    # Build query list: base + extended(optional) + zone-specific
    queries = list(_BASE_QUERIES)
    if include_extended:
        queries.extend(_EXTENDED_QUERIES)
    for zone in zone_names:
        queries.append(f"{zone} 건폐율")
        queries.append(f"{zone} 건축제한")

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    return _parallel_search(unique_queries, limit_per_query, timeout=_TOTAL_TIMEOUT)


# ──────────────────────────────────────────────────────
# Fan-out parallel search core
# ──────────────────────────────────────────────────────


def _run_single_query(query: str, limit: int) -> dict:
    """Execute a single search query. Tries :8011, falls back to AG-light Worker."""
    try:
        resp = config.law_client.post(
            "/api/search",
            json={"query": query, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Fallback to AG-light Worker hybrid search
        resp = config.light_client.post(
            "/search",
            json={"query": query, "limit": limit, "mode": "hybrid"},
        )
        resp.raise_for_status()
        raw = resp.json()
        # Map AG-light fields → law-domain-agents format
        data = {"results": [
            {
                "hang_id": r.get("id", ""),
                "content": r.get("content", ""),
                "similarity": r.get("score", 0),
                "law_name": r.get("law_name", ""),
                "law_type": r.get("law_type", ""),
                "source": "ag-light",
            }
            for r in raw.get("results", [])
        ]}

    results = data.get("results", [])
    results = [
        r for r in results
        if r.get("similarity", 1.0) >= _MIN_SIMILARITY
        and r.get("law_name", "") not in _NOISE_LAWS
    ]
    return {"query": query, "results": results}


def _parallel_search(queries: list[str], limit_per_query: int,
                     timeout: float = _TOTAL_TIMEOUT) -> dict:
    """
    Fan-out parallel search: run queries concurrently via ThreadPoolExecutor.

    Respects overall timeout and fails fast on ConnectError.
    """
    all_articles = []
    errors = []
    t0 = time.monotonic()

    workers = min(_MAX_WORKERS, len(queries))
    if workers == 0:
        return {"articles": [], "total_count": 0, "errors": []}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_query = {
            executor.submit(_run_single_query, q, limit_per_query): q
            for q in queries
        }
        for future in as_completed(future_to_query):
            if time.monotonic() - t0 > timeout:
                pending = sum(1 for f in future_to_query if not f.done())
                errors.append(
                    f"Overall timeout ({timeout}s) exceeded, {pending} queries skipped"
                )
                executor.shutdown(wait=False, cancel_futures=True)
                break

            query = future_to_query[future]
            try:
                result = future.result(timeout=5)
                if result["results"]:
                    all_articles.append(result)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                errors.append("law-domain-agents unreachable (using fallback)")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            except Exception as e:
                errors.append(f"Query '{query}' failed: {e}")

    total = sum(len(a["results"]) for a in all_articles)
    return {"articles": all_articles, "total_count": total, "errors": errors}


# ──────────────────────────────────────────────────────
# LLM Structured Extraction
# ──────────────────────────────────────────────────────

_extraction_cache: dict[str, dict] = {}
_CACHE_MAX_SIZE = 100


def clear_extraction_cache():
    """Clear the LLM extraction cache. Call in tests or after config changes."""
    _extraction_cache.clear()


def extract_regulation_values(
    zone_names: list[str], regulation_type: str
) -> dict | None:
    """
    Neo4j 법조문 검색 → LLM structured extraction → 규제 수치 dict.

    Args:
        zone_names: 용도지역 리스트 (예: ["제3종일반주거지역"])
        regulation_type: "sunlight" | "adjacent_setback" | "bcr_far" | "height"

    Returns:
        regulation_calculator 호환 dict or None (실패/비활성)
    """
    if not config.LLM_EXTRACTION_ENABLED or not config.OPENAI_API_KEY:
        return None

    from land.data.regulation_prompts import EXTRACTION_CONFIG, SYSTEM_PROMPT

    cfg = EXTRACTION_CONFIG.get(regulation_type)
    if not cfg:
        logger.warning(f"Unknown regulation_type: {regulation_type}")
        return None

    zone_key = ",".join(sorted(zone_names))
    cache_key = f"{zone_key}:{regulation_type}"
    if cache_key in _extraction_cache:
        return _extraction_cache[cache_key]

    # Step 1: 관련 법조문 텍스트 수집
    article_texts = _fetch_article_texts(cfg["queries"], zone_names)
    if not article_texts:
        return None  # transient failure — do NOT cache None

    # Step 2: LLM extraction
    zone_name = zone_names[0] if zone_names else ""
    combined_text = "\n\n---\n\n".join(article_texts[:5])
    prompt = cfg["prompt"].format(article_text=combined_text, zone_name=zone_name)

    result = _call_llm_extraction(prompt, SYSTEM_PROMPT)

    # Only cache successful results (not None from transient failures)
    if result is not None:
        if len(_extraction_cache) >= _CACHE_MAX_SIZE:
            _extraction_cache.clear()
        _extraction_cache[cache_key] = result

    return result


def _fetch_article_texts(queries: list[str], zone_names: list[str]) -> list[str]:
    """법조문 텍스트를 :8011에서 검색하여 수집."""
    texts = []
    seen = set()

    for query_template in queries:
        query = query_template.format(
            zone_name=zone_names[0] if zone_names else ""
        ) if "{zone_name}" in query_template else query_template

        try:
            try:
                resp = config.law_client.post(
                    "/api/search",
                    json={"query": query, "limit": 3},
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout):
                resp = config.light_client.post(
                    "/search",
                    json={"query": query, "limit": 3, "mode": "hybrid"},
                )
                resp.raise_for_status()
                data = resp.json()
            for r in data.get("results", []):
                content = r.get("content", "")
                dedup_key = r.get("hang_id") or r.get("id") or content[:80]
                if content and dedup_key not in seen:
                    seen.add(dedup_key)
                    law_name = r.get("law_name", "")
                    jo_name = r.get("jo_name", "")
                    header = f"[{law_name} {jo_name}]" if law_name else ""
                    texts.append(f"{header}\n{content}" if header else content)
        except Exception as e:
            logger.debug(f"Article fetch failed for '{query}': {e}")
            continue

    return texts


_openai_client = None


def _get_openai_client():
    """Lazy singleton for OpenAI client (reuses connection pool)."""
    global _openai_client
    if _openai_client is None:
        import openai
        _openai_client = openai.OpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.LLM_EXTRACTION_TIMEOUT,
        )
    return _openai_client


def _call_llm_extraction(prompt: str, system_prompt: str) -> dict | None:
    """OpenAI API로 structured JSON 추출."""
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=config.LLM_EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return None

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None

        # Validate critical field types (LLM may return wrong types)
        for key in ("sunlight_applies",):
            if key in parsed and not isinstance(parsed[key], bool):
                logger.warning(f"LLM returned non-bool for {key}: {parsed[key]}")
                return None
        for key in ("sunlight_rules", "applies_to_zones", "exceptions",
                     "height_dependent_rules"):
            if key in parsed and not isinstance(parsed[key], list):
                logger.warning(f"LLM returned non-list for {key}: {type(parsed[key])}")
                return None
        for key in ("adjacent_setback_m", "bcr_pct", "far_pct", "height_limit_m",
                     "building_designation_setback_m"):
            if key in parsed and parsed[key] is not None:
                if not isinstance(parsed[key], (int, float)):
                    logger.warning(f"LLM returned non-numeric for {key}: {parsed[key]}")
                    return None

        return parsed

    except json.JSONDecodeError as e:
        logger.warning(f"LLM extraction JSON parse failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return None
