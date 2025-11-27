"""
"다른 조항을 준용하는 경우는?" 쿼리의 실제 검색 결과 검증

목적:
- 관계 검색 결과의 to_id HANG 노드 content 확인
- 정말 "준용"과 관련있는 내용인지 검증
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
from src.shared.common_fn import load_embedding_model


def verify_reference_search():
    """준용 검색 결과 검증"""

    print("=" * 80)
    print("준용 검색 결과 검증")
    print("=" * 80)
    print()

    # Neo4j 연결
    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    # 임베딩 모델 로드
    print("[1] 임베딩 모델 로드")
    embedding_model, dimension = load_embedding_model("openai")
    print(f"[OK] OpenAI {dimension}-dim")
    print()

    # 테스트 쿼리
    query = "다른 조항을 준용하는 경우는?"
    print(f"[2] 쿼리: \"{query}\"")
    print("-" * 80)
    print()

    # 쿼리 임베딩
    query_emb = embedding_model.embed_query(query)

    # 관계 검색
    rel_query = """
    CALL db.index.vector.queryRelationships(
        'contains_embedding',
        5,
        $query_embedding
    ) YIELD relationship, score
    MATCH (from)-[relationship]->(to)
    RETURN
        from.full_id as from_id,
        to.full_id as to_id,
        relationship.context as rel_context,
        relationship.semantic_type as semantic_type,
        score
    ORDER BY score DESC
    """

    rel_results = neo4j.execute_query(rel_query, {'query_embedding': query_emb})

    print(f"[3] 관계 검색 결과 (Top-{len(rel_results)})")
    print("=" * 80)
    print()

    for i, rel in enumerate(rel_results, 1):
        print(f"[검색 결과 #{i}]")
        print(f"  유사도: {rel['score']:.4f}")
        print(f"  타입: {rel['semantic_type']}")
        print(f"  From: {rel['from_id']}")
        print(f"  To: {rel['to_id']}")
        print(f"  관계 Context: {rel['rel_context'][:100]}...")
        print()

        # to_id가 HANG 노드인지 확인
        to_id = rel['to_id']

        # HANG 노드 content 가져오기
        if '항' in to_id or 'HANG' in to_id.upper():
            hang_query = """
            MATCH (hang:HANG {full_id: $hang_id})
            RETURN hang.content as content
            """
            hang_results = neo4j.execute_query(hang_query, {'hang_id': to_id})

            if hang_results:
                content = hang_results[0]['content']
                print(f"  [HANG 노드 실제 Content]:")
                print(f"  {content[:200]}...")
                print()

                # "준용" 키워드 확인
                if '준용' in content:
                    print(f"  [OK] '준용' 키워드 포함!")
                else:
                    print(f"  [X] '준용' 키워드 없음")
            else:
                print(f"  [WARN] HANG 노드를 찾을 수 없음")
        else:
            # HANG이 아닌 경우 (JO, HO 등)
            print(f"  [INFO] to_id는 HANG이 아님 (JO/HO/etc)")

            # 하위 HANG 노드 찾기
            sub_hang_query = """
            MATCH (parent {full_id: $parent_id})-[:CONTAINS*1..2]->(hang:HANG)
            RETURN hang.full_id as hang_id, hang.content as content
            LIMIT 3
            """
            sub_results = neo4j.execute_query(sub_hang_query, {'parent_id': to_id})

            if sub_results:
                print(f"  [하위 HANG 노드들]:")
                for j, sub in enumerate(sub_results, 1):
                    print(f"    #{j} {sub['hang_id']}")
                    print(f"       {sub['content'][:100]}...")
                    if '준용' in sub['content']:
                        print(f"       [OK] '준용' 키워드 포함!")
                    else:
                        print(f"       [X] '준용' 키워드 없음")

        print()
        print("-" * 80)
        print()

    # 최종 평가
    print("[4] 최종 평가")
    print("=" * 80)
    print()
    print("질문: \"다른 조항을 준용하는 경우는?\"")
    print()
    print("결과 분석:")
    print("- 관계 context에 '준용' 키워드가 있는지")
    print("- to_id HANG 노드 content에 '준용' 키워드가 있는지")
    print("- DomainAgent가 LLM에게 전달할 content가 질문과 관련있는지")
    print()

    neo4j.disconnect()


if __name__ == "__main__":
    verify_reference_search()
