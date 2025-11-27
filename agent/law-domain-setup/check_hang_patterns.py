import sys
from pathlib import Path

agent_root = Path(__file__).parent.parent
sys.path.insert(0, str(agent_root / "law-domain-agents" / "shared"))

from neo4j_client import get_neo4j_client

client = get_neo4j_client()
session = client.get_session()

# Get sample HANG nodes
query = """
MATCH (h:HANG)
RETURN h.full_id as full_id
LIMIT 20
"""

results = session.run(query)

print("Sample HANG full_id patterns:")
print("=" * 80)
for r in results:
    print(r['full_id'])

session.close()
