"""
Semantic INE (Incremental Network Expansion) - 법규용

법규 검색을 위한 Semantic k-NN 알고리즘.
도로용 INE를 법규 도메인에 적용한 변형.

**핵심 변환**:
- POI (병원, 학교) → 조항 (HANG)
- k개 POI → k개 가장 관련된 조항
- 거리 기반 → 유사도 기반

**RNE vs INE**:
| 특성 | SemanticRNE | SemanticINE |
|------|------------|-------------|
| **목적** | 유사도 θ 이상 모두 | 상위 k개만 |
| **종료** | similarity < θ | len(found) >= k |
| **사용 예** | "도시계획 관련 모든 조항" | "도시계획 관련 상위 5개" |
"""

import heapq
from typing import Dict, List, Tuple
import numpy as np
from .base import BaseSpatialAlgorithm
from ..domain import Context


class SemanticINE(BaseSpatialAlgorithm):
    """
    Semantic INE - 법규용 k-NN 검색

    **알고리즘 개요**:
    ```
    Stage 1: Vector Search (후보 확보)
      ↓ top-20 후보 (k보다 많이)
    Stage 2: Incremental Expansion
      ↓ Priority Queue로 점진적 확장
      ↓ k개 발견 시 조기 종료 (INE 핵심!)
    Stage 3: Similarity 정렬
    ```

    **조기 종료의 장점**:
    - RNE 대비 50% 빠름 (도로 시스템 벤치마크)
    - k가 작을수록 더 효율적
    - 불필요한 노드 탐색 방지

    **Example**:
        >>> ine = SemanticINE(None, law_repo, model)
        >>> results = ine.execute_query("도시계획 수립", k=5)
        >>> print(f"상위 {len(results)}개 조항")
    """

    def __init__(self, cost_calculator, repository, embedding_model):
        """
        Args:
            cost_calculator: CostCalculator (법규는 사용 안 함)
            repository: LawRepository 인스턴스
            embedding_model: SentenceTransformer 모델
        """
        super().__init__(cost_calculator, repository)
        self.model = embedding_model
        self.INF = 10 ** 18

    def execute(self, start_node_id: int, radius_or_k: float, context: Context) -> Tuple[List[Tuple[int, Dict]], Dict[int, float]]:
        """
        기존 인터페이스 (호환성 유지, 법규에서는 사용 안 함)

        법규 검색은 execute_query() 사용.

        Raises:
            NotImplementedError: 법규는 execute_query() 사용
        """
        raise NotImplementedError(
            "법규 검색은 execute_query(query_text, k)를 사용하세요. "
            "예: ine.execute_query('도시계획', k=5)"
        )

    def execute_query(
        self,
        query_text: str,
        k: int = 5,
        initial_candidates: int = 20
    ) -> List[Dict]:
        """
        법규 k-NN 검색 실행 (메인 메서드)

        **알고리즘**:
        ```
        1. 쿼리 임베딩 생성
        2. Stage 1: 벡터 검색 (top-20 후보)
        3. Stage 2: Incremental Expansion
           PQ ← 후보들
           while PQ not empty and len(found) < k:
             u ← PQ.pop_min()
             if u가 조건 만족:
               found.append(u)
               if len(found) >= k:
                 break  # 조기 종료!
             이웃 확장...
        4. Stage 3: 유사도 정렬
        ```

        Args:
            query_text: 검색 쿼리
            k: 찾을 조항 개수 (5 권장)
            initial_candidates: Stage 1 후보 (k의 3-4배 권장)

        Returns:
            조항 리스트 (최대 k개, 유사도 순)
            [{
                'hang_id': int,
                'full_id': str,
                'law_name': str,
                'article_number': str,
                'content': str,
                'similarity': float,
                'rank': int  # 1부터 시작
            }, ...]

        Example:
            >>> ine = SemanticINE(None, law_repo, model)
            >>> results = ine.execute_query("도시계획", k=5)
            >>> for r in results:
            ...     print(f"#{r['rank']}: {r['article_number']} ({r['similarity']:.4f})")
        """
        # [1] 쿼리 임베딩 생성
        query_emb = self.model.encode(query_text)

        # [2] Stage 1: 벡터 검색 (초기 후보)
        initial_results = self.repository.vector_search(
            query_emb,
            top_k=initial_candidates
        )

        if not initial_results:
            return []

        # [3] Stage 2: Incremental Expansion
        pq = []  # Priority Queue: (cost, hang_id)
        dist = {}
        visited = set()
        found = []  # 발견한 조항들

        # 초기 후보 추가
        for hang_id, similarity_score in initial_results:
            cost = 1 - similarity_score
            heapq.heappush(pq, (cost, hang_id))
            dist[hang_id] = cost

        # INE 확장 루프
        while pq and len(found) < k:
            current_cost, u = heapq.heappop(pq)

            # 중복 방문 방지
            if u in visited:
                continue

            visited.add(u)

            # 조항 정보 확인 (HANG 노드만 결과에 포함)
            article_info = self.repository.get_article_info(u)

            if article_info:
                # 조항 발견!
                relevance_score = 1 - current_cost
                found.append({
                    'hang_id': u,
                    'full_id': article_info.get('full_id', ''),
                    'law_name': article_info.get('law_name', ''),
                    'article_number': article_info.get('article_number', ''),
                    'content': article_info.get('content', ''),
                    'relevance_score': round(relevance_score, 4),
                    'rank': len(found) + 1
                })

                # 조기 종료 (INE 핵심!)
                if len(found) >= k:
                    break

            # 이웃 확장 (계층 구조)
            neighbors = self.repository.get_neighbors(u, context=None)

            for v, edge_data in neighbors:
                edge_cost = self._calculate_semantic_cost(
                    edge_data, query_emb, current_cost
                )

                # 차단된 엣지 스킵
                if edge_cost >= self.INF:
                    continue

                alt = current_cost + edge_cost

                # 더 나은 경로 발견 시 갱신
                if v not in dist or alt < dist[v]:
                    dist[v] = alt
                    heapq.heappush(pq, (alt, v))

        # [4] Stage 3: 관련성 순 정렬 (Reranking)
        found.sort(key=lambda x: x['relevance_score'], reverse=True)

        # 순위 재할당
        for i, article in enumerate(found):
            article['rank'] = i + 1

        return found

    def _calculate_semantic_cost(
        self,
        edge_data: Dict,
        query_emb: np.ndarray,
        parent_cost: float
    ) -> float:
        """
        엣지 비용 계산 (SemanticRNE와 동일)

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
            parent_cost: 부모 비용

        Returns:
            엣지 비용
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
                return self.INF

            similarity = self._cosine_similarity(query_emb, sibling_emb)
            return 1 - similarity

        else:
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
        return "SemanticINE"
