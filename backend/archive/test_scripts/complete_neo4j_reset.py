"""
완전한 Neo4j 초기화 스크립트
- 모든 Law 관련 노드 삭제
- Domain 노드 삭제
- 벡터 인덱스 삭제
- 관계 임베딩 삭제
"""

import os
import sys
import django
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def complete_reset():
    """완전 초기화"""

    print("=" * 80)
    print("Neo4j 완전 초기화")
    print("=" * 80)
    print()

    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return 1

    try:
        # [1] 현재 상태 확인
        print("[1] 현재 상태 확인")
        print("-" * 80)

        check_queries = {
            'LAW nodes': 'MATCH (n:LAW) RETURN count(n) as c',
            'JO nodes': 'MATCH (n:JO) RETURN count(n) as c',
            'HANG nodes': 'MATCH (n:HANG) RETURN count(n) as c',
            'HANG with embeddings': 'MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as c',
            'HO nodes': 'MATCH (n:HO) RETURN count(n) as c',
            'Domain nodes': 'MATCH (n:Domain) RETURN count(n) as c',
            'CONTAINS relationships': 'MATCH ()-[r:CONTAINS]->() RETURN count(r) as c',
            'CONTAINS with embeddings': 'MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NOT NULL RETURN count(r) as c',
        }

        for name, query in check_queries.items():
            result = neo4j.execute_query(query)
            count = result[0]['c'] if result else 0
            print(f"  {name}: {count}")

        print()

        # [2] 벡터 인덱스 삭제
        print("[2] 벡터 인덱스 삭제")
        print("-" * 80)

        indexes_to_drop = [
            'hang_embedding',       # HANG 노드 임베딩
            'contains_embedding',   # CONTAINS 관계 임베딩
        ]

        for index_name in indexes_to_drop:
            try:
                drop_query = f"DROP INDEX {index_name} IF EXISTS"
                neo4j.execute_query(drop_query)
                print(f"  [OK] {index_name} 삭제됨")
            except Exception as e:
                print(f"  [SKIP] {index_name} 삭제 실패 또는 존재하지 않음: {e}")

        print()

        # [3] 모든 노드 삭제
        print("[3] 모든 노드 삭제")
        print("-" * 80)

        delete_queries = [
            ('Domain nodes', 'MATCH (n:Domain) DETACH DELETE n'),
            ('LAW nodes', 'MATCH (n:LAW) DETACH DELETE n'),
            ('JANG nodes', 'MATCH (n:JANG) DETACH DELETE n'),
            ('JEOL nodes', 'MATCH (n:JEOL) DETACH DELETE n'),
            ('JO nodes', 'MATCH (n:JO) DETACH DELETE n'),
            ('HANG nodes', 'MATCH (n:HANG) DETACH DELETE n'),
            ('HO nodes', 'MATCH (n:HO) DETACH DELETE n'),
            ('MOK nodes', 'MATCH (n:MOK) DETACH DELETE n'),
        ]

        total_deleted = 0
        for name, query in delete_queries:
            result = neo4j.execute_query(query)
            # DETACH DELETE는 count를 반환하지 않으므로, 삭제 전 count를 확인
            check_query = query.replace('DETACH DELETE n', 'RETURN count(n) as c')
            check_result = neo4j.execute_query(check_query)
            count = check_result[0]['c'] if check_result else 0

            if count > 0:
                neo4j.execute_query(query)
                print(f"  [OK] {name} 삭제: {count}개")
                total_deleted += count
            else:
                print(f"  [SKIP] {name}: 0개")

        print(f"\n  총 {total_deleted}개 노드 삭제됨")
        print()

        # [4] 최종 확인
        print("[4] 최종 확인")
        print("-" * 80)

        for name, query in check_queries.items():
            result = neo4j.execute_query(query)
            count = result[0]['c'] if result else 0
            print(f"  {name}: {count}")

        print()
        print("=" * 80)
        print("[SUCCESS] Neo4j 완전 초기화 완료")
        print("=" * 80)
        print()
        print("다음 단계:")
        print("  1. python process_law_full_auto.py  # PDF 파싱 → Neo4j 로드 → 노드 임베딩")
        print("  2. python add_relationship_embeddings.py  # 관계 임베딩 추가")
        print()

        neo4j.disconnect()
        return 0

    except Exception as e:
        print(f"\n[ERROR] 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        neo4j.disconnect()
        return 1


if __name__ == "__main__":
    sys.exit(complete_reset())
