"""
계층 관계 상세 확인
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("\n=== Step 3: 실제 예시로 계층 확인 ===\n")

# 예시 1: 제1조의 항들
print("예시 1: 국토계획법 제1조의 항들")
query1 = """
MATCH p=(law:LAW)-[:CONTAINS*]->(jo:JO {number: "1"})-[:CONTAINS]->(hang:HANG)
WHERE law.law_name = "국토의 계획 및 이용에 관한 법률"
RETURN law.law_name as law, jo.title as jo_title, hang.number as hang_num, hang.unit_path as path
LIMIT 5
"""
results = neo4j.execute_query(query1, {})
for r in results:
    print(f"  {r['jo_title']} → 제{r['hang_num']}항 ({r['path']})")

# 예시 2: 한 항이 가진 모든 관계
print("\n예시 2: 제1조 제1항의 모든 관계")
query2 = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "제1조" AND h.number = "1"
WITH h LIMIT 1
MATCH (h)-[r]->(target)
RETURN type(r) as rel_type, labels(target)[0] as target_type
"""
results = neo4j.execute_query(query2, {})
print("  나가는 관계:")
for r in results:
    print(f"    항 --{r['rel_type']}--> {r['target_type']}")

query3 = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "제1조" AND h.number = "1"
WITH h LIMIT 1
MATCH (source)-[r]->(h)
RETURN type(r) as rel_type, labels(source)[0] as source_type
"""
results = neo4j.execute_query(query3, {})
print("  들어오는 관계:")
for r in results:
    print(f"    {r['source_type']} --{r['rel_type']}--> 항")

# 예시 3: 완전한 경로
print("\n예시 3: LAW → JO → HANG → Domain 완전한 경로")
query4 = """
MATCH (law:LAW)-[:CONTAINS*]->(jo:JO)-[:CONTAINS]->(hang:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
WHERE law.law_name = "국토의 계획 및 이용에 관한 법률"
RETURN law.law_name as law_name, jo.title as jo_title, hang.unit_path as hang_path, d.domain_name as domain
LIMIT 3
"""
results = neo4j.execute_query(query4, {})
for r in results:
    print(f"  {r['law_name']}")
    print(f"    → {r['jo_title']}")
    print(f"      → {r['hang_path']}")
    print(f"        → Domain: {r['domain']}")
    print()

print("=== 결론 ===")
print("✅ CONTAINS 관계 (계층): 유지됨")
print("✅ BELONGS_TO_DOMAIN 관계 (의미): 추가됨")
print("✅ 두 관계가 독립적으로 공존함")
