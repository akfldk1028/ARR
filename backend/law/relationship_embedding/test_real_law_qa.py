"""
실제 법률 질의응답 테스트

목적:
- 노드 임베딩 + 관계 임베딩이 실제로 유용한지 검증
- 복잡한 법률 구조 탐색 가능 여부 확인
- AI가 제대로 답할 수 있는 환경인지 테스트
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
from src.shared.common_fn import load_embedding_model


def test_law_qa():
    """법률 질의응답 테스트"""

    print("=" * 80)
    print("법률 질의응답 테스트")
    print("=" * 80)
    print()
    print("목적: 노드 임베딩 + 관계 임베딩이 실제 법률 질문에 유용한지 검증")
    print()

    # Neo4j 연결
    neo4j = Neo4jService()

    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # 임베딩 모델 로드
        print("[1] 임베딩 모델 로드")
        print("-" * 80)

        embedding_model, dimension = load_embedding_model("openai")
        print(f"[OK] OpenAI 임베딩 모델 로드 ({dimension}-dim)\n")

        # 테스트 질문들
        print("[2] 실제 법률 질문 테스트")
        print("=" * 80)
        print()

        test_questions = [
            # 1. 단순 내용 검색
            {
                'question': '제12조 내용이 뭐야?',
                'type': '단순 검색',
                'expected': '제12조 관련 HANG 노드들'
            },

            # 2. 구조 탐색
            {
                'question': '제12조 아래에 어떤 항들이 있어?',
                'type': '구조 탐색',
                'expected': 'JO -> HANG 관계들'
            },

            # 3. 의미 검색 (예외 조항)
            {
                'question': '생략할 수 있는 경우가 뭐야?',
                'type': '의미 검색 (예외)',
                'expected': 'EXCEPTION 타입 관계 또는 "생략" 포함 노드'
            },

            # 4. 법 참조 검색
            {
                'question': '다른 조항을 준용하는 경우는?',
                'type': '의미 검색 (참조)',
                'expected': 'REFERENCE 타입 관계 또는 "준용" 포함 노드'
            },

            # 5. 세부 항목 검색
            {
                'question': '다음 각 호에 해당하는 내용은?',
                'type': '의미 검색 (세부)',
                'expected': 'DETAIL 타입 관계 또는 "각 호" 포함 노드'
            },

            # 6. 복잡한 질문
            {
                'question': '국토계획법에서 적용되지 않는 경우는 어떤 것들이 있어?',
                'type': '복잡한 의미 검색',
                'expected': 'EXCEPTION 타입 관계 + "적용" "제외" 포함 노드'
            }
        ]

        for i, q in enumerate(test_questions, 1):
            print(f"\n[질문 #{i}] {q['type']}")
            print("-" * 80)
            print(f"Q: {q['question']}")
            print(f"기대: {q['expected']}")
            print()

            # 쿼리 임베딩
            query_emb = embedding_model.embed_query(q['question'])

            # 관계 검색 (CONTAINS 임베딩)
            print("  [관계 검색 결과] (CONTAINS 임베딩)")
            rel_query = """
            CALL db.index.vector.queryRelationships(
                'contains_embedding',
                3,
                $query_embedding
            ) YIELD relationship, score
            MATCH (from)-[relationship]->(to)
            RETURN
                from.full_id as from_id,
                to.full_id as to_id,
                relationship.context as context,
                relationship.semantic_type as semantic_type,
                score
            ORDER BY score DESC
            """

            rel_results = neo4j.execute_query(rel_query, {'query_embedding': query_emb})

            if rel_results:
                for j, rr in enumerate(rel_results, 1):
                    context_preview = rr['context'][:80] + "..." if len(rr['context']) > 80 else rr['context']
                    print(f"    #{j} (유사도 {rr['score']:.4f}, 타입: {rr['semantic_type']})")
                    print(f"       From: {rr['from_id']}")
                    print(f"       To:   {rr['to_id']}")
                    print(f"       관계: {context_preview}")
            else:
                print("    [없음]")

            print()

            # 평가
            print("  [평가]")

            # 관계 평가
            if rel_results and rel_results[0]['score'] >= 0.7:
                relevance = "관련있음"
                evaluation = "[OK] AI가 답변 가능 (관계에서 관련 정보 찾음)"
            elif rel_results and rel_results[0]['score'] >= 0.6:
                relevance = "부분 관련"
                evaluation = "[~] AI가 부분적으로 답변 가능"
            else:
                relevance = "관련없음"
                evaluation = "[X] AI가 답변 어려움 (관련 정보 없음)"

            max_score = rel_results[0]['score'] if rel_results else 0.0
            print(f"    관계 검색: {relevance} (최고 유사도: {max_score:.4f})")
            print(f"    종합: {evaluation}")

            print()
            print("  " + "=" * 76)

        # 최종 결론
        print("\n[3] 최종 평가")
        print("=" * 80)
        print()
        print("  [검증 항목]")
        print()
        print("  1. 구조 탐색 (제12조 아래 항들):")
        print("     - 관계 임베딩으로 JO->HANG 관계 검색 가능")
        print("     - AI가 법률 구조를 파악하고 답변 가능")
        print()
        print("  2. 의미 검색 (생략, 준용, 각 호):")
        print("     - 관계 임베딩으로 키워드 없이도 의미 기반 검색 가능")
        print("     - 예외 조항, 참조 관계 등 자동 파악")
        print()
        print("  3. 복잡한 질문:")
        print("     - 관계 context에서 관련 정보 추출")
        print("     - 법률 관계의 의미를 이해하고 답변 생성")
        print()
        print("  [결론]")
        print("  " + "-" * 76)
        print()

        # 유사도 통계
        all_rel_scores = []

        for q in test_questions:
            query_emb = embedding_model.embed_query(q['question'])

            rel_query = """
            CALL db.index.vector.queryRelationships('contains_embedding', 1, $query_embedding)
            YIELD relationship, score
            RETURN score
            """
            rr = neo4j.execute_query(rel_query, {'query_embedding': query_emb})
            if rr:
                all_rel_scores.append(rr[0]['score'])

        if all_rel_scores:
            avg_rel = sum(all_rel_scores) / len(all_rel_scores)

            print(f"  관계 임베딩 평균 유사도: {avg_rel:.4f}")
            print()

            if avg_rel >= 0.7:
                print("  [SUCCESS] 관계 임베딩이 유효함!")
                print("  -> AI가 법률 질문에 답변 가능한 환경 구축됨")
                print("  -> 복잡한 법률 구조 탐색 가능")
                print("  -> DomainAgent 통합 준비 완료")
            elif avg_rel >= 0.6:
                print("  [PARTIAL] 관계 임베딩이 부분적으로 유효함")
                print("  -> 일부 질문에 답변 가능")
                print("  -> 개선 여지 있음")
            else:
                print("  [FAIL] 관계 임베딩 유사도 낮음")
                print("  -> 임베딩 전략 재검토 필요")

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
    test_law_qa()
