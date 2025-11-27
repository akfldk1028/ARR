"""
Simple test to check what 36조 search returns
"""

import os
import sys
import django
from pathlib import Path
import json

# Setup Django
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService

def main():
    neo4j = Neo4jService()
    neo4j.connect()

    # Query for 36조 HANG nodes directly
    query = """
    MATCH (hang:HANG)
    WHERE hang.full_id CONTAINS '제36조'
    MATCH (hang)<-[:CONTAINS*]-(law:LAW)
    RETURN hang.full_id as hang_id,
           hang.content as content,
           hang.unit_path as unit_path,
           law.law_name as law_name,
           law.law_type as law_type,
           law.full_id as law_full_id
    LIMIT 20
    """

    results = neo4j.execute_query(query)

    print(f"\nFound {len(results)} results for 36조:")
    print("="*100)

    for idx, r in enumerate(results, 1):
        print(f"\n{idx}. HANG ID: {r['hang_id']}")
        print(f"   Law Name: {r['law_name']}")
        print(f"   Law Type: {r['law_type']}")
        print(f"   Law Full ID: {r['law_full_id']}")
        print(f"   Unit Path: {r['unit_path']}")
        print(f"   Content: {r['content'][:100]}...")

    # Save to JSON
    output_file = backend_dir / "test_36jo_direct_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()
