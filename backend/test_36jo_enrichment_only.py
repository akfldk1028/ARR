"""
Test enrichment, deduplication, and diversity boosting
Uses direct Neo4j queries to get 36조 results, then applies our utility functions
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

from graph_db.services.neo4j_service import Neo4jService
from agents.law.utils import (
    enrich_hang_results,
    deduplicate_results,
    boost_diversity_by_law_type,
    parse_hang_id
)


def analyze_results(results: list, title: str):
    """Analyze and display results"""
    print("\n" + "="*80)
    print(f"{title}")
    print("="*80)

    if not results:
        print("No results!")
        return

    print(f"Total: {len(results)} results\n")

    # Law type distribution
    law_types = defaultdict(int)
    for r in results:
        law_type = r.get('law_type', 'Unknown')
        law_types[law_type] += 1

    print("Law Type Distribution:")
    for law_type, count in sorted(law_types.items()):
        pct = (count / len(results)) * 100
        print(f"  - {law_type}: {count} ({pct:.1f}%)")

    # Check diversity
    diversity_ok = len(law_types) >= 2 and 'Unknown' not in law_types
    print(f"\nDiversity: {'GOOD' if diversity_ok else 'LIMITED'}")

    # Check for required fields
    has_law_name = sum(1 for r in results if r.get('law_name') and r['law_name'] != 'Unknown')
    has_law_type = sum(1 for r in results if r.get('law_type') and r['law_type'] != 'Unknown')

    print(f"\nField Coverage:")
    print(f"  - law_name: {has_law_name}/{len(results)} ({has_law_name/len(results)*100:.1f}%)")
    print(f"  - law_type: {has_law_type}/{len(results)} ({has_law_type/len(results)*100:.1f}%)")

    # Show first 5 samples
    print(f"\nSample Results (first 5):")
    for idx, r in enumerate(results[:5], 1):
        print(f"\n  [{idx}] {r.get('law_name', 'Unknown')}")
        print(f"      Type: {r.get('law_type', 'Unknown')}")
        print(f"      Article: 제{r.get('jo_number', '?')}조 제{r.get('hang_number', '?')}항")


def main():
    """Main test"""
    print("\n" + "="*80)
    print("36조 ENRICHMENT FUNCTIONS TEST")
    print("="*80)

    # Connect to Neo4j
    neo4j = Neo4jService()
    neo4j.connect()

    # Get 36조 HANG nodes directly
    query = """
    MATCH (h:HANG)
    WHERE h.full_id CONTAINS '제36조'
      AND NOT h.full_id CONTAINS '제4절'
    RETURN h.full_id as hang_id,
           h.content as content,
           h.unit_path as unit_path
    LIMIT 50
    """

    print("\nQuerying Neo4j for 36조 results...")
    raw_results = neo4j.execute_query(query)
    print(f"Found {len(raw_results)} raw results")

    if not raw_results:
        print("ERROR: No results found in database!")
        return False

    # Convert to list of dicts
    results = [
        {
            'hang_id': r['hang_id'],
            'content': r['content'],
            'unit_path': r['unit_path'],
            'similarity': 1.0  # Mock similarity for testing
        }
        for r in raw_results
    ]

    # Test 1: Parse hang_id
    print("\n\n" + "="*80)
    print("TEST 1: Parse hang_id")
    print("="*80)

    sample_hang_id = results[0]['hang_id']
    print(f"\nSample hang_id: {sample_hang_id}")

    parsed = parse_hang_id(sample_hang_id)
    print("\nParsed information:")
    for key, value in parsed.items():
        print(f"  {key}: {value}")

    # Test 2: Enrich results
    print("\n\n" + "="*80)
    print("TEST 2: Enrich Results")
    print("="*80)

    enriched_results = enrich_hang_results(results)
    print(f"\nEnriched {len(enriched_results)} results")

    analyze_results(enriched_results, "Enriched Results")

    # Test 3: Create duplicates and test deduplication
    print("\n\n" + "="*80)
    print("TEST 3: Deduplication")
    print("="*80)

    # Artificially create duplicates
    results_with_dups = enriched_results + enriched_results[:5]  # Add 5 duplicates
    print(f"\nBefore deduplication: {len(results_with_dups)} results")

    deduped_results = deduplicate_results(results_with_dups)
    print(f"After deduplication: {len(deduped_results)} results")
    print(f"Removed: {len(results_with_dups) - len(deduped_results)} duplicates")

    if len(deduped_results) == len(enriched_results):
        print("PASS: Deduplication worked correctly!")
    else:
        print(f"FAIL: Expected {len(enriched_results)}, got {len(deduped_results)}")

    # Test 4: Diversity boosting
    print("\n\n" + "="*80)
    print("TEST 4: Diversity Boosting")
    print("="*80)

    print("\nBefore diversity boosting (first 10 types):")
    for idx, r in enumerate(enriched_results[:10], 1):
        print(f"  {idx}. {r['law_type']}")

    diversified_results = boost_diversity_by_law_type(enriched_results)

    print("\nAfter diversity boosting (first 10 types):")
    for idx, r in enumerate(diversified_results[:10], 1):
        print(f"  {idx}. {r['law_type']}")

    # Analyze diversity improvement
    print("\nDiversity Analysis:")

    # Count types in first 10
    types_before = [r['law_type'] for r in enriched_results[:10]]
    types_after = [r['law_type'] for r in diversified_results[:10]]

    unique_before = len(set(types_before))
    unique_after = len(set(types_after))

    print(f"  Unique types in first 10 before: {unique_before}")
    print(f"  Unique types in first 10 after: {unique_after}")

    if unique_after >= unique_before:
        print("  PASS: Diversity maintained or improved!")
    else:
        print("  WARNING: Diversity may have decreased")

    # Final Summary
    print("\n\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)

    checks = {
        'Enrichment': len(enriched_results) == len(results),
        'Deduplication': len(deduped_results) == len(enriched_results),
        'Diversity Boosting': unique_after >= unique_before,
        'Field Coverage': (
            sum(1 for r in enriched_results if r.get('law_name') != 'Unknown') / len(enriched_results) > 0.9
            and sum(1 for r in enriched_results if r.get('law_type') != 'Unknown') / len(enriched_results) > 0.9
        ),
        'Type Diversity': len(set(r['law_type'] for r in enriched_results)) >= 2
    }

    print("\nChecks:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check_name}: {status}")
        if not passed:
            all_passed = False

    # Save results
    output_file = backend_dir / "test_36jo_enrichment_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'checks': checks,
            'raw_count': len(results),
            'enriched_count': len(enriched_results),
            'deduped_count': len(deduped_results),
            'diversified_sample': diversified_results[:20]
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    print("\n" + "="*80)
    if all_passed:
        print("OVERALL: ALL TESTS PASSED!")
    else:
        print("OVERALL: SOME TESTS FAILED")
    print("="*80 + "\n")

    return all_passed


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
