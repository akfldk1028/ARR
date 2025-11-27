"""
누락된 69개 임베딩 노드 분석
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("\n=== 임베딩 누락 노드 분석 ===\n")

# 누락된 노드들의 조 분석
query = "MATCH (h:HANG) WHERE h.embedding IS NULL RETURN h.full_id as id"
all_missing = neo4j.execute_query(query, {})

jo_counts = {}
for r in all_missing:
    if '::' in r['id']:
        parts = r['id'].split('::')
        if len(parts) >= 2:
            jo = parts[1]
            jo_counts[jo] = jo_counts.get(jo, 0) + 1

print(f"총 누락: {len(all_missing)}개\n")
print("조별 누락 통계:")
for jo, cnt in sorted(jo_counts.items(), key=lambda x: -x[1]):
    print(f"  {jo}: {cnt}개")

# add_hang_embeddings.py 코드 확인
print("\n=== 원인 추정 ===")
print("로그: 'Progress: 1477/1477 (100%)'")
print("Neo4j: 1408개만 저장")
print(f"차이: {len(all_missing)}개")
print("\n가능한 원인:")
print("1. 배치 커밋 실패")
print("2. 특정 조의 내용이 너무 길어서 API 호출 실패")
print("3. Neo4j 트랜잭션 타임아웃")
