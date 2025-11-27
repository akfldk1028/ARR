"""17조 직접 검색 및 부칙 필터링 테스트"""
import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("="*80)
print("1. 실제 17조 full_id 확인")
print("="*80)

# 실제 17조 찾기 (부칙 제외)
query1 = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "제17조"
  AND NOT h.full_id CONTAINS "제4절"
RETURN h.full_id as id, h.content as content, h.embedding IS NOT NULL as has_embedding
LIMIT 5
"""

results = neo4j.execute_query(query1, {})
print(f"\n실제 17조 발견: {len(results)}개")
for i, r in enumerate(results, 1):
    print(f"\n{i}. full_id: {r['id']}")
    print(f"   임베딩 존재: {r['has_embedding']}")
    print(f"   내용 (100자): {r['content'][:100]}")

print("\n" + "="*80)
print("2. 부칙(제4절) 통계")
print("="*80)

# 부칙 노드 개수 확인
query2 = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "제4절"
RETURN count(h) as total_bukchik
"""

result = neo4j.execute_query(query2, {})
print(f"\n부칙(제4절) 노드 총 개수: {result[0]['total_bukchik']}개")

# 전체 HANG 노드 개수
query3 = """
MATCH (h:HANG)
RETURN count(h) as total_hang
"""

result = neo4j.execute_query(query3, {})
print(f"전체 HANG 노드 개수: {result[0]['total_hang']}개")

print("\n" + "="*80)
print("3. 17조 관계 임베딩 확인")
print("="*80)

# 17조가 포함된 CONTAINS 관계 확인
query4 = """
MATCH (parent)-[r:CONTAINS]->(h:HANG)
WHERE h.full_id CONTAINS "제17조"
  AND NOT h.full_id CONTAINS "제4절"
RETURN
  h.full_id as hang_id,
  parent.full_id as parent_id,
  r.embedding IS NOT NULL as has_rel_embedding,
  r.embedding_text as rel_text
LIMIT 3
"""

results = neo4j.execute_query(query4, {})
print(f"\n17조 CONTAINS 관계: {len(results)}개 발견")
for i, r in enumerate(results, 1):
    print(f"\n{i}. HANG: {r['hang_id']}")
    print(f"   부모: {r['parent_id']}")
    print(f"   관계 임베딩: {r['has_rel_embedding']}")
    if r['rel_text']:
        print(f"   임베딩 텍스트 (100자): {r['rel_text'][:100]}")

print("\n" + "="*80)
print("4. full_id 구조 분석")
print("="*80)

# 전체 법률의 full_id 패턴 확인
query5 = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "국토의 계획 및 이용에 관한 법률"
WITH h.full_id as id
WITH split(id, '::') as parts
RETURN
  size(parts) as depth,
  count(*) as count,
  collect(parts)[0..3] as samples
ORDER BY depth
"""

results = neo4j.execute_query(query5, {})
print("\nfull_id 깊이 분포:")
for r in results:
    print(f"  깊이 {r['depth']}: {r['count']}개 노드")
    if r['samples']:
        print(f"    예시: {r['samples'][0]}")

neo4j.disconnect()

print("\n" + "="*80)
print("분석 완료")
print("="*80)
