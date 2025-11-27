"""
DomainAgent 전체 데이터 테스트 (1477개 HANG 노드)
관계 임베딩 검색 확인
"""

import os
import sys
import django
import asyncio
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.domain_agent import DomainAgent
from graph_db.services.neo4j_service import Neo4jService


async def test_with_full_dataset():
    print("=" * 80)
    print("DomainAgent 전체 데이터 테스트 (관계 임베딩 확인)")
    print("=" * 80)
    print()

    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    # 전체 HANG 노드 가져오기
    hang_query = """
    MATCH (hang:HANG)
    WHERE hang.embedding IS NOT NULL
    RETURN hang.full_id AS hang_id
    """
    hang_results = neo4j.execute_query(hang_query, {})
    node_ids = [r['hang_id'] for r in hang_results]

    print(f"[OK] 전체 HANG 노드: {len(node_ids)}개")
    print()

    # DomainAgent 초기화
    domain_info = {
        'domain_id': 'full_domain',
        'domain_name': '법률 전체 검색',
        'node_ids': node_ids,
        'neighbor_agents': []
    }

    agent_config = {
        'rne_threshold': 0.65,  # threshold 낮춤 (0.75 → 0.65)
        'ine_k': 10
    }

    agent = DomainAgent(
        agent_slug='full-law-domain',
        agent_config=agent_config,
        domain_info=domain_info
    )

    print("[OK] DomainAgent 초기화 완료")
    print()

    # 테스트 질문
    questions = [
        "도시계획 수립은 어떻게 해야 하나요?",
        "개발행위 허가를 받아야 하는 경우는?",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n[질문 #{i}]")
        print("-" * 80)
        print(f"Q: {question}")
        print()

        # 응답 생성
        response = await agent._generate_response(
            user_input=question,
            context_id=f'test_full_{i}',
            session_id='test_session',
            user_name='테스터'
        )

        print("[AI 응답]")
        print(response)
        print()
        print("=" * 80)

    print()
    print("[검증 포인트]")
    print("- 관계 임베딩 검색 결과가 표시되는지 확인")
    print("- [검색 통계]에 '관계 임베딩: X개' (X > 0) 확인")
    print()

    neo4j.disconnect()


if __name__ == "__main__":
    asyncio.run(test_with_full_dataset())
