"""
Step 1: 현재 Neo4j 관계 분석

목적:
- CONTAINS, CITES, NEXT 관계 개수 확인
- 관계의 from/to 노드 라벨 분포
- 관계 속성 확인
- 샘플 관계 출력
"""

import os
import sys
import django
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def analyze_relationships():
    """관계 분석 메인 함수"""

    neo4j = Neo4jService()

    print("=" * 80)
    print("Step 1: Neo4j 관계 분석")
    print("=" * 80)

    # 연결
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # 1. 전체 관계 타입 및 개수
        print("[1] 전체 관계 타입 및 개수")
        print("-" * 80)
        query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        """
        result = neo4j.execute_query(query)

        total_relationships = 0
        for record in result:
            rel_type = record['relationship_type']
            count = record['count']
            total_relationships += count
            print(f"  {rel_type:20s}: {count:6,d}개")

        print(f"\n  {'총합':20s}: {total_relationships:6,d}개")
        print()

        # 2. CONTAINS 관계 상세 분석
        print("[2] CONTAINS 관계 상세 분석")
        print("-" * 80)
        query = """
        MATCH (from)-[r:CONTAINS]->(to)
        RETURN
            labels(from)[0] as from_label,
            labels(to)[0] as to_label,
            count(r) as count
        ORDER BY count DESC
        """
        result = neo4j.execute_query(query)

        print(f"  {'From':10s} -> {'To':10s} | {'개수':>8s}")
        print(f"  {'-'*10}    {'-'*10}   {'-'*8}")
        for record in result:
            from_label = record['from_label']
            to_label = record['to_label']
            count = record['count']
            print(f"  {from_label:10s} -> {to_label:10s} | {count:8,d}")
        print()

        # 3. CONTAINS 관계 속성 확인
        print("[3] CONTAINS 관계 속성 확인 (샘플 10개)")
        print("-" * 80)
        query = """
        MATCH (from)-[r:CONTAINS]->(to)
        RETURN
            labels(from)[0] as from_label,
            from.full_id as from_id,
            labels(to)[0] as to_label,
            to.full_id as to_id,
            properties(r) as props
        LIMIT 10
        """
        result = neo4j.execute_query(query)

        for i, record in enumerate(result, 1):
            print(f"\n  #{i}")
            print(f"    From: [{record['from_label']}] {record['from_id']}")
            print(f"    To:   [{record['to_label']}] {record['to_id']}")
            print(f"    Properties: {record['props']}")
        print()

        # 4. CITES 관계 분석 (있다면)
        print("[4] CITES 관계 분석")
        print("-" * 80)
        query = """
        MATCH (from)-[r:CITES]->(to)
        RETURN count(r) as count
        """
        result = neo4j.execute_query(query)
        cites_count = result[0]['count'] if result else 0

        if cites_count > 0:
            print(f"  CITES 관계: {cites_count:,d}개\n")

            # CITES 샘플
            query = """
            MATCH (from)-[r:CITES]->(to)
            RETURN
                from.full_id as from_id,
                to.full_id as to_id,
                properties(r) as props
            LIMIT 5
            """
            result = neo4j.execute_query(query)

            print("  샘플 5개:")
            for i, record in enumerate(result, 1):
                print(f"    #{i}: {record['from_id']} -> {record['to_id']}")
                print(f"        Properties: {record['props']}")
        else:
            print("  CITES 관계 없음")
        print()

        # 5. 관계에 content 접근 가능한지 확인 (임베딩 생성용)
        print("[5] 관계 텍스트 추출 가능성 확인")
        print("-" * 80)
        query = """
        MATCH (from:HANG)-[r:CONTAINS]->(to:HO)
        RETURN
            from.content as from_content,
            to.content as to_content,
            from.full_id as from_id,
            to.full_id as to_id
        LIMIT 3
        """
        result = neo4j.execute_query(query)

        if result:
            print("  [OK] 노드 content 접근 가능\n")
            for i, record in enumerate(result, 1):
                from_content = record['from_content'][:50] + "..." if len(record['from_content']) > 50 else record['from_content']
                to_content = record['to_content'][:50] + "..." if len(record['to_content']) > 50 else record['to_content']

                print(f"  예시 #{i}:")
                print(f"    From [{record['from_id']}]: {from_content}")
                print(f"    To   [{record['to_id']}]: {to_content}")
                print()
        else:
            print("  [WARNING] HANG->HO 관계 없음, 다른 관계 확인 필요")

        # 6. 요약
        print("[6] 요약 및 다음 단계")
        print("=" * 80)
        print(f"  총 관계 개수: {total_relationships:,d}개")
        print(f"  CITES 관계: {cites_count:,d}개")
        print()
        print("  다음 단계:")
        print("  → Step 2: 관계 맥락 텍스트 추출 (step2_extract_contexts.py)")
        print("  → Step 3: 임베딩 생성 (step3_generate_embeddings.py)")
        print("  → Step 4: Neo4j 업데이트 (step4_update_neo4j.py)")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    analyze_relationships()
