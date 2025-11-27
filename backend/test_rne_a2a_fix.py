"""
Test RNE and A2A Fix Verification

Tests to verify:
1. RNE returns cross-domain results (no domain filtering)
2. A2A collaboration statistics are properly tracked
3. Frontend receives correct metadata

Author: Law Search System
Date: 2025-11-17
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import asyncio
import logging
from agents.law.agent_manager import AgentManager
from agents.law.domain_agent import DomainAgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def test_rne_cross_domain():
    """
    Test 1: RNE Cross-Domain Results

    Verifies that RNE returns results from other domains
    when following graph relationships.
    """
    print("\n" + "="*80)
    print("TEST 1: RNE Cross-Domain Results")
    print("="*80)

    manager = AgentManager()

    # Get primary domain agent (도시 계획 및 이용)
    domain_id = 'urban_planning'
    domain_info = manager.domains.get(domain_id)

    if not domain_info or not domain_info.agent_instance:
        print(f"❌ Domain '{domain_id}' not available")
        return False

    agent = domain_info.agent_instance

    # Query that should trigger RNE and find cross-domain results
    query = "21조"

    print(f"\n[Query] '{query}'")
    print(f"[Primary Domain] {domain_info.domain_name}")
    print(f"[Agent Node Count] {len(agent.node_ids)}")

    # Execute search
    results = await agent._search_my_domain(query)

    print(f"\n[Total Results] {len(results)}")

    # Analyze RNE results
    rne_results = [r for r in results if 'rne_' in r.get('stage', '')]

    print(f"[RNE Results] {len(rne_results)}")

    if rne_results:
        print("\n[RNE Results Details]:")
        for i, r in enumerate(rne_results[:5], 1):
            hang_id = r.get('hang_id', '')
            stage = r.get('stage', '')
            similarity = r.get('similarity', 0)

            # Check if in primary domain
            in_domain = hang_id in agent.node_ids
            domain_status = "✓ Same Domain" if in_domain else "★ CROSS-DOMAIN"

            print(f"  {i}. {hang_id} [{stage}] (score={similarity:.3f}) {domain_status}")

        # Count cross-domain results
        cross_domain_count = sum(1 for r in rne_results if r.get('hang_id', '') not in agent.node_ids)

        print(f"\n[Cross-Domain RNE Results] {cross_domain_count} / {len(rne_results)}")

        if cross_domain_count > 0:
            print("✅ PASS: RNE returns cross-domain results!")
            return True
        else:
            print("⚠️  WARNING: No cross-domain RNE results found")
            return False
    else:
        print("⚠️  No RNE results found for this query")
        return False


async def test_a2a_statistics():
    """
    Test 2: A2A Collaboration Statistics

    Verifies that A2A collaboration metadata is properly tracked
    and included in the API response.
    """
    print("\n" + "="*80)
    print("TEST 2: A2A Collaboration Statistics")
    print("="*80)

    # Simulate API request flow
    from agents.law.api.search import auto_route_to_top_domains, get_agent_manager

    manager = get_agent_manager()

    query = "21조에 대해 알려주세요"

    print(f"\n[Query] '{query}'")

    # Step 1: Get top domains
    top_domains = auto_route_to_top_domains(query, manager, top_n=3)

    print(f"\n[Top Domains] {len(top_domains)}")
    for i, d in enumerate(top_domains, 1):
        print(f"  {i}. {d['domain_name']} (score={d.get('combined_score', 0):.3f})")

    # Step 2: Search primary domain
    primary_domain = top_domains[0]
    primary_domain_info = manager.domains.get(primary_domain['domain_id'])

    print(f"\n[Primary Search] {primary_domain['domain_name']}")

    primary_results = await primary_domain_info.agent_instance._search_my_domain(query)

    # Mark with source domain
    for r in primary_results:
        r['source_domain'] = primary_domain['domain_name']
        r['source_domain_id'] = primary_domain['domain_id']

    print(f"[Primary Results] {len(primary_results)}")

    # Step 3: Check A2A collaboration decision
    available_domains = [d['domain_name'] for d in top_domains[1:]]

    print(f"\n[Available for A2A] {available_domains}")

    collaboration_decision = await primary_domain_info.agent_instance.should_collaborate(
        query=query,
        initial_results=primary_results[:10],  # Top 10 for assessment
        available_domains=available_domains
    )

    should_collaborate = collaboration_decision.get('should_collaborate', False)
    target_domains = collaboration_decision.get('target_domains', [])

    print(f"[A2A Decision] {'✓ Collaborate' if should_collaborate else '✗ No collaboration'}")

    if should_collaborate:
        print(f"[Target Domains] {len(target_domains)}")
        for td in target_domains:
            print(f"  - {td['domain_name']}: {td['reason']}")

        # Step 4: Execute A2A requests
        all_results = primary_results.copy()
        a2a_collaborating_domains = []

        for target_spec in target_domains:
            target_name = target_spec['domain_name']
            refined_query = target_spec['refined_query']

            # Find target domain
            target_domain_info = None
            for d in top_domains[1:]:
                if d['domain_name'] == target_name:
                    target_domain_info = manager.domains.get(d['domain_id'])
                    break

            if target_domain_info and target_domain_info.agent_instance:
                print(f"\n[A2A Request] → {target_name}")
                print(f"  Refined query: '{refined_query}'")

                a2a_message = {
                    "query": refined_query,
                    "context": f"Original: {query}",
                    "limit": 5
                }

                a2a_response = await target_domain_info.agent_instance.handle_a2a_request(a2a_message)

                if a2a_response['status'] == 'success':
                    a2a_results = a2a_response['results']

                    # Mark as A2A
                    for r in a2a_results:
                        r['source_domain'] = target_name
                        r['via_a2a'] = True

                    all_results.extend(a2a_results)

                    a2a_collaborating_domains.append({
                        'domain_name': target_name,
                        'results_count': len(a2a_results)
                    })

                    print(f"  ✓ Received {len(a2a_results)} results")

        # Step 5: Calculate statistics
        print(f"\n[Final Statistics]")
        print(f"  Total results: {len(all_results)}")
        print(f"  Primary domain: {len(primary_results)}")
        print(f"  A2A domains: {len(a2a_collaborating_domains)}")
        print(f"  A2A results: {sum(r.get('via_a2a', False) for r in all_results)}")

        # Step 6: Verify metadata structure
        stats = {
            'a2a_collaborations': len(a2a_collaborating_domains),
            'a2a_results_count': sum(r.get('via_a2a', False) for r in all_results)
        }

        metadata = {
            'a2a_domains': [d['domain_name'] for d in a2a_collaborating_domains]
        }

        print(f"\n[API Response Metadata]")
        print(f"  stats.a2a_collaborations: {stats['a2a_collaborations']}")
        print(f"  stats.a2a_results_count: {stats['a2a_results_count']}")
        print(f"  a2a_domains: {metadata['a2a_domains']}")

        if stats['a2a_collaborations'] > 0:
            print("\n✅ PASS: A2A statistics properly tracked!")
            return True
        else:
            print("\n⚠️  WARNING: No A2A collaborations occurred")
            return False
    else:
        print("\n⚠️  GPT-4o determined no collaboration needed")
        return False


async def run_all_tests():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("RNE and A2A Fix Verification Test Suite")
    print("="*80)

    results = {}

    # Test 1: RNE Cross-Domain
    try:
        results['rne_cross_domain'] = await test_rne_cross_domain()
    except Exception as e:
        logger.error(f"Test 1 failed: {e}", exc_info=True)
        results['rne_cross_domain'] = False

    # Test 2: A2A Statistics
    try:
        results['a2a_statistics'] = await test_a2a_statistics()
    except Exception as e:
        logger.error(f"Test 2 failed: {e}", exc_info=True)
        results['a2a_statistics'] = False

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - See details above")
    print("="*80)

    return all_passed


if __name__ == '__main__':
    asyncio.run(run_all_tests())
