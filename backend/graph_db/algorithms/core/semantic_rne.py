"""
Semantic RNE (Range Network Expansion) - 법규용

법규 검색을 위한 Semantic Range Network Expansion 알고리즘.
도로용 RNE를 법규 도메인에 적용한 변형.

**핵심 변환**:
- 거리 (km) → 벡터 유사도 (0~1)
- 반경 e (초) → 유사도 임계값 θ (0.75)
- RoadNode → HANG (항)
- Context (차량, 시간) → Query (검색어)

**웹 검색 기반 최적화** (2024-2025):
- HybridRAG: Vector + Graph 결합
- Two-stage retrieval: 벡터 후보 → 그래프 확장
- +14.05% 관련성 향상 (Graph RAG 논문)
"""

import heapq
import os
from typing import Dict, List, Set, Tuple, Optional
import numpy as np
from openai import OpenAI
from .base import BaseSpatialAlgorithm
from ..domain import Context


class SemanticRNE(BaseSpatialAlgorithm):
    """
    Semantic RNE - 법규용 범위 기반 검색

    **알고리즘 개요** (HybridRAG 방식):
    ```
    Stage 1: Vector Search
      ↓ Neo4j 벡터 인덱스 (top-10)
    Stage 2: Graph Expansion
      ↓ 계층 구조 탐색 (부모/형제/자식)
    Stage 3: Reranking
      ↓ 유사도 재정렬
    ```

    **도로 RNE와 차이점**:
    | 항목 | 도로 RNE | Semantic RNE |
    |------|---------|-------------|
    | 비용 | baseTime (초) | 1 - similarity |
    | 반경 | e (초) | similarity threshold θ |
    | 시작점 | 단일 노드 | 벡터 검색 top-k |
    | 확장 | SEGMENT 관계 | 계층 구조 |

    **Example**:
        >>> from sentence_transformers import SentenceTransformer
        >>> model = SentenceTransformer('jhgan/ko-sbert-sts')
        >>> rne = SemanticRNE(None, law_repo, model)
        >>> results = rne.execute_query("도시계획 수립 절차", threshold=0.75)
        >>> print(f"발견한 조항: {len(results)}개")
    """

    def __init__(self, cost_calculator, repository, embedding_model):
        """
        Args:
            cost_calculator: CostCalculator (법규는 사용 안 함, 호환성 유지)
            repository: LawRepository 인스턴스
            embedding_model: SentenceTransformer 모델 (KR-SBERT, sibling 관계 유사도용)
        """
        super().__init__(cost_calculator, repository)
        self.model = embedding_model  # KR-SBERT for sibling similarity only
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))  # For vector search
        self.INF = 10 ** 18

    def execute(self, start_node_id: int, radius_or_k: float, context: Context) -> Tuple[Set[int], Dict[int, float]]:
        """
        기존 인터페이스 (호환성 유지, 법규에서는 사용 안 함)

        법규 검색은 execute_query() 사용.

        Raises:
            NotImplementedError: 법규는 execute_query() 사용
        """
        raise NotImplementedError(
            "법규 검색은 execute_query(query_text, threshold)를 사용하세요. "
            "예: rne.execute_query('도시계획 수립 절차', 0.75)"
        )

    def execute_query(
        self,
        query_text: str,
        similarity_threshold: float = 0.75,
        max_results: Optional[int] = None,
        initial_candidates: int = 10
    ) -> Tuple[List[Dict], Dict[int, float]]:
        """
        법규 검색 실행 (메인 메서드)

        **알고리즘**:
        ```
        1. 쿼리 임베딩 생성
        2. Stage 1: 벡터 검색으로 시작점 (top-10)
        3. Stage 2: RNE 확장
           - Priority Queue (1-similarity 기준)
           - 부모 JO: 자동 포함 (비용 0)
           - 형제 HANG: 유사도 > threshold만
           - 자식 HO: 자동 포함 (비용 0)
        4. Stage 3: 결과 정렬 (유사도 순)
        ```

        Args:
            query_text: 검색 쿼리 (예: "도시계획 수립 절차는?")
            similarity_threshold: 유사도 임계값 (0.75 권장)
            max_results: 최대 결과 수 (None이면 무제한)
            initial_candidates: Stage 1 후보 개수 (10 권장)

        Returns:
            (results, distances):
                - results: 조항 정보 리스트
                  [{
                      'hang_id': int,
                      'full_id': str,
                      'law_name': str,
                      'article_number': str,
                      'content': str,
                      'similarity': float,
                      'expansion_type': str  # 'vector', 'parent', 'sibling', 'child'
                  }, ...]
                - distances: {hang_id: 1-similarity}

        Example:
            >>> rne = SemanticRNE(None, law_repo, model)
            >>> results, _ = rne.execute_query("도시계획 수립", 0.75)
            >>> for r in results[:5]:
            ...     print(f"{r['article_number']}: {r['similarity']:.4f}")
        """
        # [1] 쿼리 임베딩 생성 (OpenAI 3072-dim)
        # ✅ FIXED: Use OpenAI embeddings (3072-dim) instead of KR-SBERT (768-dim)
        # HANG nodes in Neo4j have OpenAI embeddings, so we must match dimensions
        response = self.openai_client.embeddings.create(
            input=query_text,
            model="text-embedding-3-large"
        )
        query_emb = np.array(response.data[0].embedding)

        # [2] Stage 1: 벡터 검색 (초기 후보)
        initial_results = self.repository.vector_search(
            query_emb,
            top_k=initial_candidates
        )

        if not initial_results:
            return [], {}

        # [3] Stage 2: RNE 확장
        pq = []  # Priority Queue: (cost, hang_id, expansion_type)
        dist = {}
        reached = set()
        expansion_info = {}  # {hang_id: expansion_type}

        # 초기 후보 추가
        for hang_id, similarity_score in initial_results:
            cost = 1 - similarity_score  # 유사도 → 거리 변환
            heapq.heappush(pq, (cost, hang_id, 'vector'))
            dist[hang_id] = cost
            expansion_info[hang_id] = 'vector'

        # RNE 확장 루프
        while pq:
            current_cost, u, exp_type = heapq.heappop(pq)

            # 유사도 임계값 체크 (RNE의 반경 체크)
            similarity = 1 - current_cost
            if similarity < similarity_threshold:
                break  # 너무 관련 없음

            # 중복 방문 방지
            if u in reached:
                continue

            reached.add(u)

            # 최대 결과 수 체크
            if max_results and len(reached) >= max_results:
                break

            # 이웃 확장
            neighbors = self.repository.get_neighbors(u, context=None)

            for v, edge_data in neighbors:
                edge_type = edge_data.get('type')
                edge_cost = self._calculate_semantic_cost(
                    edge_data, query_emb, current_cost
                )

                # 차단된 엣지 스킵 (없어야 정상)
                if edge_cost >= self.INF:
                    continue

                alt = current_cost + edge_cost

                # 더 나은 경로 발견 시 갱신
                if v not in dist or alt < dist[v]:
                    dist[v] = alt
                    heapq.heappush(pq, (alt, v, edge_type))

                    # 확장 타입 기록 (처음 발견 시)
                    if v not in expansion_info:
                        expansion_info[v] = edge_type

        # [4] Stage 3: 결과 포맷 및 Reranking
        results = []
        for hang_id in reached:
            article_info = self.repository.get_article_info(hang_id)

            if article_info:
                relevance_score = 1 - dist[hang_id]
                results.append({
                    'hang_id': hang_id,
                    'full_id': article_info.get('full_id', ''),
                    'law_name': article_info.get('law_name', ''),
                    'article_number': article_info.get('article_number', ''),
                    'content': article_info.get('content', ''),
                    'relevance_score': round(relevance_score, 4),
                    'expansion_type': expansion_info.get(hang_id, 'unknown')
                })

        # 관련성 순 정렬 (Reranking)
        results.sort(key=lambda x: x['relevance_score'], reverse=True)

        return results, dist

    def _calculate_semantic_cost(
        self,
        edge_data: Dict,
        query_emb: np.ndarray,
        parent_cost: float
    ) -> float:
        """
        엣지 비용 계산 (법규 특화)

        **비용 함수**:
        - parent/child: 0 (계층 구조 보존)
        - cross_law: 0 (법률 간 계층 구조 보존)
        - sibling: 1 - cosine_similarity(query_emb, sibling.embedding)

        Args:
            edge_data: 엣지 정보
                - type: 'parent' | 'sibling' | 'child' | 'cross_law'
                - embedding: np.array (sibling, cross_law)
                - law_name: str (cross_law만)
            query_emb: 쿼리 임베딩
            parent_cost: 부모 노드의 비용

        Returns:
            엣지 비용 (0 또는 1-similarity)
        """
        edge_type = edge_data.get('type')

        if edge_type in ['parent', 'child', 'cross_law']:
            # 계층 관계는 무료 (맥락 보존)
            # cross_law: 법률 → 시행령 → 시행규칙 위임 관계
            # 시행령/시행규칙은 법률 조항을 구체화하므로 자동 탐색
            return 0.0

        elif edge_type == 'sibling':
            # 형제 항은 유사도 재계산
            sibling_emb = edge_data.get('embedding')

            if sibling_emb is None:
                # 임베딩 없으면 스킵
                return self.INF

            # 코사인 유사도 계산
            similarity = self._cosine_similarity(query_emb, sibling_emb)
            return 1 - similarity

        else:
            # 알 수 없는 타입
            return self.INF

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        코사인 유사도 계산

        Args:
            vec1: 벡터 1
            vec2: 벡터 2

        Returns:
            유사도 (0~1)
        """
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(np.clip(similarity, 0.0, 1.0))

        except Exception:
            return 0.0

    def get_algorithm_name(self) -> str:
        """알고리즘 이름"""
        return "SemanticRNE"
