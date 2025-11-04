"""
Base Spatial Algorithm

공간 네트워크 알고리즘 추상 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, Set, Tuple
from ..domain import Context


class BaseSpatialAlgorithm(ABC):
    """
    공간 네트워크 알고리즘 추상 클래스

    모든 알고리즘 (RNE, INE, IER)의 공통 인터페이스 정의.
    Strategy 패턴으로 알고리즘 교체 가능.

    Attributes:
        cost_calculator: 비용 계산기 (DIP 적용)
        repository: 그래프 데이터 접근 (DIP 적용)
    """

    def __init__(self, cost_calculator, repository):
        """
        Args:
            cost_calculator: CostCalculator 인스턴스
            repository: GraphRepository 인터페이스 구현체
        """
        self.cost_calculator = cost_calculator
        self.repository = repository

    @abstractmethod
    def execute(
        self, start_node_id: int, radius_or_k: float, context: Context
    ) -> Tuple[Set[int], Dict[int, float]]:
        """
        알고리즘 실행 (추상 메서드)

        Args:
            start_node_id: 시작 노드 ID
            radius_or_k: RNE의 경우 반경 e, INE의 경우 k개
            context: 라우팅 컨텍스트 θ

        Returns:
            (도달 가능 노드 집합, 노드별 비용 딕셔너리)

        Example:
            >>> algorithm = RNE(cost_calculator, repository)
            >>> reached, costs = algorithm.execute(node_id=1, radius_or_k=1000.0, context=ctx)
            >>> len(reached)
            5
        """
        pass

    def get_algorithm_name(self) -> str:
        """알고리즘 이름 반환 (디버깅/로깅용)"""
        return self.__class__.__name__
