"""
Test 36조 search using DomainAgent directly
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
    print("\n1. Field Completeness:")
    required_fields = ['hang_id', 'law_name', 'law_type', 'jo_number', 'hang_number']
    field_coverage = {field: 0 for field in required_fields}

    for r in results:
        for field in required_fields:
            if field in r and r[field] and r[field] != 'Unknown':
                field_coverage[field] += 1

    for field, count in field_coverage.items():
        percentage = (count / len(results)) * 100
        status = "OK" if percentage >= 90 else "FAIL"
        print(f"   {field}: {count}/{len(results)} ({percentage:.1f}%) - {status}")

    # Check for duplicates
    print("\n2. Duplicate Check:")
    hang_ids = [r.get('hang_id', '') for r in results]
    unique_ids = set(hang_ids)
    duplicate_count = len(hang_ids) - len(unique_ids)

    if duplicate_count > 0:
        print(f"   FAIL: Found {duplicate_count} duplicates")
    else:
        print(f"   PASS: No duplicates")

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

    diversity_ok = len(law_types) >= 2 and 'Unknown' not in law_types
    print(f"   {'PASS' if diversity_ok else 'FAIL'}: Diversity check")

    # Show sample results
    print("\n4. Sample Results (First 5):")
    for idx, r in enumerate(results[:5], 1):
        print(f"\n   [{idx}] {r.get('law_name', 'Unknown')} ({r.get('law_type', 'Unknown')})")
        print(f"       조항: 제{r.get('jo_number', '?')}조 제{r.get('hang_number', '?')}항")
        print(f"       Similarity: {r.get('similarity', 0):.3f}")

    # Overall assessment
    print("\n" + "="*80)
    issues = []
    if duplicate_count > 0:
        issues.append(f"{duplicate_count} duplicates")
    if field_coverage['law_name'] / len(results) < 0.9:
        issues.append("Missing law_name")
    if field_coverage['law_type'] / len(results) < 0.9:
        issues.append("Missing law_type")
    if not diversity_ok:
        issues.append("Low diversity")

    if not issues:
        print("PASS: All checks passed!")
    else:
        print(f"FAIL: Issues - {', '.join(issues)}")
    print("="*80)

    return {
        'total_results': len(results),
        'unique_results': len(unique_ids),
        'duplicate_count': duplicate_count,
        'law_types': dict(law_types),
        'field_coverage': field_coverage,
        'passed': len(issues) == 0
    }


async def test_domain_search():
    """Test search with a domain agent"""
    print("\n" + "="*80)
    print("36조 DOMAIN AGENT SEARCH TEST")
    print("="*80)

    # Get a domain that contains 36조
    neo4j = Neo4jService()
    neo4j.connect()

    # Find which domain contains 36조
    query = """
    MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
    WHERE h.full_id CONTAINS '제36조'
      AND NOT h.full_id CONTAINS '제4절'
    RETURN DISTINCT d.domain_id as domain_id,
           d.domain_name as domain_name,
           count(h) as count
    ORDER BY count DESC
    LIMIT 1
    """

    results = neo4j.execute_query(query)

    if not results:
        print("ERROR: No domain found with 36조!")
        return False

    domain_id = results[0]['domain_id']
    domain_name = results[0]['domain_name']

    print(f"\nFound domain with 36조:")
    print(f"  Domain ID: {domain_id}")
    print(f"  Domain Name: {domain_name}")
    print(f"  36조 HANG count: {results[0]['count']}")

    # Get node_ids for this domain
    query2 = """
    MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain {domain_id: $domain_id})
    RETURN collect(h.full_id) as node_ids
    """

    node_results = neo4j.execute_query(query2, {'domain_id': domain_id})
    node_ids = node_results[0]['node_ids'] if node_results else []

    print(f"\nDomain has {len(node_ids)} total nodes")

    # Create DomainAgent
    print(f"\nCreating DomainAgent...")

    agent_config = {
        'rne_threshold': 0.75,
        'ine_k': 10
    }

    domain_info = {
        'domain_id': domain_id,
        'domain_name': domain_name,
        'node_ids': node_ids,
        'neighbor_agents': []
    }

    agent = DomainAgent(
        agent_slug=f"domain-{domain_id}",
        agent_config=agent_config,
        domain_info=domain_info
    )

    # Test search
    test_query = "36조"
    print(f"\nSearching for: '{test_query}'")
    print("-" * 80)

    search_results = await agent._search_my_domain(test_query, limit=20)

    print(f"\nReceived {len(search_results)} results")

    # Analyze results
    analysis = analyze_results(search_results, test_query)

    # Save results
    output_file = backend_dir / "test_36jo_domain_search_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'query': test_query,
            'domain_id': domain_id,
            'domain_name': domain_name,
            'analysis': analysis,
            'results': search_results
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    return analysis['passed']


def main():
    """Main entry point"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(test_domain_search())
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
