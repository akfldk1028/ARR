"""Phase 1.5: RNE Graph Expansion 테스트

SemanticRNE 알고리즘 통합 검증:
- LawRepository 초기화 확인
- RNE 그래프 확장 수행 확인
- Hybrid + RNE 결과 병합 확인
- 도메인 필터링 확인
- stages 필드에 RNE 마커 포함 확인
"""
import requests
import json
from typing import Dict, List, Any

# Test queries
test_queries = [
    {
        "query": "도시관리계획의 입안 절차",
        "description": "Single domain query - RNE should expand within domain",
        "expected_rne_triggered": True,
        "expected_rne_results": True
    },
    {
        "query": "용도지역 지정 기준",
        "description": "Domain-specific query - RNE expansion expected",
        "expected_rne_triggered": True,
        "expected_rne_results": True
    },
    {
        "query": "개발행위허가와 용도지역",
        "description": "Multi-concept query - RNE should find related articles",
        "expected_rne_triggered": True,
        "expected_rne_results": True
    }
]

url = "http://localhost:8000/agents/law/api/search"

print("=" * 80)
print("Phase 1.5: RNE Graph Expansion Test")
print("=" * 80)
print("\nPurpose: Verify SemanticRNE integration in domain_agent.py")
print("Expected: RNE stage markers in results, expanded article discovery")
print("=" * 80)

def analyze_rne_integration(result: Dict[str, Any]) -> Dict[str, Any]:
    """RNE 통합 분석"""
    analysis = {
        'total_results': len(result.get('results', [])),
        'rne_results_count': 0,
        'rne_stages_found': set(),
        'hybrid_only_count': 0,
        'both_hybrid_and_rne': 0,
        'sample_rne_results': []
    }

    for res in result.get('results', []):
        stages = res.get('stages', [])

        # Check for RNE stage markers
        rne_stages = [s for s in stages if 'rne' in s.lower()]

        if rne_stages:
            analysis['rne_results_count'] += 1
            analysis['rne_stages_found'].update(rne_stages)

            # Sample first 3 RNE results
            if len(analysis['sample_rne_results']) < 3:
                analysis['sample_rne_results'].append({
                    'hang_id': res.get('hang_id', 'N/A')[:60],
                    'similarity': res.get('similarity', 0),
                    'stages': stages
                })

            # Check if also found by hybrid
            hybrid_stages = [s for s in stages if s in ['exact', 'semantic', 'relationship']]
            if hybrid_stages:
                analysis['both_hybrid_and_rne'] += 1
        else:
            analysis['hybrid_only_count'] += 1

    analysis['rne_stages_found'] = list(analysis['rne_stages_found'])

    return analysis

for i, test in enumerate(test_queries, 1):
    print(f"\n{'=' * 80}")
    print(f"Test {i}: {test['description']}")
    print(f"{'=' * 80}")
    print(f"Query: {test['query']}")

    try:
        response = requests.post(
            url,
            json={
                "query": test['query'],
                "limit": 20  # Increase limit to see more RNE results
            },
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            stats = result.get('stats', {})

            print(f"\nBasic Info:")
            print(f"  - Primary domain: {result.get('domain_name', 'N/A')}")
            print(f"  - Total results: {len(result.get('results', []))}")
            print(f"  - Response time: {result.get('response_time', 0)}ms")

            # Analyze RNE integration
            rne_analysis = analyze_rne_integration(result)

            print(f"\n[Phase 1.5] RNE Integration Analysis:")
            print(f"  {'=' * 76}")
            print(f"  Total results:        {rne_analysis['total_results']}")
            print(f"  RNE results:          {rne_analysis['rne_results_count']}")
            print(f"  Hybrid only:          {rne_analysis['hybrid_only_count']}")
            print(f"  Both Hybrid + RNE:    {rne_analysis['both_hybrid_and_rne']}")

            if rne_analysis['rne_stages_found']:
                print(f"\n  RNE Stage Markers Found:")
                for stage in rne_analysis['rne_stages_found']:
                    print(f"    - {stage}")

            if rne_analysis['sample_rne_results']:
                print(f"\n  Sample RNE Results:")
                for j, sample in enumerate(rne_analysis['sample_rne_results'], 1):
                    print(f"    {j}. {sample['hang_id']}")
                    print(f"       Similarity: {sample['similarity']:.3f}")
                    print(f"       Stages: {sample['stages']}")

            # Validation
            print(f"\n[Validation]")

            if test['expected_rne_results']:
                if rne_analysis['rne_results_count'] > 0:
                    print(f"  ✓ RNE expansion WORKING: {rne_analysis['rne_results_count']} results with RNE stages")
                else:
                    print(f"  ✗ RNE expansion NOT WORKING: No RNE stage markers found!")
                    print(f"    Expected RNE results but got none.")

            # Check for specific RNE stage types
            expected_rne_stages = ['rne_initial_candidate', 'rne_neighbor_expansion', 'rne_unknown']
            found_expected_stages = [s for s in rne_analysis['rne_stages_found'] if s in expected_rne_stages]

            if found_expected_stages:
                print(f"  ✓ Expected RNE stage types found: {found_expected_stages}")
            elif rne_analysis['rne_stages_found']:
                print(f"  ⚠ Unexpected RNE stage types: {rne_analysis['rne_stages_found']}")

            # Show result distribution by stage
            print(f"\n  Result Distribution:")
            stage_distribution = {}
            for res in result.get('results', []):
                stages_str = ','.join(sorted(res.get('stages', [])))
                if stages_str:
                    stage_distribution[stages_str] = stage_distribution.get(stages_str, 0) + 1

            for stages, count in sorted(stage_distribution.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {stages}: {count} results")

            # Show top 5 results with their search path
            print(f"\n  Top 5 Results (by similarity):")
            for j, res in enumerate(result.get('results', [])[:5], 1):
                hang_id = res.get('hang_id', 'N/A')
                similarity = res.get('similarity', 0)
                stages = res.get('stages', [])
                source = res.get('source_domain', result.get('domain_name', 'Primary'))

                print(f"    {j}. {hang_id[:70]}")
                print(f"       Score: {similarity:.3f} | Stages: {stages} | Source: {source}")

        else:
            print(f"\n✗ Error: Status {response.status_code}")
            print(response.text[:500])

    except requests.exceptions.Timeout:
        print(f"\n✗ Timeout! (>120s)")
    except Exception as e:
        print(f"\n✗ Exception: {e}")

print(f"\n{'=' * 80}")
print("Test Complete")
print(f"{'=' * 80}")
print("\nExpected Behavior:")
print("1. RNE results should have stage markers like 'rne_initial_candidate' or 'rne_neighbor_expansion'")
print("2. Some results should be found by BOTH Hybrid and RNE (merged)")
print("3. RNE should discover additional related articles not found by Hybrid alone")
print("4. Total results should be higher than Hybrid-only searches")
print("\nIntegration Points (domain_agent.py):")
print("- Lines 47-50: Lazy initialization of _law_repository, _semantic_rne")
print("- Lines 155-164: RNE integration in _search_my_domain()")
print("- Lines 492-559: _rne_graph_expansion() implementation")
print("=" * 80)
