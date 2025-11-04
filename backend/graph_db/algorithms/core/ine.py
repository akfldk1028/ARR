"""
INE (Incremental Network Expansion) Algorithm

점진적 네트워크 확장 알고리즘 (k-NN POI 검색)
"""

import heapq
from typing import Dict, List, Set, Tuple
from .base import BaseSpatialAlgorithm
from ..domain import Context


class INE(BaseSpatialAlgorithm):
    """
    INE (Incremental Network Expansion) 알고리즘

    Integration.md 6절: "RNE 확장 로직 그대로, 최초 도달 대상이 해답"

    **알고리즘 개요**:
    1. Dijkstra 방식으로 네트워크 확장
    2. POI 발견 시 결과 리스트에 추가
    3. k개 POI 발견하면 조기 종료
    4. 네트워크 거리 기준 k-NN

    **시간 복잡도**: O((E + V) log V) (worst case, Dijkstra와 동일)
    **공간 복잡도**: O(V)

    **RNE와의 차이**:
    - RNE: 반경 e 내 모든 노드
    - INE: k개 POI (개수 제한, 거리 무제한)

    Example:
        >>> from ..domain import Context
        >>> from datetime import datetime
        >>> ctx = Context("car", datetime.now())
        >>> ine = INE(cost_calculator, repository)
        >>> pois, costs = ine.execute(node_id=1, radius_or_k=3, context=ctx)
        >>> print(f"찾은 POI: {len(pois)}개")
        찾은 POI: 3개
    """

    def execute(
        self, start_node_id: int, radius_or_k: float, context: Context
    ) -> Tuple[List[Tuple[int, Dict]], Dict[int, float]]:
        """
        INE 알고리즘 실행 (k-NN POI 검색)

        Args:
            start_node_id: 시작 노드 ID
            radius_or_k: POI 개수 k (int로 변환됨)
            context: 라우팅 컨텍스트 θ

        Returns:
            (POI 리스트, 거리 딕셔너리):
                - POI 리스트: [(노드ID, POI정보), ...] (거리순 정렬)
                - 거리 딕셔너리: {노드ID: 비용}

        Integration.md 6절 참조:
        "INE(1-NN): RNE 확장 로직 그대로, 최초 도달 대상이 해답"
        """
        k = int(radius_or_k)  # POI 개수

        # 초기화
        pq: List[Tuple[float, int]] = [(0.0, start_node_id)]  # (비용, 노드ID)
        dist: Dict[int, float] = {start_node_id: 0.0}
        visited: Set[int] = set()
        pois_found: List[Tuple[int, Dict, float]] = []  # (노드ID, POI정보, 거리)

        while pq and len(pois_found) < k:
            current_cost, u = heapq.heappop(pq)

            # 이미 방문한 노드 스킵
            if u in visited:
                continue

            visited.add(u)

            # POI 확인
            poi_info = self.repository.get_poi_at_node(u)
            if poi_info:
                pois_found.append((u, poi_info, current_cost))
                # k개 찾았으면 종료 (조기 종료 최적화)
                if len(pois_found) >= k:
                    break

            # 이웃 노드 확장
            neighbors = self._get_neighbors(u, context)

            for v, edge_data in neighbors:
                # w'(u→v;θ) 계산
                edge_cost = self._calculate_edge_cost(edge_data, context)

                # 차단된 엣지는 건너뛰기
                if edge_cost >= self.cost_calculator.INF:
                    continue

                # 대안 경로 비용
                alt = current_cost + edge_cost

                # 더 나은 경로인 경우 갱신
                if v not in dist or alt < dist[v]:
                    dist[v] = alt
                    heapq.heappush(pq, (alt, v))

        # POI 리스트 정렬 (거리순) 및 반환 포맷 변환
        pois_found.sort(key=lambda x: x[2])  # 거리순 정렬
        poi_list = [(node_id, poi_info) for node_id, poi_info, _ in pois_found]

        return poi_list, dist

    def _get_neighbors(self, node_id: int, context: Context) -> List[Tuple[int, Dict]]:
        """
        노드의 이웃 노드 및 엣지 데이터 조회

        Args:
            node_id: 노드 ID
            context: 컨텍스트

        Returns:
            [(이웃_노드_ID, 엣지_데이터), ...]
        """
        return self.repository.get_neighbors(node_id, context)

    def _calculate_edge_cost(self, edge_data: Dict, context: Context) -> float:
        """
        엣지 비용 계산 (w'(e;θ))

        Args:
            edge_data: 엣지 정보
                - base_cost: 기본 비용 w(e)
                - regulations: 적용 규정 목록
            context: 라우팅 컨텍스트 θ

        Returns:
            최종 비용 w'(e;θ)
        """
        base_cost = edge_data.get("base_cost", 0.0)
        regulations = edge_data.get("regulations", [])

        return self.cost_calculator.calculate_edge_cost(base_cost, regulations, context)
