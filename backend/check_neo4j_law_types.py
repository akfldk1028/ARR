"""Check LAW node types in Neo4j database"""
from graph_db.services.neo4j_service import Neo4jService
import json

def check_law_nodes():
    service = Neo4jService()

    try:
        # Connect to database
        service.connect()
        print("[OK] Connected to Neo4j")

        # Check LAW nodes
        print("\n" + "="*80)
        print("LAW Nodes in Database")
        print("="*80)

        query = '''
        MATCH (law:LAW)
        RETURN law.name as name, law.law_type as law_type, law.full_id as full_id
        ORDER BY law.name
        '''

        results = service.execute_query(query)

        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['name']}")
            print(f"   Type: {r.get('law_type', 'NOT SET')}")
            print(f"   Full ID: {r['full_id']}")

        print(f"\n총 LAW 노드: {len(results)}개")

        # Check law_type distribution
        print("\n" + "="*80)
        print("LAW Type Distribution")
        print("="*80)

        type_query = '''
        MATCH (law:LAW)
        RETURN law.law_type as law_type, count(*) as count
        ORDER BY count DESC
        '''

        type_results = service.execute_query(type_query)

        for r in type_results:
            law_type = r.get('law_type', 'NULL')
            count = r['count']
            print(f"{law_type}: {count}개")

        # Check sample JO nodes from different laws
        print("\n" + "="*80)
        print("Sample JO Nodes (조)")
        print("="*80)

        jo_query = '''
        MATCH (law:LAW)-[:CONTAINS]->(jo:JO)
        WHERE jo.unit_number IN ['36조', '94조']
        RETURN law.name as law_name, law.law_type as law_type,
               jo.unit_number as jo_number, jo.full_id as jo_full_id
        ORDER BY law.name, jo.unit_number
        '''

        jo_results = service.execute_query(jo_query)

        for r in jo_results:
            print(f"\n{r['jo_number']} - {r['law_name']}")
            print(f"  Law Type: {r.get('law_type', 'NOT SET')}")
            print(f"  JO Full ID: {r['jo_full_id']}")

    finally:
        service.disconnect()
        print("\n[OK] Disconnected from Neo4j")

if __name__ == "__main__":
    check_law_nodes()
