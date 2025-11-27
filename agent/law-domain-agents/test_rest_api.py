"""
Agent Server REST API Test

프론트엔드와 동일한 방식으로 REST API 테스트
"""

import requests
import json

BASE_URL = "http://localhost:8011"


def test_api_health():
    """Test: GET /api/health"""
    print("\n" + "="*70)
    print("TEST 1: GET /api/health")
    print("="*70)

    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def test_api_domains():
    """Test: GET /api/domains"""
    print("\n" + "="*70)
    print("TEST 2: GET /api/domains")
    print("="*70)

    response = requests.get(f"{BASE_URL}/api/domains")
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Total domains: {data['total']}")
    for domain in data['domains']:
        print(f"  - {domain['domain_name']} ({domain['node_count']} nodes)")


def test_api_search():
    """Test: POST /api/search"""
    print("\n" + "="*70)
    print("TEST 3: POST /api/search")
    print("="*70)

    payload = {
        "query": "도시관리계획이란 무엇인가요?",
        "limit": 5
    }

    response = requests.post(f"{BASE_URL}/api/search", json=payload)
    data = response.json()

    print(f"Status: {response.status_code}")
    print(f"\nQuery: {payload['query']}")
    print(f"Results: {len(data['results'])}")
    print(f"Domain: {data['domain_name']}")
    print(f"Response time: {data['response_time']}ms")

    print(f"\nStats:")
    stats = data['stats']
    print(f"  - Total: {stats['total']}")
    print(f"  - Vector: {stats['vector_count']}")
    print(f"  - Relationship: {stats['relationship_count']}")
    print(f"  - Graph expansion: {stats['graph_expansion_count']}")

    if data['results']:
        print(f"\nFirst result:")
        result = data['results'][0]
        print(f"  - Hang ID: {result['hang_id']}")
        print(f"  - Content: {result['content'][:100]}...")
        print(f"  - Similarity: {result['similarity']:.3f}")
        print(f"  - Stages: {result['stages']}")


def test_api_domain_search():
    """Test: POST /api/domain/{domain_id}/search"""
    print("\n" + "="*70)
    print("TEST 4: POST /api/domain/{domain_id}/search")
    print("="*70)

    # 첫 번째 도메인 ID 가져오기
    domains_response = requests.get(f"{BASE_URL}/api/domains")
    domain_id = domains_response.json()['domains'][0]['domain_id']

    payload = {
        "query": "용도지역이란 무엇인가요?",
        "limit": 5
    }

    response = requests.post(f"{BASE_URL}/api/domain/{domain_id}/search", json=payload)
    data = response.json()

    print(f"Status: {response.status_code}")
    print(f"\nDomain ID: {domain_id}")
    print(f"Query: {payload['query']}")
    print(f"Results: {len(data['results'])}")
    print(f"Response time: {data['response_time']}ms")


def run_all_tests():
    """모든 테스트 실행"""
    print("="*70)
    print("     Agent Server REST API Test")
    print("="*70)

    try:
        test_api_health()
        test_api_domains()
        test_api_search()
        test_api_domain_search()

        print("\n" + "="*70)
        print("[SUCCESS] All REST API tests passed!")
        print("="*70)

        print("\n[Next Steps]")
        print("1. Update frontend VITE_BACKEND_URL to http://localhost:8011")
        print("2. Test in browser at http://localhost:5173/#/law")
        print("3. Verify RNE/INE algorithms working correctly")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to Agent server.")
        print(f"Check if server is running at {BASE_URL}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
