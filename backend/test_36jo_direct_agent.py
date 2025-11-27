"""
Direct test of 36조 search with enrichment
Uses DomainAgent with all HANG nodes (no domain filtering)
"""

import os
import sys
import django
from pathlib import Path
import json
from collections import defaultdict
import asyncio

# Setup Django
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService
from agents.law.domain_agent import DomainAgent
from agents.law.utils import enrich_hang_results, deduplicate_results, boost_diversity_by_law_type


def analyze_results(results: list, query: str):
    """Analyze search results"""
    print("\n" + "="*80)
    print(f"ANALYSIS: {query}")
    print("="*80)

    if not results:
        print("WARNING: No results found!")
        return {'passed': False, 'total_results': 0}

    print(f"\nTotal Results: {len(results)}")

    # Check for required fields
    print("\n[1] Field Completeness Check:")
    required_fields = ['hang_id', 'law_name', 'law_type', 'jo_number', 'hang_number']
    field_coverage = {field: 0 for field in required_fields}

    for r in results:
        for field in required_fields:
            if field in r and r[field] and r[field] != 'Unknown':
                field_coverage[field] += 1

    all_fields_ok = True
    for field, count in field_coverage.items():
        percentage = (count / len(results)) * 100
        status = "PASS" if percentage >= 90 else "FAIL"
        if percentage < 90:
            all_fields_ok = False
        print(f"   {field}: {count}/{len(results)} ({percentage:.1f}%) - {status}")

    # Check for duplicates
    print("\n[2] Duplicate Check:")
    hang_ids = [r.get('hang_id', '') for r in results]
    unique_ids = set(hang_ids)
    duplicate_count = len(hang_ids) - len(unique_ids)

    if duplicate_count > 0:
        print(f"   FAIL: Found {duplicate_count} duplicates")
        # Show first few duplicates
        from collections import Counter
        id_counts = Counter(hang_ids)
        for hang_id, count in list(id_counts.most_common())[:3]:
            if count > 1:
                print(f"     - {hang_id[:80]}... appears {count} times")
        duplicates_ok = False
    else:
        print(f"   PASS: No duplicates found")
        duplicates_ok = True

    # Check for law type diversity
    print("\n[3] Law Type Diversity Check:")
    law_types = defaultdict(int)
    for r in results:
        law_type = r.get('law_type', 'Unknown')
        law_types[law_type] += 1

    print(f"   Found {len(law_types)} different types:")
    for law_type, count in sorted(law_types.items()):
        percentage = (count / len(results)) * 100
        print(f"     - {law_type}: {count} ({percentage:.1f}%)")

    # Check for actual diversity (not all the same)
    diversity_ok = len(law_types) >= 2 and 'Unknown' not in law_types
    print(f"   {'PASS' if diversity_ok else 'FAIL'}: Diversity check")

    # Check for specific types
    has_law = '법률' in law_types
    has_decree = '시행령' in law_types
    has_rule = '시행규칙' in law_types

    print(f"\n   Type Coverage:")
    print(f"     - 법률: {'YES' if has_law else 'NO'}")
    print(f"     - 시행령: {'YES' if has_decree else 'NO'}")
    print(f"     - 시행규칙: {'YES' if has_rule else 'NO'}")

    full_diversity = has_law and has_decree and has_rule
    if full_diversity:
        print(f"   EXCELLENT: All three types represented!")

    # Show sample results
    print("\n[4] Sample Results (First 10):")
    for idx, r in enumerate(results[:10], 1):
        print(f"\n   [{idx}] {r.get('law_name', 'Unknown')} ({r.get('law_type', 'Unknown')})")
        print(f"       Article: 제{r.get('jo_number', '?')}조 제{r.get('hang_number', '?')}항")
        print(f"       Similarity: {r.get('similarity', 0):.4f}")
        content_preview = r.get('content', '')[:60]
        print(f"       Content: {content_preview}...")

    # Overall assessment
    print("\n" + "="*80)
    print("OVERALL ASSESSMENT:")
    print("="*80)

    issues = []
    if duplicate_count > 0:
        issues.append(f"{duplicate_count} duplicates found")
    if not all_fields_ok:
        issues.append("Some fields missing")
    if not diversity_ok:
        issues.append("Low diversity (all same type)")
    if not full_diversity:
        issues.append("Not all law types represented")

    if not issues:
        print("PASS: All quality checks passed!")
        print("  - No duplicates")
        print("  - All fields present")
        print("  - Good diversity")
    else:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")

    return {
        'total_results': len(results),
        'unique_results': len(unique_ids),
        'duplicate_count': duplicate_count,
        'law_types': dict(law_types),
        'field_coverage': field_coverage,
        'full_diversity': full_diversity,
        'passed': len(issues) == 0
    }


async def test_search():
    """Test search with enrichment"""
    print("\n" + "="*80)
    print("36조 ENRICHMENT TEST")
    print("Testing: law_name, law_type, deduplication, diversity")
    print("="*80)

    # Get all HANG nodes for testing (no domain filtering)
    neo4j = Neo4jService()
    neo4j.connect()

    query = """
    MATCH (h:HANG)
    RETURN collect(h.full_id) as node_ids
    LIMIT 2000
    """

    results = neo4j.execute_query(query)
    all_node_ids = results[0]['node_ids'] if results else []

    print(f"\nTotal HANG nodes in database: {len(all_node_ids)}")

    # Create a test DomainAgent with all nodes
    agent_config = {
        'rne_threshold': 0.75,
        'ine_k': 10
    }

    domain_info = {
        'domain_id': 'test_domain',
        'domain_name': 'Test Domain (All Nodes)',
        'node_ids': all_node_ids,
        'neighbor_agents': []
    }

    agent = DomainAgent(
        agent_slug="test-agent",
        agent_config=agent_config,
        domain_info=domain_info
    )

    # Test search
    test_query = "36조"
    print(f"\nSearching for: '{test_query}'")
    print("-" * 80)

    search_results = await agent._search_my_domain(test_query, limit=30)

    print(f"\nReceived {len(search_results)} results from DomainAgent")

    # The results should already be enriched by the agent
    # Let's verify and analyze
    analysis = analyze_results(search_results, test_query)

    # Also test the utility functions directly
    print("\n\n" + "="*80)
    print("TESTING DEDUPLICATION & DIVERSITY BOOSTING")
    print("="*80)

    # Simulate some duplicates
    test_results_with_dups = search_results + search_results[:3]  # Add 3 duplicates
    print(f"\nBefore deduplication: {len(test_results_with_dups)} results")

    deduped = deduplicate_results(test_results_with_dups)
    print(f"After deduplication: {len(deduped)} results")
    print(f"Removed: {len(test_results_with_dups) - len(deduped)} duplicates")

    # Test diversity boosting
    print(f"\nApplying diversity boosting...")
    diversified = boost_diversity_by_law_type(deduped)

    # Show type distribution before and after
    print(f"\nType distribution (first 10):")
    print("Before diversity boost:")
    for idx, r in enumerate(deduped[:10], 1):
        print(f"  {idx}. {r.get('law_type', 'Unknown')}")

    print("\nAfter diversity boost:")
    for idx, r in enumerate(diversified[:10], 1):
        print(f"  {idx}. {r.get('law_type', 'Unknown')}")

    # Save results
    output_file = backend_dir / "test_36jo_enrichment_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'query': test_query,
            'analysis': analysis,
            'original_results': search_results,
            'deduped_count': len(deduped),
            'diversified_sample': diversified[:20]
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\nResults saved to: {output_file}")
    print("="*80 + "\n")

    return analysis['passed']


def main():
    """Main entry point"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(test_search())
        finally:
            loop.close()

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
