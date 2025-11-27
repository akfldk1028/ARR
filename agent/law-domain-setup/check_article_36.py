import sys
from pathlib import Path

agent_root = Path(__file__).parent.parent
sys.path.insert(0, str(agent_root / "law-domain-agents" / "shared"))

from neo4j_client import get_neo4j_client

client = get_neo4j_client()
session = client.get_session()

# Find Article 36
query = """
MATCH (h:HANG)
WHERE h.full_id CONTAINS '제36조'
RETURN h.full_id as full_id
LIMIT 10
"""

print("Article 36 (제36조) locations:")
print("=" * 80)
results = session.run(query)
for r in results:
    print(r['full_id'])

# Check all unique chapters
query2 = """
MATCH (h:HANG)
WITH split(h.full_id, '::') as parts
WHERE size(parts) > 1
WITH parts[1] as chapter
RETURN DISTINCT chapter
ORDER BY chapter
"""

print("\n" + "=" * 80)
print("All chapters in database:")
print("=" * 80)
results2 = session.run(query2)
for r in results2:
    print(r['chapter'])

session.close()
