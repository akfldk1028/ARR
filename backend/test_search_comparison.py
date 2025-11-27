"""17조 검색 비교 테스트"""
import requests
import json

BASE_URL = "http://localhost:8000/agents/law/api/search"

test_queries = [
    {
        "name": "현재 쿼리 (잘못된 결과)",
        "query": "국토계획법 17조",
        "limit": 5
    },
    {
        "name": "실제 17조 내용 키워드",
        "query": "도시관리계획 수립",
        "limit": 5
    },
    {
        "name": "조합 쿼리",
        "query": "제17조 도시관리계획",
        "limit": 5
    },
    {
        "name": "더 구체적인 쿼리",
        "query": "도시관리계획을 수립하거나 변경하는 경우",
        "limit": 5
    }
]

for test in test_queries:
    print(f"\n{'='*80}")
    print(f"테스트: {test['name']}")
    print(f"쿼리: {test['query']}")
    print('='*80)

    try:
        response = requests.post(
            BASE_URL,
            json={"query": test["query"], "limit": test["limit"]},
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

        if response.status_code == 200:
            result = response.json()

            # 결과 요약 출력
            if 'search_response' in result:
                search_resp = result['search_response']
                print(f"\n라우팅 도메인: {search_resp.get('domain_id', 'N/A')}")
                print(f"총 결과: {len(search_resp.get('results', []))}개")

                # 상위 5개 결과 출력
                for i, r in enumerate(search_resp.get('results', [])[:5], 1):
                    print(f"\n{i}. full_id: {r.get('full_id', 'N/A')}")
                    print(f"   score: {r.get('score', 0):.4f}")
                    print(f"   내용 (처음 100자): {r.get('content', '')[:100]}")

                    # 제4절 (부칙) 체크
                    if '제4절' in r.get('full_id', ''):
                        print(f"   ⚠️  WARNING: 부칙(제4절) 결과!")

                    # 17조 체크
                    if '제17조' in r.get('full_id', ''):
                        print(f"   ✅ 17조 발견!")
            else:
                print(f"에러: {result}")
        else:
            print(f"HTTP 에러: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"예외 발생: {e}")

print(f"\n{'='*80}")
print("테스트 완료")
print('='*80)
