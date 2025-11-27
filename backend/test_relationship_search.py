"""관계 임베딩 검색 테스트"""
import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService
from sentence_transformers import SentenceTransformer
import openai

# OpenAI API 설정
openai.api_key = os.getenv('OPENAI_API_KEY')

neo4j = Neo4jService()
neo4j.connect()

# 테스트 쿼리
test_query = "국토계획법 17조"

print("="*80)
print(f"테스트 쿼리: {test_query}")
print("="*80)

# OpenAI 임베딩 생성 (3072-dim)
print("\n[1] OpenAI 임베딩 생성 중...")
response = openai.embeddings.create(
    model="text-embedding-3-large",
    input=test_query
)
openai_embedding = response.data[0].embedding
print(f"   OpenAI embedding created (dim: {len(openai_embedding)})")

# 관계 검색 쿼리 (실제 DomainAgent와 동일)
query = """
CALL db.index.vector.queryRelationships(
    'contains_embedding',
    $limit_multiplier,
    $query_embedding
) YIELD relationship, score
MATCH (from)-[relationship]->(to:HANG)
WHERE score >= 0.65
RETURN
    from.full_id AS from_id,
    to.full_id AS to_id,
    to.content AS content,
    score AS similarity
ORDER BY similarity DESC
LIMIT $limit
"""

print("\n[2] 관계 검색 실행 (score >= 0.65)...")
results = neo4j.execute_query(query, {
    'query_embedding': openai_embedding,
    'limit': 10,
    'limit_multiplier': 30
})

print(f"   결과: {len(results)}개")
if results:
    for i, r in enumerate(results[:5], 1):
        print(f"\n   {i}. Score: {r['similarity']:.4f}")
        print(f"      From: {r['from_id']}")
        print(f"      To: {r['to_id']}")
        print(f"      Content (50자): {r['content'][:50]}")
else:
    print("   [WARNING] No results!")

# 더 낮은 threshold로 테스트
print("\n" + "="*80)
print("[3] 낮은 threshold 테스트 (score >= 0.5)...")
print("="*80)

query_low = """
CALL db.index.vector.queryRelationships(
    'contains_embedding',
    $limit_multiplier,
    $query_embedding
) YIELD relationship, score
MATCH (from)-[relationship]->(to:HANG)
WHERE score >= 0.5
RETURN
    from.full_id AS from_id,
    to.full_id AS to_id,
    to.content AS content,
    score AS similarity
ORDER BY similarity DESC
LIMIT $limit
"""

results_low = neo4j.execute_query(query_low, {
    'query_embedding': openai_embedding,
    'limit': 10,
    'limit_multiplier': 30
})

print(f"\n결과: {len(results_low)}개")
if results_low:
    for i, r in enumerate(results_low[:5], 1):
        print(f"\n{i}. Score: {r['similarity']:.4f}")
        print(f"   From: {r['from_id']}")
        print(f"   To: {r['to_id']}")
        print(f"   Content (50자): {r['content'][:50]}")

        # 17조 포함 체크
        if '제17조' in r['to_id']:
            print(f"   [FOUND] Article 17!")
        if '제4절' in r['to_id']:
            print(f"   [WARNING] Bukchik (Section 4)")
else:
    print("[WARNING] Still no results!")

# 임베딩 존재 여부 확인
print("\n" + "="*80)
print("[4] CONTAINS 관계 임베딩 통계")
print("="*80)

stats_query = """
MATCH (jo:JO)-[r:CONTAINS]->(h:HANG)
RETURN
    count(r) as total_contains,
    sum(CASE WHEN r.embedding IS NOT NULL THEN 1 ELSE 0 END) as has_embedding,
    sum(CASE WHEN r.embedding IS NULL THEN 1 ELSE 0 END) as no_embedding
"""

stats = neo4j.execute_query(stats_query, {})
if stats:
    s = stats[0]
    print(f"\n총 CONTAINS 관계: {s['total_contains']}개")
    print(f"임베딩 있음: {s['has_embedding']}개")
    print(f"임베딩 없음: {s['no_embedding']}개")

    if s['has_embedding'] > 0:
        pct = (s['has_embedding'] / s['total_contains']) * 100
        print(f"임베딩 비율: {pct:.1f}%")

neo4j.disconnect()

print("\n" + "="*80)
print("테스트 완료")
print("="*80)
