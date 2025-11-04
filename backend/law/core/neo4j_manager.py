"""
Neo4j 데이터 로더

파싱된 법령 데이터를 Neo4j 그래프 DB에 적재
"""

from neo4j import GraphDatabase
from typing import List, Dict, Optional
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jLawLoader:
    """Neo4j 법령 데이터 로더"""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        """
        Args:
            uri: Neo4j 연결 URI (예: "bolt://localhost:7687")
            user: 사용자명
            password: 비밀번호
            database: 데이터베이스 이름 (기본값: "neo4j")
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        logger.info(f"Neo4j 연결 성공: {uri}, database: {database}")

    def close(self):
        """드라이버 종료"""
        self.driver.close()
        logger.info("Neo4j 연결 종료")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_constraints_and_indexes(self):
        """제약조건 및 인덱스 생성"""
        with self.driver.session(database=self.database) as session:
            # UNIQUE 제약조건 (full_id는 고유해야 함)
            unique_constraints = [
                "CREATE CONSTRAINT law_fullid_unique IF NOT EXISTS FOR (n:LAW) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT pyeon_fullid_unique IF NOT EXISTS FOR (n:PYEON) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT jang_fullid_unique IF NOT EXISTS FOR (n:JANG) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT jeol_fullid_unique IF NOT EXISTS FOR (n:JEOL) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT gwan_fullid_unique IF NOT EXISTS FOR (n:GWAN) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT jo_fullid_unique IF NOT EXISTS FOR (n:JO) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT hang_fullid_unique IF NOT EXISTS FOR (n:HANG) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT ho_fullid_unique IF NOT EXISTS FOR (n:HO) REQUIRE n.full_id IS UNIQUE",
                "CREATE CONSTRAINT mok_fullid_unique IF NOT EXISTS FOR (n:MOK) REQUIRE n.full_id IS UNIQUE",
            ]

            for constraint in unique_constraints:
                try:
                    session.run(constraint)
                    logger.info(f"UNIQUE 제약조건 생성: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"제약조건 생성 실패 (이미 존재할 수 있음): {e}")

            # NOT NULL 제약조건 (필수 속성 보장)
            not_null_constraints = [
                # law_name은 모든 단위 노드에 필수
                "CREATE CONSTRAINT jo_law_name_not_null IF NOT EXISTS FOR (n:JO) REQUIRE n.law_name IS NOT NULL",
                "CREATE CONSTRAINT hang_law_name_not_null IF NOT EXISTS FOR (n:HANG) REQUIRE n.law_name IS NOT NULL",
                "CREATE CONSTRAINT ho_law_name_not_null IF NOT EXISTS FOR (n:HO) REQUIRE n.law_name IS NOT NULL",
                "CREATE CONSTRAINT mok_law_name_not_null IF NOT EXISTS FOR (n:MOK) REQUIRE n.law_name IS NOT NULL",
                # full_id도 필수
                "CREATE CONSTRAINT jo_fullid_not_null IF NOT EXISTS FOR (n:JO) REQUIRE n.full_id IS NOT NULL",
                "CREATE CONSTRAINT hang_fullid_not_null IF NOT EXISTS FOR (n:HANG) REQUIRE n.full_id IS NOT NULL",
                "CREATE CONSTRAINT ho_fullid_not_null IF NOT EXISTS FOR (n:HO) REQUIRE n.full_id IS NOT NULL",
                "CREATE CONSTRAINT mok_fullid_not_null IF NOT EXISTS FOR (n:MOK) REQUIRE n.full_id IS NOT NULL",
            ]

            for constraint in not_null_constraints:
                try:
                    session.run(constraint)
                    logger.info(f"NOT NULL 제약조건 생성: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"제약조건 생성 실패 (이미 존재할 수 있음): {e}")

            # 단일 인덱스 생성
            single_indexes = [
                # LAW 노드
                "CREATE INDEX law_name_idx IF NOT EXISTS FOR (n:LAW) ON (n.name)",
                "CREATE INDEX law_category_idx IF NOT EXISTS FOR (n:LAW) ON (n.law_category)",
                "CREATE INDEX law_base_name_idx IF NOT EXISTS FOR (n:LAW) ON (n.base_law_name)",
                "CREATE INDEX law_number_idx IF NOT EXISTS FOR (n:LAW) ON (n.law_number)",
                "CREATE INDEX law_agent_id_idx IF NOT EXISTS FOR (n:LAW) ON (n.agent_id)",
                # 각 단위 노드에 law_name 인덱스 (법률별 필터링)
                "CREATE INDEX jo_law_name_idx IF NOT EXISTS FOR (n:JO) ON (n.law_name)",
                "CREATE INDEX hang_law_name_idx IF NOT EXISTS FOR (n:HANG) ON (n.law_name)",
                "CREATE INDEX ho_law_name_idx IF NOT EXISTS FOR (n:HO) ON (n.law_name)",
                "CREATE INDEX mok_law_name_idx IF NOT EXISTS FOR (n:MOK) ON (n.law_name)",
                # 각 단위 노드에 law_category 인덱스
                "CREATE INDEX jo_law_category_idx IF NOT EXISTS FOR (n:JO) ON (n.law_category)",
                "CREATE INDEX hang_law_category_idx IF NOT EXISTS FOR (n:HANG) ON (n.law_category)",
                "CREATE INDEX ho_law_category_idx IF NOT EXISTS FOR (n:HO) ON (n.law_category)",
                "CREATE INDEX mok_law_category_idx IF NOT EXISTS FOR (n:MOK) ON (n.law_category)",
                # 각 단위 노드에 base_law_name 인덱스
                "CREATE INDEX jo_base_name_idx IF NOT EXISTS FOR (n:JO) ON (n.base_law_name)",
                "CREATE INDEX hang_base_name_idx IF NOT EXISTS FOR (n:HANG) ON (n.base_law_name)",
                "CREATE INDEX ho_base_name_idx IF NOT EXISTS FOR (n:HO) ON (n.base_law_name)",
                "CREATE INDEX mok_base_name_idx IF NOT EXISTS FOR (n:MOK) ON (n.base_law_name)",
                # 각 단위 노드에 agent_id 인덱스 (멀티 에이전트 라우팅)
                "CREATE INDEX jo_agent_id_idx IF NOT EXISTS FOR (n:JO) ON (n.agent_id)",
                "CREATE INDEX hang_agent_id_idx IF NOT EXISTS FOR (n:HANG) ON (n.agent_id)",
                "CREATE INDEX ho_agent_id_idx IF NOT EXISTS FOR (n:HO) ON (n.agent_id)",
                "CREATE INDEX mok_agent_id_idx IF NOT EXISTS FOR (n:MOK) ON (n.agent_id)",
                # unit_number 인덱스
                "CREATE INDEX jo_number_idx IF NOT EXISTS FOR (n:JO) ON (n.unit_number)",
                "CREATE INDEX jo_title_idx IF NOT EXISTS FOR (n:JO) ON (n.title)",
            ]

            for index in single_indexes:
                try:
                    session.run(index)
                    logger.info(f"인덱스 생성: {index[:60]}...")
                except Exception as e:
                    logger.warning(f"인덱스 생성 실패: {e}")

            # Composite 인덱스 생성 (법률명 + 단위번호로 빠른 검색)
            composite_indexes = [
                "CREATE INDEX jo_law_unit_idx IF NOT EXISTS FOR (n:JO) ON (n.law_name, n.unit_number)",
                "CREATE INDEX hang_law_unit_idx IF NOT EXISTS FOR (n:HANG) ON (n.law_name, n.unit_number)",
                "CREATE INDEX ho_law_unit_idx IF NOT EXISTS FOR (n:HO) ON (n.law_name, n.unit_number)",
                "CREATE INDEX mok_law_unit_idx IF NOT EXISTS FOR (n:MOK) ON (n.law_name, n.unit_number)",
            ]

            for index in composite_indexes:
                try:
                    session.run(index)
                    logger.info(f"Composite 인덱스 생성: {index[:60]}...")
                except Exception as e:
                    logger.warning(f"Composite 인덱스 생성 실패: {e}")

            # 전문 검색 인덱스 (Neo4j Enterprise에서만 사용 가능)
            try:
                session.run("""
                    CREATE FULLTEXT INDEX jo_content_fulltext IF NOT EXISTS
                    FOR (n:JO) ON EACH [n.title, n.content]
                """)
                logger.info("전문 검색 인덱스 생성")
            except Exception as e:
                logger.warning(f"전문 검색 인덱스 생성 실패 (Enterprise 기능): {e}")

    def clear_database(self):
        """데이터베이스 전체 삭제 (주의: 모든 데이터가 삭제됨)"""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.warning("⚠️  데이터베이스 전체 삭제 완료")

    def create_law_node(self, law_name: str, law_type: str = "법률",
                       metadata: Optional[Dict] = None):
        """법률 노드 생성"""
        with self.driver.session(database=self.database) as session:
            query = """
            MERGE (law:LAW {full_id: $law_name})
            ON CREATE SET
                law.name = $law_name,
                law.law_type = $law_type,
                law.created_at = datetime()
            ON MATCH SET
                law.updated_at = datetime()
            """

            params = {
                'law_name': law_name,
                'law_type': law_type
            }

            if metadata:
                for key, value in metadata.items():
                    query += f", law.{key} = ${key}"
                    params[key] = value

            session.run(query, params)
            logger.info(f"법률 노드 생성: {law_name}")

    def create_nodes_batch(self, nodes: List[Dict], batch_size: int = 1000):
        """노드 배치 생성"""
        total = len(nodes)
        created = 0

        with self.driver.session(database=self.database) as session:
            for i in range(0, total, batch_size):
                batch = nodes[i:i + batch_size]

                for node in batch:
                    label = node['labels'][0]
                    props = node['properties']

                    # 동적 쿼리 생성
                    prop_assignments = []
                    params = {'full_id': props['full_id']}

                    for key, value in props.items():
                        if key != 'full_id' and value is not None:
                            prop_assignments.append(f"n.{key} = ${key}")
                            params[key] = value

                    prop_str = ', '.join(prop_assignments) if prop_assignments else ""

                    query = f"""
                    MERGE (n:{label} {{full_id: $full_id}})
                    ON CREATE SET {prop_str}, n.created_at = datetime()
                    ON MATCH SET {prop_str}, n.updated_at = datetime()
                    """

                    session.run(query, params)
                    created += 1

                logger.info(f"노드 생성 진행: {created}/{total}")

        logger.info(f"총 {created}개 노드 생성 완료")

    def create_relationships_batch(self, relationships: List[Dict], batch_size: int = 1000):
        """관계 배치 생성"""
        total = len(relationships)
        created = 0

        with self.driver.session(database=self.database) as session:
            for i in range(0, total, batch_size):
                batch = relationships[i:i + batch_size]

                for rel in batch:
                    rel_type = rel['type']
                    from_id = rel['from_id']
                    to_id = rel['to_id']
                    props = rel.get('properties', {})

                    # 관계 속성 설정
                    prop_assignments = []
                    params = {
                        'from_id': from_id,
                        'to_id': to_id
                    }

                    for key, value in props.items():
                        if value is not None:
                            prop_assignments.append(f"r.{key} = ${key}")
                            params[key] = value

                    prop_str = f"SET {', '.join(prop_assignments)}" if prop_assignments else ""

                    query = f"""
                    MATCH (a {{full_id: $from_id}})
                    MATCH (b {{full_id: $to_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    {prop_str}
                    """

                    try:
                        session.run(query, params)
                        created += 1
                    except Exception as e:
                        logger.error(f"관계 생성 실패: {from_id} -[{rel_type}]-> {to_id}: {e}")

                logger.info(f"관계 생성 진행: {created}/{total}")

        logger.info(f"총 {created}개 관계 생성 완료")

    def load_law_data(self, data: Dict):
        """Neo4j 형식의 dict 데이터를 로드"""
        law_name = data.get('law_name')
        nodes = data.get('nodes', [])
        relationships = data.get('relationships', [])

        logger.info(f"법률: {law_name}, 노드: {len(nodes)}개, 관계: {len(relationships)}개")

        # 법률 노드 생성
        self.create_law_node(law_name)

        # 노드 및 관계 생성
        self.create_nodes_batch(nodes)
        self.create_relationships_batch(relationships)

        logger.info("데이터 로드 완료")

        return {
            'nodes_created': len(nodes),
            'relationships_created': len(relationships)
        }

    def load_from_json(self, json_file_path: str):
        """JSON 파일에서 데이터 로드"""
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return self.load_law_data(data)

    def verify_data(self, law_name: str):
        """데이터 검증"""
        with self.driver.session(database=self.database) as session:
            # 노드 개수 확인
            result = session.run("""
                MATCH (n)
                WHERE n.full_id STARTS WITH $law_name
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY label
            """, law_name=law_name)

            print("\n=== 노드 통계 ===")
            for record in result:
                print(f"{record['label']}: {record['count']}개")

            # 관계 개수 확인
            result = session.run("""
                MATCH (a)-[r]->(b)
                WHERE a.full_id STARTS WITH $law_name
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY rel_type
            """, law_name=law_name)

            print("\n=== 관계 통계 ===")
            for record in result:
                print(f"{record['rel_type']}: {record['count']}개")

            # 샘플 조 조회
            result = session.run("""
                MATCH (jo:JO)
                WHERE jo.full_id STARTS WITH $law_name
                RETURN jo.number, jo.title, jo.content
                ORDER BY jo.order
                LIMIT 3
            """, law_name=law_name)

            print("\n=== 샘플 조 ===")
            for record in result:
                print(f"제{record['jo.number']} ({record['jo.title']})")
                print(f"  {record['jo.content'][:50]}...")

    def query_hierarchy(self, full_id: str, max_depth: int = 5):
        """특정 조의 계층 구조 조회"""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH path = (root)-[:CONTAINS*0..%d]->(target {full_id: $full_id})-[:CONTAINS*0..%d]->(leaf)
                RETURN path
                LIMIT 100
            """ % (max_depth, max_depth), full_id=full_id)

            print(f"\n=== {full_id} 계층 구조 ===")
            for record in result:
                path = record['path']
                print(f"경로 길이: {len(path)}")

    def export_to_json(self, law_name: str, output_file: str):
        """Neo4j 데이터를 JSON으로 내보내기"""
        with self.driver.session(database=self.database) as session:
            # 노드 조회
            nodes_result = session.run("""
                MATCH (n)
                WHERE n.full_id STARTS WITH $law_name
                RETURN n, labels(n) as labels
            """, law_name=law_name)

            nodes = []
            for record in nodes_result:
                node = dict(record['n'])
                nodes.append({
                    'labels': record['labels'],
                    'properties': node
                })

            # 관계 조회
            rels_result = session.run("""
                MATCH (a)-[r]->(b)
                WHERE a.full_id STARTS WITH $law_name
                RETURN a.full_id as from_id, b.full_id as to_id, type(r) as rel_type, properties(r) as props
            """, law_name=law_name)

            relationships = []
            for record in rels_result:
                relationships.append({
                    'from_id': record['from_id'],
                    'to_id': record['to_id'],
                    'type': record['rel_type'],
                    'properties': dict(record['props'])
                })

            # JSON 저장
            export_data = {
                'law_name': law_name,
                'nodes': nodes,
                'relationships': relationships,
                'exported_at': datetime.now().isoformat()
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"데이터 내보내기 완료: {output_file}")


# 사용 예시
if __name__ == "__main__":
    # Neo4j 연결 정보
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "your_password"  # 실제 비밀번호로 변경 필요

    try:
        with Neo4jLawLoader(URI, USER, PASSWORD) as loader:
            # 1. 제약조건 및 인덱스 생성
            loader.create_constraints_and_indexes()

            # 2. 기존 데이터 삭제 (선택사항)
            # loader.clear_database()

            # 3. JSON 파일에서 데이터 로드
            loader.load_from_json('neo4j_data.json')

            # 4. 데이터 검증
            loader.verify_data("건축법")

            # 5. 특정 조 계층 조회
            loader.query_hierarchy("건축법::제3조")

    except Exception as e:
        logger.error(f"오류 발생: {e}")
