"""
Phase 1.2: JO 노드에 임베딩 추가

Design Plan Option C: Title + HANG summary
- JO with HANG children: Title + concatenated HANG contents (max 500 chars)
- JO without HANG children: Title only (fallback)

기존 HANG 임베딩 시스템과 동일한 모델 사용 (consistency)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for Django import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import django
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


def create_jo_embedding_text(jo_record):
    """
    Option C: Title + HANG summary

    Args:
        jo_record: {
            'title': str,
            'hang_contents': list[str] or None
        }

    Returns:
        str: Text for embedding
    """
    title = jo_record.get('title', '')
    hang_contents = jo_record.get('hang_contents', [])

    # JO without HANG children: Title only
    if not hang_contents:
        return title

    # JO with HANG children: Title + summary
    all_hang_text = " ".join(hang_contents)

    # Summarize if too long (>500 chars)
    max_length = 500
    if len(all_hang_text) > max_length:
        summary = all_hang_text[:max_length] + "..."
    else:
        summary = all_hang_text

    return f"{title}. {summary}"


def fetch_jo_nodes_with_hang_content(graph):
    """
    JO 노드와 HANG 자식 노드의 content를 함께 가져오기

    Returns:
        list: [{'elementId': str, 'full_id': str, 'title': str, 'hang_contents': list[str]}]
    """
    query = """
    MATCH (jo:JO)
    WHERE jo.embedding IS NULL

    OPTIONAL MATCH (jo)-[:CONTAINS]->(hang:HANG)

    WITH jo, collect(hang.content) as hang_contents

    RETURN elementId(jo) AS elementId,
           jo.full_id AS full_id,
           coalesce(jo.title, jo.unit_number, '') AS title,
           CASE
               WHEN size(hang_contents) = 0 THEN null
               ELSE hang_contents
           END AS hang_contents
    ORDER BY jo.full_id
    """

    result = graph.query(query)

    rows = []
    for r in result:
        rows.append({
            'elementId': r['elementId'],
            'full_id': r['full_id'],
            'title': r['title'],
            'hang_contents': r['hang_contents']
        })

    return rows


def main():
    # Open output file for logging
    output_path = Path(__file__).parent / "jo_embedding_log.txt"

    with open(output_path, 'w', encoding='utf-8') as log_file:
        def log(msg):
            log_file.write(msg + '\n')
            log_file.flush()
            print(msg)

        log("\n" + "=" * 70)
        log("Phase 1.2: JO 노드 임베딩 생성")
        log("Strategy: Option C (Title + HANG summary)")
        log("=" * 70)

        try:
            # Neo4j 연결
            uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
            user = os.getenv('NEO4J_USER', 'neo4j')
            password = os.getenv('NEO4J_PASSWORD', '11111111')
            database = os.getenv('NEO4J_DATABASE', 'neo4j')

            logger.info(f"Connecting to Neo4j: {uri}")
            graph = Neo4jGraph(url=uri, username=user, password=password, database=database)

            # JO 노드 가져오기 (HANG content 포함)
            logger.info("Fetching JO nodes with HANG content...")
            rows = fetch_jo_nodes_with_hang_content(graph)

            logger.info(f"Found {len(rows)} JO nodes without embeddings")

            if not rows:
                log("No JO nodes to process!")
                return 0

            # 통계 수집
            jos_with_hang = sum(1 for r in rows if r['hang_contents'])
            jos_without_hang = len(rows) - jos_with_hang

            log(f"\nStatistics:")
            log(f"  Total JO nodes: {len(rows)}")
            log(f"  JO with HANG children: {jos_with_hang}")
            log(f"  JO without HANG children: {jos_without_hang} (will use title only)")

            # Sample preview
            log(f"\nSample JO nodes (first 3):")
            for i, row in enumerate(rows[:3], 1):
                text = create_jo_embedding_text(row)
                has_hang = "YES" if row['hang_contents'] else "NO"
                log(f"\n{i}. {row['full_id']}")
                log(f"   Title: {row['title']}")
                log(f"   Has HANG: {has_hang}")
                log(f"   Embedding text: {text[:100]}...")

            # 임베딩 모델 로드 (HANG과 동일한 모델 사용)
            embedding_model_name = os.getenv('LAW_EMBEDDING_MODEL', 'openai')
            logger.info(f"Loading embedding model: {embedding_model_name}")
            embeddings, dimension = load_embedding_model(embedding_model_name)
            logger.info(f"Embedding dimension: {dimension}")

            log(f"\nUsing embedding model: {embedding_model_name}")
            log(f"Embedding dimension: {dimension}")

            # 배치 처리
            batch_size = 100
            total_to_process = len(rows)
            total_saved = 0
            batch_success_count = 0
            batch_partial_count = 0
            batch_fail_count = 0

            log(f"\nProcessing {total_to_process} JO nodes in batches of {batch_size}...")

            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                batch_num = i//batch_size + 1
                total_batches = (len(rows)-1)//batch_size + 1

                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} nodes)...")

                # 임베딩 텍스트 생성 및 임베딩
                batch_data = []
                for row in batch:
                    text = create_jo_embedding_text(row)
                    embedding = embeddings.embed_query(text)
                    batch_data.append({
                        'elementId': row['elementId'],
                        'embedding': embedding
                    })

                # 저장 및 검증
                saved_in_batch = save_batch_with_verification(graph, batch_data)
                total_saved += saved_in_batch

                # 통계
                if saved_in_batch == len(batch):
                    batch_success_count += 1
                elif saved_in_batch > 0:
                    batch_partial_count += 1
                else:
                    batch_fail_count += 1

                progress_pct = 100 * total_saved // total_to_process
                logger.info(f"  Progress: {total_saved}/{total_to_process} ({progress_pct}%)")

            log("\n" + "=" * 70)
            log("JO 임베딩 생성 완료!")
            log("=" * 70)
            log(f"  총 대상 노드: {total_to_process}")
            log(f"  성공적으로 저장: {total_saved}")
            log(f"  실패: {total_to_process - total_saved}")
            log(f"  임베딩 차원: {dimension}")
            log("")
            log(f"Batch Statistics:")
            log(f"  Total batches: {batch_success_count + batch_partial_count + batch_fail_count}")
            log(f"  Full success: {batch_success_count}")
            log(f"  Partial success: {batch_partial_count}")
            log(f"  Failed: {batch_fail_count}")
            log("")
            log(f"Results saved to: {output_path}")
            log("=" * 70)

            return 0

        except Exception as e:
            logger.error(f"Error during JO embedding generation: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
