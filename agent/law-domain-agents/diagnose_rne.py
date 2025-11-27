"""
RNE 진단 스크립트 - 왜 RNE expansion이 0개 결과를 반환하는지 분석
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    os.system('chcp 65001 > nul')

sys.path.insert(0, str(Path(__file__).parent / "shared"))

from shared.neo4j_client import get_neo4j_client
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Test seed node from our results
SEED_NODE_ID = "국토의 계획 및 이용에 관한 법률::제12조::제4항::제109조::2"
DOMAIN_ID = "domain_09b3af0d"

def diagnose_rne():
    print("="*70)
    print("RNE Diagnostic Script")
    print("="*70)

    neo4j_client = get_neo4j_client()
    session = neo4j_client.get_session()

    # Step 1: Check if seed node exists
    print(f"\n[1] Checking seed node: {SEED_NODE_ID[:50]}...")
    query1 = """
    MATCH (h:HANG {full_id: $seed_id})
    RETURN h.full_id, h.content IS NOT NULL as has_content, h.embedding IS NOT NULL as has_embedding
    """
    result = session.run(query1, {"seed_id": SEED_NODE_ID})
    record = result.single()
    if record:
        print(f"    ✓ Seed node found")
        print(f"    - Has content: {record['has_content']}")
        print(f"    - Has embedding: {record['has_embedding']}")
    else:
        print(f"    ✗ Seed node NOT found!")
        return

    # Step 2: Check JO connection
    print(f"\n[2] Checking JO connection...")
    query2 = """
    MATCH (seed:HANG {full_id: $seed_id})<-[:CONTAINS]-(jo:JO)
    RETURN jo.full_id as jo_id
    """
    result = session.run(query2, {"seed_id": SEED_NODE_ID})
    records = list(result)
    if records:
        jo_id = records[0]['jo_id']
        print(f"    ✓ Connected to JO: {jo_id}")
    else:
        print(f"    ✗ Not connected to any JO!")
        return

    # Step 3: Check neighbor HANG nodes
    print(f"\n[3] Checking neighbor HANG nodes...")
    query3 = """
    MATCH (seed:HANG {full_id: $seed_id})<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
    WHERE neighbor.full_id <> $seed_id
    RETURN neighbor.full_id as hang_id,
           neighbor.embedding IS NOT NULL as has_embedding,
           size(neighbor.embedding) as embedding_size
    LIMIT 10
    """
    result = session.run(query3, {"seed_id": SEED_NODE_ID})
    neighbors = list(result)

    if not neighbors:
        print(f"    ✗ No neighbor HANG nodes found!")
        print(f"    → The JO '{jo_id}' has no other HANG children")
        return

    print(f"    ✓ Found {len(neighbors)} neighbors:")
    for n in neighbors[:5]:
        print(f"      - {n['hang_id'][:60]}... (embedding: {n['has_embedding']}, size: {n['embedding_size']})")

    # Step 4: Get seed embedding and calculate similarities
    print(f"\n[4] Calculating similarities...")
    query4 = """
    MATCH (seed:HANG {full_id: $seed_id})
    RETURN seed.embedding as embedding
    """
    result = session.run(query4, {"seed_id": SEED_NODE_ID})
    seed_record = result.single()

    if not seed_record or not seed_record['embedding']:
        print(f"    ✗ Seed has no embedding!")
        return

    seed_emb = np.array(seed_record['embedding']).reshape(1, -1)
    print(f"    Seed embedding shape: {seed_emb.shape}")

    # Get neighbor embeddings and calculate similarities
    query5 = """
    MATCH (seed:HANG {full_id: $seed_id})<-[:CONTAINS]-(jo:JO)-[:CONTAINS]->(neighbor:HANG)
    WHERE neighbor.full_id <> $seed_id
      AND neighbor.embedding IS NOT NULL
    RETURN neighbor.full_id as hang_id, neighbor.embedding as embedding
    LIMIT 20
    """
    result = session.run(query5, {"seed_id": SEED_NODE_ID})
    neighbors_with_emb = list(result)

    if not neighbors_with_emb:
        print(f"    ✗ No neighbors have embeddings!")
        return

    print(f"    ✓ Calculating similarities for {len(neighbors_with_emb)} neighbors:")
    similarities = []
    for n in neighbors_with_emb:
        neighbor_emb = np.array(n['embedding']).reshape(1, -1)
        sim = cosine_similarity(seed_emb, neighbor_emb)[0][0]
        similarities.append((n['hang_id'], sim))

    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)

    print(f"\n    Top 10 similarities:")
    for hang_id, sim in similarities[:10]:
        threshold_status = "✓" if sim >= 0.65 else "✗"
        print(f"      {threshold_status} {sim:.4f} - {hang_id[:50]}...")

    # Summary
    print(f"\n{'='*70}")
    print("DIAGNOSIS SUMMARY")
    print(f"{'='*70}")
    print(f"Total neighbors with embeddings: {len(neighbors_with_emb)}")
    print(f"Max similarity: {max(s[1] for s in similarities):.4f}")
    print(f"Min similarity: {min(s[1] for s in similarities):.4f}")
    print(f"Above threshold 0.65: {sum(1 for s in similarities if s[1] >= 0.65)}")
    print(f"Above threshold 0.50: {sum(1 for s in similarities if s[1] >= 0.50)}")

    if max(s[1] for s in similarities) < 0.65:
        print(f"\n⚠️  ISSUE: All similarities below 0.65 threshold!")
        print(f"    Recommendation: Lower threshold to 0.5 or accept no RNE expansion")
    else:
        print(f"\n✓ Some nodes above threshold - RNE should work")

    session.close()

if __name__ == "__main__":
    diagnose_rne()
