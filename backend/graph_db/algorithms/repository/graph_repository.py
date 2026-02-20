"""
Graph Repository Interface

그래프 데이터 접근 추상화 (DIP 적용)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
from ..domain import Context


class GraphRepository(ABC):
    """
    그래프 데이터 접근 인터페이스

    DIP (Dependency Inversion Principle) 적용:
        - Core Layer는 이 인터페이스에만 의존
        - Neo4j 구현체는 이 인터페이스를 구현
        - 테스트 시 Mock Repository로 교체 가능

    **책임**:
        - 노드의 이웃 노드 조회
        - 엣지 데이터 (비용, 규정) 조회
        - 그래프 연결성 검증
    """

    @abstractmethod
    def get_neighbors(
        self, node_id: int, context: Context
    ) -> List[Tuple[int, Dict]]:
        """
        노드의 이웃 노드 조회

        Args:
            node_id: 노드 ID
            context: 라우팅 컨텍스트 (필요 시 규정 필터링 등에 사용)

        Returns:
            [(이웃_노드_ID, 엣지_데이터), ...]

            엣지_데이터 딕셔너리는 다음을 포함:
                - base_cost: 기본 비용 w(e) (float)
                - regulations: 적용 규정 목록 (List[Dict])
                    각 규정:
                        - type: 규정 타입 (str)
                        - limit: 중량 제한 (float, weightLimit 타입)
                        - start_time, end_time: 시간대 (datetime.time, timeBan 타입)
                        - penalty: 페널티 비용 (float, toll/busOnly 등)
                        - required_permit: 필요 허가증 (str, permitBased 타입)

        Example:
            >>> neighbors = repository.get_neighbors(node_id=1, context=ctx)
            >>> for neighbor_id, edge_data in neighbors:
            ...     print(f"Node {neighbor_id}, cost: {edge_data['base_cost']}")
            Node 2, cost: 100.5
            Node 3, cost: 200.0
        """
        pass

    @abstractmethod
    def get_node_exists(self, node_id: int) -> bool:
        """
        노드 존재 여부 확인

        Args:
            node_id: 노드 ID

        Returns:
            노드 존재 여부 (True/False)
        """
        pass

    @abstractmethod
    def get_node_count(self) -> int:
        """
        전체 노드 개수 조회

        Returns:
            노드 개수
        """
        pass

    @abstractmethod
    def get_poi_at_node(self, node_id: int) -> Dict:
        """
        노드에 연결된 POI 정보 조회 (INE 알고리즘용)

        Args:
            node_id: 노드 ID

        Returns:
            POI 정보 딕셔너리 (POI 없으면 빈 딕셔너리)
                - poi_type: POI 타입 (str, 예: "hospital", "school")
                - name: POI 이름 (str, optional)
                - properties: 기타 속성 (Dict, optional)

        Example:
            >>> poi_info = repository.get_poi_at_node(node_id=5)
            >>> if poi_info:
            ...     print(f"POI: {poi_info['poi_type']}")
            POI: hospital
        """
        pass

    @abstractmethod
    def close(self):
        """
        리소스 정리 (연결 종료 등)

        with 문 또는 명시적 호출로 사용.
        """
        pass

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()
