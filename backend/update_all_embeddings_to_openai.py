"""
모든 HANG 노드의 임베딩을 OpenAI text-embedding-3-large로 통일

A2A 협업 시 차원 불일치 문제 해결
"""

import os
import django

# Django 설정
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from openai import OpenAI
from graph_db.services.neo4j_service import Neo4jService
import time

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# OpenAI 클라이언트
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_openai_embedding(text: str) -> list[float]:
    """OpenAI text-embedding-3-large로 임베딩 생성"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"OpenAI embedding error: {e}")
        raise

def main():
    logger.info("=" * 70)
    logger.info("모든 HANG 노드를 OpenAI 임베딩으로 통일 시작")
    logger.info("=" * 70)

    neo4j = Neo4jService()
    neo4j.connect()

    try:
        # 모든 HANG 노드 조회
        query = """
        MATCH (law:LAW)-[:CONTAINS*]->(h:HANG)
        WHERE h.content IS NOT NULL
        RETURN law.name as domain,
               elementId(h) as element_id,
               h.hang_id as hang_id,
               h.content as content,
               size(h.embedding) as current_dim
        ORDER BY domain, hang_id
        """

        with neo4j.driver.session() as session:
            result = session.run(query)
            hangs = list(result)

        total = len(hangs)
        logger.info(f"총 {total}개 HANG 노드 발견")

        # 도메인별 카운트
        domains = {}
        for hang in hangs:
            domain = hang['domain']
            dim = hang['current_dim']
            if domain not in domains:
                domains[domain] = {'768': 0, '3072': 0, 'null': 0}
            if dim == 768:
                domains[domain]['768'] += 1
            elif dim == 3072:
                domains[domain]['3072'] += 1
            else:
                domains[domain]['null'] += 1

        logger.info("\n도메인별 현재 임베딩 상태:")
        for domain, counts in domains.items():
            logger.info(f"  {domain}:")
            logger.info(f"    - KR-SBERT (768차원): {counts['768']}개")
            logger.info(f"    - OpenAI (3072차원): {counts['3072']}개")
            logger.info(f"    - 없음: {counts['null']}개")

        # OpenAI로 업데이트할 노드만 필터링 (768차원 또는 임베딩 없는 노드)
        to_update = [h for h in hangs if h['current_dim'] != 3072]
        logger.info(f"\nOpenAI로 업데이트할 노드: {len(to_update)}개")

        if len(to_update) == 0:
            logger.info("모든 노드가 이미 OpenAI 임베딩입니다.")
            return

        # 자동 실행 (사용자 확인 없이)
        logger.info(f"\n{len(to_update)}개 노드를 OpenAI 임베딩으로 업데이트합니다.")
        logger.info(f"예상 비용: 약 ${len(to_update) * 0.00013:.2f} (text-embedding-3-large 기준)")
        logger.info("자동 실행 모드 - 바로 시작합니다...")

        # 업데이트 시작
        updated = 0
        failed = 0
        start_time = time.time()

        for i, hang in enumerate(to_update, 1):
            try:
                # OpenAI 임베딩 생성
                embedding = get_openai_embedding(hang['content'])

                # Neo4j에 저장
                update_query = """
                MATCH (h) WHERE elementId(h) = $element_id
                CALL db.create.setNodeVectorProperty(h, "embedding", $embedding)
                """

                with neo4j.driver.session() as session:
                    session.run(update_query, {
                        'element_id': hang['element_id'],
                        'embedding': embedding
                    })

                updated += 1

                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    remaining = (len(to_update) - i) / rate
                    logger.info(f"진행: {i}/{len(to_update)} ({i/len(to_update)*100:.1f}%) - "
                              f"예상 남은 시간: {remaining/60:.1f}분")

                # Rate limit 고려 (3000 RPM = 50 RPS)
                time.sleep(0.02)

            except Exception as e:
                logger.error(f"실패 - {hang['domain']} / {hang['hang_id']}: {e}")
                failed += 1

        elapsed = time.time() - start_time
        logger.info("=" * 70)
        logger.info(f"완료! 총 소요 시간: {elapsed/60:.1f}분")
        logger.info(f"성공: {updated}개, 실패: {failed}개")
        logger.info("=" * 70)

    finally:
        neo4j.disconnect()

if __name__ == "__main__":
    main()
