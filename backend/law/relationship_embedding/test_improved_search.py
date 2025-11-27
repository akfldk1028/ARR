"""
개선된 관계 검색 테스트
- Top-K 증가 (5 → 20)
- 다양성 필터링
- 유사도 임계값 조정
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


def improved_relationship_search(neo4j, embedding_model, query, top_k=20, threshold=0.70):
    """
    개선된 관계 검색

    Args:
        neo4j: Neo4j 서비스
        embedding_model: 임베딩 모델
        query: 검색 쿼리
        top_k: 검색할 최대 개수 (기존 5 → 20으로 증가)
        threshold: 유사도 임계값
    """
    # 1. 쿼리 임베딩
    query_embedding = embedding_model.embed_query(query)

    # 2. 벡터 검색 (Top-K 증가)
    cypher = """
    CALL db.index.vector.queryRelationships(
        'contains_embedding',
        $top_k,
        $query_embedding
    ) YIELD relationship, score
    WHERE score >= $threshold
    MATCH (from)-[relationship]->(to)
    RETURN
        from.full_id as from_id,
        to.full_id as to_id,
        relationship.context as context,
        relationship.semantic_type as semantic_type,
        score
    ORDER BY score DESC
    """

    results = neo4j.execute_query(cypher, {
        'query_embedding': query_embedding,
        'top_k': top_k,
        'threshold': threshold
    })

    return results


def diverse_filtering(results, diversity_weight=0.3):
    """
    다양성 필터링: 같은 타입이 연속으로 나오지 않도록

    Args:
        results: 검색 결과 리스트
        diversity_weight: 다양성 가중치
    """
    if not results:
        return []

    filtered = [results[0]]  # 첫 번째는 무조건 포함
    seen_types = {results[0]['semantic_type']}

    for r in results[1:]:
        # 새로운 타입이면 우선 추가
        if r['semantic_type'] not in seen_types:
            filtered.append(r)
            seen_types.add(r['semantic_type'])
        # 같은 타입이지만 유사도가 높으면 추가
        elif r['score'] >= filtered[0]['score'] - 0.05:  # 최고점 대비 -0.05 이내
            filtered.append(r)

        if len(filtered) >= 10:  # 최대 10개
            break

    return filtered


def test_improved_search():
    """개선된 검색 테스트"""
    print("=" * 80)
    print("개선된 관계 검색 테스트")
    print("=" * 80)
    print()

    # 1. 초기화
    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[1] 임베딩 모델 로드")
    print("-" * 80)
    embedding_model, dimension = load_embedding_model("openai")
    print(f"[OK] OpenAI text-embedding-3-large (dimension: {dimension})")
    print()

    # 2. 테스트 쿼리
    test_cases = [
        {
            'query': '제12조를 준용한다',
            'expected_types': ['REFERENCE', 'STRUCTURAL'],
            'description': 'REFERENCE 검색 (이전 실패)'
        },
        {
            'query': '생략할 수 있는 경우',
            'expected_types': ['EXCEPTION'],
            'description': 'EXCEPTION 검색 (이전 성공)'
        },
        {
            'query': '다음 각 호의 사항',
            'expected_types': ['DETAIL'],
            'description': 'DETAIL 검색 (이전 성공)'
        }
    ]

    print("[2] 개선 전후 비교")
    print("=" * 80)
    print()

    for i, test in enumerate(test_cases, 1):
        query = test['query']
        expected = test['expected_types']
        desc = test['description']

        print(f"[테스트 #{i}] {desc}")
        print(f"쿼리: \"{query}\"")
        print(f"기대 타입: {', '.join(expected)}")
        print("-" * 80)

        # 기존 방식 (Top-5)
        print("\n  [기존 방식] Top-5, 타입 무시")
        results_old = improved_relationship_search(
            neo4j, embedding_model, query,
            top_k=5, threshold=0.70
        )

        print(f"    검색 결과: {len(results_old)}개")
        if results_old:
            type_dist = {}
            for r in results_old:
                t = r['semantic_type']
                type_dist[t] = type_dist.get(t, 0) + 1

            print("    타입 분포:", end=" ")
            for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
                print(f"{t}({c})", end=" ")
            print()

            # 최고 유사도
            print(f"    최고 유사도: {results_old[0]['score']:.4f}")

            # 기대 타입 포함 여부
            found = any(r['semantic_type'] in expected for r in results_old)
            print(f"    기대 타입 포함: {'YES' if found else 'NO'}")

        # 개선 방식 (Top-20 + 다양성 필터링)
        print("\n  [개선 방식] Top-20, 다양성 필터링")
        results_new = improved_relationship_search(
            neo4j, embedding_model, query,
            top_k=20, threshold=0.65  # 임계값 약간 낮춤
        )
        results_filtered = diverse_filtering(results_new)

        print(f"    검색 결과: {len(results_new)}개 → 필터링 후 {len(results_filtered)}개")
        if results_filtered:
            type_dist = {}
            for r in results_filtered:
                t = r['semantic_type']
                type_dist[t] = type_dist.get(t, 0) + 1

            print("    타입 분포:", end=" ")
            for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
                print(f"{t}({c})", end=" ")
            print()

            print(f"    최고 유사도: {results_filtered[0]['score']:.4f}")

            found = any(r['semantic_type'] in expected for r in results_filtered)
            print(f"    기대 타입 포함: {'YES' if found else 'NO'}")

            # 기대 타입 순위
            for r in results_filtered:
                if r['semantic_type'] in expected:
                    rank = results_filtered.index(r) + 1
                    print(f"    기대 타입 순위: #{rank} (유사도 {r['score']:.4f})")
                    print(f"    Context: {r['context'][:100]}...")
                    break

        print("\n" + "=" * 80 + "\n")

    # 3. 통계
    print("[3] 결론")
    print("=" * 80)
    print()
    print("[OK] 개선 사항:")
    print("  1. Top-K 증가 (5 -> 20): 더 많은 후보 검토")
    print("  2. 다양성 필터링: 타입 쏠림 방지")
    print("  3. 유사도 임계값 조정: 0.70 -> 0.65 (더 많은 결과)")
    print()
    print("[NOTE] 권장사항:")
    print("  - semantic_type은 참고용으로만 사용")
    print("  - context 내용을 LLM이 직접 판단")
    print("  - 사용자에게 Top-10 결과 모두 제시")
    print()

    neo4j.disconnect()


if __name__ == "__main__":
    test_improved_search()
