"""
Quick query test - 직접 검색 결과 확인
"""
import sys
import requests
import json

# UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def search(query: str, limit: int = 3):
    """Search API 호출"""
    print(f"\n{'='*80}")
    print(f"검색어: '{query}'")
    print(f"{'='*80}\n")

    try:
        response = requests.post(
            "http://localhost:8011/api/search",
            json={"query": query, "limit": limit},
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        print(f"✅ {len(data['results'])} 개 결과 발견")
        print(f"도메인: {data.get('domain_name', 'N/A')}")
        print(f"응답시간: {data.get('response_time', 0)}ms\n")

        for i, result in enumerate(data['results'], 1):
            print(f"[{i}] {result.get('article', 'N/A')}")
            print(f"    법령: {result.get('law_name', 'N/A')}")
            print(f"    유형: {result.get('law_type', 'N/A')}")
            print(f"    유사도: {result.get('similarity', 0):.3f}")
            print(f"    내용: {result.get('content', '')[:100]}...")
            print()

        return data

    except Exception as e:
        print(f"❌ 검색 실패: {e}")
        return None

if __name__ == "__main__":
    # 여러 쿼리 테스트
    queries = ["36조", "용도지역", "개발행위허가"]

    for query in queries:
        search(query, limit=3)
