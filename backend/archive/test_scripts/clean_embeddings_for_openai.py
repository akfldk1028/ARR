"""
기존 임베딩 삭제 및 벡터 인덱스 삭제
OpenAI 임베딩으로 전환하기 전 준비 작업
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(uri, auth=(user, password))

print("=" * 70)
print("CLEANING EMBEDDINGS FOR OPENAI TRANSITION")
print("=" * 70)

with driver.session() as session:
    # 1. 기존 임베딩 확인
    print("\n[1] Checking existing embeddings...")
    result = session.run("""
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN count(h) as count, size(h.embedding) as dimension
        LIMIT 1
    """)
    record = result.single()
    if record and record['count'] > 0:
        print(f"  Current: {record['count']} nodes with {record['dimension']} dimensions")
    else:
        print("  No embeddings found")

    # 2. 벡터 인덱스 삭제
    print("\n[2] Dropping vector index...")
    try:
        session.run("DROP INDEX hang_embedding_index IF EXISTS")
        print("  [OK] Vector index dropped")
    except Exception as e:
        print(f"  [INFO] No index to drop or error: {e}")

    # 3. 기존 임베딩 삭제
    print("\n[3] Deleting existing embeddings...")
    result = session.run("""
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        SET h.embedding = null
        RETURN count(h) as deleted_count
    """)
    deleted = result.single()['deleted_count']
    print(f"  [OK] Deleted embeddings from {deleted} nodes")

    # 4. 검증
    print("\n[4] Verifying cleanup...")
    result = session.run("""
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN count(h) as remaining
    """)
    remaining = result.single()['remaining']
    print(f"  Remaining embeddings: {remaining}")

driver.close()

print("\n" + "=" * 70)
print("CLEANUP COMPLETE!")
print("=" * 70)
print("Next: Run add_embeddings_v2.py to add OpenAI embeddings")
print("  Expected: 1536 dimensions (OpenAI text-embedding-3-large)")
print("  Cost: ~$0.50-1.00 for 1,586 HANG nodes")
