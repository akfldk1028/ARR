"""
실제 DomainAgent AI 질문 테스트

목적:
- GraphDB 장점을 살려서 파싱이 되는지 확인
- 관계 임베딩 + 노드 임베딩 통합 작동 검증
- 상위 조항 정보 표시 확인
"""

import os
import sys
import django
import asyncio
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.domain_agent import DomainAgent
from graph_db.services.neo4j_service import Neo4jService


async def test_domain_agent():
    """DomainAgent 실제 질문 테스트"""

    print("=" * 80)
    print("DomainAgent AI 질문 테스트 (GraphDB 장점 활용)")
    print("=" * 80)
    print()

    # Neo4j 연결
    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # [1] 도메인 정보 가져오기 (임시로 모든 HANG 노드 사용)
        print("[1] 도메인 정보 조회")
        print("-" * 80)

        # 모든 HANG 노드의 full_id 가져오기 (전체 사용)
        hang_query = """
        MATCH (hang:HANG)
        WHERE hang.embedding IS NOT NULL
        RETURN hang.full_id AS hang_id
        """
        hang_results = neo4j.execute_query(hang_query, {})

        node_ids = [r['hang_id'] for r in hang_results]

        print(f"[OK] 테스트 도메인: {len(node_ids)}개 HANG 노드 포함\n")

        # [2] DomainAgent 초기화
        print("[2] DomainAgent 초기화")
        print("-" * 80)

        domain_info = {
            'domain_id': 'test_domain_001',
            'domain_name': '법률 통합 검색 (테스트)',
            'node_ids': node_ids,
            'neighbor_agents': []
        }

        agent_config = {
            'rne_threshold': 0.75,
            'ine_k': 10
        }

        agent = DomainAgent(
            agent_slug='test-law-domain',
            agent_config=agent_config,
            domain_info=domain_info
        )

        print(f"[OK] DomainAgent 초기화 완료\n")

        # [3] 실제 질문 테스트
        print("[3] 실제 질문 테스트")
        print("=" * 80)
        print()

        test_questions = [
            "도시계획 수립은 어떻게 해야 하나요?",
            "개발행위 허가를 받아야 하는 경우는?",
            "생략할 수 있는 경우가 뭐야?",
        ]

        for i, question in enumerate(test_questions, 1):
            print(f"\n[질문 #{i}]")
            print("-" * 80)
            print(f"Q: {question}")
            print()

            # AI 응답 생성
            response = await agent._generate_response(
                user_input=question,
                context_id=f"test_context_{i}",
                session_id="test_session_001",
                user_name="테스터"
            )

            print("[AI 응답]")
            print(response)
            print()
            print("=" * 80)

        print()
        print("[4] 테스트 완료")
        print("=" * 80)
        print()
        print("[검증 항목]")
        print()
        print("1. 관계 임베딩 검색:")
        print("   - [검색 통계]에 '관계 임베딩: X개' 표시되는지 확인")
        print()
        print("2. GraphDB 경로 탐색:")
        print("   - 각 조항에 '제XX조 (제목)' 형식으로 상위 조항 표시되는지 확인")
        print("   - '상위 조항 정보 없음'이 나오지 않는지 확인")
        print()
        print("3. 통합 검색:")
        print("   - 노드 임베딩 + 관계 임베딩 + GraphDB 확장 모두 작동하는지 확인")
        print("   - [검색 통계]에 3가지 검색 방식 모두 표시되는지 확인")
        print()
        print("만약 위 3가지가 모두 확인되면:")
        print("-> [SUCCESS] AI가 GraphDB 장점을 제대로 살려서 파싱함!")
        print()
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    asyncio.run(test_domain_agent())
