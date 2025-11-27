"""Phase 3: Result Synthesis 테스트

GraphTeam Answer Agent 패턴 테스트:
- GPT-4o가 여러 domain agent 결과를 자연어로 종합
- synthesize=true 파라미터로 활성화
- synthesized_answer 필드에 종합된 답변 반환
"""
import requests
import json

# Test queries
test_queries = [
    {
        "query": "국토계획법 17조에 따른 토지 보상은 어떻게 처리되나요?",
        "description": "Multi-domain synthesis: 도시계획법 17조 + 토지 보상",
        "synthesize": True
    },
    {
        "query": "도시관리계획의 입안 절차는?",
        "description": "Single-domain synthesis: 도시계획법만",
        "synthesize": True
    },
    {
        "query": "용도지역과 개발행위허가 관련 규정",
        "description": "Synthesis OFF (비교용)",
        "synthesize": False
    }
]

url = "http://localhost:8000/agents/law/api/search"

print("="*80)
print("Phase 3: Result Synthesis Test")
print("="*80)

for i, test in enumerate(test_queries, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}: {test['description']}")
    print(f"{'='*80}")
    print(f"Query: {test['query']}")
    print(f"Synthesize: {test['synthesize']}")

    try:
        response = requests.post(
            url,
            json={
                "query": test['query'],
                "limit": 10,
                "synthesize": test['synthesize']
            },
            headers={"Content-Type": "application/json"},
            timeout=180  # 3 minutes (synthesis 시간 포함)
        )

        if response.status_code == 200:
            result = response.json()
            stats = result.get('stats', {})

            print(f"\nResponse:")
            print(f"  - Primary domain: {result.get('domain_name', 'N/A')}")
            print(f"  - Domains queried: {', '.join(result.get('domains_queried', []))}")
            print(f"  - A2A collaboration: {stats.get('a2a_collaboration_triggered', False)}")
            print(f"  - Results: {len(result.get('results', []))}")
            print(f"  - Response time: {result.get('response_time', 0)}ms")

            # Phase 3: Check synthesized answer
            if 'synthesized_answer' in result:
                synthesized = result['synthesized_answer']
                print(f"\n  ✓ Synthesized Answer Generated!")
                print(f"  {'-'*76}")
                print(f"  {synthesized}")
                print(f"  {'-'*76}")
                print(f"  Length: {len(synthesized)} characters")
            else:
                if test['synthesize']:
                    print(f"\n  ✗ Synthesized answer NOT generated (expected!)")
                else:
                    print(f"\n  - Synthesis was OFF (as expected)")

            # Show top 3 raw results for comparison
            print(f"\n  Top 3 Raw Results:")
            for j, res in enumerate(result.get('results', [])[:3], 1):
                print(f"    {j}. {res.get('hang_id', 'N/A')} (score: {res.get('similarity', 0):.3f})")
                print(f"       {res.get('content', '')[:100]}...")
                if res.get('source_domain'):
                    print(f"       [Source: {res['source_domain']}]")

        else:
            print(f"\nError: Status {response.status_code}")
            print(response.text)

    except requests.exceptions.Timeout:
        print(f"\nTimeout! (>180s)")
    except Exception as e:
        print(f"\nException: {e}")

print(f"\n{'='*80}")
print("Test Complete")
print(f"{'='*80}")
