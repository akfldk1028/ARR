"""
Domain Agent - 특정 법률 도메인 담당 Worker

자가 조직화 MAS의 핵심 컴포넌트:
- 특정 법률 도메인 (예: "도시계획", "건축규제")의 HANG 노드들 관리
- RNE/INE 알고리즘으로 그래프 검색
- A2A 프로토콜로 이웃 도메인과 협업
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from agents.worker_agents.base.base_worker import BaseWorkerAgent
from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)


class DomainAgent(BaseWorkerAgent):
    """
    도메인 에이전트 - 특정 법률 도메인 전문가

    특징:
    - 도메인별 HANG 노드 집합 관리
    - RNE/INE 알고리즘으로 의미론적 검색
    - A2A로 이웃 도메인 에이전트와 협업
    - QueryCoordinator로부터 호출됨
    """

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any], domain_info: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # 도메인 정보
        self.domain_id = domain_info['domain_id']
        self.domain_name = domain_info['domain_name']
        self.node_ids = set(domain_info.get('node_ids', []))
        self.neighbor_agents = domain_info.get('neighbor_agents', [])

        # RNE/INE 알고리즘 설정
        self.rne_threshold = agent_config.get('rne_threshold', 0.75)
        self.ine_k = agent_config.get('ine_k', 10)

        logger.info(f"DomainAgent '{self.domain_name}' initialized with {len(self.node_ids)} nodes")

    @property
    def agent_name(self) -> str:
        return f"Law Domain Agent - {self.domain_name}"

    @property
    def agent_description(self) -> str:
        return f"한국 법률 전문 에이전트 - {self.domain_name} 도메인 담당 ({len(self.node_ids)} 조항)"

    @property
    def capabilities(self) -> List[str]:
        return [
            "legal_search",
            "semantic_graph_search",
            "cross_law_reference",
            "domain_collaboration"
        ]

    @property
    def system_prompt(self) -> str:
        return f"""당신은 한국 법률 전문 AI 어시스턴트입니다.
전문 분야: {self.domain_name}
관리 조항: {len(self.node_ids)}개

당신의 역할:
1. 사용자의 법률 질문을 분석합니다
2. RNE/INE 알고리즘으로 관련 조항을 검색합니다
3. 필요 시 다른 도메인 에이전트와 협업합니다
4. 정확하고 간결한 법률 정보를 제공합니다

검색 방식:
- Stage 1: Vector Search (의미론적 유사도)
- Stage 2: Graph Expansion (RNE/INE로 연관 조항 탐색)
- Stage 3: Cross-law 확장 (시행령/시행규칙 포함)

응답 형식:
1. 핵심 조항 (가장 관련도 높은 조항)
2. 연관 조항 (그래프 확장으로 발견된 조항)
3. 시행령/시행규칙 (cross_law 관계)
"""

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """
        사용자 질의에 대한 응답 생성

        워크플로우:
        1. 자기 도메인 검색 (RNE/INE)
        2. 결과 품질 평가
        3. 필요 시 이웃 도메인 에이전트에게 A2A 요청
        4. 결과 통합 및 응답 생성
        """
        try:
            # [1] 자기 도메인 검색
            my_results = await self._search_my_domain(user_input)

            # [2] 결과 품질 평가
            quality_score = self._evaluate_results(my_results)

            # [3] 협업 필요성 판단
            neighbor_results = []
            if quality_score < 0.6 and self.neighbor_agents:
                logger.info(f"Quality score {quality_score:.2f} < 0.6, consulting neighbors")
                neighbor_results = await self._consult_neighbors(user_input)

            # [4] 결과 통합
            all_results = self._merge_results(my_results, neighbor_results)

            # [5] 응답 생성
            response = self._format_response(user_input, all_results)

            return response

        except Exception as e:
            logger.error(f"Error in DomainAgent._generate_response: {e}")
            return f"죄송합니다. 법률 검색 중 오류가 발생했습니다: {str(e)}"

    async def _search_my_domain(self, query: str) -> List[Dict]:
        """
        자기 도메인 내 검색 (RNE/INE)

        Args:
            query: 사용자 질의

        Returns:
            검색 결과 리스트
        """
        # [1] 쿼리 임베딩 생성
        query_embedding = await self._generate_query_embedding(query)

        # [2] Stage 1: Vector Search
        vector_results = await self._vector_search(query_embedding, limit=5)

        if not vector_results:
            return []

        # [3] Stage 2: Graph Expansion (RNE)
        expanded_results = await self._graph_expansion(vector_results[0]['hang_id'], query_embedding)

        # [4] Stage 3: Reranking
        all_results = vector_results + expanded_results
        reranked = self._rerank_results(all_results, query_embedding)

        return reranked[:10]  # Top 10

    async def _vector_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        벡터 검색 (Stage 1)

        Args:
            query_embedding: 쿼리 임베딩
            limit: 결과 개수

        Returns:
            검색 결과 리스트
        """
        # Neo4j native vector index query (no GDS plugin needed)
        query = """
        CALL db.index.vector.queryNodes('hang_embedding_index', $limit_multiplier, $query_embedding)
        YIELD node, score
        WHERE node.full_id IN $node_ids
          AND score >= 0.5
        RETURN node.full_id AS hang_id,
               node.content AS content,
               node.unit_path AS unit_path,
               score AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        # Use limit * 3 to get enough results after filtering by node_ids
        results = self.neo4j_service.execute_query(query, {
            'node_ids': list(self.node_ids),
            'query_embedding': query_embedding,
            'limit': limit,
            'limit_multiplier': limit * 3
        })

        return [
            {
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'vector'
            }
            for r in results
        ]

    async def _graph_expansion(self, start_hang_id: str, query_embedding: List[float]) -> List[Dict]:
        """
        그래프 확장 (Stage 2: RNE)

        Args:
            start_hang_id: 시작 노드 ID
            query_embedding: 쿼리 임베딩

        Returns:
            확장된 검색 결과
        """
        # RNE 알고리즘으로 이웃 확장 (Python에서 유사도 계산)
        query = """
        MATCH (start:HANG {full_id: $start_hang_id})
        MATCH (start)<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
        WHERE neighbor.full_id <> $start_hang_id
          AND neighbor.full_id IN $node_ids
          AND neighbor.embedding IS NOT NULL

        // Cross-law 확장
        OPTIONAL MATCH (neighbor)<-[:CONTAINS*]-(law1:LAW)
                       -[:IMPLEMENTS*]->(law2:LAW)
                       -[:CONTAINS*]->(cross_hang:HANG)
        WHERE cross_hang.embedding IS NOT NULL
          AND cross_hang.full_id IN $node_ids

        RETURN neighbor.full_id AS hang_id,
               neighbor.content AS content,
               neighbor.unit_path AS unit_path,
               neighbor.embedding AS embedding,
               collect(DISTINCT {
                   hang_id: cross_hang.full_id,
                   content: cross_hang.content,
                   unit_path: cross_hang.unit_path,
                   embedding: cross_hang.embedding
               }) AS cross_law_nodes
        LIMIT 50
        """

        results = self.neo4j_service.execute_query(query, {
            'start_hang_id': start_hang_id,
            'node_ids': list(self.node_ids)
        })

        # Python에서 코사인 유사도 계산
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        query_vec = np.array(query_embedding).reshape(1, -1)
        expanded_results = []

        for r in results:
            # 메인 노드 유사도 계산
            neighbor_emb = np.array(r['embedding']).reshape(1, -1)
            similarity = cosine_similarity(query_vec, neighbor_emb)[0][0]

            if similarity >= self.rne_threshold:
                expanded_results.append({
                    'hang_id': r['hang_id'],
                    'content': r['content'],
                    'unit_path': r['unit_path'],
                    'similarity': float(similarity),
                    'stage': 'graph_expansion'
                })

            # Cross-law 노드들 유사도 계산
            for cross_node in r['cross_law_nodes']:
                if cross_node['hang_id'] and cross_node['embedding']:
                    cross_emb = np.array(cross_node['embedding']).reshape(1, -1)
                    cross_sim = cosine_similarity(query_vec, cross_emb)[0][0]

                    if cross_sim >= self.rne_threshold:
                        expanded_results.append({
                            'hang_id': cross_node['hang_id'],
                            'content': cross_node['content'],
                            'unit_path': cross_node['unit_path'],
                            'similarity': float(cross_sim),
                            'stage': 'cross_law'
                        })

        return expanded_results

    def _rerank_results(self, results: List[Dict], query_embedding: List[float]) -> List[Dict]:
        """
        결과 재순위화 (Stage 3)

        Args:
            results: 검색 결과 리스트
            query_embedding: 쿼리 임베딩

        Returns:
            재순위화된 결과
        """
        # 중복 제거
        seen = set()
        unique_results = []
        for r in results:
            if r['hang_id'] not in seen:
                seen.add(r['hang_id'])
                unique_results.append(r)

        # 유사도 내림차순 정렬
        unique_results.sort(key=lambda x: x['similarity'], reverse=True)

        return unique_results

    async def _consult_neighbors(self, query: str) -> List[Dict]:
        """
        이웃 도메인 에이전트와 협업 (A2A)

        Args:
            query: 사용자 질의

        Returns:
            이웃으로부터 받은 검색 결과
        """
        neighbor_results = []

        for neighbor_slug in self.neighbor_agents[:3]:  # 최대 3개 이웃
            try:
                # A2A 메시지 전송
                response = await self.communicate_with_agent(
                    target_agent_slug=neighbor_slug,
                    message=f"법률 검색 협업 요청: {query}",
                    context_id=f"domain_collaboration_{self.domain_id}"
                )

                if response:
                    # 응답 파싱 (JSON 형식 기대)
                    import json
                    try:
                        data = json.loads(response)
                        neighbor_results.extend(data.get('results', []))
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from neighbor {neighbor_slug}")

            except Exception as e:
                logger.error(f"Error consulting neighbor {neighbor_slug}: {e}")

        return neighbor_results

    def _evaluate_results(self, results: List[Dict]) -> float:
        """
        검색 결과 품질 평가

        Args:
            results: 검색 결과

        Returns:
            품질 점수 (0.0 ~ 1.0)
        """
        if not results:
            return 0.0

        # 평균 유사도
        avg_similarity = sum(r['similarity'] for r in results) / len(results)

        # 결과 개수 (최소 5개 이상 권장)
        count_score = min(len(results) / 5.0, 1.0)

        # 종합 점수
        quality_score = (avg_similarity * 0.7) + (count_score * 0.3)

        return quality_score

    def _merge_results(self, my_results: List[Dict], neighbor_results: List[Dict]) -> List[Dict]:
        """
        자기 결과와 이웃 결과 통합

        Args:
            my_results: 자기 도메인 결과
            neighbor_results: 이웃 도메인 결과

        Returns:
            통합된 결과
        """
        # 중복 제거
        seen = set()
        merged = []

        # 자기 결과 우선 (도메인 전문성)
        for r in my_results:
            if r['hang_id'] not in seen:
                seen.add(r['hang_id'])
                r['source'] = 'my_domain'
                merged.append(r)

        # 이웃 결과 추가
        for r in neighbor_results:
            if r['hang_id'] not in seen:
                seen.add(r['hang_id'])
                r['source'] = 'neighbor_domain'
                merged.append(r)

        # 유사도 순 정렬
        merged.sort(key=lambda x: x['similarity'], reverse=True)

        return merged[:15]  # Top 15

    def _format_response(self, query: str, results: List[Dict]) -> str:
        """
        사용자 친화적 응답 생성

        Args:
            query: 사용자 질의
            results: 검색 결과

        Returns:
            응답 텍스트
        """
        if not results:
            return f"'{query}'에 대한 관련 법률 조항을 찾지 못했습니다."

        # 응답 구성
        response_parts = [
            f"'{query}'에 대한 {self.domain_name} 관련 법률 정보입니다.\n"
        ]

        # 핵심 조항 (Top 3)
        response_parts.append("\n[핵심 조항]")
        for i, r in enumerate(results[:3], 1):
            response_parts.append(
                f"\n{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})\n"
                f"   {r['content'][:200]}..."
            )

        # 연관 조항 (4~6위)
        if len(results) > 3:
            response_parts.append("\n\n[연관 조항]")
            for i, r in enumerate(results[3:6], 4):
                response_parts.append(
                    f"\n{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})"
                )

        # 통계 정보
        my_domain_count = sum(1 for r in results if r.get('source') == 'my_domain')
        neighbor_count = sum(1 for r in results if r.get('source') == 'neighbor_domain')

        response_parts.append(
            f"\n\n총 {len(results)}개 조항 발견 "
            f"(자체: {my_domain_count}, 협업: {neighbor_count})"
        )

        return ''.join(response_parts)

    async def _generate_query_embedding(self, query: str) -> List[float]:
        """쿼리 임베딩 생성"""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
        embedding = model.encode(query)
        return embedding.tolist()
