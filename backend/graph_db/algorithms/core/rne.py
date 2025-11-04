"""
RNE (Range Network Expansion) Algorithm

범위 네트워크 확장 알고리즘
"""

import heapq
from typing import Dict, List, Set, Tuple
from .base import BaseSpatialAlgorithm
from ..domain import Context


class RNE(BaseSpatialAlgorithm):
    """
    RNE (Range Network Expansion) 알고리즘

    Integration.md 4절 RNE-First Road 구현.
    Dijkstra 변형으로 비용 e 이내 모든 도달 가능 노드 탐색.

    **알고리즘 개요**:
    1. 우선순위 큐에 시작 노드 추가 (비용=0)
    2. 큐에서 최소 비용 노드 u 추출
    3. 비용이 e 초과하면 종료 (조기 종료)
    4. u의 이웃 노드 v들에 대해:
        - w'(u→v;θ) 계산 (CostCalculator 사용)
        - alt = cost[u] + w'(u→v;θ)
        - alt ≤ e이고 더 나은 경로면 갱신
    5. 2번으로 돌아가 반복

    **시간 복잡도**: O((E + V) log V) (Dijkstra와 동일)
    **공간 복잡도**: O(V) (거리 배열 + 우선순위 큐)

    Example:
        >>> from ..domain import Context
        >>> from datetime import datetime
        >>> ctx = Context("car", datetime.now())
        >>> rne = RNE(cost_calculator, repository)
        >>> reached, costs = rne.execute(node_id=1, radius_or_k=1000.0, context=ctx)
        >>> print(f"도달 가능 노드: {len(reached)}개")
        도달 가능 노드: 5개
    """

    def execute(
        self, start_node_id: int, radius_or_k: float, context: Context
    ) -> Tuple[Set[int], Dict[int, float]]:
        """
        RNE 알고리즘 실행

        Args:
            start_node_id: 시작 노드 ID
            radius_or_k: 반경 e (초 단위)
            context: 라우팅 컨텍스트 θ

        Returns:
            (REACHED, dist):
                - REACHED: 도달 가능 노드 집합
                - dist: 노드별 최소 비용

        Integration.md 126-138줄 의사코드 참조
        """
        radius_e = radius_or_k

        # 초기화
        pq: List[Tuple[float, int]] = [(0.0, start_node_id)]  # (비용, 노드ID)
        dist: Dict[int, float] = {start_node_id: 0.0}
        reached: Set[int] = set()

        while pq:
            current_cost, u = heapq.heappop(pq)

            # 조기 종료: 비용이 반경 초과
            if current_cost > radius_e:
                break

            # 이미 처리된 노드 스킵 (중복 방문 방지)
            if u in reached:
                continue

            # 도달 가능 노드에 추가
            reached.add(u)

            # 이웃 노드 탐색
            neighbors = self._get_neighbors(u, context)

            for v, edge_data in neighbors:
                # w'(u→v;θ) 계산
                edge_cost = self._calculate_edge_cost(edge_data, context)

                # 차단된 엣지는 건너뛰기
                if edge_cost >= self.cost_calculator.INF:
                    continue

                # 대안 경로 비용
                alt = current_cost + edge_cost

                # 반경 이내이고 더 나은 경로인 경우 갱신
                if alt <= radius_e and (v not in dist or alt < dist[v]):
                    dist[v] = alt
                    heapq.heappush(pq, (alt, v))

        return reached, dist

    def _get_neighbors(self, node_id: int, context: Context) -> List[Tuple[int, Dict]]:
        """
        노드의 이웃 노드 및 엣지 데이터 조회

        Args:
            node_id: 노드 ID
            context: 컨텍스트 (Repository 쿼리에 사용 가능)

        Returns:
            [(이웃_노드_ID, 엣지_데이터), ...]
            엣지_데이터는 다음을 포함:
                - base_cost: 기본 비용
                - regulations: 적용 규정 목록
        """
        # Repository를 통해 이웃 조회 (DIP 적용)
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

        # CostCalculator를 통해 비용 계산 (DIP 적용)
        return self.cost_calculator.calculate_edge_cost(base_cost, regulations, context)
