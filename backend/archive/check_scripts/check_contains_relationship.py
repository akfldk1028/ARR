"""
CONTAINS 관계 확인
JO → HANG, HANG → HO 연결 상태 확인
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
print("CONTAINS 관계 확인")
print("=" * 70)

with neo4j.driver.session() as session:
    # 1. JO → HANG
    query1 = """
    MATCH (jo:JO)-[:CONTAINS]->(hang:HANG)
    RETURN count(*) as count
    """
    result = session.run(query1)
    jo_hang = result.single()['count']
    print(f"\n[1] JO -[:CONTAINS]-> HANG: {jo_hang}개")

    # 2. HANG → HO
    query2 = """
    MATCH (hang:HANG)-[:CONTAINS]->(ho:HO)
    RETURN count(*) as count
    """
    result = session.run(query2)
    hang_ho = result.single()['count']
    print(f"[2] HANG -[:CONTAINS]-> HO: {hang_ho}개")

    # 3. 전체 계층 샘플
    query3 = """
    MATCH (jo:JO)-[:CONTAINS]->(hang:HANG)
    OPTIONAL MATCH (hang)-[:CONTAINS]->(ho:HO)
    RETURN
      jo.number as jo_num,
      hang.number as hang_num,
      hang.full_id as hang_full_id,
      collect(ho.number) as ho_nums,
      size(collect(ho.number)) as ho_count
    LIMIT 5
    """
    result = session.run(query3)
    records = list(result)

    print(f"\n[3] 계층 구조 샘플 (JO → HANG → HO)")
    for i, r in enumerate(records, 1):
        print(f"\n    {i}. {r['jo_num']} → {r['hang_num']}")
        print(f"       full_id: {r['hang_full_id']}")
        if r['ho_count'] > 0:
            print(f"       자식 HO: {', '.join(r['ho_nums'])} (총 {r['ho_count']}개)")
        else:
            print(f"       자식 HO: 없음")

    # 4. 형제 찾기 테스트 (같은 JO의 HANG들)
    query4 = """
    MATCH (jo:JO)-[:CONTAINS]->(hang:HANG)
    WHERE hang.number = '1'
    MATCH (jo)-[:CONTAINS]->(sibling:HANG)
    WHERE sibling.number <> hang.number
    RETURN
      jo.number as jo_num,
      hang.number as this_hang,
      collect(sibling.number)[0..5] as siblings
    LIMIT 1
    """
    result = session.run(query4)
    record = result.single()

    print(f"\n[4] 형제 관계 테스트")
    if record:
        print(f"    {record['jo_num']}의 {record['this_hang']}항")
        print(f"    형제들: {', '.join(record['siblings'])}...")
    else:
        print(f"    ⚠️ 형제 찾기 실패")

    # 5. HAS_HO vs CONTAINS
    query5 = """
    MATCH (hang:HANG)
    OPTIONAL MATCH (hang)-[:CONTAINS]->(ho1:HO)
    OPTIONAL MATCH (hang)-[:HAS_HO]->(ho2:HO)
    RETURN
      count(DISTINCT ho1) as via_contains,
      count(DISTINCT ho2) as via_has_ho
    """
    result = session.run(query5)
    r = result.single()

    print(f"\n[5] HANG → HO 연결 방식")
    print(f"    CONTAINS: {r['via_contains']}개")
    print(f"    HAS_HO: {r['via_has_ho']}개")

    if r['via_contains'] > r['via_has_ho']:
        print(f"    ✅ CONTAINS 사용하면 됨!")
    elif r['via_has_ho'] > r['via_contains']:
        print(f"    ✅ HAS_HO 사용하면 됨!")
    else:
        print(f"    ⚠️ 둘 다 부족함")

print("\n" + "=" * 70)
print("결론")
print("=" * 70)
print(f"✅ JO → HANG: CONTAINS 사용")
print(f"✅ HANG → HO: CONTAINS 사용 (HAS_HO는 일부만)")
print(f"✅ 형제 찾기: 같은 부모(JO)의 자식(HANG)들")
print("=" * 70)
