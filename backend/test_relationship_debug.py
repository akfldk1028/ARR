"""
관계 임베딩 검색 디버깅
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


async def debug_relationship_search():
    """관계 검색 단계별 디버깅"""

    print("=" * 80)
    print("관계 임베딩 검색 디버깅")
    print("=" * 80)
    print()

    # Neo4j 연결
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

    print(f"[INFO] 도메인 HANG 노드: {len(node_ids)}개")
    print()

    # DomainAgent 초기화
    domain_info = {
        'domain_id': 'test',
        'domain_name': '테스트',
        'node_ids': node_ids,
        'neighbor_agents': []
    }

    agent = DomainAgent(
        agent_slug='test',
        agent_config={},
        domain_info=domain_info
    )

    # 테스트 쿼리
    query = "도시계획 수립"
    print(f"[TEST] 쿼리: '{query}'")
    print()

    # OpenAI 임베딩 생성
    print("[STEP 1] OpenAI 임베딩 생성...")
    openai_emb = await agent._generate_openai_embedding(query)
    print(f"  - 임베딩 차원: {len(openai_emb)}차원")
    print()

    # 관계 검색 실행
    print("[STEP 2] 관계 임베딩 검색 실행...")
    rel_results = await agent._search_relationships(openai_emb, limit=5)
    print(f"  - 검색 결과: {len(rel_results)}개")
    print()

    if len(rel_results) == 0:
        print("[ERROR] 관계 검색 결과가 0개입니다!")
        print()

        # 직접 Neo4j 쿼리로 테스트
        print("[DEBUG] 직접 Neo4j 쿼리 테스트...")
        direct_query = """
        CALL db.index.vector.queryRelationships(
            'contains_embedding',
            5,
            $query_embedding
        ) YIELD relationship, score
        MATCH (from)-[relationship]->(to)
        WHERE score >= 0.65
        RETURN from.full_id, to.full_id, score
        LIMIT 5
        """
        direct_results = neo4j.execute_query(direct_query, {
            'query_embedding': openai_emb
        })
        print(f"  - 직접 쿼리 결과: {len(direct_results)}개")
        for i, r in enumerate(direct_results, 1):
            print(f"    {i}. {r['from.full_id']} -> {r['to.full_id']} (score: {r['score']:.3f})")
        print()
    else:
        print("[SUCCESS] 관계 검색 성공!")
        for i, rel in enumerate(rel_results, 1):
            print(f"  {i}. {rel['from_id']} -> {rel['to_id']}")
            print(f"     Similarity: {rel['similarity']:.3f}")
            print(f"     Context: {rel['context']}")
        print()

        # HANG 노드 변환 테스트
        print("[STEP 3] HANG 노드 변환 테스트...")
        for i, rel in enumerate(rel_results, 1):
            to_id = rel['to_id']
            print(f"\n  [{i}] to_id = {to_id}")

            if '항' in to_id:
                print(f"     -> Case 1: HANG 노드 (full_id에 '항' 포함)")

                # 도메인 필터링으로 조회
                hang_query = """
                MATCH (hang:HANG {full_id: $hang_id})
                WHERE hang.full_id IN $node_ids
                RETURN hang.full_id AS hang_id
                """
                results = neo4j.execute_query(hang_query, {
                    'hang_id': to_id,
                    'node_ids': node_ids
                })

                if len(results) > 0:
                    print(f"     -> ✓ 도메인에서 발견됨")
                else:
                    print(f"     -> ✗ 도메인에서 발견 안됨")

                    # 도메인 필터 없이 조회
                    check_query = """
                    MATCH (hang:HANG {full_id: $hang_id})
                    RETURN hang.full_id AS hang_id
                    """
                    check_results = neo4j.execute_query(check_query, {'hang_id': to_id})
                    if len(check_results) > 0:
                        print(f"     -> (Neo4j에는 존재함, 도메인 필터링 문제)")
                    else:
                        print(f"     -> (Neo4j에도 없음, to_id 오류)")
            else:
                print(f"     -> Case 2: JO/HO 노드 (하위 HANG 찾기)")

                # 하위 HANG 노드 조회
                hang_query = """
                MATCH (parent {full_id: $parent_id})-[:CONTAINS*1..2]->(hang:HANG)
                WHERE hang.full_id IN $node_ids
                RETURN hang.full_id AS hang_id
                LIMIT 3
                """
                results = neo4j.execute_query(hang_query, {
                    'parent_id': to_id,
                    'node_ids': node_ids
                })

                if len(results) > 0:
                    print(f"     -> ✓ 하위 HANG {len(results)}개 발견")
                else:
                    print(f"     -> ✗ 하위 HANG 발견 안됨")

    neo4j.disconnect()
    print()
    print("=" * 80)
    print("[완료] 디버깅 종료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_relationship_search())
