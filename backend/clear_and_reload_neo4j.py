"""
Neo4j 데이터베이스 초기화 및 재구축 스크립트

법률 타입 구분 문제 해결 후 전체 데이터 재구축
"""

import os
import sys
import django

# Django 설정
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

def main():
    logger.info("=" * 80)
    logger.info("Neo4j 데이터베이스 초기화 및 재구축")
    logger.info("=" * 80)

    # 1. Neo4j 연결 확인
    logger.info("\n[1/4] Neo4j 연결 확인 중...")
    from graph_db.services.neo4j_service import Neo4jService

    neo4j = Neo4jService()
    try:
        neo4j.connect()
        logger.info("✅ Neo4j 연결 성공")
    except Exception as e:
        logger.error(f"❌ Neo4j 연결 실패: {e}")
        logger.error("Neo4j가 실행 중인지 확인하세요")
        return

    # 2. 기존 데이터 삭제
    logger.info("\n[2/4] 기존 데이터 삭제 중...")
    try:
        with neo4j.driver.session() as session:
            # 모든 노드와 관계 삭제
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()['count']
            logger.info(f"삭제할 노드 수: {count}개")

            session.run("MATCH (n) DETACH DELETE n")
            logger.info("✅ 모든 데이터 삭제 완료")
    except Exception as e:
        logger.error(f"❌ 데이터 삭제 실패: {e}")
        return
    finally:
        neo4j.disconnect()

    # 3. JSON 파일로부터 재구축
    logger.info("\n[3/4] JSON 파일로부터 Neo4j 재구축 중...")

    from law.scripts.json_to_neo4j import process_multiple_jsons

    json_dir = Path(__file__).parent / "law" / "data" / "parsed"
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    try:
        process_multiple_jsons(
            json_dir=str(json_dir),
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            output_dir="neo4j",
            pattern="*.json"
        )
        logger.info("✅ Neo4j 재구축 완료")
    except Exception as e:
        logger.error(f"❌ Neo4j 재구축 실패: {e}")
        return

    # 4. 데이터 검증
    logger.info("\n[4/4] 데이터 검증 중...")

    neo4j = Neo4jService()
    neo4j.connect()

    try:
        with neo4j.driver.session() as session:
            # LAW 노드 확인
            result = session.run("MATCH (law:LAW) RETURN count(law) as count")
            law_count = result.single()['count']
            logger.info(f"LAW 노드: {law_count}개")

            # LAW 노드 샘플 확인
            result = session.run("""
                MATCH (law:LAW)
                RETURN law.full_id as full_id, law.law_type as law_type
                LIMIT 5
            """)
            logger.info("\nLAW 노드 샘플:")
            for record in result:
                logger.info(f"  - {record['full_id']} ({record['law_type']})")

            # HANG 노드 확인
            result = session.run("MATCH (h:HANG) RETURN count(h) as count")
            hang_count = result.single()['count']
            logger.info(f"\nHANG 노드: {hang_count}개")

            # HANG 노드 샘플 확인
            result = session.run("""
                MATCH (h:HANG)
                WHERE h.full_id CONTAINS '국토'
                RETURN h.full_id as full_id
                LIMIT 3
            """)
            logger.info("\nHANG 노드 샘플:")
            for record in result:
                logger.info(f"  - {record['full_id']}")

            # CONTAINS 관계 확인
            result = session.run("""
                MATCH (law:LAW)-[r:CONTAINS]->(child)
                RETURN count(r) as count
            """)
            rel_count = result.single()['count']
            logger.info(f"\nCONTAINS 관계: {rel_count}개")

    except Exception as e:
        logger.error(f"❌ 데이터 검증 실패: {e}")
    finally:
        neo4j.disconnect()

    logger.info("\n" + "=" * 80)
    logger.info("✅ 전체 프로세스 완료!")
    logger.info("=" * 80)
    logger.info("\n다음 단계: 임베딩 재생성")
    logger.info("  python law/scripts/add_hang_embeddings.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
