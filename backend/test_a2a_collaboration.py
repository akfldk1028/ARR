"""A2A Collaboration 테스트

Phase 2: A2A Message Exchange 테스트
- GPT-4o가 협업 필요 여부 판단
- DomainAgent 간 메시지 교환
- Refined query로 검색
- 결과 병합
"""
import requests
import json

# Test queries
test_queries = [
    {
        "query": "국토계획법 17조에 따른 토지 보상은 어떻게 처리되나요?",
        "description": "Multi-domain query: 도시계획법 17조 + 토지 보상",
        "expected_collaboration": True,
        "expected_domains": ["도시 계획 및 이용", "토지 이용 및 보상절차"]
    },
    {
        "query": "도시관리계획의 입안 절차는?",
        "description": "Single-domain query: 도시계획법만",
        "expected_collaboration": False,
        "expected_domains": ["도시 계획 및 이용"]
    },
    {
        "query": "용도지역과 개발행위허가 관련 규정",
        "description": "Multi-domain query: 용도지역 + 개발행위허가",
        "expected_collaboration": True,
        "expected_domains": ["도시 계획 및 이용", "토지 등 및 계획"]
    }
]

url = "http://localhost:8000/agents/law/api/search"

print("="*80)
print("A2A Collaboration Test")
print("="*80)

for i, test in enumerate(test_queries, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}: {test['description']}")
    print(f"{'='*80}")
    print(f"Query: {test['query']}")
    print(f"Expected collaboration: {test['expected_collaboration']}")
    print(f"Expected domains: {', '.join(test['expected_domains'])}")

    try:
        response = requests.post(
            url,
            json={"query": test['query'], "limit": 10},
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            stats = result.get('stats', {})
            domains_queried = result.get('domains_queried', [])

            print(f"\nResponse:")
            print(f"  - Primary domain: {result.get('domain_name', 'N/A')}")
            print(f"  - Domains queried: {', '.join(domains_queried)}")
            print(f"  - Total domains: {stats.get('domains_queried', 0)}")
            print(f"  - A2A collaboration triggered: {stats.get('a2a_collaboration_triggered', False)}")
            print(f"  - Results: {len(result.get('results', []))}")
            print(f"  - Response time: {result.get('response_time', 0)}ms")

            # Analyze results by domain
            results_by_domain = {}
            for res in result.get('results', []):
                domain = res.get('source_domain', 'Unknown')
                if domain not in results_by_domain:
                    results_by_domain[domain] = []
                results_by_domain[domain].append(res)

            print(f"\n  Results by domain:")
            for domain, domain_results in results_by_domain.items():
                print(f"    - {domain}: {len(domain_results)} results")
                for dr in domain_results[:2]:  # Show first 2 from each domain
                    full_id = dr.get('full_id', 'N/A')
                    score = dr.get('score', 0)
                    a2a_query = dr.get('a2a_refined_query', '')
                    print(f"      * {full_id} (score: {score:.3f})")
                    if a2a_query:
                        print(f"        [A2A refined query: {a2a_query}]")

            # Validation
            collaboration_triggered = stats.get('a2a_collaboration_triggered', False)
            if collaboration_triggered == test['expected_collaboration']:
                print(f"\n  ✓ Collaboration expectation met!")
            else:
                print(f"\n  ✗ Collaboration expectation FAILED!")
                print(f"    Expected: {test['expected_collaboration']}")
                print(f"    Actual: {collaboration_triggered}")

        else:
            print(f"\nError: Status {response.status_code}")
            print(response.text)

    except requests.exceptions.Timeout:
        print(f"\nTimeout! (>120s)")
    except Exception as e:
        print(f"\nException: {e}")

print(f"\n{'='*80}")
print("Test Complete")
print(f"{'='*80}")
