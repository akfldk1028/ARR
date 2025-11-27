"""
Neo4j 도메인 재초기화 스크립트

기존 단일 도메인을 삭제하고 멀티 에이전트 시스템을 위한 5개 도메인을 생성합니다.
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService
from agents.law.agent_manager import AgentManager


def main():
    print("=" * 80)
    print("멀티 도메인 MAS 재초기화")
    print("=" * 80)

    neo4j = Neo4jService()
    neo4j.connect()

    # [1] 기존 도메인 데이터 확인
    print("\n[1/4] 기존 도메인 확인 중...")
    domain_count_query = 'MATCH (d:Domain) RETURN count(d) as count'
    result = neo4j.execute_query(domain_count_query)
    existing_domains = result[0]['count']
    print(f"  - 기존 도메인: {existing_domains}개")

    # [2] 기존 도메인 및 관계 삭제
    if existing_domains > 0:
        print("\n[2/4] 기존 도메인 삭제 중...")

        # BELONGS_TO_DOMAIN 관계 삭제
        delete_rels_query = 'MATCH ()-[r:BELONGS_TO_DOMAIN]->() DELETE r'
        neo4j.execute_query(delete_rels_query)
        print("  - BELONGS_TO_DOMAIN 관계 삭제 완료")

        # Domain 노드 삭제
        delete_domains_query = 'MATCH (d:Domain) DELETE d'
        neo4j.execute_query(delete_domains_query)
        print("  - Domain 노드 삭제 완료")
    else:
        print("\n[2/4] 기존 도메인 없음, 건너뜀")

    # [3] HANG 노드 개수 확인
    print("\n[3/4] HANG 노드 확인 중...")
    hang_count_query = 'MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as count'
    result = neo4j.execute_query(hang_count_query)
    hang_count = result[0]['count']
    print(f"  - 임베딩 포함 HANG 노드: {hang_count}개")

    if hang_count == 0:
        print("\n⚠️  HANG 노드가 없습니다. 먼저 데이터를 로드하세요.")
        neo4j.disconnect()
        return

    neo4j.disconnect()

    # [4] AgentManager로 5개 도메인 자동 생성
    print("\n[4/4] 멀티 도메인 생성 중 (5개 도메인)...")
    print("  ※ K-means 클러스터링으로 HANG 노드들을 5개 도메인으로 분할합니다.")
    print("  ※ 각 도메인에는 DomainAgent가 자동 생성됩니다.")
    print()

    manager = AgentManager()

    # AgentManager.__init__이 자동으로 도메인을 로드하거나 초기화함
    # - 기존 Domain 노드가 있으면 _load_domains_from_neo4j()
    # - 없으면 _initialize_from_existing_hangs(n_clusters=5) 자동 실행

    print(f"\n✅ 완료! {len(manager.domains)}개 도메인 생성됨:")
    print()

    for domain_id, domain_info in manager.domains.items():
        print(f"  • {domain_info.domain_name}")
        print(f"    - Domain ID: {domain_id}")
        print(f"    - 노드 개수: {domain_info.size()}개")
        print(f"    - Agent Slug: {domain_info.agent_slug}")
        print()

    # [5] Neo4j 확인
    print("=" * 80)
    print("Neo4j 데이터베이스 확인:")
    print("=" * 80)

    neo4j = Neo4jService()
    neo4j.connect()

    domain_check = neo4j.execute_query('MATCH (d:Domain) RETURN count(d) as count')
    print(f"  - Domain 노드: {domain_check[0]['count']}개")

    rel_check = neo4j.execute_query('MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) as count')
    print(f"  - BELONGS_TO_DOMAIN 관계: {rel_check[0]['count']}개")

    neo4j.disconnect()

    print("\n" + "=" * 80)
    print("✅ 멀티 에이전트 시스템(MAS) 활성화 완료!")
    print("=" * 80)
    print()
    print("다음 단계:")
    print("  1. Django 서버 재시작")
    print("  2. SSE 스트리밍에서 A2A 협업 활성화 (top_n=3)")
    print()


if __name__ == "__main__":
    main()
