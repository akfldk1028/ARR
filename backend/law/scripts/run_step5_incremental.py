"""
Step5 Incremental: Generate embeddings for CONTAINS relationships that don't have them yet.

Targets only relationships where embedding IS NULL.
Uses same model (text-embedding-3-large, 3072-dim) as the original step5 pipeline.

Usage:
    LAW_NEO4J_PASSWORD=11111111 C:/Python313/python law/scripts/run_step5_incremental.py
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

NEO4J_URI = os.environ.get('LAW_NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.environ.get('LAW_NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.environ.get('LAW_NEO4J_PASSWORD', 'demodemo')

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
BATCH_SIZE = 50  # Smaller batches for relationship context (longer texts)


def get_rels_without_embeddings(driver):
    """Get CONTAINS relationships without embeddings, with context text."""
    with driver.session() as session:
        result = session.run("""
            MATCH (parent)-[r:CONTAINS]->(child)
            WHERE r.embedding IS NULL
            RETURN elementId(r) AS relId,
                   coalesce(parent.title, '') + ' ' + coalesce(parent.content, '') AS parent_text,
                   coalesce(child.title, '') + ' ' + coalesce(child.content, '') AS child_text,
                   labels(parent)[0] AS parent_label,
                   labels(child)[0] AS child_label
            ORDER BY relId
        """)
        rows = []
        for r in result:
            # Build context: "[ParentLabel→ChildLabel] parent_text | child_text"
            context = f"[{r['parent_label']}→{r['child_label']}] {r['parent_text'].strip()} | {r['child_text'].strip()}"
            # Truncate to ~2000 chars to stay within token limits
            if len(context) > 2000:
                context = context[:2000]
            rows.append({
                'relId': r['relId'],
                'context': context
            })
        return rows


def generate_embeddings(client, texts):
    """Generate OpenAI embeddings for a batch of texts."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def save_rel_embeddings_batch(driver, batch):
    """Save embeddings to CONTAINS relationships."""
    with driver.session() as session:
        for row in batch:
            session.run("""
                MATCH ()-[r]->()
                WHERE elementId(r) = $relId
                CALL db.create.setRelationshipVectorProperty(r, "embedding", $embedding)
            """, relId=row['relId'], embedding=row['embedding'])


def main():
    print("\n" + "=" * 70)
    print("Step5 Incremental: CONTAINS relationship embeddings")
    print(f"  Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM}-dim)")
    print(f"  Neo4j: {NEO4J_URI}")
    print("=" * 70)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        logger.info("Neo4j connected")
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        return 1

    client = OpenAI()

    # Get current stats
    with driver.session() as s:
        total = s.run("MATCH ()-[r:CONTAINS]->() RETURN count(r) as c").single()['c']
        with_emb = s.run("MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NOT NULL RETURN count(r) as c").single()['c']
    logger.info(f"CONTAINS: {total} total, {with_emb} with embeddings, {total - with_emb} without")

    # Get relationships needing embeddings
    rels = get_rels_without_embeddings(driver)
    if not rels:
        print("\nAll CONTAINS relationships already have embeddings!")
        driver.close()
        return 0

    logger.info(f"Processing {len(rels)} relationships without embeddings...")

    est_tokens = len(rels) * 200  # avg ~200 tokens per context
    est_cost = est_tokens / 1_000_000 * 0.13
    logger.info(f"Estimated cost: ~${est_cost:.2f} ({est_tokens:,} tokens)")

    total_saved = 0
    start_time = time.time()

    for i in range(0, len(rels), BATCH_SIZE):
        batch_rels = rels[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(rels) - 1) // BATCH_SIZE + 1

        texts = [r['context'] for r in batch_rels]

        try:
            embeddings = generate_embeddings(client, texts)
        except Exception as e:
            logger.error(f"Batch {batch_num}: OpenAI embedding failed: {e}")
            time.sleep(5)
            try:
                embeddings = generate_embeddings(client, texts)
            except Exception as e2:
                logger.error(f"Batch {batch_num}: Retry also failed: {e2}")
                continue

        batch_data = [
            {'relId': r['relId'], 'embedding': emb}
            for r, emb in zip(batch_rels, embeddings)
        ]

        try:
            save_rel_embeddings_batch(driver, batch_data)
            total_saved += len(batch_data)
        except Exception as e:
            logger.error(f"Batch {batch_num}: Neo4j save failed: {e}")
            # Try one at a time
            for row in batch_data:
                try:
                    save_rel_embeddings_batch(driver, [row])
                    total_saved += 1
                except Exception:
                    pass

        elapsed = time.time() - start_time
        rate = total_saved / elapsed if elapsed > 0 else 0
        logger.info(f"Batch {batch_num}/{total_batches}: {len(batch_data)} saved | "
                     f"Total: {total_saved}/{len(rels)} ({100*total_saved//len(rels)}%) | "
                     f"{rate:.1f} rels/sec")

    elapsed = time.time() - start_time
    driver.close()

    print("\n" + "=" * 70)
    print("Relationship embedding complete!")
    print(f"  Target: {len(rels)} relationships")
    print(f"  Success: {total_saved}")
    print(f"  Failed: {len(rels) - total_saved}")
    print(f"  Time: {elapsed:.1f}s")
    print("=" * 70)

    return 0 if total_saved == len(rels) else 1


if __name__ == "__main__":
    sys.exit(main())
