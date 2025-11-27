"""
A2A 검색 테스트 - law_utils enrichment 포함
"""
import requests
import json

# Test 1: Basic search API
print("=" * 80)
print("Test 1: Search API (with enrichment)")
print("=" * 80)

response = requests.post(
    "http://localhost:8011/api/search",
    json={"query": "용도지역이 어디야?"}
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
else:
    print(f"Error: {response.text}")

# Test 2: 36조 검색 (enrichment 확인)
print("\n" + "=" * 80)
print("Test 2: 36조 검색 (article enrichment 확인)")
print("=" * 80)

response = requests.post(
    "http://localhost:8011/api/search",
    json={"query": "36조"}
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    results = data.get('results', [])

    print(f"\n총 {len(results)}개 결과 찾음\n")

    for i, result in enumerate(results[:3], 1):
        print(f"결과 {i}:")
        print(f"  article:  {result.get('article', 'N/A')}")  # ← 우리가 추가한 필드!
        print(f"  law_type: {result.get('law_type', 'N/A')}")  # ← 우리가 추가한 필드!
        print(f"  law_name: {result.get('law_name', 'N/A')}")  # ← 우리가 추가한 필드!
        print(f"  content:  {result.get('content', '')[:100]}...")
        print()
else:
    print(f"Error: {response.text}")

print("=" * 80)
