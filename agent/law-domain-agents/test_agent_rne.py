"""
Agent Server RNE/INE Algorithm Test

백엔드 domain_agent.py에서 추출한 law_search_engine.py의
RNE/INE 알고리즘이 제대로 작동하는지 검증

테스트 항목:
1. Exact Match (조문 번호 검색)
2. Vector Search (KR-SBERT 768-dim)
3. Relationship Search (OpenAI 3072-dim)
4. RNE Graph Expansion
5. Reciprocal Rank Fusion
"""

import requests
import json
from typing import Dict, Any

# Agent 서버 설정
AGENT_SERVER = "http://localhost:8011"
FIRST_DOMAIN_SLUG = "domain_domain_09b3af0d"  # 첫 번째 도메인 (국토 계획 및 이용)

def send_a2a_message(domain_slug: str, query: str) -> Dict[str, Any]:
    """A2A JSON-RPC 메시지 전송"""
    url = f"{AGENT_SERVER}/messages/{domain_slug}"

    request_payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "parts": [{"kind": "text", "text": query}]
            }
        },
        "id": f"test-{query[:10]}"
    }

    response = requests.post(url, json=request_payload, timeout=60)
    return response.json()


def analyze_search_response(query: str, response: Dict[str, Any]):
    """검색 응답 분석"""
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"{'='*70}")

    if "error" in response and response["error"]:
        print(f"[ERROR] {response['error']}")
        return

    result = response.get("result", {})
    parts = result.get("parts", [])

    if not parts:
        print("[ERROR] No response parts")
        return

    # 응답 텍스트 출력 (전체가 아닌 요약)
    response_text = parts[0].get("text", "")
    print(f"\nResponse (first 500 chars):\n{response_text[:500]}...")

    print(f"\n[SUCCESS] Response received")
    print(f"Total response length: {len(response_text)} characters")


def test_exact_match():
    """Test 1: Exact Match - 조문 번호 검색"""
    print("\n" + "="*70)
    print("TEST 1: Exact Match - '제17조' 검색")
    print("="*70)

    query = "제17조"
    response = send_a2a_message(FIRST_DOMAIN_SLUG, query)
    analyze_search_response(query, response)

    print("\n[기대 결과]")
    print("- Exact Match로 제17조 발견")
    print("- RNE로 관련 조항 확장")
    print("- stages: ['exact_match', 'rne_expansion'] 포함")


def test_semantic_search():
    """Test 2: Semantic Search - 의미론적 검색"""
    print("\n" + "="*70)
    print("TEST 2: Semantic Search - '도시관리계획의 입안 절차'")
    print("="*70)

    query = "도시관리계획의 입안 절차는 어떻게 되나요?"
    response = send_a2a_message(FIRST_DOMAIN_SLUG, query)
    analyze_search_response(query, response)

    print("\n[기대 결과]")
    print("- Vector Search (KR-SBERT) 작동")
    print("- Relationship Search (OpenAI) 작동")
    print("- Hybrid Search 병합")
    print("- RNE 그래프 확장")


def test_hybrid_search():
    """Test 3: Hybrid Search - 복합 검색"""
    print("\n" + "="*70)
    print("TEST 3: Hybrid Search - '개발행위허가와 용도지역'")
    print("="*70)

    query = "개발행위허가와 용도지역의 관계를 설명해주세요"
    response = send_a2a_message(FIRST_DOMAIN_SLUG, query)
    analyze_search_response(query, response)

    print("\n[기대 결과]")
    print("- Exact + Vector + Relationship 병합")
    print("- RRF (Reciprocal Rank Fusion) 적용")
    print("- 다양한 검색 방법 결과 통합")


def test_domain_list():
    """도메인 목록 확인"""
    print("\n" + "="*70)
    print("SETUP: Domain List 확인")
    print("="*70)

    response = requests.get(f"{AGENT_SERVER}/domains")
    data = response.json()

    print(f"\nTotal domains: {data['total']}")
    print("\nDomain list:")
    for domain in data['domains']:
        print(f"  - {domain['domain_name']}")
        print(f"    ID: {domain['domain_id']}")
        print(f"    Slug: {domain['agent_slug']}")
        print(f"    Nodes: {domain['node_count']}")
        print()


def run_all_tests():
    """모든 테스트 실행"""
    print("="*70)
    print("     Agent Server RNE/INE Test Suite")
    print("="*70)

    try:
        # 0. 도메인 목록 확인
        test_domain_list()

        # 1. Exact Match
        test_exact_match()

        # 2. Semantic Search
        test_semantic_search()

        # 3. Hybrid Search
        test_hybrid_search()

        print("\n" + "="*70)
        print("[SUCCESS] All tests completed!")
        print("="*70)

        print("\n[Next Steps]")
        print("1. Check server logs for RNE/INE execution")
        print("   - KR-SBERT model loading")
        print("   - OpenAI API calls")
        print("   - RNE graph expansion")
        print("2. Evaluate response quality")
        print("3. Decide frontend integration approach")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to Agent server.")
        print(f"Check if server is running at {AGENT_SERVER}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
