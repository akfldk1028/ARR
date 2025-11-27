"""
Create Test Network with POIs for INE Algorithm

3x3 그리드 네트워크 + POI 노드 생성
Integer node_id (1-9) 사용
"""

import os
import sys
from dotenv import load_dotenv

# Django 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from graph_db.algorithms.repository import Neo4jGraphRepository


def create_test_network(clean_first=False):
    """
    테스트 네트워크 생성

    네트워크 구조 (3x3 그리드):
    ```
    1 -- 2 -- 3
    |    |    |
    4 -- 5 -- 6
    |    |    |
    7 -- 8 -- 9
    ```

    POI 배치:
    - Node 2: Hospital
    - Node 4: School
    - Node 6: GasStation
    - Node 8: Restaurant
    - Node 9: Pharmacy
    """
    print("=" * 60)
    print("Create Test Network with POIs for INE Algorithm")
    print("=" * 60)

    load_dotenv()

    repo = Neo4jGraphRepository(
        uri=os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "11111111"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )

    try:
        with repo.driver.session(database=repo.database) as session:
            # 1. 기존 데이터 삭제 (optional)
            if clean_first:
                print("\n[1] Cleaning existing test data...")
                session.run("""
                    MATCH (n)
                    WHERE n:RoadNode OR n:POI OR n:Zone OR n:Regulation
                    DETACH DELETE n
                """)
                print("  [OK] Cleaned")

            # 2. RoadNode 생성 (1-9)
            print("\n[2] Creating RoadNodes (1-9)...")
            for node_id in range(1, 10):
                session.run("""
                    MERGE (n:RoadNode {node_id: $node_id})
                    SET n.created_at = datetime()
                """, node_id=node_id)
            print("  [OK] Created 9 RoadNodes")

            # 3. SEGMENT 관계 생성 (양방향)
            print("\n[3] Creating SEGMENT relationships...")

            # 그리드 구조 정의
            edges = [
                # 가로 연결
                (1, 2), (2, 3),
                (4, 5), (5, 6),
                (7, 8), (8, 9),
                # 세로 연결
                (1, 4), (4, 7),
                (2, 5), (5, 8),
                (3, 6), (6, 9),
            ]

            segment_count = 0
            for src, dst in edges:
                # 양방향 생성 (src -> dst, dst -> src)
                session.run("""
                    MATCH (src:RoadNode {node_id: $src})
                    MATCH (dst:RoadNode {node_id: $dst})
                    MERGE (src)-[seg:SEGMENT]->(dst)
                    SET seg.baseTime = 100.0
                """, src=src, dst=dst)

                session.run("""
                    MATCH (src:RoadNode {node_id: $src})
                    MATCH (dst:RoadNode {node_id: $dst})
                    MERGE (dst)-[seg:SEGMENT]->(src)
                    SET seg.baseTime = 100.0
                """, src=src, dst=dst)

                segment_count += 2

            print(f"  [OK] Created {segment_count} SEGMENTs (bidirectional)")

            # 4. POI 노드 생성
            print("\n[4] Creating POI nodes...")

            pois = [
                (2, "hospital", "Central Hospital"),
                (4, "school", "Elementary School"),
                (6, "gas_station", "Shell Gas Station"),
                (8, "restaurant", "Korean Restaurant"),
                (9, "pharmacy", "24H Pharmacy"),
            ]

            for node_id, poi_type, poi_name in pois:
                session.run("""
                    CREATE (p:POI {
                        type: $poi_type,
                        name: $poi_name,
                        created_at: datetime()
                    })
                    WITH p
                    MATCH (n:RoadNode {node_id: $node_id})
                    MERGE (n)-[:LOCATED_AT]->(p)
                """, node_id=node_id, poi_type=poi_type, poi_name=poi_name)
                print(f"    - Node {node_id}: {poi_type} ({poi_name})")

            print(f"  [OK] Created {len(pois)} POIs")

            # 5. 검증
            print("\n[5] Verification...")

            # RoadNode 개수
            result = session.run("MATCH (n:RoadNode) RETURN count(n) AS count")
            node_count = result.single()['count']
            print(f"  RoadNodes: {node_count}")

            # SEGMENT 개수
            result = session.run("MATCH ()-[r:SEGMENT]->() RETURN count(r) AS count")
            seg_count = result.single()['count']
            print(f"  SEGMENTs: {seg_count}")

            # POI 개수
            result = session.run("MATCH (p:POI) RETURN count(p) AS count")
            poi_count = result.single()['count']
            print(f"  POIs: {poi_count}")

            # LOCATED_AT 개수
            result = session.run("MATCH ()-[r:LOCATED_AT]->() RETURN count(r) AS count")
            located_count = result.single()['count']
            print(f"  LOCATED_AT: {located_count}")

            # 샘플 쿼리 (Node 1의 이웃)
            print("\n[6] Sample Query (Node 1 neighbors)...")
            result = session.run("""
                MATCH (src:RoadNode {node_id: 1})-[seg:SEGMENT]->(dst:RoadNode)
                RETURN dst.node_id AS neighbor_id, seg.baseTime AS base_cost
                ORDER BY neighbor_id
            """)

            for record in result:
                print(f"    -> Node {record['neighbor_id']}: {record['base_cost']}s")

            # POI가 있는 노드 확인
            print("\n[7] POI Locations...")
            result = session.run("""
                MATCH (n:RoadNode)-[:LOCATED_AT]->(p:POI)
                RETURN n.node_id AS node_id, p.type AS poi_type, p.name AS poi_name
                ORDER BY node_id
            """)

            for record in result:
                print(f"    Node {record['node_id']}: {record['poi_type']} ({record['poi_name']})")

            print("\n" + "=" * 60)
            print("[SUCCESS] Test network created successfully!")
            print("=" * 60)
            print("\nNext steps:")
            print("  1. Run: .venv/Scripts/python.exe test_new_algorithm_stack.py")
            print("  2. Run: .venv/Scripts/python.exe test_ine_integration.py")

    finally:
        repo.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create test network with POIs")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing test data before creating new network",
    )
    args = parser.parse_args()

    create_test_network(clean_first=args.clean)
