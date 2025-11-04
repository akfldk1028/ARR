"""
샘플 도로 네트워크 + 규정 생성

Integration.md 스키마 기반:
- RoadNode: 도로 교차점
- SEGMENT: 도로 구간
- Zone: 용도 지역
- Regulation: 규정 (법률 기반)
- SNDB: 기존 JO 노드에 레이블 추가
"""

import sys
from neo4j import GraphDatabase
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# Neo4j 연결
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "11111111"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def create_indexes():
    """인덱스 생성 (Integration.md 3절)"""
    print("\n" + "=" * 80)
    print("[1/5] 인덱스 생성")
    print("=" * 80)

    with driver.session() as session:
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:RoadNode) ON (n.point)",
            "CREATE INDEX IF NOT EXISTS FOR (p:POI) ON (p.point)",
            "CREATE INDEX IF NOT EXISTS FOR (z:Zone) ON (z.name)",
            "CREATE INDEX IF NOT EXISTS FOR (r:Regulation) ON (r.type)",
            "CREATE INDEX IF NOT EXISTS FOR (s:SNDB) ON (s.id)",
        ]

        for idx_query in indexes:
            session.run(idx_query)
            print(f"  ✅ {idx_query.split('FOR')[1].split('ON')[0].strip()}")


def add_sndb_labels():
    """
    기존 JO 노드에 SNDB 레이블 추가

    JO → SNDB 변환:
        - full_id → id
        - citation_uri 생성
        - version, effective_from 추가
    """
    print("\n" + "=" * 80)
    print("[2/5] JO → SNDB 변환")
    print("=" * 80)

    with driver.session() as session:
        # JO 노드 개수 확인
        count_result = session.run("MATCH (jo:JO) RETURN count(jo) as count")
        jo_count = count_result.single()['count']
        print(f"\n기존 JO 노드: {jo_count}개")

        if jo_count == 0:
            print("⚠️  JO 노드가 없습니다. 먼저 법률 데이터를 로드하세요.")
            return

        # SNDB 레이블 추가 및 속성 설정
        query = """
        MATCH (jo:JO)
        WHERE jo.law_name = '국토의 계획 및 이용에 관한 법률'
        SET jo:SNDB
        SET jo.id = jo.full_id
        SET jo.citation_uri = 'https://law.go.kr/법령/' + replace(jo.law_name, ' ', '') + '/' + jo.number
        SET jo.version = '제19117호'
        SET jo.effective_from = date('2023-06-28')
        SET jo.article_number = jo.number
        SET jo.article_title = jo.title
        RETURN count(jo) as updated_count
        """

        result = session.run(query)
        updated = result.single()['updated_count']
        print(f"\n✅ {updated}개 JO 노드 → SNDB 변환 완료")


def create_road_network():
    """
    샘플 도로 네트워크 생성

    구조:
        n1 --- n2 --- n3
        |      |      |
        n4 --- n5 --- n6
        |      |      |
        n7 --- n8 --- n9

    총 9개 노드, 12개 양방향 세그먼트 (24개 엣지)
    """
    print("\n" + "=" * 80)
    print("[3/5] 도로 네트워크 생성")
    print("=" * 80)

    with driver.session() as session:
        # 기존 도로 데이터 삭제
        session.run("MATCH (n:RoadNode) DETACH DELETE n")

        # 노드 생성 (3x3 그리드)
        nodes = []
        for i in range(1, 10):
            row = (i - 1) // 3
            col = (i - 1) % 3
            lat = 37.5 + row * 0.01
            lon = 127.0 + col * 0.01

            query = """
            CREATE (n:RoadNode {
                node_id: $node_id,
                name: $name,
                point: point({latitude: $lat, longitude: $lon})
            })
            RETURN id(n) as internal_id
            """

            result = session.run(query, node_id=f"n{i}", name=f"교차로{i}", lat=lat, lon=lon)
            internal_id = result.single()['internal_id']
            nodes.append({'node_id': f"n{i}", 'internal_id': internal_id})
            print(f"  ✅ n{i} (ID: {internal_id})")

        # 세그먼트 생성 (양방향)
        edges = [
            # 수평선
            ('n1', 'n2', 800, 120), ('n2', 'n3', 1000, 150),
            ('n4', 'n5', 600, 90), ('n5', 'n6', 800, 120),
            ('n7', 'n8', 900, 135), ('n8', 'n9', 700, 105),
            # 수직선
            ('n1', 'n4', 1200, 180), ('n4', 'n7', 1100, 165),
            ('n2', 'n5', 1000, 150), ('n5', 'n8', 900, 135),
            ('n3', 'n6', 1300, 195), ('n6', 'n9', 1000, 150),
        ]

        segment_count = 0
        for a_id, b_id, length, base_time in edges:
            # A -> B
            query_ab = """
            MATCH (a:RoadNode {node_id: $a_id})
            MATCH (b:RoadNode {node_id: $b_id})
            CREATE (a)-[:SEGMENT {
                length: $length,
                baseTime: $base_time,
                dir: 'both',
                axleWeight: 20.0
            }]->(b)
            """
            session.run(query_ab, a_id=a_id, b_id=b_id, length=length, base_time=base_time)

            # B -> A
            query_ba = """
            MATCH (a:RoadNode {node_id: $a_id})
            MATCH (b:RoadNode {node_id: $b_id})
            CREATE (b)-[:SEGMENT {
                length: $length,
                baseTime: $base_time,
                dir: 'both',
                axleWeight: 20.0
            }]->(a)
            """
            session.run(query_ba, a_id=a_id, b_id=b_id, length=length, base_time=base_time)
            segment_count += 2

        print(f"\n✅ {len(nodes)}개 노드, {segment_count}개 세그먼트 생성")


def create_zones_and_regulations():
    """
    용도 지역 + 규정 생성

    Zone 1: 주거지역 (n4-n5 세그먼트)
        - 중량 제한 10톤
        - 야간 금지 (22:00-06:00)

    Zone 2: 상업지역 (n2-n5 세그먼트)
        - 버스 전용 (일반 차량 300초 페널티)

    Zone 3: 공업지역 (n8-n9 세그먼트)
        - 통행료 (60초 페널티)
    """
    print("\n" + "=" * 80)
    print("[4/5] 구역 및 규정 생성")
    print("=" * 80)

    with driver.session() as session:
        # 기존 Zone, Regulation 삭제
        session.run("MATCH (n:Zone) DETACH DELETE n")
        session.run("MATCH (n:Regulation) DETACH DELETE n")

        # === Zone 1: 주거지역 ===
        print("\n[Zone 1] 주거지역")

        zone1_query = """
        CREATE (z:Zone {
            name: '주거지역',
            geom: 'POLYGON((...))',
            description: 'n4-n5 구간'
        })
        RETURN id(z) as zone_id
        """
        zone1_id = session.run(zone1_query).single()['zone_id']
        print(f"  ✅ Zone ID: {zone1_id}")

        # 세그먼트에 Zone ID 속성 추가 (관계->노드 연결 불가 문제 해결)
        session.run("""
            MATCH (a:RoadNode {node_id: 'n4'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n5'})
            SET seg.zone_id = '주거지역'
        """)
        session.run("""
            MATCH (a:RoadNode {node_id: 'n5'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n4'})
            SET seg.zone_id = '주거지역'
        """)
        print("  ✅ n4<->n5 세그먼트에 Zone ID 추가")

        # 규정 1-1: 중량 제한
        reg1_query = """
        CREATE (r:Regulation {
            type: 'weightLimit',
            limit: 10.0,
            severity: 'block',
            articleId: '국토의 계획 및 이용에 관한 법률::제4장::제2절::제56조',
            description: '주거지역 중량 제한 10톤'
        })
        RETURN id(r) as reg_id
        """
        reg1_id = session.run(reg1_query).single()['reg_id']
        print(f"  ✅ Regulation (weightLimit): {reg1_id}")

        # Zone-Regulation 연결
        session.run("""
            MATCH (z:Zone {name: '주거지역'})
            MATCH (r:Regulation {type: 'weightLimit'})
            MERGE (z)-[:ENFORCES]->(r)
        """)

        # Regulation-SNDB 연결
        session.run("""
            MATCH (r:Regulation {type: 'weightLimit'})
            MATCH (s:SNDB {id: '국토의 계획 및 이용에 관한 법률::제4장::제2절::제56조'})
            MERGE (r)-[:CITES]->(s)
        """)
        print("  ✅ Regulation → SNDB 연결")

        # 규정 1-2: 야간 금지
        reg2_query = """
        CREATE (r:Regulation {
            type: 'timeBan',
            start: '22:00:00',
            end: '06:00:00',
            severity: 'block',
            articleId: '국토의 계획 및 이용에 관한 법률::제7장::제76조',
            description: '주거지역 야간 통행 금지'
        })
        RETURN id(r) as reg_id
        """
        reg2_id = session.run(reg2_query).single()['reg_id']
        print(f"  ✅ Regulation (timeBan): {reg2_id}")

        session.run("""
            MATCH (z:Zone {name: '주거지역'})
            MATCH (r:Regulation {type: 'timeBan'})
            MERGE (z)-[:ENFORCES]->(r)
        """)

        # === Zone 2: 상업지역 ===
        print("\n[Zone 2] 상업지역")

        zone2_query = """
        CREATE (z:Zone {
            name: '상업지역',
            geom: 'POLYGON((...))',
            description: 'n2-n5 구간'
        })
        RETURN id(z) as zone_id
        """
        zone2_id = session.run(zone2_query).single()['zone_id']
        print(f"  ✅ Zone ID: {zone2_id}")

        # 세그먼트에 Zone ID 속성 추가
        session.run("""
            MATCH (a:RoadNode {node_id: 'n2'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n5'})
            SET seg.zone_id = '상업지역'
        """)
        session.run("""
            MATCH (a:RoadNode {node_id: 'n5'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n2'})
            SET seg.zone_id = '상업지역'
        """)
        print("  ✅ n2<->n5 세그먼트에 Zone ID 추가")

        # 규정 2-1: 버스 전용
        reg3_query = """
        CREATE (r:Regulation {
            type: 'busOnly',
            severity: 'penalty',
            articleId: '국토의 계획 및 이용에 관한 법률::제4장::제1절::제25조',
            description: '버스 전용 차로 (일반 차량 300초 페널티)'
        })
        RETURN id(r) as reg_id
        """
        reg3_id = session.run(reg3_query).single()['reg_id']
        print(f"  ✅ Regulation (busOnly): {reg3_id}")

        session.run("""
            MATCH (z:Zone {name: '상업지역'})
            MATCH (r:Regulation {type: 'busOnly'})
            MERGE (z)-[:ENFORCES]->(r)
        """)

        # === Zone 3: 공업지역 ===
        print("\n[Zone 3] 공업지역")

        zone3_query = """
        CREATE (z:Zone {
            name: '공업지역',
            geom: 'POLYGON((...))',
            description: 'n8-n9 구간'
        })
        RETURN id(z) as zone_id
        """
        zone3_id = session.run(zone3_query).single()['zone_id']
        print(f"  ✅ Zone ID: {zone3_id}")

        session.run("""
            MATCH (a:RoadNode {node_id: 'n8'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n9'})
            SET seg.zone_id = '공업지역'
        """)
        session.run("""
            MATCH (a:RoadNode {node_id: 'n9'})-[seg:SEGMENT]->(b:RoadNode {node_id: 'n8'})
            SET seg.zone_id = '공업지역'
        """)
        print("  ✅ n8<->n9 세그먼트에 Zone ID 추가")

        # 규정 3-1: 통행료
        reg4_query = """
        CREATE (r:Regulation {
            type: 'toll',
            timePenalty: 60,
            severity: 'penalty',
            articleId: '국토의 계획 및 이용에 관한 법률::제8장::제88조',
            description: '통행료 (60초 페널티)'
        })
        RETURN id(r) as reg_id
        """
        reg4_id = session.run(reg4_query).single()['reg_id']
        print(f"  ✅ Regulation (toll): {reg4_id}")

        session.run("""
            MATCH (z:Zone {name: '공업지역'})
            MATCH (r:Regulation {type: 'toll'})
            MERGE (z)-[:ENFORCES]->(r)
        """)

        print("\n✅ 3개 구역, 4개 규정 생성 완료")


def verify_data():
    """데이터 검증"""
    print("\n" + "=" * 80)
    print("[5/5] 데이터 검증")
    print("=" * 80)

    with driver.session() as session:
        # RoadNode 개수
        road_count = session.run("MATCH (n:RoadNode) RETURN count(n) as count").single()['count']
        print(f"\n✅ RoadNode: {road_count}개")

        # SEGMENT 개수
        seg_count = session.run("MATCH ()-[r:SEGMENT]->() RETURN count(r) as count").single()['count']
        print(f"✅ SEGMENT: {seg_count}개")

        # SNDB 개수
        sndb_count = session.run("MATCH (n:SNDB) RETURN count(n) as count").single()['count']
        print(f"✅ SNDB: {sndb_count}개")

        # Zone 개수
        zone_count = session.run("MATCH (n:Zone) RETURN count(n) as count").single()['count']
        print(f"✅ Zone: {zone_count}개")

        # Regulation 개수
        reg_count = session.run("MATCH (n:Regulation) RETURN count(n) as count").single()['count']
        print(f"✅ Regulation: {reg_count}개")

        # 속성 검증
        print("\n속성 검증:")
        zone_segs = session.run("MATCH ()-[r:SEGMENT]->() WHERE r.zone_id IS NOT NULL RETURN count(r) as count").single()['count']
        print(f"  - SEGMENT with zone_id: {zone_segs}개")

        enforces = session.run("MATCH ()-[r:ENFORCES]->() RETURN count(r) as count").single()['count']
        print(f"  - Zone -[:ENFORCES]-> Regulation: {enforces}개")

        cites = session.run("MATCH ()-[r:CITES]->() RETURN count(r) as count").single()['count']
        print(f"  - Regulation -[:CITES]-> SNDB: {cites}개")


if __name__ == "__main__":
    try:
        print("\n" + "=" * 80)
        print("샘플 도로 네트워크 + 규정 생성")
        print("=" * 80)

        create_indexes()
        add_sndb_labels()
        create_road_network()
        create_zones_and_regulations()
        verify_data()

        print("\n" + "=" * 80)
        print("✅ 모든 작업 완료!")
        print("=" * 80)

        print("\n다음 단계:")
        print("1. RNE 엔진 테스트:")
        print("   python law/routing/rne_engine.py")
        print("\n2. Neo4j Browser에서 확인 (http://localhost:7474):")
        print("   MATCH (n:RoadNode)-[r:SEGMENT]->(m) RETURN n,r,m LIMIT 25")

        driver.close()

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        driver.close()
