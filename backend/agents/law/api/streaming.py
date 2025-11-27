"""
Law Search SSE Streaming API

Server-Sent Events (SSE) endpoint for real-time search progress updates.

This provides real-time progress updates for Multi-Agent System (MAS) searches,
allowing the frontend to display the progress of each search stage.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Dict, Any

from django.http import StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from agents.law.agent_manager import AgentManager
from agents.law.api.search import (
    get_agent_manager,
    auto_route_to_top_domains,
    transform_results,
    calculate_statistics
)

logger = logging.getLogger(__name__)


def sse_message(data: Dict[str, Any]) -> str:
    """
    Format data as Server-Sent Events message

    Args:
        data: Dictionary to send as SSE message

    Returns:
        Formatted SSE message string
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def search_stream_generator(query: str, limit: int = 10):
    """
    Async generator for SSE search progress updates

    Stages:
    1. started - Search initialization
    2. searching/exact_match - Exact match search (20%)
    3. searching/vector_search - Vector similarity search (40%)
    4. searching/relationship_search - Relationship embedding search (60%)
    5. searching/rne_expansion - RNE graph expansion (80%)
    6. processing/enrichment - Result enrichment (95%)
    7. complete - Final results

    Args:
        query: Search query
        limit: Maximum results to return

    Yields:
        SSE formatted messages
    """
    try:
        start_time = time.time()

        # Get AgentManager
        agent_manager = get_agent_manager()

        # [Stage 0] Domain routing
        logger.info(f"[SSE] Starting search stream for query: '{query[:50]}...'")

        # Get top domains for A2A collaboration (Multi-Agent System)
        top_domains = auto_route_to_top_domains(query, agent_manager, top_n=3, use_llm_assessment=True)

        if not top_domains:
            yield sse_message({
                'status': 'error',
                'message': 'No domains available'
            })
            return

        primary_domain = top_domains[0]
        primary_domain_id = primary_domain['domain_id']
        primary_domain_info = agent_manager.domains.get(primary_domain_id)

        if not primary_domain_info or not primary_domain_info.agent_instance:
            yield sse_message({
                'status': 'error',
                'message': f'Primary domain {primary_domain_id} not initialized'
            })
            return

        # [Stage 1] Started
        yield sse_message({
            'status': 'started',
            'agent': primary_domain['domain_name'],
            'domain_id': primary_domain_id,
            'node_count': primary_domain_info.size(),
            'timestamp': time.time()
        })

        import time as time_module
        time_module.sleep(0.01)  # Give UI time to update

        # [Stage 2] Exact Match Search (20%)
        yield sse_message({
            'status': 'searching',
            'stage': 'exact_match',
            'stage_name': '정확 일치 검색',
            'progress': 0.2
        })

        time_module.sleep(0.01)

        # [Stage 3] Vector Search (40%)
        yield sse_message({
            'status': 'searching',
            'stage': 'vector_search',
            'stage_name': '벡터 유사도 검색',
            'progress': 0.4
        })

        time_module.sleep(0.01)

        # [Stage 4] Relationship Search (60%)
        yield sse_message({
            'status': 'searching',
            'stage': 'relationship_search',
            'stage_name': '관계 임베딩 검색',
            'progress': 0.6
        })

        time_module.sleep(0.01)

        # [Stage 5] RNE Expansion & A2A Collaboration (80%)
        yield sse_message({
            'status': 'searching',
            'stage': 'rne_expansion',
            'stage_name': f'RNE 확장 + A2A 협업 ({len(top_domains)}개 도메인)',
            'progress': 0.8
        })

        # Execute A2A Multi-Agent search across top domains
        all_results = []
        active_domains = []

        for idx, domain in enumerate(top_domains):
            domain_id = domain['domain_id']
            domain_info = agent_manager.domains.get(domain_id)

            if not domain_info or not domain_info.agent_instance:
                logger.warning(f"[SSE] Domain {domain_id} not initialized, skipping")
                continue

            logger.info(f"[SSE] Agent {idx+1}/{len(top_domains)}: {domain['domain_name']} searching...")

            # Run async function synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(domain_info.agent_instance._search_my_domain(query))
            finally:
                loop.close()

            if results:
                all_results.extend(results)
                active_domains.append(domain['domain_name'])
                logger.info(f"[SSE]   → Found {len(results)} results in {domain['domain_name']}")

        logger.info(f"[SSE] A2A Collaboration complete: {len(all_results)} total results from {len(active_domains)} domains")

        # [Stage 6] Result Processing (95%)
        yield sse_message({
            'status': 'processing',
            'stage': 'enrichment',
            'stage_name': f'결과 병합 및 정렬 ({len(active_domains)}개 도메인)',
            'progress': 0.95
        })

        time_module.sleep(0.01)

        # Sort by score and limit
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_results = all_results[:limit]

        # Transform and calculate stats
        transformed_results = transform_results(top_results)
        stats = calculate_statistics(transformed_results)

        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)

        # [Stage 7] Complete
        logger.info(
            f"[SSE] Search completed: {len(transformed_results)} results in {response_time}ms"
        )

        yield sse_message({
            'status': 'complete',
            'results': transformed_results,
            'result_count': len(transformed_results),
            'stats': stats,
            'response_time': response_time,
            'domain_id': primary_domain_id,
            'domain_name': f"A2A협업: {', '.join(active_domains)}",
            'active_agents': active_domains
        })

    except Exception as e:
        logger.error(f"[SSE] Streaming error: {e}", exc_info=True)
        yield sse_message({
            'status': 'error',
            'message': str(e)
        })


def sync_generator_wrapper(query: str, limit: int):
    """
    Wrapper for sync generator (now simplified since search_stream_generator is sync)

    Args:
        query: Search query
        limit: Maximum results

    Yields:
        SSE messages
    """
    # Now that search_stream_generator is synchronous, just yield directly
    for message in search_stream_generator(query, limit):
        yield message


@method_decorator(csrf_exempt, name='dispatch')
class LawSearchStreamAPIView(View):
    """
    Law Search SSE Streaming API

    GET /agents/law/api/search/stream?query=...&limit=10

    Query Parameters:
        - query: str (required)
        - limit: int (optional, default=10)

    Response:
        Server-Sent Events (text/event-stream)

    SSE Event Format:
        data: {"status": "started", "agent": "용도지역", ...}

    Status Stages:
        - started: Search initialization
        - searching: In progress (with stage and progress)
        - processing: Result enrichment
        - complete: Final results
        - error: Error occurred
    """

    def options(self, request):
        """Handle CORS preflight request"""
        response = StreamingHttpResponse(
            iter([]),  # Empty response for OPTIONS
            content_type='text/event-stream'
        )
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    def get(self, request):
        """Handle SSE streaming search request"""
        try:
            # Parse query parameters (EventSource uses GET)
            query = request.GET.get('query')
            limit = int(request.GET.get('limit', 10))

            if not query:
                # Return error as SSE
                def error_generator():
                    yield sse_message({
                        'status': 'error',
                        'message': 'Query is required'
                    })

                response = StreamingHttpResponse(
                    error_generator(),
                    content_type='text/event-stream'
                )
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                response['Access-Control-Allow-Origin'] = '*'
                response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type'
                return response

            logger.info(f"[SSE] Received streaming search request: query='{query[:50]}...', limit={limit}")

            # Create streaming response
            response = StreamingHttpResponse(
                sync_generator_wrapper(query, limit),
                content_type='text/event-stream'
            )

            # SSE headers
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering

            # CORS headers for SSE
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'

            return response

        except Exception as e:
            logger.error(f"[SSE] Error in LawSearchStreamAPIView: {e}", exc_info=True)

            # Return error as SSE
            def error_generator():
                yield sse_message({
                    'status': 'error',
                    'message': str(e)
                })

            response = StreamingHttpResponse(
                error_generator(),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
