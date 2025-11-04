"""
Neo4j Domain 스키마 생성 스크립트

MAS 도메인 정보를 Neo4j에 저장하기 위한 스키마 생성:
- Domain 노드 타입
- BELONGS_TO_DOMAIN 관계
- NEIGHBOR_DOMAIN 관계 (A2A 네트워크)
- 인덱스 및 제약조건

실행: python law/scripts/create_domain_schema.py
"""

import os
import sys
import django

# Django 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services import get_neo4j_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_domain_schema():
    """Domain 스키마 생성"""

    neo4j = get_neo4j_service()

    try:
        logger.info("=" * 60)
        logger.info("Neo4j Domain 스키마 생성 시작")
        logger.info("=" * 60)

        # ============== 1. 제약조건 생성 ==============

        logger.info("\n[1/4] 제약조건 생성 중...")

        # Domain 노드 UNIQUE 제약조건
        constraints = [
            {
                'name': 'domain_id_unique',
                'query': 'CREATE CONSTRAINT domain_id_unique IF NOT EXISTS FOR (n:Domain) REQUIRE n.domain_id IS UNIQUE'
            },
            {
                'name': 'domain_name_not_null',
                'query': 'CREATE CONSTRAINT domain_name_not_null IF NOT EXISTS FOR (n:Domain) REQUIRE n.domain_name IS NOT NULL'
            }
        ]

        for constraint in constraints:
            try:
                neo4j.execute_query(constraint['query'], {})
                logger.info(f"  [OK] {constraint['name']} 생성 완료")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'equivalent' in str(e).lower():
                    logger.info(f"  [SKIP] {constraint['name']} 이미 존재")
                else:
                    logger.error(f"  [ERROR] {constraint['name']} 생성 실패: {e}")

        # ============== 2. 인덱스 생성 ==============

        logger.info("\n[2/4] 인덱스 생성 중...")

        indexes = [
            {
                'name': 'domain_name_idx',
                'query': 'CREATE INDEX domain_name_idx IF NOT EXISTS FOR (n:Domain) ON (n.domain_name)'
            },
            {
                'name': 'domain_node_count_idx',
                'query': 'CREATE INDEX domain_node_count_idx IF NOT EXISTS FOR (n:Domain) ON (n.node_count)'
            },
            {
                'name': 'domain_created_at_idx',
                'query': 'CREATE INDEX domain_created_at_idx IF NOT EXISTS FOR (n:Domain) ON (n.created_at)'
            }
        ]

        for index in indexes:
            try:
                neo4j.execute_query(index['query'], {})
                logger.info(f"  [OK] {index['name']} 생성 완료")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'equivalent' in str(e).lower():
                    logger.info(f"  [SKIP] {index['name']} 이미 존재")
                else:
                    logger.error(f"  [ERROR] {index['name']} 생성 실패: {e}")

        # ============== 3. 벡터 인덱스 생성 (선택적) ==============

        logger.info("\n[3/4] 벡터 인덱스 생성 중...")

        # centroid_embedding용 벡터 인덱스
        vector_index_query = """
        CREATE VECTOR INDEX domain_centroid_idx IF NOT EXISTS
        FOR (n:Domain) ON (n.centroid_embedding)
        OPTIONS {indexConfig: {
          `vector.dimensions`: 768,
          `vector.similarity_function`: 'cosine'
        }}
        """

        try:
            neo4j.execute_query(vector_index_query, {})
            logger.info("  [OK] domain_centroid_idx 벡터 인덱스 생성 완료")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'equivalent' in str(e).lower():
                logger.info("  [SKIP] domain_centroid_idx 이미 존재")
            else:
                logger.warning(f"  [WARN] 벡터 인덱스 생성 실패 (Neo4j 버전 확인 필요): {e}")

        # ============== 4. 기존 데이터 확인 ==============

        logger.info("\n[4/4] 기존 데이터 확인 중...")

        # HANG 노드 개수
        hang_count_query = "MATCH (h:HANG) RETURN count(h) as count"
        hang_result = neo4j.execute_query(hang_count_query, {})
        hang_count = hang_result[0]['count'] if hang_result else 0
        logger.info(f"  [DATA] HANG 노드: {hang_count:,}개")

        # embedding 있는 HANG 개수
        embedding_count_query = "MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as count"
        embedding_result = neo4j.execute_query(embedding_count_query, {})
        embedding_count = embedding_result[0]['count'] if embedding_result else 0
        logger.info(f"  [DATA] 임베딩 있는 HANG: {embedding_count:,}개")

        # 기존 Domain 노드 개수
        domain_count_query = "MATCH (d:Domain) RETURN count(d) as count"
        domain_result = neo4j.execute_query(domain_count_query, {})
        domain_count = domain_result[0]['count'] if domain_result else 0
        logger.info(f"  [DATA] 기존 Domain 노드: {domain_count}개")

        # ============== 완료 ==============

        logger.info("\n" + "=" * 60)
        logger.info("[SUCCESS] Neo4j Domain 스키마 생성 완료!")
        logger.info("=" * 60)

        logger.info("\n다음 단계:")
        logger.info("1. AgentManager 동기화 로직 추가")
        logger.info("2. 서버 재시작 -> 자동 마이그레이션")
        logger.info("3. Neo4j Browser에서 시각화 확인")

        return True

    except Exception as e:
        logger.error(f"\n[FAIL] 스키마 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        pass  # Neo4jService는 close() 없음


def verify_schema():
    """스키마 생성 확인"""

    neo4j = get_neo4j_service()

    try:
        logger.info("\n" + "=" * 60)
        logger.info("스키마 검증 중...")
        logger.info("=" * 60)

        # 제약조건 확인
        constraints_query = "SHOW CONSTRAINTS"
        constraints = neo4j.execute_query(constraints_query, {})

        domain_constraints = [c for c in constraints if 'Domain' in str(c)]
        logger.info(f"\n[OK] Domain 제약조건: {len(domain_constraints)}개")
        for c in domain_constraints:
            logger.info(f"  - {c.get('name', 'unnamed')}")

        # 인덱스 확인
        indexes_query = "SHOW INDEXES"
        indexes = neo4j.execute_query(indexes_query, {})

        domain_indexes = [i for i in indexes if 'Domain' in str(i)]
        logger.info(f"\n[OK] Domain 인덱스: {len(domain_indexes)}개")
        for i in domain_indexes:
            logger.info(f"  - {i.get('name', 'unnamed')}")

        logger.info("\n" + "=" * 60)

    except Exception as e:
        logger.warning(f"[WARN] 스키마 검증 실패 (Neo4j 버전에 따라 지원 안 될 수 있음): {e}")
    finally:
        pass  # Neo4jService는 close() 없음


if __name__ == '__main__':
    print("\n==== Neo4j Domain 스키마 생성 스크립트 ====\n")

    success = create_domain_schema()

    if success:
        print("\n[SUCCESS] 스키마 생성 성공!")

        # 검증 (선택적)
        try:
            verify_schema()
        except Exception as e:
            print(f"\n[WARN] 검증 생략 (Neo4j 버전 문제): {e}")
    else:
        print("\n[FAIL] 스키마 생성 실패!")
        sys.exit(1)
