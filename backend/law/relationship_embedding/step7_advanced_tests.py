"""
Step 7: 고급 검증 테스트 (패턴 없는 자연어)

목적:
- 패턴 기반 과적합 검증
- 순수 의미 기반 검색 성능 평가
- 실제 사용 시나리오 시뮬레이션
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


def run_advanced_tests():
    """고급 검증 테스트 메인 함수"""

    print("=" * 80)
    print("Step 7: 고급 검증 테스트 (패턴 없는 자연어)")
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

        # 패턴 없는 자연어 테스트 케이스
        print("[3] 패턴 없는 자연어 테스트")
        print("=" * 80)
        print()

        test_cases = [
            # EXCEPTION 타입 (예외 조항)
            {
                'category': 'EXCEPTION',
                'queries': [
                    {
                        'text': '의무를 면제받을 수 있는 상황',
                        'description': '예외 조항 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '규정이 적용되지 않는 때',
                        'description': '예외 조항 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '특별히 허용되는 조건',
                        'description': '예외 조항 (패턴 없음)',
                        'has_pattern': False
                    },
                    # 대조군: 패턴 있음
                    {
                        'text': '다만 제외되는 경우',
                        'description': '예외 조항 (패턴 있음 - 대조군)',
                        'has_pattern': True
                    }
                ]
            },
            # REFERENCE 타입 (법 조항 참조)
            {
                'category': 'REFERENCE',
                'queries': [
                    {
                        'text': '다른 조항과의 연결 관계',
                        'description': '법 참조 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '상위 규정과의 관련성',
                        'description': '법 참조 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '유사한 법률 내용',
                        'description': '법 참조 (패턴 없음)',
                        'has_pattern': False
                    },
                    # 대조군: 패턴 있음
                    {
                        'text': '제5조를 준용한다',
                        'description': '법 참조 (패턴 있음 - 대조군)',
                        'has_pattern': True
                    }
                ]
            },
            # DETAIL 타입 (상세 설명)
            {
                'category': 'DETAIL',
                'queries': [
                    {
                        'text': '구체적인 하위 내용',
                        'description': '상세 설명 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '세부 구분 사항',
                        'description': '상세 설명 (패턴 없음)',
                        'has_pattern': False
                    },
                    {
                        'text': '항목별 설명',
                        'description': '상세 설명 (패턴 없음)',
                        'has_pattern': False
                    },
                    # 대조군: 패턴 있음
                    {
                        'text': '다음 각 호와 같다',
                        'description': '상세 설명 (패턴 있음 - 대조군)',
                        'has_pattern': True
                    }
                ]
            }
        ]

        # 테스트 실행
        overall_results = {
            'pattern_free': {'total': 0, 'correct': 0, 'scores': []},
            'with_pattern': {'total': 0, 'correct': 0, 'scores': []}
        }

        for category_test in test_cases:
            category = category_test['category']

            print(f"[{category}] 카테고리 테스트")
            print("-" * 80)
            print()

            for query_info in category_test['queries']:
                query_text = query_info['text']
                has_pattern = query_info['has_pattern']
                description = query_info['description']

                print(f"  쿼리: \"{query_text}\"")
                print(f"  설명: {description}")
                print(f"  예상 타입: {category}")
                print()

                # 임베딩 생성
                try:
                    query_embedding = embedding_model.embed_query(query_text)
                except Exception as e:
                    print(f"    [ERROR] 임베딩 생성 실패: {e}\n")
                    continue

                # 벡터 검색
                search_query = """
                CALL db.index.vector.queryRelationships(
                    'contains_embedding',
                    5,
                    $query_embedding
                ) YIELD relationship, score
                MATCH (from)-[relationship]->(to)
                RETURN
                    relationship.semantic_type as semantic_type,
                    score
                ORDER BY score DESC
                LIMIT 5
                """

                try:
                    results = neo4j.execute_query(search_query, {'query_embedding': query_embedding})

                    if results:
                        # Top 5 타입 분포
                        type_counts = {}
                        scores = []
                        for r in results:
                            sem_type = r['semantic_type']
                            score = r['score']
                            type_counts[sem_type] = type_counts.get(sem_type, 0) + 1
                            scores.append(score)

                        # 가장 많은 타입
                        top_type = max(type_counts.items(), key=lambda x: x[1])
                        predicted_type = top_type[0]
                        count = top_type[1]
                        avg_score = sum(scores) / len(scores)

                        # 정확도 계산
                        is_correct = predicted_type == category
                        result_icon = "[OK]" if is_correct else "[X]"

                        print(f"    {result_icon} 예측 타입: {predicted_type} ({count}/5)")
                        print(f"    평균 유사도: {avg_score:.4f}")
                        print(f"    Top 5 분포: {dict(type_counts)}")

                        # 통계 수집
                        if has_pattern:
                            overall_results['with_pattern']['total'] += 1
                            if is_correct:
                                overall_results['with_pattern']['correct'] += 1
                            overall_results['with_pattern']['scores'].append(avg_score)
                        else:
                            overall_results['pattern_free']['total'] += 1
                            if is_correct:
                                overall_results['pattern_free']['correct'] += 1
                            overall_results['pattern_free']['scores'].append(avg_score)

                    else:
                        print("    [WARNING] 검색 결과 없음")

                except Exception as e:
                    print(f"    [ERROR] 검색 실패: {e}")

                print()

            print()

        # 최종 통계
        print("[4] 최종 결과 분석")
        print("=" * 80)
        print()

        # 패턴 없는 쿼리 성능
        pf = overall_results['pattern_free']
        if pf['total'] > 0:
            pf_accuracy = pf['correct'] / pf['total'] * 100
            pf_avg_score = sum(pf['scores']) / len(pf['scores']) if pf['scores'] else 0

            print("  [패턴 없는 자연어 쿼리]")
            print(f"    총 테스트: {pf['total']}개")
            print(f"    정확: {pf['correct']}개")
            print(f"    오류: {pf['total'] - pf['correct']}개")
            print(f"    정확도: {pf_accuracy:.1f}%")
            print(f"    평균 유사도: {pf_avg_score:.4f}")
            print()

        # 패턴 있는 쿼리 성능 (대조군)
        wp = overall_results['with_pattern']
        if wp['total'] > 0:
            wp_accuracy = wp['correct'] / wp['total'] * 100
            wp_avg_score = sum(wp['scores']) / len(wp['scores']) if wp['scores'] else 0

            print("  [패턴 있는 쿼리 (대조군)]")
            print(f"    총 테스트: {wp['total']}개")
            print(f"    정확: {wp['correct']}개")
            print(f"    오류: {wp['total'] - wp['correct']}개")
            print(f"    정확도: {wp_accuracy:.1f}%")
            print(f"    평균 유사도: {wp_avg_score:.4f}")
            print()

        # 비교 분석
        print("  [비교 분석]")
        if pf['total'] > 0 and wp['total'] > 0:
            accuracy_diff = wp_accuracy - pf_accuracy
            score_diff = wp_avg_score - pf_avg_score

            print(f"    정확도 차이: {accuracy_diff:+.1f}% (패턴 있음 - 패턴 없음)")
            print(f"    유사도 차이: {score_diff:+.4f}")
            print()

            if accuracy_diff > 20:
                print("    [WARNING] 패턴 기반 과적합 의심!")
                print("    → 패턴 없는 쿼리 정확도가 20% 이상 낮음")
            elif accuracy_diff > 10:
                print("    [CAUTION] 패턴 의존도 높음")
                print("    → 패턴 없는 쿼리 정확도가 10% 이상 낮음")
            else:
                print("    [OK] 과적합 위험 낮음")
                print("    → 패턴 유무에 관계없이 일관된 성능")

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
    run_advanced_tests()
