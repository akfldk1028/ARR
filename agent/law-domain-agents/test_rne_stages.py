"""
RNE Stage 테스트 - stages 정보 확인
"""

import requests
import json

BASE_URL = "http://localhost:8011"

def test_search_with_stages(query: str):
    """검색하고 stages 정보 출력"""
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"{'='*70}")

    payload = {"query": query, "limit": 10}
    response = requests.post(
        f"{BASE_URL}/api/domain/domain_09b3af0d/search",
        json=payload
    )

    if response.status_code != 200:
        print(f"[ERROR] Status: {response.status_code}")
        print(response.text)
        return

    data = response.json()
    print(f"Results: {len(data['results'])}")
    print(f"Response time: {data.get('response_time', 'N/A')}ms")

    # stages 통계
    stage_counts = {}
    for result in data['results']:
        for stage in result.get('stages', []):
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print(f"\nStages:")
    for stage, count in stage_counts.items():
        print(f"  - {stage}: {count}개")

    # 첫 3개 결과 상세
    print(f"\nTop 3 results:")
    for i, result in enumerate(data['results'][:3], 1):
        print(f"{i}. {result['hang_id']}")
        print(f"   Similarity: {result['similarity']:.3f}")
        print(f"   Stages: {result['stages']}")
        print(f"   Content: {result['content'][:60]}...")


if __name__ == "__main__":
    print("="*70)
    print("     RNE Stage Test")
    print("="*70)

    # Test 1: 결과가 나오는 쿼리
    test_search_with_stages("용도지역")

    # Test 2: 복합 쿼리
    test_search_with_stages("개발행위허가와 용도지역의 관계")

    # Test 3: 조문 번호
    test_search_with_stages("제56조")

    print(f"\n{'='*70}")
    print("[DONE] RNE Stage Test Complete")
    print("="*70)
