"""
Law Repository - 법규 전용 Neo4j Repository

법규 검색을 위한 Graph Repository 구현.
RoadNode 대신 HANG (항) 노드를 사용하며,
계층 구조 (JO → HANG → HO)를 탐색합니다.
"""

from .graph_repository import GraphRepository
from typing import List, Tuple, Dict, Optional
import numpy as np


class LawRepository(GraphRepository):
    """
    법규 검색용 Repository

    **특징**:
    - Vector search: Neo4j 벡터 인덱스 (hang_embedding_index)
    - Graph traversal: 계층 구조 (부모 JO, 형제 HANG, 자식 HO)
    - Hybrid retrieval: 벡터 + 그래프 결합

    **노드 구조**:
    ```
    (JO:조) -[:HAS_HANG]-> (HANG:항) -[:HAS_HO]-> (HO:호)
    ```

    **웹 검색 기반 최적화**:
    - Two-stage retrieval (HybridRAG 2024)
    - Hierarchical graph traversal
    - Similarity-based filtering
    """

    def __init__(self, neo4j_service):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스
        """
        self.neo4j = neo4j_service
        self._vector_index_name = "hang_embedding_index"

    def vector_search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Neo4j 벡터 인덱스로 유사 조항 검색 (Stage 1)

        Args:
            query_embedding: 쿼리 임베딩 (3072차원)
            top_k: 상위 k개 결과

        Returns:
            [(hang_id, similarity_score), ...]
            similarity_score는 0~1 (1이 가장 유사)

        Example:
            >>> query_emb = model.encode("도시계획 수립 절차")
            >>> results = repo.vector_search(query_emb, top_k=10)
            >>> for hang_id, score in results:
            ...     print(f"HANG {hang_id}: {score:.4f}")
        """
        query = f"""
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_emb)
        YIELD node, score
        RETURN id(node) as hang_id, score
        ORDER BY score DESC
        """

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(
                    query,
                    index_name=self._vector_index_name,
                    top_k=top_k,
                    query_emb=query_embedding.tolist()
                )
                return [(record['hang_id'], record['score']) for record in result]
        except Exception as e:
            # 벡터 인덱스 없음 등의 에러
            raise RuntimeError(f"Vector search failed: {e}. "
                             f"Ensure '{self._vector_index_name}' index exists in Neo4j.")

    def get_neighbors(self, node_id: int, context=None) -> List[Tuple[int, Dict]]:
        """
        법규 이웃 노드 조회 (Stage 2: Graph Expansion)

        **이웃 정의** (법규 특화):
        1. 부모 JO (조) - 맥락 파악
        2. 형제 HANG (항) - 같은 조의 다른 항
        3. 자식 HO (호) - 상세 내용
        4. 법률 간 관련 조항 (IMPLEMENTS 관계) - 시행령/시행규칙의 해당 조항

        Args:
            node_id: HANG 노드 ID
            context: 사용 안 함 (호환성 유지)

        Returns:
            [(neighbor_id, edge_data), ...]

            edge_data 구조:
                {
                    'type': 'parent' | 'sibling' | 'child' | 'cross_law',
                    'base_cost': float,  # 부모/자식/cross_law는 0, 형제는 나중에 계산
                    'embedding': array (sibling, cross_law)
                    'law_name': str (cross_law만)
                }

        Example:
            >>> neighbors = repo.get_neighbors(hang_id=123)
            >>> for nid, data in neighbors:
            ...     print(f"{data['type']}: {nid}")
        """
        query = """
        MATCH (h:HANG) WHERE id(h) = $hang_id

        // [1] 부모 조 (JO) - 맥락 제공
        OPTIONAL MATCH (h)<-[:CONTAINS]-(jo:JO)

        // [2] 형제 항 (HANG) - 같은 조의 다른 항
        OPTIONAL MATCH (jo)-[:CONTAINS]->(sibling:HANG)
        WHERE id(sibling) <> $hang_id
          AND sibling.embedding IS NOT NULL

        // [3] 자식 호 (HO) - 상세 내용
        OPTIONAL MATCH (h)-[:CONTAINS]->(ho:HO)

        // [4] 법률 간 관련 조항 (IMPLEMENTS 관계)
        // 현재 HANG → LAW → IMPLEMENTS → 관련 LAW의 모든 HANG (내용 유사도 기반)
        OPTIONAL MATCH (h)<-[:CONTAINS*]-(law:LAW)
        OPTIONAL MATCH (law)-[:IMPLEMENTS*1..2]->(related_law:LAW)
        OPTIONAL MATCH (related_law)-[:CONTAINS*]->(cross_hang:HANG)
        WHERE cross_hang.embedding IS NOT NULL
          AND id(cross_hang) <> $hang_id

        RETURN
          id(jo) as parent_id,
          COLLECT(DISTINCT {
              id: id(sibling),
              embedding: sibling.embedding
          }) as siblings,
          COLLECT(DISTINCT id(ho)) as children,
          COLLECT(DISTINCT {
              id: id(cross_hang),
              embedding: cross_hang.embedding,
              law_name: related_law.name
          }) as cross_law_hangs
        """

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query, hang_id=node_id)
                record = result.single()

                if not record:
                    return []

                neighbors = []

                # 부모 JO (비용 0 - 자동 포함)
                if record['parent_id']:
                    neighbors.append((
                        record['parent_id'],
                        {'type': 'parent', 'base_cost': 0.0}
                    ))

                # 형제 HANG (유사도 체크 필요)
                for sibling in record['siblings']:
                    if sibling['id'] and sibling['embedding']:
                        neighbors.append((
                            sibling['id'],
                            {
                                'type': 'sibling',
                                'base_cost': 0.5,  # 임시값, 실제로는 유사도로 계산
                                'embedding': np.array(sibling['embedding'])
                            }
                        ))

                # 자식 HO (비용 0 - 자동 포함)
                for child_id in record['children']:
                    if child_id:
                        neighbors.append((
                            child_id,
                            {'type': 'child', 'base_cost': 0.0}
                        ))

                # 법률 간 관련 조항 (비용 0 - 자동 포함, 유사도 체크는 알고리즘에서)
                for cross_hang in record['cross_law_hangs']:
                    if cross_hang['id'] and cross_hang['embedding']:
                        neighbors.append((
                            cross_hang['id'],
                            {
                                'type': 'cross_law',
                                'base_cost': 0.0,  # 법률 계층은 무료 확장
                                'embedding': np.array(cross_hang['embedding']),
                                'law_name': cross_hang.get('law_name', '')
                            }
                        ))

                return neighbors

        except Exception as e:
            raise RuntimeError(f"Failed to get neighbors for node {node_id}: {e}")

    def get_article_info(self, hang_id: int) -> Dict:
        """
        조항 상세 정보 조회 (자식 HO 포함)

        Args:
            hang_id: HANG 노드 ID

        Returns:
            {
                'full_id': '국토의 계획 및 이용에 관한 법률::제13조::제1항',
                'law_name': '국토의 계획 및 이용에 관한 법률',
                'article_number': '제13조제1항',
                'content': '...',
                'order': 13,
                'children': [  # 자식 HO들
                    {
                        'number': '제1호',
                        'content': '...',
                        'full_id': '...'
                    },
                    ...
                ]
            }
        """
        query = """
        MATCH (h:HANG) WHERE id(h) = $hang_id
        OPTIONAL MATCH (h)-[:CONTAINS]->(ho:HO)
        RETURN
          h.full_id as full_id,
          h.law_name as law_name,
          h.number as article_number,
          h.content as content,
          h.order as order,
          COLLECT({
              number: ho.number,
              content: ho.content,
              full_id: ho.full_id
          }) as children
        """

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query, hang_id=hang_id)
                record = result.single()

                if not record:
                    return {}

                # HO 자식들 필터링 (null 제거)
                children = [
                    child for child in record['children']
                    if child['number'] is not None
                ]

                return {
                    'full_id': record['full_id'],
                    'law_name': record['law_name'],
                    'article_number': record['article_number'],
                    'content': record['content'],
                    'order': record['order'],
                    'children': children
                }

        except Exception as e:
            return {}

    def get_node_exists(self, node_id: int) -> bool:
        """
        노드 존재 여부 확인

        Args:
            node_id: 노드 ID

        Returns:
            노드 존재 여부
        """
        query = "MATCH (h:HANG) WHERE id(h) = $node_id RETURN count(h) > 0 as exists"

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query, node_id=node_id)
                record = result.single()
                return record['exists'] if record else False
        except:
            return False

    def get_node_count(self) -> int:
        """
        전체 HANG 노드 개수 조회

        Returns:
            HANG 노드 개수
        """
        query = "MATCH (h:HANG) RETURN count(h) as count"

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query)
                record = result.single()
                return record['count'] if record else 0
        except:
            return 0

    def get_poi_at_node(self, node_id: int) -> Dict:
        """
        POI 조회 (법규에는 없음, 호환성 유지)

        Args:
            node_id: 노드 ID

        Returns:
            빈 딕셔너리 (법규에는 POI 개념 없음)
        """
        return {}

    def close(self):
        """
        리소스 정리

        Neo4j 연결은 neo4j_service에서 관리하므로
        여기서는 특별한 처리 불필요.
        """
        pass

    # === 추가 유틸리티 메서드 ===

    def get_embedding_dimension(self) -> int:
        """
        임베딩 차원 조회

        Returns:
            임베딩 차원 (3072 예상)
        """
        query = """
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN size(h.embedding) as dim
        LIMIT 1
        """

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query)
                record = result.single()
                return record['dim'] if record else 0
        except:
            return 0

    def get_statistics(self) -> Dict:
        """
        법규 데이터 통계

        Returns:
            {
                'total_hangs': int,
                'hangs_with_embedding': int,
                'embedding_dimension': int,
                'total_jos': int,
                'total_hos': int
            }
        """
        query = """
        MATCH (h:HANG)
        WITH count(h) as total_hangs,
             count(CASE WHEN h.embedding IS NOT NULL THEN 1 END) as with_emb
        MATCH (jo:JO)
        WITH total_hangs, with_emb, count(jo) as total_jos
        MATCH (ho:HO)
        RETURN
          total_hangs,
          with_emb,
          total_jos,
          count(ho) as total_hos
        """

        try:
            with self.neo4j.driver.session() as session:
                result = session.run(query)
                record = result.single()

                if not record:
                    return {}

                return {
                    'total_hangs': record['total_hangs'],
                    'hangs_with_embedding': record['with_emb'],
                    'embedding_dimension': self.get_embedding_dimension(),
                    'total_jos': record['total_jos'],
                    'total_hos': record['total_hos']
                }
        except Exception as e:
            return {'error': str(e)}
