"""
법률 타입 확인
법률, 시행령, 시행규칙이 Neo4j에 어떻게 저장되어 있는지 확인
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
print("법률 타입 및 상하위법 관계 확인")
print("=" * 70)

with neo4j.driver.session() as session:
    # 1. LAW 노드 확인
    query1 = """
    MATCH (law:LAW)
    RETURN law.name as name,
           law.full_id as full_id,
           law.law_type as law_type
    """
    result = session.run(query1)
    records = list(result)

    print(f"\n[1] LAW 노드 ({len(records)}개)")
    for r in records:
        print(f"    - {r['name']}")
        print(f"      full_id: {r['full_id']}")
        print(f"      law_type: {r['law_type']}")

    # 2. 법률명 분포 (HANG 노드 기준)
    query2 = """
    MATCH (h:HANG)
    RETURN DISTINCT h.law_name as law_name, count(h) as hang_count
    ORDER BY hang_count DESC
    """
    result = session.run(query2)
    records = list(result)

    print(f"\n[2] 법률명 분포 (HANG 기준)")
    for r in records:
        print(f"    {r['law_name']}: {r['hang_count']}개 HANG")

    # 3. 법률 타입 구분 (이름으로 추론)
    print(f"\n[3] 법률 타입 추론 (이름 기반)")
    for r in records:
        name = r['law_name']
        if '시행규칙' in name:
            law_type = '시행규칙 (부령)'
        elif '시행령' in name:
            law_type = '시행령 (대통령령)'
        else:
            law_type = '법률'

        print(f"    {law_type}: {name}")

    # 4. 법률 간 참조 관계 확인
    query4 = """
    MATCH (h1:HANG)-[r]->(h2:HANG)
    WHERE h1.law_name <> h2.law_name
    RETURN type(r) as rel_type,
           h1.law_name as from_law,
           h2.law_name as to_law,
           count(*) as count
    LIMIT 10
    """
    result = session.run(query4)
    records = list(result)

    print(f"\n[4] 법률 간 참조 관계 (HANG 간)")
    if records:
        for r in records:
            print(f"    {r['from_law']}")
            print(f"      -[{r['rel_type']}]->")
            print(f"    {r['to_law']} ({r['count']}개)")
    else:
        print(f"    ⚠️ 법률 간 참조 관계 없음!")

    # 5. REFERENCE 관계 확인 (있을 수도)
    query5 = """
    MATCH ()-[r:REFERENCE]->()
    RETURN count(r) as count
    """
    result = session.run(query5)
    ref_count = result.single()['count']

    print(f"\n[5] REFERENCE 관계: {ref_count}개")
    if ref_count == 0:
        print(f"    ⚠️ 법률 간 참조 관계가 설정되지 않음!")

    # 6. 샘플 조항에서 참조 확인
    query6 = """
    MATCH (h:HANG)
    WHERE h.content CONTAINS '시행령' OR h.content CONTAINS '시행규칙'
    RETURN h.law_name as law_name,
           h.number as number,
           substring(h.content, 0, 100) as content_preview
    LIMIT 5
    """
    result = session.run(query6)
    records = list(result)

    print(f"\n[6] 참조 포함 조항 샘플")
    for i, r in enumerate(records, 1):
        print(f"\n    {i}. {r['law_name']} {r['number']}")
        print(f"       {r['content_preview']}...")

print("\n" + "=" * 70)
print("결론")
print("=" * 70)
print("✅ 3개 법규(법률/시행령/시행규칙) 모두 Neo4j에 있나?")
print("✅ 법률 간 상하위 관계가 설정되어 있나?")
print("✅ 알고리즘이 이 관계를 탐색할 수 있나?")
print("=" * 70)
