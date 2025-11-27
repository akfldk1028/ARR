"""
실제 Neo4j 구조 확인
관계 이름이 뭔지 확인합니다
"""
import sys
import io
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("=" * 70)
print("실제 Neo4j 구조 확인")
print("=" * 70)

# 1. 노드 타입 확인
query1 = """
MATCH (n)
RETURN DISTINCT labels(n) as node_type, count(*) as count
ORDER BY count DESC
"""

with neo4j.driver.session() as session:
    result = session.run(query1)
    records = list(result)

    print("\n[1] 노드 타입")
    for r in records:
        print(f"    {r['node_type']}: {r['count']}개")

# 2. 관계 타입 확인
query2 = """
MATCH ()-[r]->()
RETURN DISTINCT type(r) as rel_type, count(*) as count
ORDER BY count DESC
"""

with neo4j.driver.session() as session:
    result = session.run(query2)
    records = list(result)

    print("\n[2] 관계 타입")
    for r in records:
        print(f"    {r['rel_type']}: {r['count']}개")

# 3. 실제 계층 구조 샘플 (관계 이름 모름, 그냥 다 찾기)
query3 = """
MATCH (parent)-[r]->(child)
WHERE 'JO' IN labels(parent) OR 'HANG' IN labels(parent)
RETURN
  labels(parent) as parent_label,
  type(r) as rel_type,
  labels(child) as child_label,
  parent.number as parent_num,
  child.number as child_num
LIMIT 10
"""

with neo4j.driver.session() as session:
    result = session.run(query3)
    records = list(result)

    print("\n[3] 실제 계층 구조 샘플")
    if records:
        for r in records:
            print(f"    {r['parent_label']}({r['parent_num']}) -[{r['rel_type']}]-> {r['child_label']}({r['child_num']})")
    else:
        print("    ⚠️ 계층 관계가 없습니다!")

# 4. HANG 샘플 확인
query4 = """
MATCH (h:HANG)
RETURN h.number, h.full_id, h.embedding IS NOT NULL as has_emb
LIMIT 3
"""

with neo4j.driver.session() as session:
    result = session.run(query4)
    records = list(result)

    print("\n[4] HANG 샘플")
    for r in records:
        print(f"    {r['h.number']}: {r['h.full_id']} (임베딩: {r['has_emb']})")

print("\n" + "=" * 70)
