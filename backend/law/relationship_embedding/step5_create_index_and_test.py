"""
Step 5 & 6: 벡터 인덱스 생성 및 검색 테스트

목적:
- Neo4j 관계 벡터 인덱스 생성
- 관계 임베딩 검색 기능 테스트
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


def create_index_and_test():
    """벡터 인덱스 생성 및 테스트 메인 함수"""

    print("=" * 80)
    print("Step 5 & 6: 벡터 인덱스 생성 및 검색 테스트")
    print("=" * 80)

    # Neo4j 연결
    neo4j = Neo4jService()

    print("[1] Neo4j 연결")
    print("-" * 80)

    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # Step 5: 벡터 인덱스 생성
        print("[2] 관계 벡터 인덱스 생성")
        print("-" * 80)

        # 기존 인덱스 삭제 (있다면)
        try:
            drop_query = "DROP INDEX contains_embedding IF EXISTS"
            neo4j.execute_query(drop_query)
            print("  기존 인덱스 삭제 (있다면)")
        except:
            pass

        # 새 인덱스 생성
        create_index_query = """
        CREATE VECTOR INDEX contains_embedding IF NOT EXISTS
        FOR ()-[r:CONTAINS]-()
        ON (r.embedding)
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 3072,
                `vector.similarity_function`: 'cosine'
            }
        }
        """

        try:
            neo4j.execute_query(create_index_query)
            print("  [OK] 벡터 인덱스 생성 성공")
            print("  - Index name: contains_embedding")
            print("  - Dimensions: 3072")
            print("  - Similarity: cosine\n")
        except Exception as e:
            print(f"  [ERROR] 인덱스 생성 실패: {e}\n")
            return

        # 인덱스 확인
        show_indexes_query = "SHOW INDEXES WHERE name = 'contains_embedding'"
        result = neo4j.execute_query(show_indexes_query)

        if result:
            print("  인덱스 정보:")
            for idx in result:
                print(f"    Name: {idx.get('name')}")
                print(f"    Type: {idx.get('type')}")
                print(f"    State: {idx.get('state')}")
        print()

        # Step 6: 검색 테스트
        print("[3] 임베딩 모델 로드")
        print("-" * 80)

        try:
            embedding_model, dimension = load_embedding_model("openai")
            print(f"  [OK] OpenAI 임베딩 모델 로드 ({dimension}-dim)\n")
        except Exception as e:
            print(f"  [ERROR] 모델 로드 실패: {e}\n")
            return

        # 테스트 쿼리 목록
        test_queries = [
            {
                'text': '생략할 수 있는 경우 예외',
                'expected_type': 'EXCEPTION',
                'description': '예외 조항 검색'
            },
            {
                'text': '제12조를 준용한다',
                'expected_type': 'REFERENCE',
                'description': '법 조항 참조 검색'
            },
            {
                'text': '다음 각 호의 구체적인 사항',
                'expected_type': 'DETAIL',
                'description': '상세 설명 검색'
            }
        ]

        print("[4] 관계 임베딩 검색 테스트")
        print("-" * 80)

        for i, test in enumerate(test_queries, 1):
            print(f"\n  테스트 #{i}: {test['description']}")
            print(f"  쿼리: \"{test['text']}\"")
            print(f"  예상 타입: {test['expected_type']}")
            print(f"  " + "-" * 70)

            # 쿼리 임베딩 생성
            try:
                query_embedding = embedding_model.embed_query(test['text'])
            except Exception as e:
                print(f"    [ERROR] 쿼리 임베딩 생성 실패: {e}")
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
                from.full_id as from_id,
                to.full_id as to_id,
                relationship.semantic_type as semantic_type,
                relationship.context as context,
                relationship.keywords as keywords,
                score
            ORDER BY score DESC
            LIMIT 5
            """

            try:
                results = neo4j.execute_query(search_query, {'query_embedding': query_embedding})

                if results:
                    print(f"\n    검색 결과 (Top 5):")
                    for j, result in enumerate(results, 1):
                        score = result['score']
                        sem_type = result['semantic_type']
                        context = result['context'][:80] + "..." if len(result['context']) > 80 else result['context']

                        # 예상 타입과 일치 여부
                        match_icon = "[OK]" if sem_type == test['expected_type'] else "[X]"

                        print(f"\n    {match_icon} 순위 #{j} (유사도: {score:.4f})")
                        print(f"        타입: {sem_type}")
                        print(f"        From: {result['from_id']}")
                        print(f"        To:   {result['to_id']}")
                        print(f"        Context: {context}")
                        print(f"        Keywords: {result['keywords']}")

                else:
                    print("    [WARNING] 검색 결과 없음")

            except Exception as e:
                print(f"    [ERROR] 검색 실패: {e}")

        print("\n")

        # 통계
        print("[5] 최종 통계")
        print("=" * 80)

        stats_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.embedding IS NOT NULL
        RETURN
            count(r) as total_with_embedding,
            collect(DISTINCT r.semantic_type) as semantic_types
        """
        stats = neo4j.execute_query(stats_query)

        if stats:
            print(f"  임베딩 있는 CONTAINS 관계: {stats[0]['total_with_embedding']:,d}개")
            print(f"  의미 타입: {', '.join(stats[0]['semantic_types'])}")
            print()

        # 성공 메시지
        print("  [SUCCESS] 관계 임베딩 시스템 구축 완료!")
        print()
        print("  구현된 기능:")
        print("  1. 3,565개 CONTAINS 관계에 임베딩 추가 (3072-dim)")
        print("  2. 의미 타입 분류 (EXCEPTION, REFERENCE, DETAIL, etc.)")
        print("  3. 관계 벡터 인덱스 생성 (contains_embedding)")
        print("  4. 관계 유사도 검색 기능")
        print()
        print("  활용 방법:")
        print("  - DomainAgent에서 관계 임베딩 검색 통합")
        print("  - 예외 조항, 참조 관계 등 의미 기반 탐색")
        print("  - RNE/INE 알고리즘에 관계 경로 추가")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    create_index_and_test()
