"""
Law Search API Views

REST API endpoints for law article search using DomainAgent system.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from agents.law.agent_manager import AgentManager
from agents.law.utils import deduplicate_results, boost_diversity_by_law_type
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Global AgentManager singleton
_agent_manager = None


def get_agent_manager() -> AgentManager:
    """Get or create AgentManager singleton"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager


# Global embedding model for auto-routing
_kr_sbert_model = None


def get_kr_sbert_model():
    """Get or create KR-SBERT model singleton"""
    global _kr_sbert_model
    if _kr_sbert_model is None:
        _kr_sbert_model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
    return _kr_sbert_model


def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calculate search statistics from results

    Args:
        results: List of search results with 'stages' field

    Returns:
        Statistics dictionary
    """
    stats = {
        'total': len(results),
        'vector_count': 0,
        'relationship_count': 0,
        'graph_expansion_count': 0,
        'my_domain_count': 0,
        'neighbor_count': 0,
    }

    for result in results:
        # Count by stages (a result can have multiple stages)
        stages = result.get('stages', [result.get('stage', '')])
        stages_str = ' '.join(stages) if isinstance(stages, list) else str(stages)

        if 'vector' in stages_str:
            stats['vector_count'] += 1
        if 'relationship' in stages_str:
            stats['relationship_count'] += 1
        # Count RNE results (stages like "rne_vector", "rne_relationship", etc.)
        if 'rne_' in stages_str:
            stats['graph_expansion_count'] += 1

        # Count by source
        source = result.get('source', 'my_domain')
        if source == 'my_domain':
            stats['my_domain_count'] += 1
        else:
            stats['neighbor_count'] += 1

    return stats


def synthesize_results(query: str, results: List[Dict[str, Any]]) -> str:
    """
    GraphTeam Answer Agent 패턴으로 결과 종합

    Phase 3: Result Synthesis
    - GPT-4o가 multiple domain agent 결과를 natural language로 종합
    - GraphTeam/GraphAgent-Reasoner 논문 기반 Answer Agent 역할

    Args:
        query: 사용자 원본 쿼리
        results: 모든 domain agent의 검색 결과 (all_results)

    Returns:
        종합된 자연어 답변 (한국어)
    """
    from openai import OpenAI
    import json

    # [1] 상위 10개 결과만 사용 (토큰 제한)
    top_results = results[:10]

    if not top_results:
        return "검색 결과가 없어 답변을 생성할 수 없습니다."

    # [2] 결과 요약 생성 (GPT-4o에 전달할 context)
    results_summary = []
    for r in top_results:
        results_summary.append({
            "조항": r.get("hang_id", "N/A"),
            "도메인": r.get("source_domain", "주 도메인"),
            "내용": r.get("content", "")[:300],  # 300자 제한
            "유사도": round(r.get("similarity", 0), 3),
            "검색단계": r.get("stages", [])
        })

    # [3] GPT-4o 프롬프트 구성
    prompt = f"""당신은 한국 법률 전문 Answer Agent입니다.

사용자 질문: "{query}"

여러 법률 도메인 에이전트가 검색한 결과:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

작업:
1. 위 검색 결과들을 분석하여 사용자 질문에 대한 명확한 답변을 작성하세요
2. 여러 도메인에서 온 결과를 자연스럽게 통합하세요
3. 법률 조항을 구체적으로 인용하세요 (예: "국토의 계획 및 이용에 관한 법률 제17조")
4. 전문적이지만 이해하기 쉽게 작성하세요

답변 형식 (JSON):
{{
  "summary": "핵심 요약 (2-3문장)",
  "detailed_answer": "상세 설명 (법률 조항 인용 포함)",
  "cited_articles": ["인용된 조항 목록"],
  "confidence": 0.0-1.0
}}
"""

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Korean legal Answer Agent. Respond only in JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # [4] 최종 답변 생성 (summary + detailed_answer)
        summary = result.get("summary", "")
        detailed = result.get("detailed_answer", "")
        cited = result.get("cited_articles", [])
        confidence = result.get("confidence", 0.0)

        synthesized_answer = f"{summary}\n\n{detailed}"

        if cited:
            cited_str = ", ".join(cited)
            synthesized_answer += f"\n\n[참고 조항: {cited_str}]"

        logger.info(
            f"[Synthesis] Query='{query[:50]}...', "
            f"Results={len(top_results)}, "
            f"Confidence={confidence:.2f}, "
            f"Answer length={len(synthesized_answer)}"
        )

        return synthesized_answer

    except Exception as e:
        logger.error(f"[Synthesis] Error: {e}", exc_info=True)
        # Fallback: 기본 결과 나열
        fallback = f"'{query}' 검색 결과:\n\n"
        for i, r in enumerate(top_results[:3], 1):
            fallback += f"{i}. {r.get('hang_id', 'N/A')}: {r.get('content', '')[:100]}...\n\n"
        return fallback + "\n(자동 종합 실패 - 원본 결과 표시)"


def transform_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform DomainAgent results to frontend format

    Args:
        results: Raw results from DomainAgent

    Returns:
        Transformed results matching LawArticle interface
    """
    transformed = []

    for result in results:
        # Ensure stages is a list
        stages = result.get('stages', [])
        if not isinstance(stages, list):
            stages = [result.get('stage', 'vector')]

        transformed_result = {
            'hang_id': result.get('hang_id', ''),
            'content': result.get('content', ''),
            'unit_path': result.get('unit_path', ''),
            'similarity': float(result.get('similarity', 0.0)),
            'stages': stages,
            'source': result.get('source', 'my_domain'),
        }

        # Add optional A2A metadata if present
        if result.get('source_domain'):
            transformed_result['source_domain'] = result['source_domain']
        if result.get('via_a2a'):
            transformed_result['via_a2a'] = result['via_a2a']
        if result.get('a2a_refined_query'):
            transformed_result['a2a_refined_query'] = result['a2a_refined_query']

        transformed.append(transformed_result)

    return transformed


def auto_route_to_domain(query: str, agent_manager: AgentManager) -> str:
    """
    Auto-route query to best matching domain

    Args:
        query: User query
        agent_manager: AgentManager instance

    Returns:
        Best matching domain_id
    """
    domains_ranked = auto_route_to_top_domains(query, agent_manager, top_n=1)
    if not domains_ranked:
        raise ValueError("No domains available")
    return domains_ranked[0]['domain_id']


def auto_route_to_top_domains(query: str, agent_manager: AgentManager, top_n: int = 3, use_llm_assessment: bool = True) -> List[Dict[str, Any]]:
    """
    Auto-route query to top N matching domains with LLM Self-Assessment

    Hybrid Approach (GraphTeam/GraphAgent-Reasoner 논문 기반):
    1. Vector similarity로 후보 domains 선택 (fast pre-filtering)
    2. 각 domain agent가 GPT-4로 자기 평가 (true A2A reasoning)
    3. Confidence score로 재정렬
    4. Top N 반환

    Args:
        query: User query
        agent_manager: AgentManager instance
        top_n: Number of top domains to return
        use_llm_assessment: Use GPT-4 self-assessment (default: True)

    Returns:
        List of dicts with domain_id, domain_name, confidence, reasoning
    """
    if not agent_manager.domains:
        raise ValueError("No domains available")

    # [1] Vector similarity pre-filtering (fast)
    # Use OpenAI embeddings to match domain centroid dimensions (3072)
    from openai import OpenAI
    import os

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    response = client.embeddings.create(
        input=query,
        model="text-embedding-3-large"
    )
    query_embedding = np.array(response.data[0].embedding)

    logger.info(f"[Domain Routing] Query embedded with OpenAI (dim={len(query_embedding)})")

    domain_similarities = []

    for domain_id, domain_info in agent_manager.domains.items():
        if domain_info.centroid is None:
            domain_info.update_centroid(agent_manager.embeddings_cache)

        if domain_info.centroid is not None:
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                domain_info.centroid.reshape(1, -1)
            )[0][0]

            domain_similarities.append({
                'domain_id': domain_id,
                'domain_name': domain_info.domain_name,
                'vector_similarity': float(similarity),
                'domain_info': domain_info
            })

    # Sort by vector similarity
    domain_similarities.sort(key=lambda x: x['vector_similarity'], reverse=True)

    # Select top 5 candidates for LLM assessment (or top_n * 2)
    candidates = domain_similarities[:max(5, top_n * 2)]

    logger.info(f"[Domain Routing] Vector similarity: top {len(candidates)} candidates")

    # [2] LLM Self-Assessment (각 agent가 GPT-4로 자기 평가)
    if use_llm_assessment and candidates:
        logger.info(f"[LLM Assessment] Starting GPT-4 self-assessment for {len(candidates)} domains...")

        import asyncio

        async def assess_domain(candidate):
            domain_info = candidate['domain_info']
            if domain_info.agent_instance:
                try:
                    assessment = await domain_info.agent_instance.assess_query_confidence(query)
                    return {
                        'domain_id': candidate['domain_id'],
                        'domain_name': candidate['domain_name'],
                        'vector_similarity': candidate['vector_similarity'],
                        'llm_confidence': assessment.get('confidence', 0.0),
                        'llm_reasoning': assessment.get('reasoning', ''),
                        'can_answer': assessment.get('can_answer', False),
                        # Combined score: 70% LLM confidence + 30% vector similarity
                        'combined_score': assessment.get('confidence', 0.0) * 0.7 + candidate['vector_similarity'] * 0.3
                    }
                except Exception as e:
                    logger.error(f"[LLM Assessment] Error for {candidate['domain_name']}: {e}")
                    return {
                        'domain_id': candidate['domain_id'],
                        'domain_name': candidate['domain_name'],
                        'vector_similarity': candidate['vector_similarity'],
                        'llm_confidence': 0.0,
                        'llm_reasoning': f'Assessment failed: {str(e)}',
                        'can_answer': False,
                        'combined_score': candidate['vector_similarity'] * 0.3  # Fallback to vector only
                    }
            else:
                # Fallback: no agent instance
                return {
                    'domain_id': candidate['domain_id'],
                    'domain_name': candidate['domain_name'],
                    'vector_similarity': candidate['vector_similarity'],
                    'llm_confidence': 0.0,
                    'llm_reasoning': 'No agent instance',
                    'can_answer': False,
                    'combined_score': candidate['vector_similarity']
                }

        # Run assessments concurrently
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            assessed_domains = loop.run_until_complete(
                asyncio.gather(*[assess_domain(c) for c in candidates])
            )
        finally:
            loop.close()

        # Sort by combined score
        assessed_domains.sort(key=lambda x: x['combined_score'], reverse=True)

        # Return top N
        top_domains = assessed_domains[:top_n]

        logger.info(f"[LLM Assessment] Top {len(top_domains)} domains after GPT-4 assessment:")
        for i, d in enumerate(top_domains, 1):
            logger.info(
                f"  {i}. {d['domain_name']}: "
                f"Combined={d['combined_score']:.3f} "
                f"(LLM={d['llm_confidence']:.3f}, Vector={d['vector_similarity']:.3f}) "
                f"- {d['llm_reasoning'][:50]}..."
            )

        return top_domains

    else:
        # Fallback: vector similarity only
        top_domains = candidates[:top_n]
        logger.info(f"[Domain Routing] Vector similarity only (no LLM): top {len(top_domains)} domains")
        for i, d in enumerate(top_domains, 1):
            logger.info(f"  {i}. {d['domain_name']} (similarity={d['vector_similarity']:.3f})")

        return [
            {
                'domain_id': d['domain_id'],
                'domain_name': d['domain_name'],
                'vector_similarity': d['vector_similarity'],
                'combined_score': d['vector_similarity']
            }
            for d in top_domains
        ]


@method_decorator(csrf_exempt, name='dispatch')
class LawSearchAPIView(APIView):
    """
    Law Search API with automatic domain routing

    POST /api/law/search

    Request:
        {
            "query": str,
            "limit": int (optional, default=10),
            "synthesize": bool (optional, default=false) - Phase 3: GPT-4o result synthesis
        }

    Response:
        {
            "results": [...],
            "stats": {...},
            "domain_id": str,
            "domain_name": str,
            "domains_queried": [str],
            "response_time": int (ms),
            "synthesized_answer": str (optional, if synthesize=true)
        }
    """

    def post(self, request):
        """Handle search request with multi-domain A2A fallback"""
        try:
            start_time = time.time()

            # Parse request
            query = request.data.get('query')
            limit = request.data.get('limit', 10)
            synthesize = request.data.get('synthesize', False)  # Phase 3: Result Synthesis

            if not query:
                return Response(
                    {'error': 'Query is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get AgentManager
            agent_manager = get_agent_manager()

            # Get top 3 domains for potential fallback (A2A collaboration)
            top_domains = auto_route_to_top_domains(query, agent_manager, top_n=3)

            if not top_domains:
                return Response(
                    {'error': 'No domains available'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # [1] Query primary domain first
            primary_domain = top_domains[0]
            primary_domain_id = primary_domain['domain_id']
            primary_domain_info = agent_manager.domains.get(primary_domain_id)

            if not primary_domain_info or not primary_domain_info.agent_instance:
                return Response(
                    {'error': f'Primary domain {primary_domain_id} not initialized'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Log with LLM assessment info if available
            if 'llm_confidence' in primary_domain:
                logger.info(
                    f"[Primary] Searching domain: {primary_domain['domain_name']} "
                    f"(combined_score={primary_domain.get('combined_score', 0):.3f}, "
                    f"LLM={primary_domain['llm_confidence']:.3f}, "
                    f"Vector={primary_domain.get('vector_similarity', 0):.3f})"
                )
            else:
                logger.info(f"[Primary] Searching domain: {primary_domain['domain_name']} (score={primary_domain.get('combined_score', 0):.3f})")

            # Execute primary search (async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                primary_results = loop.run_until_complete(
                    primary_domain_info.agent_instance._search_my_domain(query)
                )
            finally:
                loop.close()

            # Mark results with source domain
            for result in primary_results:
                result['source_domain'] = primary_domain['domain_name']
                result['source_domain_id'] = primary_domain_id

            # [1.5] Filter out 부칙 (제4절) results - these are amendments/transitional provisions
            bukchik_results = [r for r in primary_results if '제4절' in r.get('hang_id', '')]
            non_bukchik_results = [r for r in primary_results if '제4절' not in r.get('hang_id', '')]

            if bukchik_results:
                logger.info(f"[Filter] Removed {len(bukchik_results)} 부칙 (제4절) results from primary domain")

            all_results = non_bukchik_results

            # [2] GPT-4o A2A Collaboration (GraphTeam/GraphAgent-Reasoner 논문 기반)
            # Primary domain agent가 GPT-4o로 협업 필요 여부 판단
            collaboration_triggered = False
            a2a_collaborating_domains = []  # Track domains that successfully provided results via A2A

            # Available domains for collaboration (exclude primary)
            available_domain_names = [d['domain_name'] for d in top_domains[1:]]

            if available_domain_names:
                logger.info("[A2A] Checking if collaboration with other domains is needed...")

                # Ask primary domain agent if collaboration needed
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    collaboration_decision = loop.run_until_complete(
                        primary_domain_info.agent_instance.should_collaborate(
                            query=query,
                            initial_results=non_bukchik_results,
                            available_domains=available_domain_names
                        )
                    )
                finally:
                    loop.close()

                if collaboration_decision.get('should_collaborate', False):
                    collaboration_triggered = True
                    target_domains = collaboration_decision.get('target_domains', [])

                    logger.info(
                        f"[A2A] Collaboration needed! "
                        f"GPT-4o recommends querying {len(target_domains)} domains: "
                        f"{[td['domain_name'] for td in target_domains]}"
                    )

                    # A2A message exchange with target domains (DynTaskMAS APEE - Parallel Execution)
                    logger.info(f"[A2A Parallel] Starting parallel queries to {len(target_domains)} domains")
                    import time as time_module
                    a2a_start_time = time_module.time()

                    # Helper async function for parallel A2A requests
                    async def send_a2a_to_domain(target_domain_spec):
                        """Send A2A request to a single domain (async)"""
                        target_domain_name = target_domain_spec['domain_name']
                        refined_query = target_domain_spec['refined_query']
                        reason = target_domain_spec['reason']

                        # Find target domain
                        target_domain_info = None
                        target_domain_id = None
                        for domain in top_domains[1:]:
                            if domain['domain_name'] == target_domain_name:
                                target_domain_id = domain['domain_id']
                                target_domain_info = agent_manager.domains.get(target_domain_id)
                                break

                        if not target_domain_info or not target_domain_info.agent_instance:
                            logger.warning(f"[A2A Parallel] Target domain '{target_domain_name}' not found")
                            return None

                        logger.info(
                            f"[A2A Parallel] Sending to '{target_domain_name}' "
                            f"(Reason: {reason}, Query: '{refined_query}')"
                        )

                        # Send A2A request
                        a2a_message = {
                            "query": refined_query,
                            "context": f"Original query: {query}",
                            "limit": 5,
                            "requestor": primary_domain['domain_name']
                        }

                        a2a_response = await target_domain_info.agent_instance.handle_a2a_request(a2a_message)

                        if a2a_response['status'] == 'success':
                            a2a_results = a2a_response['results']

                            # Filter out 부칙
                            bukchik_a2a = [r for r in a2a_results if '제4절' in r.get('hang_id', '')]
                            non_bukchik_a2a = [r for r in a2a_results if '제4절' not in r.get('hang_id', '')]

                            if bukchik_a2a:
                                logger.info(f"[A2A Parallel] Filtered {len(bukchik_a2a)} 부칙 from '{target_domain_name}'")

                            # Mark results
                            for result in non_bukchik_a2a:
                                result['source_domain'] = target_domain_name
                                result['source_domain_id'] = target_domain_id
                                result['a2a_refined_query'] = refined_query
                                result['via_a2a'] = True
                                result['source'] = 'a2a'

                            logger.info(f"[A2A Parallel] '{target_domain_name}' returned {len(non_bukchik_a2a)} results")

                            return {
                                'domain_name': target_domain_name,
                                'domain_id': target_domain_id,
                                'results': non_bukchik_a2a,
                                'success': True
                            }
                        else:
                            logger.error(f"[A2A Parallel] Error from '{target_domain_name}': {a2a_response['message']}")
                            return None

                    # Execute all A2A requests in parallel
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        a2a_tasks = [send_a2a_to_domain(spec) for spec in target_domains]
                        a2a_responses = loop.run_until_complete(
                            asyncio.gather(*a2a_tasks, return_exceptions=True)
                        )
                    finally:
                        loop.close()

                    a2a_elapsed = time_module.time() - a2a_start_time
                    logger.info(f"[A2A Parallel] All {len(target_domains)} domains completed in {a2a_elapsed:.2f}s")

                    # Process results
                    successful_count = 0
                    failed_count = 0
                    for response in a2a_responses:
                        if isinstance(response, Exception):
                            failed_count += 1
                            logger.error(f"[A2A Parallel] Domain request failed: {response}")
                            continue

                        if response and response.get('success'):
                            successful_count += 1
                            all_results.extend(response['results'])

                            # Track collaboration
                            if response['results']:
                                a2a_collaborating_domains.append({
                                    'domain_name': response['domain_name'],
                                    'domain_id': response['domain_id'],
                                    'results_count': len(response['results'])
                                })
                        else:
                            failed_count += 1

                    logger.info(
                        f"[A2A Parallel] Summary: {successful_count} succeeded, {failed_count} failed, "
                        f"{sum(len(r.get('results', [])) for r in a2a_responses if r and not isinstance(r, Exception))} total results"
                    )
                else:
                    logger.info("[A2A] GPT-4o determined no collaboration needed - primary domain sufficient")

            # [3] Merge, deduplicate, and boost diversity
            logger.info(f"[Phase 3] Processing {len(all_results)} total results before deduplication")

            # [3.1] Deduplicate by hang_id
            deduplicated_results = deduplicate_results(all_results)
            logger.info(f"[Phase 3] After deduplication: {len(deduplicated_results)} results ({len(all_results) - len(deduplicated_results)} duplicates removed)")

            # [3.2] Sort by similarity
            deduplicated_results.sort(key=lambda x: x.get('similarity', 0.0), reverse=True)

            # [3.3] Boost diversity across law types (법률/시행령/시행규칙)
            diversity_boosted_results = boost_diversity_by_law_type(deduplicated_results)
            logger.info(f"[Phase 3] Applied diversity boosting for law types")

            # [3.4] Limit results
            all_results = diversity_boosted_results[:limit]
            logger.info(f"[Phase 3] Final result count: {len(all_results)}")

            # Calculate statistics
            stats = calculate_statistics(all_results)
            stats['domains_queried'] = len(set(r.get('source_domain_id', primary_domain_id) for r in all_results))
            stats['a2a_collaboration_triggered'] = collaboration_triggered
            stats['a2a_collaborations'] = len(a2a_collaborating_domains)  # Number of domains that provided A2A results
            stats['a2a_results_count'] = sum(r.get('via_a2a', False) for r in all_results)  # Total A2A results

            # Transform results
            transformed_results = transform_results(all_results)

            # [Phase 3] Result Synthesis (optional)
            synthesized_answer = None
            if synthesize and all_results:
                logger.info(f"[Synthesis] Starting GPT-4o result synthesis for query: '{query[:50]}...'")
                synthesized_answer = synthesize_results(query, all_results)

            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)

            # Build response
            response_data = {
                'results': transformed_results,
                'stats': stats,
                'domain_id': primary_domain_id,
                'domain_name': primary_domain['domain_name'],
                'domains_queried': [d['domain_name'] for d in top_domains[:stats['domains_queried']]],
                'a2a_domains': [d['domain_name'] for d in a2a_collaborating_domains],  # Domains that provided A2A results
                'response_time': response_time,
            }

            # Add synthesized answer if generated
            if synthesized_answer:
                response_data['synthesized_answer'] = synthesized_answer

            logger.info(
                f"Search completed: query='{query[:50]}...', "
                f"primary_domain={primary_domain['domain_name']}, "
                f"domains_queried={stats['domains_queried']}, "
                f"results={len(transformed_results)}, "
                f"time={response_time}ms"
            )

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in LawSearchAPIView: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class DomainSearchAPIView(APIView):
    """
    Domain-specific Law Search API

    POST /api/law/domain/<domain_id>/search

    Request:
        {
            "query": str,
            "limit": int (optional, default=10)
        }

    Response:
        {
            "results": [...],
            "stats": {...},
            "domain_id": str,
            "domain_name": str,
            "response_time": int (ms)
        }
    """

    def post(self, request, domain_id):
        """Handle search request for specific domain"""
        try:
            start_time = time.time()

            # Parse request
            query = request.data.get('query')
            limit = request.data.get('limit', 10)

            if not query:
                return Response(
                    {'error': 'Query is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get AgentManager
            agent_manager = get_agent_manager()

            # Get specified domain
            domain_info = agent_manager.domains.get(domain_id)

            if not domain_info:
                return Response(
                    {'error': f'Domain {domain_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get DomainAgent instance
            domain_agent = domain_info.agent_instance

            if not domain_agent:
                return Response(
                    {'error': f'Domain agent not initialized for {domain_id}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Execute search (async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    domain_agent._search_my_domain(query)
                )
            finally:
                loop.close()

            # Limit results
            results = results[:limit]

            # Calculate statistics
            stats = calculate_statistics(results)

            # Transform results
            transformed_results = transform_results(results)

            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)

            # Build response
            response_data = {
                'results': transformed_results,
                'stats': stats,
                'domain_id': domain_id,
                'domain_name': domain_info.domain_name,
                'response_time': response_time,
            }

            logger.info(
                f"Domain search completed: query='{query[:50]}...', "
                f"domain={domain_info.domain_name}, "
                f"results={len(transformed_results)}, "
                f"time={response_time}ms"
            )

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in DomainSearchAPIView: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
