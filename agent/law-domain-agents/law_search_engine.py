"""
Law Search Engine - Django 없이 독립 실행

Backend의 RNE/INE 검색 알고리즘을 추출하여 FastAPI에서 사용
Django 의존성 완전 제거

핵심 기능:
- Hybrid Search (Exact + Vector + Relationship)
- RNE Graph Expansion
- INE Semantic Search

Dependencies:
- Neo4j
- OpenAI API
- sentence-transformers (KR-SBERT)
- numpy, sklearn
"""

import os
import re
import logging
import heapq
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# Import law utilities for result enrichment
from law_utils import enrich_search_results

logger = logging.getLogger(__name__)


class LawSearchEngine:
    """
    독립 실행 가능한 법률 검색 엔진

    Backend domain_agent.py에서 추출한 RNE/INE 알고리즘 사용
    """

    def __init__(
        self,
        neo4j_client,  # shared.neo4j_client.get_neo4j_client()
        openai_client,  # shared.openai_client.get_openai_client()
        domain_id: Optional[str] = None,
        domain_name: str = "전체",
        rne_threshold: float = 0.65,
        ine_k: int = 10
    ):
        """
        Args:
            neo4j_client: Neo4j 클라이언트 (agent/shared/neo4j_client.py)
            openai_client: OpenAI 클라이언트 (agent/shared/openai_client.py)
            domain_id: 도메인 ID (None = 전체 검색)
            domain_name: 도메인 이름
            rne_threshold: RNE 유사도 임계값 (0.65 권장)
            ine_k: INE top-k 결과 (10 권장)
        """
        self.neo4j_client = neo4j_client
        self.openai_client = openai_client

        self.domain_id = domain_id
        self.domain_name = domain_name

        self.rne_threshold = rne_threshold
        self.ine_k = ine_k

        # Lazy loading
        self._kr_sbert_model = None

        logger.info(f"LawSearchEngine initialized for '{domain_name}'")

    # ========== PUBLIC API ==========

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        메인 검색 메소드

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수

        Returns:
            검색 결과 리스트
        """
        logger.info(f"[{self.domain_name}] Search: {query[:50]}...")

        try:
            # [1] 임베딩 생성
            kr_sbert_emb = self._generate_kr_sbert_embedding(query)
            openai_emb = self._generate_openai_embedding(query)

            # [2] Hybrid 검색
            hybrid_results = self._hybrid_search(query, openai_emb, openai_emb, limit=top_k)

            if not hybrid_results:
                logger.warning(f"No results for: {query[:30]}...")
                return []

            # [3] RNE 그래프 확장 (상위 5개 결과 기반)
            rne_results = self._rne_graph_expansion(
                query,
                hybrid_results[:5],
                openai_emb
            )

            # [4] 결과 병합
            all_results = self._merge_results(hybrid_results, rne_results)

            # [5] 결과 enrichment - law_name, law_type, article 추가
            enriched_results = enrich_search_results(all_results[:top_k])

            logger.info(f"[{self.domain_name}] Found {len(enriched_results)} results")

            return enriched_results

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return []

    # ========== CORE SEARCH METHODS ==========

    def _hybrid_search(
        self,
        query: str,
        node_emb: List[float],
        rel_emb: List[float],
        limit: int = 10
    ) -> List[Dict]:
        """
        Hybrid Search: Exact + Vector + Relationship

        Backend domain_agent.py Line 271-315 기반
        ✅ FIXED: Both use OpenAI 3072-dim embeddings
        """
        logger.info(f"[{self.domain_name}] Running hybrid search (Exact + Vector + Relationship)...")

        # [1] Exact match
        exact_results = self._exact_match_search(query, limit=limit)

        # [2] Vector search (OpenAI, 3072-dim)
        vector_results = self._vector_search(node_emb, limit=limit)

        # [3] Relationship search (OpenAI, 3072-dim)
        rel_results = self._search_relationships(rel_emb, limit=limit)

        # [4] Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion([
            exact_results,
            vector_results,
            rel_results
        ])

        return fused_results[:limit]

    def _exact_match_search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        정확 일치 검색 (조문 번호 추출)

        Backend domain_agent.py Line 166-219 기반
        ✅ FIXED: Use CONTAINS on full_id instead of article_number IN
        """
        # 조항 번호 패턴 추출 (제17조, 17조 등)
        article_pattern = re.search(r'제?(\d+)조', query)

        if not article_pattern:
            return []  # 조항 번호 없으면 빈 리스트 반환

        article_num = article_pattern.group(1)
        search_pattern = f'제{article_num}조'

        logger.info(f"[{self.domain_name}] Exact match pattern: {search_pattern}")

        # Neo4j 쿼리 - full_id CONTAINS 사용
        cypher_query = """
        MATCH (h:HANG)
        WHERE h.full_id CONTAINS $search_pattern
          AND NOT h.full_id CONTAINS '제4절'
        """

        if self.domain_id:
            cypher_query += """
          AND EXISTS((h)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
            """

        cypher_query += """
        RETURN h.full_id as hang_id,
               h.content as content,
               h.unit_path as unit_path,
               1.0 as similarity
        LIMIT $limit
        """

        try:
            session = self.neo4j_client.get_session()
            results = session.run(cypher_query, {
                'search_pattern': search_pattern,
                'domain_id': self.domain_id,
                'limit': limit
            })

            exact_results = []
            for r in results:
                exact_results.append({
                    'hang_id': r['hang_id'],
                    'content': r['content'],
                    'unit_path': r['unit_path'],
                    'similarity': r['similarity'],
                    'stage': 'exact_match'
                })

            session.close()

            logger.info(f"[{self.domain_name}] Exact match: {len(exact_results)} results for {search_pattern}")
            return exact_results

        except Exception as e:
            logger.error(f"Exact match search error: {e}")
            return []

    def _vector_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        벡터 검색 (OpenAI, 3072-dim)

        Backend domain_agent.py Line 317-360 기반
        ✅ FIXED: Now uses OpenAI embeddings
        """
        cypher_query = """
        CALL db.index.vector.queryNodes('hang_embedding_index', $limit, $embedding)
        YIELD node, score
        """

        if self.domain_id:
            cypher_query += """
            WHERE EXISTS((node)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
            """

        cypher_query += """
        RETURN node.full_id as hang_id,
               node.content as content,
               node.unit_path as unit_path,
               score as similarity
        """

        try:
            session = self.neo4j_client.get_session()
            results = session.run(cypher_query, {
                'embedding': query_embedding,
                'limit': limit,
                'domain_id': self.domain_id
            })

            vector_results = []
            for r in results:
                vector_results.append({
                    'hang_id': r['hang_id'],
                    'content': r['content'],
                    'unit_path': r['unit_path'],
                    'similarity': r['similarity'],
                    'stage': 'vector_search'
                })

            session.close()

            logger.info(f"[{self.domain_name}] Vector search: {len(vector_results)} results")
            return vector_results

        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def _search_relationships(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        """
        관계 임베딩 검색 (CONTAINS 관계, OpenAI 3072-dim)

        Backend domain_agent.py Line 362-408 기반
        ✅ FIXED: Use db.index.vector.queryRelationships instead of node property
        """
        cypher_query = """
        CALL db.index.vector.queryRelationships(
            'contains_embedding',
            $limit_multiplier,
            $query_embedding
        ) YIELD relationship, score
        MATCH (from)-[relationship]->(to:HANG)
        WHERE score >= 0.65
        """

        if self.domain_id:
            cypher_query += """
          AND EXISTS((to)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
            """

        cypher_query += """
        RETURN
            to.full_id AS hang_id,
            to.content AS content,
            to.unit_path AS unit_path,
            score AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        try:
            session = self.neo4j_client.get_session()
            results = session.run(cypher_query, {
                'query_embedding': query_embedding,
                'limit': limit,
                'limit_multiplier': limit * 3,
                'domain_id': self.domain_id
            })

            rel_results = []
            for r in results:
                rel_results.append({
                    'hang_id': r['hang_id'],
                    'content': r['content'],
                    'unit_path': r['unit_path'],
                    'similarity': float(r['similarity']),
                    'stage': 'relationship'
                })

            session.close()

            logger.info(f"[{self.domain_name}] Relationship search: {len(rel_results)} results")
            return rel_results

        except Exception as e:
            logger.error(f"Relationship search error: {e}")
            return []

    def _rne_graph_expansion(
        self,
        query: str,
        initial_results: List[Dict],
        openai_embedding: List[float]
    ) -> List[Dict]:
        """
        RNE 그래프 확장

        Backend domain_agent.py Line 492-559 기반
        ✅ FIXED: Now uses OpenAI embeddings (3072-dim)

        TODO: SemanticRNE 클래스 사용 (현재는 간단한 버전)
        """
        if not initial_results:
            return []

        logger.info(f"[{self.domain_name}] RNE expansion from {len(initial_results)} seeds...")

        # 간단 버전: 초기 결과의 이웃 노드 찾기
        start_ids = [r['hang_id'] for r in initial_results[:3]]

        cypher_query = """
        MATCH (start:HANG)
        WHERE start.full_id IN $start_ids

        MATCH (start)<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
        WHERE neighbor.full_id <> start.full_id
          AND neighbor.embedding IS NOT NULL
        """

        if self.domain_id:
            cypher_query += """
          AND EXISTS((neighbor)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: $domain_id}))
            """

        cypher_query += """
        RETURN DISTINCT neighbor.full_id as hang_id,
                        neighbor.content as content,
                        neighbor.unit_path as unit_path,
                        neighbor.embedding as embedding
        LIMIT 50
        """

        try:
            session = self.neo4j_client.get_session()
            results = session.run(cypher_query, {
                'start_ids': start_ids,
                'domain_id': self.domain_id
            })

            # 코사인 유사도 계산 (OpenAI 3072-dim)
            query_vec = np.array(openai_embedding).reshape(1, -1)
            rne_results = []

            for r in results:
                emb = np.array(r['embedding']).reshape(1, -1)
                similarity = cosine_similarity(query_vec, emb)[0][0]

                if similarity >= self.rne_threshold:
                    rne_results.append({
                        'hang_id': r['hang_id'],
                        'content': r['content'],
                        'unit_path': r['unit_path'],
                        'similarity': float(similarity),
                        'stage': 'rne_expansion'
                    })

            session.close()

            logger.info(f"[{self.domain_name}] RNE expansion: {len(rne_results)} results (threshold: {self.rne_threshold})")
            return rne_results

        except Exception as e:
            logger.error(f"RNE expansion error: {e}")
            return []

    # ========== HELPER METHODS ==========

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict]],
        k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF)

        Backend domain_agent.py Line 221-269 기반
        """
        scores = {}

        for result_list in result_lists:
            for rank, result in enumerate(result_list, 1):
                hang_id = result['hang_id']

                if hang_id not in scores:
                    scores[hang_id] = {
                        'score': 0.0,
                        'result': result
                    }

                scores[hang_id]['score'] += 1.0 / (k + rank)

        # 점수 순 정렬
        ranked = sorted(scores.values(), key=lambda x: x['score'], reverse=True)

        return [item['result'] for item in ranked]

    def _merge_results(
        self,
        hybrid_results: List[Dict],
        rne_results: List[Dict]
    ) -> List[Dict]:
        """
        Hybrid + RNE 결과 병합

        Backend domain_agent.py Line 574-628 기반
        """
        seen = set()
        merged = []

        # Hybrid 결과 먼저
        for r in hybrid_results:
            hang_id = r['hang_id']
            if hang_id not in seen:
                seen.add(hang_id)
                merged.append(r)

        # RNE 결과 추가
        for r in rne_results:
            hang_id = r['hang_id']
            if hang_id not in seen:
                seen.add(hang_id)
                merged.append(r)

        return merged

    def _generate_kr_sbert_embedding(self, query: str) -> List[float]:
        """
        KR-SBERT 임베딩 생성 (768-dim)

        Backend domain_agent.py Line 870-877 기반
        """
        if self._kr_sbert_model is None:
            logger.info("Loading KR-SBERT model...")
            self._kr_sbert_model = SentenceTransformer(
                'snunlp/KR-SBERT-V40K-klueNLI-augSTS'
            )

        embedding = self._kr_sbert_model.encode(query)
        return embedding.tolist()

    def _generate_openai_embedding(self, query: str) -> List[float]:
        """
        OpenAI 임베딩 생성 (3072-dim)

        Backend domain_agent.py Line 879-889 기반
        """
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=query
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            # Fallback: 빈 벡터 반환
            return [0.0] * 3072
