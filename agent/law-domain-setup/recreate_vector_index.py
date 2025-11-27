"""
Recreate Neo4j Vector Index for 3072-dim embeddings

After updating HANG embeddings from KR-SBERT (768-dim) to OpenAI (3072-dim),
the vector index must be recreated to match the new dimensions.
"""

import sys
from pathlib import Path

agent_root = Path(__file__).parent.parent
sys.path.insert(0, str(agent_root / "law-domain-agents" / "shared"))

from neo4j_client import get_neo4j_client

def main():
    print("=" * 80)
    print("Recreating Neo4j Vector Index for 3072-dim embeddings")
    print("=" * 80)

    client = get_neo4j_client()
    session = client.get_session()

    # Step 1: Drop old index
    print("\n[1/3] Dropping old 768-dim vector index...")
    try:
        session.run("DROP INDEX hang_embedding_index IF EXISTS")
        print("  > Old index dropped")
    except Exception as e:
        print(f"  ! Warning: {e}")

    # Step 2: Create new 3072-dim index
    print("\n[2/3] Creating new 3072-dim vector index...")
    create_index_query = """
    CREATE VECTOR INDEX hang_embedding_index IF NOT EXISTS
    FOR (h:HANG) ON (h.embedding)
    OPTIONS {
        indexConfig: {
            `vector.dimensions`: 3072,
            `vector.similarity_function`: 'cosine'
        }
    }
    """

    try:
        session.run(create_index_query)
        print("  > New 3072-dim index created")
    except Exception as e:
        print(f"  ! Error: {e}")
        session.close()
        return

    # Step 3: Verify index
    print("\n[3/3] Verifying index creation...")
    result = session.run("SHOW INDEXES")

    for r in result:
        if 'hang' in r['name']:
            print(f"  > {r['name']}: {r['type']} ({r['state']})")

    session.close()

    print("\n" + "=" * 80)
    print("Index recreation complete!")
    print("=" * 80)
    print("\nNote: Index may take a few moments to populate.")
    print("Check status with: SHOW INDEXES")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
