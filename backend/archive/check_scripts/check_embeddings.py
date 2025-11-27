"""
Check embedding status in Neo4j
"""

import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService

def check_embeddings():
    neo4j = Neo4jService()
    neo4j.connect()

    # Check HANG nodes with embeddings
    query = """
    MATCH (h:HANG)
    WHERE h.embedding IS NOT NULL
    RETURN count(h) as count, size(h.embedding) as dim
    LIMIT 1
    """

    with neo4j.driver.session() as session:
        result = session.run(query)
        record = result.single()

        if record and record['count'] > 0:
            print(f"✅ Found {record['count']} HANG nodes with embeddings")
            print(f"   Dimension: {record['dim']}")
        else:
            print(f"❌ No HANG nodes with embeddings found")

            # Check if HANG nodes exist at all
            count_query = "MATCH (h:HANG) RETURN count(h) as total"
            result = session.run(count_query)
            total = result.single()['total']
            print(f"   Total HANG nodes: {total}")

            # Check for other embedding property names
            sample_query = """
            MATCH (h:HANG)
            RETURN h
            LIMIT 1
            """
            result = session.run(sample_query)
            sample = result.single()
            if sample:
                print(f"   Sample HANG properties: {list(sample['h'].keys())}")

if __name__ == "__main__":
    check_embeddings()
