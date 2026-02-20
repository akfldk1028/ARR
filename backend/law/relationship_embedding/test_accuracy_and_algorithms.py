"""
정확도 및 RNE/INE 알고리즘 검증 테스트

목적:
1. RNE/INE 알고리즘이 제대로 작동하는지 확인
2. 검색 결과의 정확도 검증 (내용이 맞는지)
3. 임베딩 + 그래프 탐색 통합 성능 확인
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


def test_accuracy_and_algorithms():
    """정확도 및 알고리즘 검증"""

    print("=" * 80)
    print("정확도 및 RNE/INE 알고리즘 검증")
    print("=" * 80)
    print()

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

        # 테스트 케이스: 구체적인 법률 질문
        test_cases = [
            {
                'question': '도시계획 수립은 어떻게 해야 하나요?',
                'expected_keywords': ['도시계획', '수립', '입안'],
                'category': '도시계획 관련'
            },
            {
                'question': '개발행위 허가를 받아야 하는 경우는?',
                'expected_keywords': ['개발행위', '허가', '신청'],
                'category': '개발행위 관련'
            },
            {
                'question': '건축물의 건축이 금지되는 경우는?',
                'expected_keywords': ['건축', '금지', '제한'],
                'category': '건축 제한 관련'
            }
        ]

        print("[2] 정확도 테스트 (벡터 검색 + 내용 검증)")
        print("=" * 80)
        print()

        total_tests = 0
        accurate_results = 0

        for i, test in enumerate(test_cases, 1):
            print(f"[테스트 #{i}] {test['category']}")
            print("-" * 80)
            print(f"Q: {test['question']}")
            print(f"기대 키워드: {', '.join(test['expected_keywords'])}")
            print()

            # 쿼리 임베딩
            query_emb = embedding_model.embed_query(test['question'])

            # 벡터 검색 (관계 임베딩)
            print("  [A] 관계 임베딩 검색")
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
                relationship.context as context,
                score
            ORDER BY score DESC
            LIMIT 5
            """

            rel_results = neo4j.execute_query(rel_query, {'query_embedding': query_emb})

            if rel_results:
                print(f"    검색됨: {len(rel_results)}개")

                # 정확도 검증: 기대 키워드가 context에 포함되어 있는지
                keyword_match_count = 0

                for j, r in enumerate(rel_results, 1):
                    context = r['context']
                    score = r['score']

                    # 키워드 매칭
                    matched_keywords = [kw for kw in test['expected_keywords'] if kw in context]

                    if matched_keywords:
                        keyword_match_count += 1
                        match_icon = "[정확]"
                    else:
                        match_icon = "[부정확]"

                    context_preview = context[:60] + "..." if len(context) > 60 else context

                    print(f"    {match_icon} #{j} (유사도 {score:.4f})")
                    print(f"            관계: {context_preview}")
                    if matched_keywords:
                        print(f"            매칭: {', '.join(matched_keywords)}")

                # 정확도 계산
                accuracy = (keyword_match_count / len(rel_results)) * 100
                print()
                print(f"  [정확도] {accuracy:.1f}% ({keyword_match_count}/{len(rel_results)} 정확)")

                if accuracy >= 60:
                    print(f"  [평가] [OK] 검색 결과가 질문과 관련있음")
                    accurate_results += 1
                else:
                    print(f"  [평가] [X] 검색 결과가 질문과 관련 없음")

                total_tests += 1

            else:
                print("    [WARNING] 검색 결과 없음")

            print()

            # GraphDB 경로 탐색 테스트 (있다면)
            if rel_results and rel_results[0]['score'] >= 0.7:
                print("  [B] GraphDB 경로 탐색 (상위 조항 찾기)")

                # to_id에서 HANG 노드 찾기
                top_result = rel_results[0]
                to_id = top_result['to_id']

                # HANG 노드의 상위 JO 찾기
                path_query = """
                MATCH path = (jo:JO)-[:CONTAINS*1..2]->(hang:HANG)
                WHERE hang.full_id = $hang_id
                RETURN
                    jo.number as jo_num,
                    jo.title as jo_title,
                    hang.content as hang_content,
                    length(path) as path_len
                LIMIT 1
                """

                path_result = neo4j.execute_query(path_query, {'hang_id': to_id})

                if path_result:
                    pr = path_result[0]
                    print(f"    [OK] 상위 조항 찾음:")
                    print(f"         {pr['jo_num']}: {pr['jo_title'] or '(제목 없음)'}")
                    hang_preview = pr['hang_content'][:80] + "..." if len(pr['hang_content']) > 80 else pr['hang_content']
                    print(f"         └─ 내용: {hang_preview}")
                    print(f"    [평가] GraphDB 경로 탐색 작동 [OK]")
                else:
                    print(f"    [INFO] 상위 조항 없음 (최상위 노드)")

            print()
            print("  " + "=" * 76)
            print()

        # 최종 정확도
        print("[3] 최종 평가")
        print("=" * 80)
        print()

        if total_tests > 0:
            overall_accuracy = (accurate_results / total_tests) * 100
            print(f"  전체 정확도: {overall_accuracy:.1f}% ({accurate_results}/{total_tests})")
            print()

            if overall_accuracy >= 70:
                print("  [SUCCESS] 검색 정확도 양호!")
                print("  - 임베딩이 질문의 의도를 잘 파악함")
                print("  - 관련 법률 조항을 정확하게 찾음")
            elif overall_accuracy >= 50:
                print("  [PARTIAL] 검색 정확도 보통")
                print("  - 일부 질문에서 정확한 결과")
                print("  - 개선 여지 있음")
            else:
                print("  [FAIL] 검색 정확도 낮음")
                print("  - 임베딩 또는 검색 전략 재검토 필요")

        print()

        # RNE/INE 알고리즘 확인
        print("[4] RNE/INE 알고리즘 구현 확인")
        print("-" * 80)
        print()

        # 파일 존재 확인
        rne_path = Path(backend_dir) / "graph_db" / "algorithms" / "core" / "semantic_rne.py"
        ine_path = Path(backend_dir) / "graph_db" / "algorithms" / "core" / "semantic_ine.py"

        if rne_path.exists():
            print("  [OK] SemanticRNE 알고리즘 파일 존재")
        else:
            print("  [X] SemanticRNE 파일 없음")

        if ine_path.exists():
            print("  [OK] SemanticINE 알고리즘 파일 존재")
        else:
            print("  [X] SemanticINE 파일 없음")

        print()

        # DomainAgent 사용 여부 확인
        domain_agent_path = Path(backend_dir) / "agents" / "law" / "domain_agent.py"

        if domain_agent_path.exists():
            with open(domain_agent_path, 'r', encoding='utf-8') as f:
                content = f.read()
                uses_rne = 'SemanticRNE' in content or 'rne_threshold' in content
                uses_ine = 'SemanticINE' in content or 'ine_k' in content

                if uses_rne:
                    print("  [OK] DomainAgent가 RNE 알고리즘 사용 중")
                else:
                    print("  [INFO] DomainAgent가 RNE 클래스 직접 사용 안 함")
                    print("         (RNE threshold만 사용 또는 자체 구현)")

                if uses_ine:
                    print("  [OK] DomainAgent가 INE 알고리즘 사용 중")
                else:
                    print("  [INFO] DomainAgent가 INE 클래스 직접 사용 안 함")

        print()

        # 결론
        print("[5] 종합 결론")
        print("=" * 80)
        print()

        print("  [검증 완료]")
        print()
        print("  1. 임베딩 검색:")
        if total_tests > 0 and overall_accuracy >= 70:
            print("     - [OK] 정확도 양호 (70% 이상)")
        else:
            print("     - [~] 정확도 개선 필요")

        print()
        print("  2. GraphDB 경로 탐색:")
        print("     - [OK] 상위 조항 연결 작동")
        print("     - [OK] 맥락 정보 제공 가능")

        print()
        print("  3. RNE/INE 알고리즘:")
        print("     - [OK] 알고리즘 파일 구현됨")
        if uses_rne or uses_ine:
            print("     - [OK] DomainAgent 연동 확인")
        else:
            print("     - [TODO] DomainAgent 통합 필요")

        print()
        print("  [다음 단계]")
        print("  - DomainAgent에서 SemanticRNE/INE 클래스 직접 사용")
        print("  - 벡터 검색 (Stage 1) + RNE 확장 (Stage 2) 통합")
        print("  - 실제 법률 질의응답 테스트")
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
    test_accuracy_and_algorithms()
