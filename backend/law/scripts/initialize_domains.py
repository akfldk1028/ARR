"""
AgentManager 초기화 스크립트

기존 HANG 노드로부터 도메인 자동 생성:
- K-means 클러스터링
- LLM으로 도메인 이름 생성
- DomainAgent 인스턴스 생성
- Neo4j에 Domain 노드 + BELONGS_TO_DOMAIN 관계 생성
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.agent_manager import AgentManager


def main():
    print("=" * 80)
    print("AgentManager 초기화 - 도메인 자동 생성")
    print("=" * 80)

    print("\n[1/2] AgentManager 인스턴스 생성 중...")
    manager = AgentManager()

    print(f"\n[2/2] 초기화 완료!")
    print(f"  - 생성된 도메인: {len(manager.domains)}개")

    for domain_id, domain_info in manager.domains.items():
        print(f"    • {domain_info.domain_name}: {domain_info.size()}개 노드")

    print("\n" + "=" * 80)
    print("✅ 완료! Neo4j에 Domain 노드가 생성되었습니다.")
    print("=" * 80)

    # Neo4j 확인
    from graph_db.services import Neo4jService
    neo4j = Neo4jService()
    neo4j.connect()

    result = neo4j.execute_query('MATCH (d:Domain) RETURN count(d) as count')
    print(f"\n📊 Neo4j 확인:")
    print(f"  - Domain 노드: {result[0]['count']}개")

    rel_result = neo4j.execute_query('MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) as count')
    print(f"  - BELONGS_TO_DOMAIN 관계: {rel_result[0]['count']}개")

    neo4j.disconnect()


if __name__ == "__main__":
    main()
