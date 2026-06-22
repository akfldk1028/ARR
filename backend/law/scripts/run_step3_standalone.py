"""
Step3: HANG 노드에 OpenAI text-embedding-3-large (3072-dim) 임베딩 추가
Django 없이 standalone으로 실행 가능.

Usage:
  C:/Python313/python ARR/backend/law/scripts/run_step3_standalone.py

Requires:
  - Neo4j (법규 DB): bolt://localhost:7687, neo4j/demodemo
  - OPENAI_API_KEY env var (or reads from law-domain-agents .env)
"""

import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load OPENAI_API_KEY from law-domain-agents .env if not set
if not os.environ.get('OPENAI_API_KEY'):
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                            'AG', 'agent', 'law-domain-agents', '.env')
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('OPENAI_API_KEY=') and not line.startswith('#'):
                    os.environ['OPENAI_API_KEY'] = line.split('=', 1)[1].strip()
                    logger.info(f"Loaded OPENAI_API_KEY from {env_path}")
                    break

from openai import OpenAI
from neo4j import GraphDatabase

# Law Neo4j config (NOT Graphiti!)
NEO4J_URI = os.environ.get('LAW_NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.environ.get('LAW_NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.environ.get('LAW_NEO4J_PASSWORD', 'demodemo')

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
BATCH_SIZE = 100  # OpenAI max is 2048, but 100 is safe for Neo4j writes


def get_hang_nodes_without_embeddings(driver):
    """임베딩이 없는 HANG 노드 조회"""
    with driver.session() as session:
        result = session.run("""
            MATCH (h:HANG)
            WHERE h.embedding IS NULL
            RETURN elementId(h) AS elementId,
                   h.full_id AS full_id,
                   coalesce(h.title, '') + ' ' + coalesce(h.content, '') AS text
            ORDER BY h.full_id
        """)
        return [dict(r) for r in result]


def get_total_hang_count(driver):
    """전체 HANG 노드 수"""
    with driver.session() as session:
        result = session.run("MATCH (h:HANG) RETURN count(h) AS cnt")
        return result.single()['cnt']


def get_embedded_hang_count(driver):
    """임베딩이 있는 HANG 노드 수"""
    with driver.session() as session:
        result = session.run("MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) AS cnt")
        return result.single()['cnt']


def generate_embeddings(client, texts):
    """OpenAI API로 임베딩 생성 (배치)"""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def save_embeddings_batch(driver, batch):
    """배치로 임베딩 저장"""
    with driver.session() as session:
        session.run("""
            UNWIND $rows AS row
            MATCH (e) WHERE elementId(e) = row.elementId
            CALL db.create.setNodeVectorProperty(e, "embedding", row.embedding)
        """, rows=batch)


def verify_batch(driver, element_ids):
    """배치 저장 검증"""
    with driver.session() as session:
        result = session.run("""
            UNWIND $ids AS id
            MATCH (e) WHERE elementId(e) = id AND e.embedding IS NOT NULL
            RETURN count(e) AS cnt
        """, ids=element_ids)
        return result.single()['cnt']


def main():
    print("\n" + "=" * 70)
    print("Step3: HANG 노드 OpenAI 임베딩 생성 (standalone)")
    print(f"  Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")
    print(f"  Neo4j: {NEO4J_URI} (user: {NEO4J_USER})")
    print("=" * 70)

    # Neo4j 연결
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        logger.info("Neo4j connected")
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        return 1

    # OpenAI 클라이언트
    client = OpenAI()

    # 현재 상태 확인
    total = get_total_hang_count(driver)
    embedded = get_embedded_hang_count(driver)
    logger.info(f"HANG nodes: {total} total, {embedded} already embedded")

    # 임베딩 없는 노드 가져오기
    nodes = get_hang_nodes_without_embeddings(driver)
    if not nodes:
        print("\nAll HANG nodes already have embeddings!")
        driver.close()
        return 0

    logger.info(f"Processing {len(nodes)} nodes without embeddings...")

    # 비용 예상 (~$0.13/1M tokens, avg ~100 tokens per node)
    est_tokens = len(nodes) * 100
    est_cost = est_tokens / 1_000_000 * 0.13
    logger.info(f"Estimated cost: ~${est_cost:.2f} ({est_tokens:,} tokens)")

    # 배치 처리
    total_saved = 0
    start_time = time.time()

    for i in range(0, len(nodes), BATCH_SIZE):
        batch_nodes = nodes[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(nodes) - 1) // BATCH_SIZE + 1

        # 텍스트 추출 (빈 텍스트 방지)
        texts = [n['text'].strip() or n['full_id'] for n in batch_nodes]

        # 임베딩 생성
        try:
            embeddings = generate_embeddings(client, texts)
        except Exception as e:
            logger.error(f"Batch {batch_num}: OpenAI embedding failed: {e}")
            continue

        # Neo4j에 저장
        batch_data = [
            {'elementId': n['elementId'], 'embedding': emb}
            for n, emb in zip(batch_nodes, embeddings)
        ]

        try:
            save_embeddings_batch(driver, batch_data)
        except Exception as e:
            logger.error(f"Batch {batch_num}: Neo4j save failed: {e}")
            # 개별 재시도
            for row in batch_data:
                try:
                    save_embeddings_batch(driver, [row])
                    total_saved += 1
                except Exception:
                    pass
            continue

        # 검증
        element_ids = [n['elementId'] for n in batch_nodes]
        saved = verify_batch(driver, element_ids)
        total_saved += saved

        elapsed = time.time() - start_time
        rate = total_saved / elapsed if elapsed > 0 else 0
        logger.info(f"Batch {batch_num}/{total_batches}: {saved}/{len(batch_nodes)} saved | "
                     f"Total: {total_saved}/{len(nodes)} ({100*total_saved//len(nodes)}%) | "
                     f"{rate:.1f} nodes/sec")

    elapsed = time.time() - start_time
    driver.close()

    print("\n" + "=" * 70)
    print("임베딩 생성 완료!")
    print(f"  대상: {len(nodes)} nodes")
    print(f"  성공: {total_saved}")
    print(f"  실패: {len(nodes) - total_saved}")
    print(f"  소요: {elapsed:.1f}s")
    print(f"  모델: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")
    print("=" * 70)

    if total_saved == len(nodes):
        print("\nAll nodes processed successfully!")
    else:
        print(f"\n{len(nodes) - total_saved} nodes failed. Re-run to retry.")

    return 0 if total_saved == len(nodes) else 1


if __name__ == "__main__":
    sys.exit(main())
