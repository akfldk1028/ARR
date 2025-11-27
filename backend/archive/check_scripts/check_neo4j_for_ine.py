"""
Neo4j 데이터 상태 확인 (INE 알고리즘 테스트용)

목적: INE 알고리즘 테스트를 위한 Neo4j DB 현황 파악
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

def main():
    print("=" * 60)
    print("Neo4j Database Status Check for INE Algorithm")
    print("=" * 60)

    load_dotenv()

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "11111111"))
    )

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            # 1. RoadNode 확인
            print("\n[1] RoadNode Status")
            result = session.run("""
                MATCH (n:RoadNode)
                RETURN count(n) AS count,
                       collect(n.node_id)[0..5] AS samples
            """)
            record = result.single()
            node_count = record['count']
            samples = record['samples']

            print(f"  Total RoadNodes: {node_count}")
            print(f"  Sample node_ids: {samples}")

            # node_id 타입 확인
            if samples:
                sample_types = [type(s).__name__ for s in samples]
                print(f"  node_id types: {set(sample_types)}")

            # 2. SEGMENT 관계 확인
            print("\n[2] SEGMENT Relationship Status")
            result = session.run("MATCH ()-[r:SEGMENT]->() RETURN count(r) AS count")
            seg_count = result.single()['count']
            print(f"  Total SEGMENTs: {seg_count}")

            # 3. POI 노드 확인
            print("\n[3] POI Node Status")
            result = session.run("""
                MATCH (p:POI)
                RETURN count(p) AS count,
                       collect(p.type)[0..5] AS sample_types
            """)
            record = result.single()
            poi_count = record['count']
            poi_types = record['sample_types']
            print(f"  Total POIs: {poi_count}")
            if poi_types:
                print(f"  Sample POI types: {poi_types}")

            # 4. LOCATED_AT 관계 확인
            print("\n[4] LOCATED_AT Relationship Status")
            result = session.run("MATCH ()-[r:LOCATED_AT]->() RETURN count(r) AS count")
            located_count = result.single()['count']
            print(f"  Total LOCATED_AT: {located_count}")

            # 5. 판단
            print("\n" + "=" * 60)
            print("Analysis & Recommendation")
            print("=" * 60)

            if node_count == 0:
                print("\n[CASE C] No data in Neo4j")
                print("  Recommendation: Create new test network with integer node_ids + POIs")
                print("  Action: Run create_test_network_with_pois.py")
            elif samples and all(isinstance(s, int) for s in samples):
                print("\n[CASE A] Integer node_ids found")
                print(f"  RoadNodes: {node_count}, SEGMENTs: {seg_count}")
                if poi_count == 0:
                    print("  Recommendation: Add POIs to existing network")
                    print("  Action: Run add_pois_to_network.py")
                else:
                    print(f"  POIs already exist: {poi_count}")
                    print("  Status: Ready for INE testing!")
            elif samples and all(isinstance(s, str) for s in samples):
                print("\n[CASE B] String node_ids found (old format)")
                print(f"  Sample IDs: {samples}")
                print("  Recommendation: Create new test network with integer node_ids")
                print("  Action: Run create_test_network_with_pois.py")
            else:
                print("\n[CASE D] Mixed or unknown node_id types")
                print(f"  Sample IDs: {samples}")
                print("  Recommendation: Check data consistency")

    finally:
        driver.close()
        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
