"""
법률 간 관계 설정
LAW 노드 간 IMPLEMENTS 관계 추가
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
print("법률 간 IMPLEMENTS 관계 설정")
print("=" * 70)

with neo4j.driver.session() as session:
    # 1. 법률 → 시행령
    query1 = """
    MATCH (law:LAW {law_type: '법률'})
    MATCH (decree:LAW {law_type: '시행령'})
    WHERE law.name CONTAINS '국토의 계획'
      AND decree.name CONTAINS '국토의 계획'
    MERGE (law)-[:IMPLEMENTS]->(decree)
    RETURN law.name, decree.name
    """

    result = session.run(query1)
    records = list(result)

    print(f"\n[1] 법률 → 시행령")
    if records:
        for r in records:
            print(f"    ✅ {r['law.name']}")
            print(f"       → {r['decree.name']}")
    else:
        print(f"    ⚠️ 관계 생성 실패")

    # 2. 시행령 → 시행규칙
    query2 = """
    MATCH (decree:LAW {law_type: '시행령'})
    MATCH (rule:LAW {law_type: '시행규칙'})
    WHERE decree.name CONTAINS '국토의 계획'
      AND rule.name CONTAINS '국토의 계획'
    MERGE (decree)-[:IMPLEMENTS]->(rule)
    RETURN decree.name, rule.name
    """

    result = session.run(query2)
    records = list(result)

    print(f"\n[2] 시행령 → 시행규칙")
    if records:
        for r in records:
            print(f"    ✅ {r['decree.name']}")
            print(f"       → {r['rule.name']}")
    else:
        print(f"    ⚠️ 관계 생성 실패")

    # 3. 검증
    query3 = """
    MATCH p=(law:LAW)-[:IMPLEMENTS*]->(child:LAW)
    RETURN law.name as base_law,
           law.law_type as base_type,
           child.name as child_law,
           child.law_type as child_type,
           length(p) as depth
    ORDER BY depth
    """

    result = session.run(query3)
    records = list(result)

    print(f"\n[3] 검증: IMPLEMENTS 관계 ({len(records)}개)")
    for r in records:
        indent = "  " * r['depth']
        print(f"    {indent}{r['base_law']} ({r['base_type']})")
        print(f"    {indent}  → {r['child_law']} ({r['child_type']})")

print("\n" + "=" * 70)
print("완료!")
print("=" * 70)
print("✅ 법률 → 시행령 → 시행규칙 관계 설정 완료")
print("✅ 알고리즘이 이제 법률 계층을 탐색할 수 있습니다!")
print("=" * 70)
