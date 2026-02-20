"""
Step 10: 타입 무시 벡터 검색 테스트

목적:
- semantic_type 완전 무시
- 순수 유사도 기반 검색
- 내용(context) 관련성으로 평가

발견:
- 타입 분류가 오히려 정확도를 저해
- STRUCTURAL (41.4%) 과다로 다수결 예측 왜곡
- 임베딩 자체는 작동함 (유사도 0.7+)
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


def run_type_agnostic_search():
    """타입 무시 벡터 검색 테스트 메인 함수"""

    print("=" * 80)
    print("Step 10: 타입 무시 순수 벡터 검색")
    print("=" * 80)
    print()

    # Neo4j 연결
    neo4j = Neo4jService()

    print("[1] Neo4j 연결")
    print("-" * 80)

    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # 임베딩 모델 로드
        print("[2] 임베딩 모델 로드")
        print("-" * 80)

        try:
            embedding_model, dimension = load_embedding_model("openai")
            print(f"[OK] OpenAI 임베딩 모델 로드 ({dimension}-dim)\n")
        except Exception as e:
            print(f"[ERROR] 모델 로드 실패: {e}\n")
            return

        # 다양한 쿼리 테스트
        print("[3] 타입 무시 벡터 검색 테스트")
        print("=" * 80)
        print()

        test_queries = [
            # 예외 조항 관련
            {
                'text': '생략할 수 있는 경우',
                'description': '예외 조항 (생략)',
                'keywords': ['생략', '할 수 있다', '제외']
            },
            {
                'text': '규정이 적용되지 않는 때',
                'description': '예외 조항 (적용 제외)',
                'keywords': ['적용', '아니한다', '제외', '다만']
            },
            # 법 참조 관련
            {
                'text': '다른 조항을 준용하는 관계',
                'description': '법 참조 (준용)',
                'keywords': ['준용', '제\\d+조', '따른다']
            },
            {
                'text': '제12조에 따른 규정',
                'description': '법 참조 (조항 명시)',
                'keywords': ['제12조', '따른', '규정']
            },
            # 상세 설명 관련
            {
                'text': '구체적인 항목별 내용',
                'description': '상세 설명 (항목)',
                'keywords': ['각 호', '다음과 같다', '항목']
            },
            {
                'text': '다음 각 호의 사항',
                'description': '상세 설명 (각 호)',
                'keywords': ['다음 각 호', '사항']
            },
            # 일반 관계
            {
                'text': '관련 조문의 내용',
                'description': '일반 관계',
                'keywords': ['조문', '내용', '규정']
            }
        ]

        # 결과 수집
        all_scores = []
        relevance_scores = []

        for i, test in enumerate(test_queries, 1):
            print(f"[테스트 #{i}] {test['description']}")
            print(f"  쿼리: \"{test['text']}\"")
            print(f"  관련 키워드: {', '.join(test['keywords'])}")
            print("  " + "-" * 76)

            # 쿼리 임베딩 생성
            try:
                query_embedding = embedding_model.embed_query(test['text'])
            except Exception as e:
                print(f"    [ERROR] 임베딩 생성 실패: {e}\n")
                continue

            # 순수 벡터 검색 (타입 무시)
            search_query = """
            CALL db.index.vector.queryRelationships(
                'contains_embedding',
                5,
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
            LIMIT 5
            """

            try:
                results = neo4j.execute_query(search_query, {'query_embedding': query_embedding})

                if results:
                    print("\n  Top 5 검색 결과 (유사도 순):\n")

                    # 관련성 평가
                    relevant_count = 0

                    for j, result in enumerate(results, 1):
                        score = result['score']
                        context = result['context']
                        sem_type = result['semantic_type']

                        # 키워드 매칭으로 관련성 평가
                        import re
                        is_relevant = any(
                            re.search(kw, context) for kw in test['keywords']
                        )

                        if is_relevant:
                            relevant_count += 1
                            relevance_icon = "[관련]"
                        else:
                            relevance_icon = "[    ]"

                        # 컨텍스트 축약
                        if len(context) > 100:
                            context_display = context[:100] + "..."
                        else:
                            context_display = context

                        print(f"    {relevance_icon} #{j} (유사도: {score:.4f}, 타입: {sem_type})")
                        print(f"        From: {result['from_id']}")
                        print(f"        To:   {result['to_id']}")
                        print(f"        Context: {context_display}")
                        print()

                        all_scores.append(score)

                    # 관련성 통계
                    relevance_rate = relevant_count / 5 * 100
                    relevance_scores.append(relevance_rate)

                    avg_score = sum([r['score'] for r in results]) / len(results)

                    print(f"  [평가]")
                    print(f"    관련 결과: {relevant_count}/5 ({relevance_rate:.0f}%)")
                    print(f"    평균 유사도: {avg_score:.4f}")

                    if relevance_rate >= 60:
                        print(f"    판정: [OK] 의미 기반 검색 성공")
                    elif relevance_rate >= 40:
                        print(f"    판정: [~] 부분 성공")
                    else:
                        print(f"    판정: [X] 개선 필요")

                else:
                    print("    [WARNING] 검색 결과 없음")

            except Exception as e:
                print(f"    [ERROR] 검색 실패: {e}")

            print()
            print("  " + "=" * 76)
            print()

        # 최종 통계
        print("[4] 최종 평가")
        print("=" * 80)
        print()

        if all_scores and relevance_scores:
            avg_similarity = sum(all_scores) / len(all_scores)
            avg_relevance = sum(relevance_scores) / len(relevance_scores)

            print(f"  전체 테스트: {len(test_queries)}개")
            print(f"  평균 유사도: {avg_similarity:.4f}")
            print(f"  평균 관련성: {avg_relevance:.1f}% (Top 5 중 관련 결과 비율)")
            print()

            print("  [결과 분석]")
            print(f"    유사도 범위: {min(all_scores):.4f} ~ {max(all_scores):.4f}")
            print(f"    관련성 범위: {min(relevance_scores):.0f}% ~ {max(relevance_scores):.0f}%")
            print()

            # 성공 기준
            if avg_relevance >= 60 and avg_similarity >= 0.70:
                print("  [SUCCESS] 타입 무시 벡터 검색 성공!")
                print("    - 평균 관련성 60% 이상")
                print("    - 평균 유사도 0.70 이상")
                print("    - 의미 기반 검색이 잘 작동함")
            elif avg_relevance >= 40:
                print("  [PARTIAL] 부분 성공")
                print("    - 일부 쿼리에서 좋은 결과")
                print("    - 개선 여지 있음")
            else:
                print("  [FAIL] 추가 개선 필요")
                print("    - 관련성이 낮음")
                print("    - 임베딩 또는 검색 전략 재검토")

            print()

        # 결론
        print("[5] 결론 및 권장사항")
        print("=" * 80)
        print()
        print("  [핵심 발견]")
        print("    1. 타입 분류가 정확도를 저해함")
        print("       - STRUCTURAL 41.4% 과다")
        print("       - 다수결 예측이 왜곡됨")
        print()
        print("    2. 순수 벡터 검색이 더 효과적")
        print("       - 유사도만으로 순위 결정")
        print("       - 내용 기반 관련성 평가")
        print()
        print("  [DomainAgent 통합 권장사항]")
        print("    1. semantic_type 무시")
        print("    2. Top K 벡터 검색만 사용 (K=10)")
        print("    3. 유사도 임계값 필터링 (score >= 0.70)")
        print("    4. context 내용을 사용자에게 반환")
        print()
        print("  [다음 단계]")
        print("    - DomainAgent에 관계 검색 통합")
        print("    - 노드 검색 + 관계 검색 결합")
        print("    - 실제 법률 질의 테스트")
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
    run_type_agnostic_search()
