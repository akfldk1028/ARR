"""
HANG 노드에 OpenAI 임베딩 추가 (parser 시스템 사용)

src/post_processing.py의 create_entity_embedding 로직을 HANG 노드에 적용
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from langchain_neo4j import Neo4jGraph
from src.shared.common_fn import load_embedding_model

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def save_single_embedding(graph, element_id, embedding):
    """
    단일 노드에 임베딩 저장 후 검증

    Returns:
        bool: 저장 성공 여부
    """
    try:
        query = """
        MATCH (e) WHERE elementId(e) = $elementId
        CALL db.create.setNodeVectorProperty(e, "embedding", $embedding)
        """
        graph.query(query, params={'elementId': element_id, 'embedding': embedding})

        # 검증: 실제로 저장되었는지 확인
        verify_query = """
        MATCH (e) WHERE elementId(e) = $elementId AND e.embedding IS NOT NULL
        RETURN count(e) as count
        """
        result = graph.query(verify_query, params={'elementId': element_id})
        return result[0]['count'] == 1

    except Exception as e:
        logger.error(f"Failed to save single embedding: {e}")
        return False


def save_batch_with_verification(graph, batch):
    """
    배치로 임베딩 저장 후 검증, 실패 시 개별 재시도

    Returns:
        int: 실제로 저장 성공한 노드 수
    """
    batch_size = len(batch)

    # 1. 배치 저장 시도
    try:
        update_query = """
        UNWIND $rows AS row
        MATCH (e) WHERE elementId(e) = row.elementId
        CALL db.create.setNodeVectorProperty(e, "embedding", row.embedding)
        """
        graph.query(update_query, params={'rows': batch})

    except Exception as e:
        logger.error(f"Batch save failed: {e}, trying individually...")
        # 배치 실패 시 전체를 개별로 재시도
        success_count = 0
        for row in batch:
            if save_single_embedding(graph, row['elementId'], row['embedding']):
                success_count += 1
        logger.info(f"  Individual retry: {success_count}/{batch_size} saved")
        return success_count

    # 2. 검증: 실제로 저장됐는지 확인
    verify_query = """
    UNWIND $elementIds AS id
    MATCH (e) WHERE elementId(e) = id AND e.embedding IS NOT NULL
    RETURN count(e) as count
    """
    element_ids = [row['elementId'] for row in batch]
    result = graph.query(verify_query, params={'elementIds': element_ids})
    saved_count = result[0]['count']

    # 3. 일부 실패 시 실패한 것만 재시도
    if saved_count < batch_size:
        logger.warning(f"  Batch incomplete: {saved_count}/{batch_size} saved, retrying failed...")

        # 실패한 노드 찾기
        find_failed_query = """
        UNWIND $rows AS row
        MATCH (e) WHERE elementId(e) = row.elementId AND e.embedding IS NULL
        RETURN elementId(e) as elementId
        """
        failed_result = graph.query(find_failed_query, params={'rows': batch})
        failed_ids = {r['elementId'] for r in failed_result}

        # 실패한 것만 개별 재시도
        retry_count = 0
        for row in batch:
            if row['elementId'] in failed_ids:
                if save_single_embedding(graph, row['elementId'], row['embedding']):
                    retry_count += 1
                    saved_count += 1

        if retry_count > 0:
            logger.info(f"  Retry success: +{retry_count} saved")

    return saved_count


def main():
    print("\n" + "=" * 70)
    print("HANG 노드 OpenAI 임베딩 생성")
    print("=" * 70)

    try:
        # Neo4j 연결
        uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', '11111111')
        database = os.getenv('NEO4J_DATABASE', 'neo4j')

        logger.info(f"Connecting to Neo4j: {uri}")
        graph = Neo4jGraph(url=uri, username=user, password=password, database=database)

        # HANG 노드 가져오기
        logger.info("Fetching HANG nodes...")
        query = """
        MATCH (h:HANG)
        WHERE h.embedding IS NULL
        RETURN elementId(h) AS elementId,
               h.full_id AS full_id,
               coalesce(h.title, '') + ' ' + coalesce(h.content, '') AS text
        ORDER BY h.full_id
        """
        result = graph.query(query)
        rows = [{"elementId": r["elementId"], "text": r["text"]} for r in result]

        logger.info(f"Found {len(rows)} HANG nodes without embeddings")

        if not rows:
            logger.info("No HANG nodes to process!")
            return 0

        # OpenAI 임베딩 모델 로드 (LAW_EMBEDDING_MODEL 사용!)
        embedding_model_name = os.getenv('LAW_EMBEDDING_MODEL', 'openai')
        logger.info(f"Loading embedding model: {embedding_model_name}")
        embeddings, dimension = load_embedding_model(embedding_model_name)
        logger.info(f"Embedding dimension: {dimension}")

        # 배치 처리 (개선된 버전 - 검증 및 재시도 포함)
        batch_size = 100
        total_to_process = len(rows)
        total_saved = 0
        batch_success_count = 0
        batch_partial_count = 0
        batch_fail_count = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(rows)-1)//batch_size + 1

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} nodes)...")

            # 임베딩 생성
            for row in batch:
                row['embedding'] = embeddings.embed_query(row['text'])

            # 저장 및 검증 (개선된 함수 사용)
            saved_in_batch = save_batch_with_verification(graph, batch)
            total_saved += saved_in_batch

            # 통계
            if saved_in_batch == len(batch):
                batch_success_count += 1
            elif saved_in_batch > 0:
                batch_partial_count += 1
            else:
                batch_fail_count += 1

            logger.info(f"  Progress: {total_saved}/{total_to_process} ({100*total_saved//total_to_process}%)")

        print("\n" + "=" * 70)
        print("임베딩 생성 완료!")
        print("=" * 70)
        print(f"  총 대상 노드: {total_to_process}")
        print(f"  성공적으로 저장: {total_saved}")
        print(f"  실패: {total_to_process - total_saved}")
        print(f"  임베딩 차원: {dimension}")
        print(f"  모델: {embedding_model_name} (via langchain)")
        print(f"\n배치 통계:")
        print(f"  완전 성공: {batch_success_count}")
        print(f"  부분 성공: {batch_partial_count}")
        print(f"  완전 실패: {batch_fail_count}")

        if total_saved == total_to_process:
            print("\n✅ 완료! 모든 노드 처리 성공")
        else:
            print(f"\n⚠️  경고! {total_to_process - total_saved}개 노드 처리 실패")
            print("다시 실행하면 실패한 것만 재처리됩니다.")

        return 0 if total_saved == total_to_process else 1

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
