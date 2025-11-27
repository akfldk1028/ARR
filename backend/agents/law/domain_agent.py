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
# Phase 1.5: RNE Graph Expansion
from graph_db.algorithms.core.semantic_rne import SemanticRNE
from graph_db.algorithms.repository.law_repository import LawRepository
# Law information enrichment utilities
from agents.law.utils import enrich_hang_results

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

        # Phase 1.5: RNE 알고리즘 초기화
        self._law_repository = None
        self._semantic_rne = None
        self._kr_sbert_model = None

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

    async def _search_my_domain(self, query: str, limit: int = 30) -> List[Dict]:
        """
        자기 도메인 내 검색 (Hybrid Search: Exact match + Semantic)

        Args:
            query: 사용자 질의
            limit: 반환할 최대 결과 개수 (default: 30, Phase 1.8 증가)

        Returns:
            검색 결과 리스트
        """
        logger.info(f"[DomainAgent {self.domain_name}] Search query: {query[:50]}...")

        # [1] 쿼리 임베딩 생성 (2가지)
        kr_sbert_embedding = await self._generate_kr_sbert_embedding(query)  # 768-dim for RNE only
        openai_embedding = await self._generate_openai_embedding(query)      # 3072-dim for HANG nodes + relationships

        # [2] Hybrid Search (Exact match + Semantic vector + Relationship)
        # Phase 1.8: limit 증가 (10 → 30)
        hybrid_results = await self._hybrid_search(query, kr_sbert_embedding, openai_embedding, limit=30)

        logger.info(f"[DomainAgent {self.domain_name}] Hybrid search returned {len(hybrid_results)} results")

        if not hybrid_results:
            logger.warning(f"[DomainAgent {self.domain_name}] No results found for query: {query[:30]}...")
            return []

        # [3] Phase 1.5: RNE Graph Expansion (NEW)
        expanded_results = await self._rne_graph_expansion(query, hybrid_results[:5], kr_sbert_embedding)

        # [3.5] Phase 1.8: JO→HANG 확장 (JO 결과에서 하위 HANG 추가)
        expanded_hangs = await self._expand_jo_to_hangs(hybrid_results, query, openai_embedding)

        # [4] Merge hybrid + RNE + JO확장 HANG results
        all_results = self._merge_hybrid_and_rne(hybrid_results, expanded_results + expanded_hangs)

        logger.info(f"[DomainAgent {self.domain_name}] Final results (Hybrid + RNE + JO확장): {len(all_results)}")

        # [5] Enrich results with law_name, law_type, jo_number, hang_number
        enriched_results = enrich_hang_results(all_results[:limit])

        # [6] Return top N enriched results
        return enriched_results

    async def _exact_match_search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Exact match search (Sparse retrieval) - 조항 번호, 법률명 등

        Args:
            query: 원본 쿼리 문자열
            limit: 결과 개수

        Returns:
            Exact match 결과 리스트
        """
        import re

        # 조항 번호 패턴 추출 (제17조, 17조 등)
        article_pattern = re.search(r'제?(\d+)조', query)

        if not article_pattern:
            return []  # 조항 번호 없으면 빈 리스트 반환

        article_num = article_pattern.group(1)
        search_pattern = f'제{article_num}조'

        logger.info(f"[Exact Match] Searching for article pattern: {search_pattern}")

        # Neo4j exact match query
        cypher_query = """
        MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain {domain_id: $domain_id})
        WHERE h.full_id CONTAINS $search_pattern
          AND NOT h.full_id CONTAINS '제4절'
        RETURN h.full_id AS hang_id,
               h.content AS content,
               h.unit_path AS unit_path,
               1.0 as similarity
        LIMIT $limit
        """

        results = self.neo4j_service.execute_query(cypher_query, {
            'domain_id': self.domain_id,
            'search_pattern': search_pattern,
            'limit': limit
        })

        logger.info(f"[Exact Match] Found {len(results)} results for {search_pattern}")

        return [
            {
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'exact_match'
            }
            for r in results
        ]

    def _reciprocal_rank_fusion(self, result_lists: List[List[Dict]], k: int = 60) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) - Hybrid search 결과 병합

        Args:
            result_lists: 여러 검색 결과 리스트
            k: RRF 상수 (default 60, standard value)

        Returns:
            RRF 스코어로 정렬된 통합 결과
        """
        # hang_id -> RRF score 매핑
        rrf_scores = {}
        hang_data = {}  # hang_id -> 원본 데이터

        for result_list in result_lists:
            for rank, result in enumerate(result_list, start=1):
                hang_id = result['hang_id']

                # RRF formula: score = 1 / (k + rank)
                rrf_score = 1.0 / (k + rank)

                if hang_id in rrf_scores:
                    rrf_scores[hang_id] += rrf_score
                else:
                    rrf_scores[hang_id] = rrf_score
                    hang_data[hang_id] = result

        # RRF 스코어로 정렬
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 최종 결과 구성
        final_results = []
        for hang_id, rrf_score in sorted_results:
            result = hang_data[hang_id].copy()
            result['rrf_score'] = rrf_score
            result['similarity'] = rrf_score  # similarity 필드 업데이트

            # stages 통합 (여러 검색 방법에서 나온 경우)
            stages = set()
            for result_list in result_lists:
                for r in result_list:
                    if r['hang_id'] == hang_id:
                        stages.add(r.get('stage', 'unknown'))
            result['stages'] = list(stages)

            final_results.append(result)

        return final_results

    async def _hybrid_search(self, query: str, kr_sbert_embedding: List[float], openai_embedding: List[float], limit: int = 10) -> List[Dict]:
        """
        Hybrid Search: Exact match + Semantic search + RRF

        Args:
            query: 원본 쿼리 문자열
            kr_sbert_embedding: KR-SBERT 임베딩 (768-dim, RNE용으로만 사용)
            openai_embedding: OpenAI 임베딩 (3072-dim, HANG 노드 및 relationship search용)
            limit: 최종 결과 개수

        Returns:
            Hybrid search 결과
        """
        logger.info(f"[Hybrid Search] Query: {query[:50]}...")

        # [1] Exact match search (sparse retrieval)
        exact_results = await self._exact_match_search(query, limit=limit * 2)

        # [2] Semantic vector search (dense retrieval, 3072-dim OpenAI)
        # ✅ FIXED: Use openai_embedding instead of kr_sbert_embedding (HANG nodes have OpenAI embeddings)
        semantic_results = await self._vector_search(openai_embedding, limit=limit)

        # [3] Semantic relationship search (3072-dim)
        relationship_results = await self._search_relationships(openai_embedding, limit=limit)

        # [4] JO-level vector search (Phase 1.5: Multi-level Embedding)
        jo_results = await self._jo_vector_search(openai_embedding, limit=limit)

        # [5] RRF merge
        all_result_lists = []
        if exact_results:
            all_result_lists.append(exact_results)
            logger.info(f"[Hybrid] Exact match: {len(exact_results)} results")
        if semantic_results:
            all_result_lists.append(semantic_results)
            logger.info(f"[Hybrid] Semantic vector: {len(semantic_results)} results")
        if relationship_results:
            all_result_lists.append(relationship_results)
            logger.info(f"[Hybrid] Relationship: {len(relationship_results)} results")
        if jo_results:
            all_result_lists.append(jo_results)
            logger.info(f"[Hybrid] JO-level: {len(jo_results)} results")

        if not all_result_lists:
            return []

        # RRF로 결과 병합
        hybrid_results = self._reciprocal_rank_fusion(all_result_lists)

        logger.info(f"[Hybrid] Final merged results: {len(hybrid_results)}")

        return hybrid_results[:limit]

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
        # ✅ FIXED: Use BELONGS_TO_DOMAIN relationship instead of node_ids list
        query = """
        CALL db.index.vector.queryNodes('hang_embedding_index', $limit_multiplier, $query_embedding)
        YIELD node, score
        WHERE EXISTS((node)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
          AND score >= 0.5
        RETURN node.full_id AS hang_id,
               node.content AS content,
               node.unit_path AS unit_path,
               score AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        # Use limit * 3 to get enough results after filtering by domain
        results = self.neo4j_service.execute_query(query, {
            'domain_id': self.domain_id,
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

    async def _search_relationships(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        관계 임베딩 검색 (CONTAINS 관계)

        Args:
            query_embedding: 쿼리 임베딩
            limit: 결과 개수

        Returns:
            관계 검색 결과 리스트
        """
        # ✅ FIXED: Use BELONGS_TO_DOMAIN relationship instead of node_ids list
        query = """
        CALL db.index.vector.queryRelationships(
            'contains_embedding',
            $limit_multiplier,
            $query_embedding
        ) YIELD relationship, score
        MATCH (from)-[relationship]->(to:HANG)
        WHERE score >= 0.65
          AND EXISTS((to)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
        RETURN
            to.full_id AS hang_id,
            to.content AS content,
            to.unit_path AS unit_path,
            score AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        results = self.neo4j_service.execute_query(query, {
            'query_embedding': query_embedding,
            'limit': limit,
            'limit_multiplier': limit * 3,
            'domain_id': self.domain_id
        })

        return [
            {
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'relationship'
            }
            for r in results
        ]

    async def _jo_vector_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        JO 노드 벡터 검색 (Phase 1.5: Multi-level Embedding)

        JO 레벨 검색으로 HANG 없는 조항도 검색 가능
        - 제4장::제36조처럼 HANG 없는 조항도 검색됨
        - OpenAI 3072-dim 임베딩 사용

        Args:
            query_embedding: 쿼리 임베딩 (3072-dim OpenAI)
            limit: 결과 개수

        Returns:
            JO 검색 결과 리스트
        """
        # Direct Cypher query (no vector index needed for now)
        query = """
        MATCH (jo:JO)
        WHERE jo.embedding IS NOT NULL
          AND NOT jo.full_id CONTAINS '제12장'

        WITH jo,
             vector.similarity.cosine(jo.embedding, $query_embedding) AS score

        WHERE score >= 0.5

        RETURN jo.full_id AS hang_id,
               coalesce(jo.title, jo.unit_number, '') AS content,
               jo.full_id AS unit_path,
               score AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        results = self.neo4j_service.execute_query(query, {
            'query_embedding': query_embedding,
            'limit': limit
        })

        logger.info(f"[JO Search] Found {len(results)} JO-level results")

        return [
            {
                'hang_id': r['hang_id'],
                'content': r['content'],
                'unit_path': r['unit_path'],
                'similarity': r['similarity'],
                'stage': 'jo_vector'
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

    async def _expand_jo_to_hangs(self, results: List[Dict], query: str, query_embedding: List[float]) -> List[Dict]:
        """
        Phase 1.8: JO 레벨 결과에서 하위 HANG 노드 확장

        JO (조) 결과가 많은 경우, 그 아래의 HANG (항) 노드들도 가져와서 상세 내용 제공

        Args:
            results: 검색 결과 (JO 포함)
            query: 쿼리 문자열
            query_embedding: 쿼리 임베딩

        Returns:
            확장된 HANG 노드 리스트
        """
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        expanded_hangs = []

        # JO 레벨 결과만 필터
        jo_results = [r for r in results if r.get('stage') == 'jo_vector']

        if not jo_results:
            return []

        logger.info(f"[JO→HANG Expansion] Found {len(jo_results)} JO results, expanding to HANGs...")

        # 각 JO에서 하위 HANG 가져오기
        for jo_result in jo_results[:10]:  # 상위 10개 JO만
            jo_id = jo_result['hang_id']  # JO의 full_id

            # JO의 하위 HANG 노드들 가져오기
            query_hangs = """
            MATCH (jo:JO {full_id: $jo_id})-[:CONTAINS]->(hang:HANG)
            WHERE hang.embedding IS NOT NULL
              AND NOT hang.full_id CONTAINS '제12장'
              AND NOT hang.full_id CONTAINS '제4절'
            RETURN hang.full_id AS hang_id,
                   hang.content AS content,
                   hang.unit_path AS unit_path,
                   hang.embedding AS embedding
            LIMIT 10
            """

            hangs = self.neo4j_service.execute_query(query_hangs, {'jo_id': jo_id})

            if not hangs:
                continue

            # 각 HANG의 유사도 계산
            query_vec = np.array(query_embedding).reshape(1, -1)

            for hang in hangs:
                hang_emb = np.array(hang['embedding']).reshape(1, -1)
                similarity = cosine_similarity(query_vec, hang_emb)[0][0]

                if similarity >= 0.5:  # 최소 유사도 threshold
                    expanded_hangs.append({
                        'hang_id': hang['hang_id'],
                        'content': hang['content'],
                        'unit_path': hang['unit_path'],
                        'similarity': float(similarity),
                        'stage': 'jo_expansion',
                        'source': 'my_domain'
                    })

        logger.info(f"[JO→HANG Expansion] Expanded {len(expanded_hangs)} HANG nodes from JO results")

        return expanded_hangs

    async def _rne_graph_expansion(
        self,
        query: str,
        initial_results: List[Dict],
        kr_sbert_embedding: List[float]
    ) -> List[Dict]:
        """
        Phase 1.5: SemanticRNE 그래프 확장

        SemanticRNE 알고리즘으로 그래프 확장 수행.
        Hybrid search 결과는 참고용이며, RNE는 독립적으로 벡터 검색부터 수행.

        Args:
            query: 검색 쿼리
            initial_results: Hybrid search 결과 (참고용, 도메인 필터링에 활용)
            kr_sbert_embedding: KR-SBERT 임베딩 (현재 미사용, RNE가 자체 생성)

        Returns:
            RNE 확장 결과 리스트
        """
        try:
            # [1] Lazy initialization: LawRepository & SemanticRNE
            if self._law_repository is None:
                self._law_repository = LawRepository(self.neo4j_service)
                logger.info("[RNE] LawRepository initialized")

            if self._kr_sbert_model is None:
                from sentence_transformers import SentenceTransformer
                self._kr_sbert_model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
                logger.info("[RNE] KR-SBERT model loaded")

            if self._semantic_rne is None:
                self._semantic_rne = SemanticRNE(None, self._law_repository, self._kr_sbert_model)
                logger.info("[RNE] SemanticRNE initialized")

            logger.info(f"[RNE] Starting RNE expansion for query: {query[:50]}...")

            # [2] RNE 실행 (벡터 검색부터 그래프 확장까지 전체 수행)
            rne_results, _ = self._semantic_rne.execute_query(
                query_text=query,
                similarity_threshold=self.rne_threshold,  # 0.75
                max_results=20,
                initial_candidates=10  # 초기 벡터 검색 개수
            )

            logger.info(f"[RNE] RNE returned {len(rne_results)} results")

            # [3] RNE 결과를 domain_agent 포맷으로 변환
            # NOTE: 도메인 필터링 제거 - RNE의 목적은 그래프 관계를 따라
            #       다른 도메인의 관련 조항도 찾는 것이므로, 모든 결과 포함
            expanded_results = []
            for rne_r in rne_results:
                hang_full_id = rne_r.get('full_id', '')
                expanded_results.append({
                    'hang_id': hang_full_id,
                    'content': rne_r.get('content', ''),
                    'unit_path': rne_r.get('article_number', ''),
                    'similarity': rne_r.get('relevance_score', 0.0),
                    'stage': f"rne_{rne_r.get('expansion_type', 'unknown')}"
                })

            logger.info(f"[RNE] Returned {len(expanded_results)} RNE expansion results (cross-domain included)")

            return expanded_results

        except Exception as e:
            logger.error(f"[RNE] Expansion failed: {e}", exc_info=True)
            return []

    def _is_in_my_domain(self, hang_full_id: str) -> bool:
        """
        HANG이 이 도메인에 속하는지 확인

        Args:
            hang_full_id: HANG의 full_id

        Returns:
            도메인 소속 여부
        """
        # node_ids는 full_id의 집합이므로 직접 체크
        return hang_full_id in self.node_ids

    def _merge_hybrid_and_rne(self, hybrid_results: List[Dict], rne_results: List[Dict]) -> List[Dict]:
        """
        Hybrid search와 RNE 확장 결과 병합 (Phase 1.6: Score Normalization)

        중복 제거 및 정규화된 점수로 정렬 수행.

        Args:
            hybrid_results: Hybrid search 결과 (RRF normalized scores)
            rne_results: RNE 확장 결과 (raw cosine similarity)

        Returns:
            병합된 결과 리스트
        """
        # hang_id -> 결과 매핑 (중복 제거)
        merged_dict = {}

        # [1] Hybrid 결과 추가 (우선순위 높음)
        # Phase 1.9: JO 레벨 검색 strong boosting (2 → 40)
        # RRF 점수(~0.02)를 cosine similarity 척도(~0.9)로 변환
        JO_BOOST_FACTOR = 40

        for r in hybrid_results:
            hang_id = r['hang_id']
            similarity = r['similarity']
            stage = r.get('stage', 'unknown')

            # JO 레벨 검색 결과에 boost 적용
            if stage == 'jo_vector':
                similarity = similarity * JO_BOOST_FACTOR

            if hang_id not in merged_dict:
                merged_dict[hang_id] = r.copy()
                merged_dict[hang_id]['raw_similarity'] = similarity
                # stages 필드 정규화
                if 'stages' not in merged_dict[hang_id]:
                    merged_dict[hang_id]['stages'] = [stage]
            else:
                # 이미 있으면 stage 추가
                existing = merged_dict[hang_id]
                if stage not in existing.get('stages', []):
                    existing['stages'].append(stage)
                # 더 높은 유사도로 갱신
                if similarity > existing.get('raw_similarity', 0):
                    existing['similarity'] = similarity
                    existing['raw_similarity'] = similarity

        # [2] RNE 결과 추가 (새로운 노드만)
        for r in rne_results:
            hang_id = r['hang_id']
            if hang_id not in merged_dict:
                merged_dict[hang_id] = r.copy()
                merged_dict[hang_id]['raw_similarity'] = r['similarity']
                merged_dict[hang_id]['stages'] = [r.get('stage', 'rne_unknown')]
            else:
                # 이미 있으면 RNE stage 추가
                existing = merged_dict[hang_id]
                stage = r.get('stage', 'rne_unknown')
                if stage not in existing.get('stages', []):
                    existing['stages'].append(stage)
                # RNE에서 더 높은 유사도가 나오면 갱신 (드물지만)
                if r['similarity'] > existing['similarity']:
                    existing['similarity'] = r['similarity']
                    existing['raw_similarity'] = r['similarity']

        merged_list = list(merged_dict.values())

        # [3] Min-Max Score Normalization (Phase 1.6)
        if merged_list:
            # 모든 점수 추출
            all_scores = [r['raw_similarity'] for r in merged_list]
            min_score = min(all_scores)
            max_score = max(all_scores)

            # Min-Max normalization to 0-1 range
            score_range = max_score - min_score
            if score_range > 0:
                for r in merged_list:
                    normalized = (r['raw_similarity'] - min_score) / score_range
                    r['normalized_similarity'] = normalized
            else:
                # 모든 점수가 동일한 경우
                for r in merged_list:
                    r['normalized_similarity'] = 1.0

            # [4] Path Scoring: 제12장 페널티 (Phase 1.6)
            for r in merged_list:
                hang_id = r['hang_id']
                path_multiplier = 1.0

                # 제12장 (부칙) 페널티
                if '::제12장::' in hang_id or '::부칙::' in hang_id:
                    path_multiplier = 0.3  # 70% 감소

                # Final score = normalized score × path multiplier
                r['final_similarity'] = r['normalized_similarity'] * path_multiplier
                r['path_multiplier'] = path_multiplier

            # [5] Final score 기준으로 정렬
            merged_list.sort(key=lambda x: x['final_similarity'], reverse=True)

            # [6] Update similarity field for API response (Phase 1.6)
            for r in merged_list:
                r['similarity'] = r['final_similarity']

            # Logging for debugging (Phase 1.6)
            logger.info(f"[Score Normalization] Min: {min_score:.4f}, Max: {max_score:.4f}")
            logger.info(f"[Score Normalization] Top 3 after normalization:")
            for i, r in enumerate(merged_list[:3], 1):
                logger.info(
                    f"  #{i}: {r['hang_id'][:50]}... "
                    f"raw={r['raw_similarity']:.4f}, "
                    f"norm={r['normalized_similarity']:.4f}, "
                    f"path_mult={r['path_multiplier']}, "
                    f"final={r['final_similarity']:.4f}"
                )

        return merged_list

    def _get_parent_jo_info(self, hang_id: str) -> Optional[Dict]:
        """
        HANG 노드의 상위 JO 조항 정보 가져오기 (GraphDB 경로 탐색)

        Args:
            hang_id: HANG 노드 full_id

        Returns:
            상위 JO 정보 (number, title, full_id) 또는 None
        """
        query = """
        MATCH path = (hang:HANG {full_id: $hang_id})<-[:CONTAINS*]-(jo:JO)
        WHERE jo.title IS NOT NULL AND jo.title <> 'None'
        RETURN jo.number AS jo_number,
               jo.title AS jo_title,
               jo.full_id AS jo_id,
               length(path) as path_length
        ORDER BY path_length ASC
        LIMIT 1
        """

        results = self.neo4j_service.execute_query(query, {'hang_id': hang_id})

        if results:
            return {
                'jo_number': results[0]['jo_number'],
                'jo_title': results[0]['jo_title'],
                'jo_id': results[0]['jo_id']
            }
        return None

    def _rerank_results(self, results: List[Dict], query_embedding: List[float]) -> List[Dict]:
        """
        결과 재순위화 (Stage 3)

        Args:
            results: 검색 결과 리스트
            query_embedding: 쿼리 임베딩

        Returns:
            재순위화된 결과
        """
        # 중복 제거 (hang_id 기준, 높은 유사도 우선, stage 병합)
        hang_dict = {}
        for r in results:
            hang_id = r['hang_id']
            if hang_id not in hang_dict:
                # 처음 보는 HANG: stages를 리스트로 시작
                r['stages'] = [r['stage']]
                hang_dict[hang_id] = r
            else:
                # 이미 있는 HANG: stage 추가 및 유사도 갱신
                existing = hang_dict[hang_id]
                if r['stage'] not in existing.get('stages', []):
                    if 'stages' not in existing:
                        existing['stages'] = [existing['stage']]
                    existing['stages'].append(r['stage'])
                # 더 높은 유사도로 갱신
                if r['similarity'] > existing['similarity']:
                    hang_dict[hang_id]['similarity'] = r['similarity']

        unique_results = list(hang_dict.values())

        # 유사도 내림차순 정렬
        unique_results.sort(key=lambda x: x['similarity'], reverse=True)

        return unique_results

    async def _consult_neighbors(self, query: str) -> List[Dict]:
        """
        이웃 도메인 에이전트와 병렬 협업 (A2A - DynTaskMAS 패턴)

        DynTaskMAS APEE (Asynchronous Parallel Execution Engine) 방식 적용:
        - 모든 neighbor 에이전트에 동시 쿼리 전송
        - asyncio.gather()로 병렬 실행
        - return_exceptions=True로 robust한 에러 처리

        성능 개선:
        - 순차 실행: O(n * avg_time)
        - 병렬 실행: O(max_time)
        - 예상: 47초 → 18초 (약 60% 단축)

        Args:
            query: 사용자 질의

        Returns:
            이웃으로부터 받은 검색 결과

        References:
            - DynTaskMAS (ICAPS 2025): arXiv:2503.07675
            - Phase 2.0: Parallel A2A Collaboration
        """
        import json
        import time

        neighbor_results = []
        neighbors_to_query = self.neighbor_agents[:3]  # 최대 3개 이웃

        if not neighbors_to_query:
            logger.info("[A2A Parallel] No neighbor agents to consult")
            return neighbor_results

        logger.info(f"[A2A Parallel] Starting parallel queries to {len(neighbors_to_query)} neighbors: {neighbors_to_query}")
        start_time = time.time()

        # DynTaskMAS APEE 패턴: 병렬 태스크 생성
        tasks = [
            self.communicate_with_agent(
                target_agent_slug=neighbor_slug,
                message=f"법률 검색 협업 요청: {query}",
                context_id=f"domain_collaboration_{self.domain_id}"
            )
            for neighbor_slug in neighbors_to_query
        ]

        # 병렬 실행 (return_exceptions=True로 한 에이전트 실패 시에도 계속 진행)
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed_time = time.time() - start_time
        logger.info(f"[A2A Parallel] All {len(neighbors_to_query)} queries completed in {elapsed_time:.2f}s")

        # 결과 처리 (성공/실패 분리)
        successful_count = 0
        failed_count = 0

        for neighbor_slug, response in zip(neighbors_to_query, responses):
            # 에러 처리
            if isinstance(response, Exception):
                failed_count += 1
                logger.error(f"[A2A Parallel] Neighbor '{neighbor_slug}' failed: {response}")
                continue

            # 응답 파싱
            if response:
                try:
                    data = json.loads(response)
                    results = data.get('results', [])
                    neighbor_results.extend(results)
                    successful_count += 1
                    logger.info(f"[A2A Parallel] Neighbor '{neighbor_slug}' returned {len(results)} results")
                except json.JSONDecodeError:
                    failed_count += 1
                    logger.warning(f"[A2A Parallel] Invalid JSON from neighbor '{neighbor_slug}'")
            else:
                failed_count += 1
                logger.warning(f"[A2A Parallel] Empty response from neighbor '{neighbor_slug}'")

        logger.info(
            f"[A2A Parallel] Summary: {successful_count} succeeded, {failed_count} failed, "
            f"{len(neighbor_results)} total results in {elapsed_time:.2f}s"
        )

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

        # 핵심 조항 (Top 3) - GraphDB 경로 탐색으로 상위 JO 정보 표시
        response_parts.append("\n[핵심 조항]")
        for i, r in enumerate(results[:3], 1):
            # 상위 JO 조항 정보 가져오기 (GraphDB 경로 탐색)
            jo_info = self._get_parent_jo_info(r['hang_id'])

            if jo_info:
                jo_display = f"{jo_info['jo_number']} ({jo_info['jo_title']})"
            else:
                jo_display = "상위 조항 정보 없음"

            response_parts.append(
                f"\n{i}. {jo_display} → {r['unit_path']}\n"
                f"   유사도: {r['similarity']:.2f} | 검색: {r.get('stage', 'unknown')}\n"
                f"   {r['content'][:200]}..."
            )

        # 연관 조항 (4~6위) - GraphDB 경로 탐색
        if len(results) > 3:
            response_parts.append("\n\n[연관 조항]")
            for i, r in enumerate(results[3:6], 4):
                # 상위 JO 조항 정보 가져오기
                jo_info = self._get_parent_jo_info(r['hang_id'])

                if jo_info:
                    jo_display = f"{jo_info['jo_number']} ({jo_info['jo_title']})"
                else:
                    jo_display = r['unit_path']

                # stages가 있으면 첫 번째 stage 사용, 없으면 stage 사용
                stage_display = r.get('stages', [r.get('stage', 'unknown')])[0]
                response_parts.append(
                    f"\n{i}. {jo_display}\n"
                    f"   유사도: {r['similarity']:.2f} | 검색: {stage_display}"
                )

        # 통계 정보
        my_domain_count = sum(1 for r in results if r.get('source') == 'my_domain')
        neighbor_count = sum(1 for r in results if r.get('source') == 'neighbor_domain')

        # 검색 방식별 통계 (stages 리스트 기반)
        vector_count = sum(1 for r in results if 'vector' in r.get('stages', [r.get('stage', '')]))
        relationship_count = sum(1 for r in results if 'relationship' in r.get('stages', [r.get('stage', '')]))
        graph_expansion_count = sum(1 for r in results if 'graph_expansion' in r.get('stages', [r.get('stage', '')]))

        # Phase 1.5: RNE 통계 추가
        rne_count = sum(1 for r in results if any('rne_' in s for s in r.get('stages', [r.get('stage', '')])))

        response_parts.append(
            f"\n\n[검색 통계]\n"
            f"총 {len(results)}개 조항 발견\n"
            f"- 노드 임베딩: {vector_count}개\n"
            f"- 관계 임베딩: {relationship_count}개\n"
            f"- GraphDB 확장: {graph_expansion_count}개\n"
            f"- RNE 확장: {rne_count}개\n"
            f"- 도메인: 자체 {my_domain_count}개, 협업 {neighbor_count}개"
        )

        return ''.join(response_parts)

    async def _generate_kr_sbert_embedding(self, query: str) -> List[float]:
        """쿼리 임베딩 생성 - KR-SBERT (768-dim, HANG 노드 검색용)"""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
        embedding = model.encode(query)

        return embedding.tolist()

    async def _generate_openai_embedding(self, query: str) -> List[float]:
        """쿼리 임베딩 생성 - OpenAI (3072-dim, 관계 검색용)"""
        from openai import OpenAI
        client = OpenAI()

        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=query
        )

        return response.data[0].embedding

    async def assess_query_confidence(self, query: str) -> Dict[str, Any]:
        """
        LLM Self-Assessment - GPT-4로 쿼리에 답할 수 있는지 판단

        GraphTeam/GraphAgent-Reasoner 논문 기반:
        - Agent가 자신의 domain을 이해하고 판단
        - Confidence score (0-1) 반환
        - 진짜 "Agent Reasoning"의 시작점

        Args:
            query: 사용자 쿼리

        Returns:
            {
                "confidence": 0.0-1.0,
                "reasoning": "판단 근거",
                "can_answer": True/False,
                "relevant_articles": ["제17조", "제25조"]  # 예상되는 관련 조항
            }
        """
        from openai import OpenAI
        import json

        # Sample article IDs (domain의 대표 조항들)
        sample_articles = list(self.node_ids)[:10] if len(self.node_ids) > 10 else list(self.node_ids)

        # GPT-4 Prompt
        prompt = f"""You are a specialized legal domain agent for "{self.domain_name}".

Your domain information:
- Domain name: {self.domain_name}
- Total articles: {len(self.node_ids)}
- Sample article IDs: {', '.join(sample_articles[:5])}

User query: "{query}"

Task: Assess if you can answer this query with high confidence.

Consider:
1. Does the query relate to topics in your domain?
2. Do you have relevant legal articles for this query?
3. Can you extract specific article numbers from the query?

Respond in JSON format:
{{
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation in Korean",
  "can_answer": true/false,
  "relevant_articles": ["article numbers if identifiable"]
}}
"""

        try:
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a legal domain assessment agent. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            logger.info(
                f"[Self-Assessment] Domain='{self.domain_name}', "
                f"Query='{query[:50]}...', "
                f"Confidence={result.get('confidence', 0):.2f}, "
                f"Can Answer={result.get('can_answer', False)}"
            )

            return result

        except Exception as e:
            logger.error(f"[Self-Assessment] Error: {e}", exc_info=True)
            # Fallback: 낮은 confidence 반환
            return {
                "confidence": 0.1,
                "reasoning": f"Error during assessment: {str(e)}",
                "can_answer": False,
                "relevant_articles": []
            }

    async def handle_a2a_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        A2A (Agent-to-Agent) 메시지 처리

        다른 DomainAgent로부터 검색 요청을 받아 처리합니다.
        GraphTeam/GraphAgent-Reasoner 논문의 agent collaboration 구현.

        Args:
            message: {
                "query": str,           # 검색 쿼리
                "context": str,         # 선택적 컨텍스트 정보
                "limit": int,           # 결과 개수 제한
                "requestor": str        # 요청한 agent 이름
            }

        Returns:
            {
                "results": List[Dict],  # 검색 결과
                "domain_name": str,     # 이 도메인 이름
                "domain_id": str,       # 이 도메인 ID
                "status": str,          # "success" | "error"
                "message": str          # 상태 메시지
            }
        """
        query = message.get("query", "")
        context = message.get("context", "")
        limit = message.get("limit", 5)
        requestor = message.get("requestor", "unknown")

        logger.info(
            f"[A2A Request] Domain='{self.domain_name}', "
            f"From='{requestor}', Query='{query[:50]}...'"
        )

        try:
            # 컨텍스트가 있으면 쿼리에 추가
            full_query = f"{context} {query}" if context else query

            # _search_my_domain() 메서드 재사용 (이미 embedding 생성 로직 포함)
            results = await self._search_my_domain(query=full_query, limit=limit)

            logger.info(
                f"[A2A Response] Domain='{self.domain_name}', "
                f"Results={len(results)}, To='{requestor}'"
            )

            return {
                "results": results,
                "domain_name": self.domain_name,
                "domain_id": self.domain_id,
                "status": "success",
                "message": f"Found {len(results)} results in {self.domain_name}"
            }

        except Exception as e:
            logger.error(
                f"[A2A Error] Domain='{self.domain_name}', "
                f"Error: {e}", exc_info=True
            )
            return {
                "results": [],
                "domain_name": self.domain_name,
                "domain_id": self.domain_id,
                "status": "error",
                "message": f"Error during A2A search: {str(e)}"
            }

    async def should_collaborate(
        self,
        query: str,
        initial_results: List[Dict],
        available_domains: List[str]
    ) -> Dict[str, Any]:
        """
        GPT-4o로 다른 도메인과 협업이 필요한지 판단

        GraphTeam 논문의 "Question Understanding Agent" 역할:
        - 쿼리가 여러 도메인에 걸쳐 있는지 분석
        - 추가로 필요한 도메인 식별
        - 각 도메인에 요청할 구체적인 쿼리 생성

        Args:
            query: 원본 사용자 쿼리
            initial_results: 이 도메인의 초기 검색 결과
            available_domains: 사용 가능한 다른 도메인 리스트

        Returns:
            {
                "should_collaborate": bool,
                "target_domains": List[{
                    "domain_name": str,
                    "refined_query": str,
                    "reason": str
                }],
                "reasoning": str
            }
        """
        from openai import OpenAI
        import json

        # 초기 결과 요약 (GPT-4o에게 전달)
        results_summary = [
            {
                "full_id": r.get("full_id", "N/A"),
                "content_preview": r.get("content", "")[:100]
            }
            for r in initial_results[:3]
        ]

        prompt = f"""You are an intelligent legal domain coordinator.

User query: "{query}"

Current domain: {self.domain_name}
Initial search results from this domain:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

Available other domains:
{', '.join(available_domains)}

Task: Determine if this query requires information from other domains.

Consider:
1. Does the query explicitly mention multiple legal topics?
2. Do the initial results fully answer the query, or is additional information needed?
3. Are there related legal procedures/regulations in other domains?

Respond in JSON format:
{{
  "should_collaborate": true/false,
  "target_domains": [
    {{
      "domain_name": "exact domain name from available list",
      "refined_query": "specific query for this domain in Korean",
      "reason": "why this domain is needed in Korean"
    }}
  ],
  "reasoning": "overall reasoning in Korean"
}}

If no collaboration needed, return empty target_domains list.
"""

        try:
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a legal domain collaboration coordinator. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            if result.get("should_collaborate", False):
                logger.info(
                    f"[Collaboration] Domain='{self.domain_name}', "
                    f"Query='{query[:50]}...', "
                    f"Target domains: {[d['domain_name'] for d in result.get('target_domains', [])]}"
                )
            else:
                logger.info(
                    f"[Collaboration] Domain='{self.domain_name}', "
                    f"Query='{query[:50]}...', "
                    f"No collaboration needed"
                )

            return result

        except Exception as e:
            logger.error(f"[Collaboration] Error: {e}", exc_info=True)
            # Fallback: 협업 안 함
            return {
                "should_collaborate": False,
                "target_domains": [],
                "reasoning": f"Error during collaboration assessment: {str(e)}"
            }
