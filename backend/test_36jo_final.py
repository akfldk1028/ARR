"""
Final comprehensive test for 36조 search with fixes
Tests:
1. Law type diversity (법률, 시행령, 시행규칙)
2. No duplicates
3. Results enriched with law_name, law_type, jo_number, hang_number
"""

import os
import sys
import django
from pathlib import Path
import json
from collections import defaultdict

# Setup Django
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.agent_manager import AgentManager
from agents.law.domain_manager import DomainManager

def analyze_results(results: list, query: str):
    """Analyze search results for issues"""
    print("\n" + "="*80)
    print(f"ANALYSIS: {query}")
    print("="*80)

    if not results:
        print("No results found!")
        return

    print(f"\nTotal Results: {len(results)}")

    # Check for required fields
    print("\n1. Field Completeness:")
    required_fields = ['hang_id', 'law_name', 'law_type', 'jo_number', 'hang_number']
    field_coverage = {field: 0 for field in required_fields}

    for r in results:
        for field in required_fields:
            if field in r and r[field] and r[field] != 'Unknown':
                field_coverage[field] += 1

    for field, count in field_coverage.items():
        percentage = (count / len(results)) * 100
        status = "OK" if percentage == 100 else "MISSING"
        print(f"   {field}: {count}/{len(results)} ({percentage:.1f}%) - {status}")

    # Check for duplicates
    print("\n2. Duplicate Check:")
    hang_ids = [r.get('hang_id', '') for r in results]
    unique_ids = set(hang_ids)
    duplicate_count = len(hang_ids) - len(unique_ids)

    if duplicate_count > 0:
        print(f"   FAIL: Found {duplicate_count} duplicates!")
        # Show duplicates
        from collections import Counter
        id_counts = Counter(hang_ids)
        for hang_id, count in id_counts.most_common():
            if count > 1:
                print(f"     - {hang_id}: appears {count} times")
    else:
        print(f"   PASS: No duplicates (all {len(unique_ids)} results unique)")

    # Check for law type diversity
    print("\n3. Law Type Diversity:")
    law_types = defaultdict(int)
    for r in results:
        law_type = r.get('law_type', 'Unknown')
        law_types[law_type] += 1

    print(f"   Found {len(law_types)} different types:")
    for law_type, count in sorted(law_types.items()):
        percentage = (count / len(results)) * 100
        print(f"     - {law_type}: {count} ({percentage:.1f}%)")

    # Assess diversity
    if len(law_types) >= 2 and 'Unknown' not in law_types:
        print(f"   PASS: Good diversity ({len(law_types)} types)")
    elif len(law_types) == 1:
        print(f"   FAIL: No diversity (all results are '{list(law_types.keys())[0]}')")
    else:
        print(f"   WARNING: Limited diversity or unknown types")

    # Show sample results
    print("\n4. Sample Results (First 5):")
    for idx, r in enumerate(results[:5], 1):
        print(f"\n   {idx}. {r.get('law_name', 'Unknown')} ({r.get('law_type', 'Unknown')})")
        print(f"      Article: {r.get('jo_number', '?')}조 {r.get('hang_number', '?')}항")
        print(f"      HANG ID: {r.get('hang_id', 'Unknown')[:80]}...")
        print(f"      Similarity: {r.get('similarity', 0):.3f}")

    # Overall assessment
    print("\n" + "="*80)
    print("OVERALL ASSESSMENT:")
    print("="*80)

    issues = []
    if duplicate_count > 0:
        issues.append(f"Duplicates: {duplicate_count} found")
    if field_coverage['law_name'] < len(results):
        issues.append(f"Missing law_name in {len(results) - field_coverage['law_name']} results")
    if field_coverage['law_type'] < len(results):
        issues.append(f"Missing law_type in {len(results) - field_coverage['law_type']} results")
    if len(law_types) < 2:
        issues.append(f"Low diversity: only {len(law_types)} law type(s)")

    if not issues:
        print("PASS: All checks passed!")
    else:
        print("FAIL: Issues found:")
        for issue in issues:
            print(f"  - {issue}")

    return {
        'total_results': len(results),
        'unique_results': len(unique_ids),
        'duplicate_count': duplicate_count,
        'law_types': dict(law_types),
        'field_coverage': field_coverage,
        'passed': len(issues) == 0
    }


def main():
    """Main test function"""
    print("\n" + "="*80)
    print("FINAL 36조 SEARCH TEST")
    print("Testing: Diversity, Deduplication, Enrichment")
    print("="*80)

    # Initialize DomainManager
    print("\nInitializing DomainManager...")
    domain_manager = DomainManager()

    # Test query
    query = "36조"

    print(f"\nExecuting search: '{query}'")
    print("-" * 80)

    # Execute search
    try:
        import asyncio

        async def run_search():
            result = await domain_manager.search(query)
            return result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_search())
        finally:
            loop.close()

        # Extract HANG results
        hang_results = []

        # Check different result structures
        if 'hang_results' in result:
            hang_results = result['hang_results']
        elif 'results' in result:
            hang_results = result['results']
        elif isinstance(result, list):
            hang_results = result

        print(f"\nReceived {len(hang_results)} results")

        # Analyze results
        analysis = analyze_results(hang_results, query)

        # Save full results
        output_file = backend_dir / "test_36jo_final_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'query': query,
                'analysis': analysis,
                'results': hang_results,
                'full_response': result
            }, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nFull results saved to: {output_file}")

        # Final verdict
        print("\n" + "="*80)
        if analysis['passed']:
            print("TEST PASSED: All quality checks passed!")
        else:
            print("TEST FAILED: Quality issues detected!")
        print("="*80 + "\n")

        return analysis['passed']

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
