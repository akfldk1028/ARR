"""GPT-4 Self-Assessment 테스트"""
import requests
import json

# Test query
query = "국토계획법 17조"
url = "http://localhost:8000/agents/law/api/search"

print("="*80)
print(f"Testing LLM Self-Assessment with query: '{query}'")
print("="*80)

try:
    response = requests.post(
        url,
        json={"query": query, "limit": 5},
        headers={"Content-Type": "application/json"},
        timeout=60
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()

        print("\n" + "="*80)
        print("ROUTING DECISION")
        print("="*80)

        if 'routing_info' in result:
            routing = result['routing_info']
            print(f"\nSelected Domains: {routing.get('selected_domains', [])}")

            if 'domain_scores' in routing:
                print("\nDomain Scores:")
                for score in routing['domain_scores'][:5]:
                    print(f"  {score['domain_name']}:")
                    print(f"    - Vector Similarity: {score.get('vector_similarity', 0):.4f}")
                    print(f"    - LLM Confidence: {score.get('llm_confidence', 0):.4f}")
                    print(f"    - Combined Score: {score.get('combined_score', 0):.4f}")
                    print(f"    - Can Answer: {score.get('can_answer', False)}")
                    if 'llm_reasoning' in score:
                        print(f"    - Reasoning: {score['llm_reasoning'][:100]}...")

        print("\n" + "="*80)
        print("SEARCH RESULTS")
        print("="*80)

        if 'results' in result:
            print(f"\nTotal results: {len(result['results'])}")
            for i, res in enumerate(result['results'][:5], 1):
                print(f"\n{i}. {res.get('full_id', 'N/A')}")
                print(f"   Score: {res.get('score', 0):.4f}")
                print(f"   Content: {res.get('content', '')[:100]}...")

                # Check if Article 17 found
                if '제17조' in res.get('full_id', ''):
                    print("   ✓ FOUND Article 17!")
    else:
        print(f"\nError Response: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"\nRequest Error: {e}")
except Exception as e:
    print(f"\nUnexpected Error: {e}")

print("\n" + "="*80)
print("Test Complete")
print("="*80)
