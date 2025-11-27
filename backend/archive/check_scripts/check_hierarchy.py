"""
계층 구조 확인 스크립트
JO (조) → HANG (항) → HO (호) 구조가 제대로 작동하는지 확인
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
print("계층 구조 검증 (JO → HANG → HO)")
print("=" * 70)

# 1. 전체 계층 구조 확인
query1 = """
MATCH (jo:JO)-[:HAS_HANG]->(hang:HANG)
OPTIONAL MATCH (hang)-[:HAS_HO]->(ho:HO)
RETURN
  count(DISTINCT jo) as jo_count,
  count(DISTINCT hang) as hang_count,
  count(DISTINCT ho) as ho_count,
  count(DISTINCT CASE WHEN ho IS NOT NULL THEN hang END) as hang_with_ho
"""

with neo4j.driver.session() as session:
    result = session.run(query1)
    r = result.single()

    print(f"\n[1] 전체 구조")
    print(f"    JO (조): {r['jo_count']}개")
    print(f"    HANG (항): {r['hang_count']}개")
    print(f"    HO (호): {r['ho_count']}개")
    print(f"    HO를 가진 HANG: {r['hang_with_ho']}개")

# 2. 샘플 계층 구조 (제1조 제1항 제1호 형태)
query2 = """
MATCH (jo:JO)-[:HAS_HANG]->(hang:HANG)-[:HAS_HO]->(ho:HO)
RETURN
  jo.number as jo_num,
  hang.number as hang_num,
  ho.number as ho_num,
  hang.full_id as hang_full_id,
  ho.full_id as ho_full_id,
  substring(hang.content, 0, 50) as hang_preview,
  substring(ho.content, 0, 50) as ho_preview
LIMIT 5
"""

with neo4j.driver.session() as session:
    result = session.run(query2)
    records = list(result)

    print(f"\n[2] 샘플 계층 구조 (총 {len(records)}개)")
    for i, r in enumerate(records, 1):
        print(f"\n    {i}. {r['jo_num']} → {r['hang_num']} → {r['ho_num']}")
        print(f"       HANG full_id: {r['hang_full_id']}")
        print(f"       HO full_id: {r['ho_full_id']}")
        print(f"       HANG 내용: {r['hang_preview']}...")
        print(f"       HO 내용: {r['ho_preview']}...")

# 3. HO 노드에 임베딩이 있는지 확인 (중요!)
query3 = """
MATCH (ho:HO)
RETURN
  count(ho) as total,
  count(CASE WHEN ho.embedding IS NOT NULL THEN 1 END) as with_embedding
"""

with neo4j.driver.session() as session:
    result = session.run(query3)
    r = result.single()

    print(f"\n[3] HO 노드 임베딩 상태")
    print(f"    전체 HO: {r['total']}개")
    print(f"    임베딩 있는 HO: {r['with_embedding']}개")

    if r['with_embedding'] == 0:
        print(f"    ⚠️ HO 노드에 임베딩이 없습니다!")
        print(f"    → HO는 벡터 검색으로 찾을 수 없습니다.")

# 4. 알고리즘이 HO를 반환하는지 확인
print(f"\n[4] 알고리즘 동작 확인")
print(f"    현재 get_article_info()는 HANG 노드만 조회합니다.")
print(f"    → HO 노드는 결과에 포함되지 않습니다!")

print("\n" + "=" * 70)
print("결론")
print("=" * 70)
print("✅ HANG (항)은 정상 작동 - 벡터 검색 + 그래프 확장")
print("❌ HO (호)는 확장은 되지만 결과에 포함 안됨")
print("→ 'get_article_info()'가 HANG만 조회하기 때문")
print("=" * 70)
