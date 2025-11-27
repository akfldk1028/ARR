"""17jo Domain Membership Test"""
import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService
import json

neo4j = Neo4jService()
neo4j.connect()

print("="*80)
print("1. Article 17 Domain Membership")
print("="*80)

# 17조가 속한 도메인
q1 = """
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
WHERE h.full_id CONTAINS "제17조"
  AND NOT h.full_id CONTAINS "제4절"
RETURN DISTINCT d.domain_id as id, d.domain_name as name, count(h) as hang_count
"""

results = neo4j.execute_query(q1, {})
print(f"\nArticle 17 belongs to {len(results)} domain(s):")
for r in results:
    print(f"  Domain: {r['name']}")
    print(f"  ID: {r['id']}")
    print(f"  17jo nodes: {r['hang_count']}")
    article_17_domain_id = r['id']
    article_17_domain_name = r['name']

print("\n" + "="*80)
print("2. Search Query Routing Test")
print("="*80)

# 검색 쿼리 "국토계획법 17조"가 어느 도메인으로 라우팅되는지 시뮬레이션
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
query = "국토계획법 17조"
query_embedding = model.encode([query])[0].tolist()

print(f"\nQuery: {query}")
print(f"Query embedding dim: {len(query_embedding)}")

# 모든 도메인의 centroid와 유사도 계산
q2 = """
MATCH (d:Domain)
WHERE d.centroid_embedding IS NOT NULL
RETURN d.domain_id as id,
       d.domain_name as name,
       d.centroid_embedding as centroid
"""

domains = neo4j.execute_query(q2, {})
print(f"\nTotal domains: {len(domains)}")

# 코사인 유사도 계산
import numpy as np

similarities = []
for d in domains:
    centroid = d['centroid']
    if centroid and len(centroid) == len(query_embedding):
        # Cosine similarity
        sim = np.dot(query_embedding, centroid) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(centroid)
        )
        similarities.append({
            'domain_id': d['id'],
            'domain_name': d['name'],
            'similarity': sim
        })

# 정렬
similarities.sort(key=lambda x: x['similarity'], reverse=True)

print("\nRouting similarity scores:")
for i, s in enumerate(similarities[:5], 1):
    marker = " <- ROUTED HERE" if i == 1 else ""
    print(f"  {i}. {s['domain_name']}: {s['similarity']:.4f}{marker}")

routed_domain_id = similarities[0]['domain_id']
routed_domain_name = similarities[0]['domain_name']

print("\n" + "="*80)
print("3. Problem Analysis")
print("="*80)

print(f"\nArticle 17 is in: {article_17_domain_name} ({article_17_domain_id})")
print(f"Query routed to: {routed_domain_name} ({routed_domain_id})")

if article_17_domain_id == routed_domain_id:
    print("\n✓ MATCH! Query routed to correct domain.")
else:
    print("\n✗ MISMATCH! This is the problem!")
    print(f"  Article 17 is in Domain A: {article_17_domain_name}")
    print(f"  But query routed to Domain B: {routed_domain_name}")
    print(f"  So Article 17 is filtered out during search.")

# 라우팅된 도메인의 17조 포함 여부 확인
q3 = """
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain {domain_id: $domain_id})
WHERE h.full_id CONTAINS "제17조"
  AND NOT h.full_id CONTAINS "제4절"
RETURN count(h) as count
"""

routed_domain_has_17 = neo4j.execute_query(q3, {'domain_id': routed_domain_id})[0]['count']
print(f"\nRouted domain has {routed_domain_has_17} Article 17 nodes.")

if routed_domain_has_17 == 0:
    print("✗ Routed domain has NO Article 17 nodes!")

neo4j.disconnect()

print("\n" + "="*80)
print("Test Complete")
print("="*80)
