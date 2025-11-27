"""17조 검색 테스트"""
import os, sys
sys.path.insert(0, 'D:/Data/11_Backend/01_ARR/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

# 17조 내용 확인
query = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS "제17조"
  AND NOT h.full_id CONTAINS "제4절"
RETURN h.full_id as id, h.content as content
LIMIT 3
"""

results = neo4j.execute_query(query, {})

print("=== 17조 실제 내용 (부칙 제외) ===\n")
for i, r in enumerate(results):
    print(f"{i+1}. ID: {r['id']}")
    print(f"   내용: {r['content'][:200]}\n")

neo4j.disconnect()
