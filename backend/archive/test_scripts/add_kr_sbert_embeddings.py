"""
HANG 노드에 KR-SBERT 임베딩 추가 (MAS 호환)

AgentManager가 사용하는 정확한 모델: snunlp/KR-SBERT-V40K-klueNLI-augSTS (768-dim)
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from sentence_transformers import SentenceTransformer
from graph_db.services.neo4j_service import Neo4jService

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    print("\n" + "=" * 70)
    print("HANG Node KR-SBERT Embedding Generation (768-dim)")
    print("=" * 70)

    try:
        # Neo4j 연결
        neo4j = Neo4jService()
        neo4j.connect()

        # HANG 노드 가져오기
        logger.info("Fetching HANG nodes...")
        query = """
        MATCH (h:HANG)
        WHERE h.embedding IS NULL
        RETURN h.full_id AS hang_id, h.content AS content
        ORDER BY h.full_id
        """
        results = neo4j.execute_query(query, {})

        hang_ids = [r['hang_id'] for r in results]
        texts = [r['content'] or '' for r in results]

        logger.info(f"Found {len(hang_ids)} HANG nodes without embeddings")

        if not hang_ids:
            logger.info("No HANG nodes to process!")
            return 0

        # KR-SBERT 모델 로드 (AgentManager와 동일)
        logger.info("Loading KR-SBERT model: snunlp/KR-SBERT-V40K-klueNLI-augSTS...")
        model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
        logger.info("Model loaded successfully!")

        # 배치 처리
        batch_size = 100
        total_processed = 0

        for i in range(0, len(hang_ids), batch_size):
            batch_ids = hang_ids[i:i+batch_size]
            batch_texts = texts[i:i+batch_size]

            logger.info(f"Processing batch {i//batch_size + 1}/{(len(hang_ids)-1)//batch_size + 1} ({len(batch_ids)} nodes)...")

            # 임베딩 생성
            embeddings = model.encode(batch_texts, show_progress_bar=False)

            # Neo4j에 저장
            for hang_id, embedding in zip(batch_ids, embeddings):
                update_query = """
                MATCH (h:HANG {full_id: $hang_id})
                SET h.embedding = $embedding
                """
                neo4j.execute_query(update_query, {
                    'hang_id': hang_id,
                    'embedding': embedding.tolist()
                })

            total_processed += len(batch_ids)
            logger.info(f"  Progress: {total_processed}/{len(hang_ids)} ({100*total_processed//len(hang_ids)}%)")

        print("\n" + "=" * 70)
        print("Embedding Generation Complete!")
        print("=" * 70)
        print(f"  Processed HANG nodes: {total_processed}")
        print(f"  Embedding dimension: 768")
        print(f"  Model: snunlp/KR-SBERT-V40K-klueNLI-augSTS")
        print("\nSuccess! MAS-compatible embeddings created.")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
