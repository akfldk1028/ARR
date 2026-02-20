"""
Neo4j Graph Repository

Neo4j 기반 그래프 데이터 접근 구현
"""

from typing import Dict, List, Tuple
from neo4j import GraphDatabase, Driver
from .graph_repository import GraphRepository
from ..domain import Context


class Neo4jGraphRepository(GraphRepository):
    """
    Neo4j 기반 GraphRepository 구현

    **Neo4j 스키마** (Integration.md 참조):
        - (:RoadNode {node_id: int})-[:SEGMENT {baseTime: float}]->(:RoadNode)
        - SEGMENT.zone_id: 속성으로 Zone 연결 (관계 아님!)
        - (:Zone {zone_id: str})-[:ENFORCES]->(:Regulation)
        - (:Regulation)-[:CITES]->(:SNDB)

    **Cypher 쿼리 전략**:
        1. 노드의 SEGMENT 관계 조회
        2. SEGMENT.zone_id로 Zone 찾기
        3. Zone → ENFORCES → Regulation 조회
        4. Regulation 데이터를 regulations 리스트로 반환
    """

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        """
        Args:
            uri: Neo4j 연결 URI (예: "neo4j://127.0.0.1:7687")
            user: 사용자명
            password: 비밀번호
            database: 데이터베이스 이름
        """
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def get_neighbors(
        self, node_id: int, context: Context
    ) -> List[Tuple[int, Dict]]:
        """
        노드의 이웃 노드 및 엣지 데이터 조회

        **Cypher 쿼리**:
        ```cypher
        MATCH (src:RoadNode {node_id: $node_id})-[seg:SEGMENT]->(dst:RoadNode)
        OPTIONAL MATCH (z:Zone {zone_id: seg.zone_id})-[:ENFORCES]->(reg:Regulation)
        RETURN dst.node_id AS neighbor_id,
               seg.baseTime AS base_cost,
               COLLECT({
                   type: reg.type,
                   limit: reg.limit,
                   start_time: reg.start_time,
                   end_time: reg.end_time,
                   penalty: reg.penalty,
                   required_permit: reg.required_permit
               }) AS regulations
        ```

        Args:
            node_id: 시작 노드 ID
            context: 컨텍스트 (현재 미사용, 향후 규정 필터링 가능)

        Returns:
            [(neighbor_id, edge_data), ...]
        """
        query = """
        MATCH (src:RoadNode {node_id: $node_id})-[seg:SEGMENT]->(dst:RoadNode)
        OPTIONAL MATCH (z:Zone {zone_id: seg.zone_id})-[:ENFORCES]->(reg:Regulation)
        RETURN dst.node_id AS neighbor_id,
               seg.baseTime AS base_cost,
               seg.zone_id AS zone_id,
               COLLECT({
                   type: reg.type,
                   limit: reg.limit,
                   start_time: reg.start_time,
                   end_time: reg.end_time,
                   penalty: reg.penalty,
                   required_permit: reg.required_permit,
                   violated: reg.violated
               }) AS regulations
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, node_id=node_id)
            neighbors = []

            for record in result:
                neighbor_id = record["neighbor_id"]
                base_cost = record.get("base_cost", 0.0)
                regulations_raw = record.get("regulations", [])

                # None 규정 필터링 (OPTIONAL MATCH 결과)
                regulations = [
                    reg for reg in regulations_raw if reg.get("type") is not None
                ]

                edge_data = {
                    "base_cost": base_cost,
                    "regulations": regulations,
                    "zone_id": record.get("zone_id"),
                }

                neighbors.append((neighbor_id, edge_data))

            return neighbors

    def get_node_exists(self, node_id: int) -> bool:
        """
        노드 존재 여부 확인

        Args:
            node_id: 노드 ID

        Returns:
            노드 존재 여부
        """
        query = """
        MATCH (n:RoadNode {node_id: $node_id})
        RETURN COUNT(n) > 0 AS exists
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            return record["exists"] if record else False

    def get_node_count(self) -> int:
        """
        전체 노드 개수 조회

        Returns:
            RoadNode 개수
        """
        query = """
        MATCH (n:RoadNode)
        RETURN COUNT(n) AS count
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            record = result.single()
            return record["count"] if record else 0

    def get_poi_at_node(self, node_id: int) -> Dict:
        """
        노드에 연결된 POI 정보 조회

        **Neo4j 스키마**:
        (:RoadNode {node_id: int})-[:LOCATED_AT]->(:POI {type: str, name: str})

        Args:
            node_id: 노드 ID

        Returns:
            POI 정보 딕셔너리 (POI 없으면 빈 딕셔너리)
        """
        query = """
        MATCH (n:RoadNode {node_id: $node_id})-[:LOCATED_AT]->(p:POI)
        RETURN p.type AS poi_type, p.name AS poi_name, properties(p) AS poi_properties
        LIMIT 1
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, node_id=node_id)
            record = result.single()

            if record:
                return {
                    "poi_type": record["poi_type"],
                    "name": record.get("poi_name"),
                    "properties": record.get("poi_properties", {}),
                }
            return {}

    def close(self):
        """
        Neo4j 드라이버 종료

        리소스 정리 및 연결 종료.
        """
        if self.driver:
            self.driver.close()

    def __del__(self):
        """소멸자에서도 연결 종료 보장"""
        self.close()
