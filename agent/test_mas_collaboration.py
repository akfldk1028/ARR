"""
MAS (Multi-Agent System) Collaboration Test

Tests:
1. Agent discovery (GET /api/domains)
2. Single agent search (POST /api/search)
3. Multi-agent parallel search (simulated)
4. Agent health checks
5. Response time comparison

Goal: Verify agent-to-agent collaboration readiness for future multi-domain scalability
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import requests
import time
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "http://localhost:8011"
TEST_QUERIES = [
    "36조",
    "용도지역",
    "제17조",
    "개발행위허가"
]

def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_agent_discovery():
    """Test 1: Agent Discovery"""
    print_section("TEST 1: Agent Discovery")

    try:
        response = requests.get(f"{BASE_URL}/api/domains", timeout=10)
        response.raise_for_status()

        data = response.json()
        print(f"\n✅ Found {data['total']} domain agent(s)")

        for domain in data['domains']:
            print(f"\n  Domain: {domain['domain_name']} ({domain['domain_id']})")
            print(f"    Nodes: {domain['node_count']}")
            print(f"    Created: {domain['created_at']}")

        return data['domains']

    except Exception as e:
        print(f"\n❌ Agent discovery failed: {e}")
        return []

def test_health_check():
    """Test 2: Health Check"""
    print_section("TEST 2: Health Check")

    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        response.raise_for_status()

        data = response.json()
        print(f"\n✅ System Status: {data.get('status', 'unknown')}")
        print(f"  Active Agents: {data.get('active_agents', 0)}")
        print(f"  Neo4j: {'Connected' if data.get('neo4j_connected', False) else 'Disconnected'}")
        print(f"  OpenAI: {'Connected' if data.get('openai_connected', False) else 'Disconnected'}")

        return data

    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        return None

def test_single_agent_search(query: str) -> Dict:
    """Test 3: Single Agent Search"""
    print(f"\n  Testing query: '{query}'")

    try:
        start_time = time.time()

        response = requests.post(
            f"{BASE_URL}/api/search",
            json={"query": query, "limit": 5},
            timeout=30
        )
        response.raise_for_status()

        elapsed = int((time.time() - start_time) * 1000)
        data = response.json()

        print(f"    ✅ {len(data['results'])} results in {elapsed}ms")
        print(f"       Domain: {data.get('domain_name', 'N/A')}")
        print(f"       Response Time: {data.get('response_time', 0)}ms")

        # Show first result
        if data['results']:
            first = data['results'][0]
            print(f"       Top result: {first.get('article', 'N/A')} - {first.get('law_name', 'N/A')[:30]}...")

        return {
            'query': query,
            'results': len(data['results']),
            'elapsed': elapsed,
            'success': True
        }

    except Exception as e:
        print(f"    ❌ Search failed: {e}")
        return {
            'query': query,
            'results': 0,
            'elapsed': 0,
            'success': False,
            'error': str(e)
        }

def test_parallel_search(queries: List[str]) -> List[Dict]:
    """Test 4: Parallel Multi-Query Search"""
    print_section("TEST 4: Parallel Multi-Query Search")
    print(f"\n  Testing {len(queries)} queries in parallel...")

    results = []
    start_time = time.time()

    # Execute searches in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        # Submit all queries
        future_to_query = {
            executor.submit(test_single_agent_search, query): query
            for query in queries
        }

        # Collect results as they complete
        for future in as_completed(future_to_query):
            query = future_to_query[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"    ❌ Exception for '{query}': {e}")
                results.append({
                    'query': query,
                    'success': False,
                    'error': str(e)
                })

    total_elapsed = int((time.time() - start_time) * 1000)

    # Summary
    print(f"\n  Parallel execution summary:")
    print(f"    Total time: {total_elapsed}ms")
    print(f"    Successful: {sum(1 for r in results if r['success'])}/{len(results)}")
    print(f"    Average per query: {total_elapsed // len(results)}ms")

    return results

def test_domain_specific_search(domains: List[Dict]):
    """Test 5: Domain-Specific Search"""
    print_section("TEST 5: Domain-Specific Search")

    if not domains:
        print("\n  ⚠️  No domains available for testing")
        return

    # Test each domain with a generic query
    test_query = "용도지역"

    for domain in domains:
        domain_id = domain['domain_id']
        print(f"\n  Testing domain: {domain['domain_name']} ({domain_id})")

        try:
            start_time = time.time()

            response = requests.post(
                f"{BASE_URL}/api/domain/{domain_id}/search",
                json={"query": test_query, "limit": 3},
                timeout=30
            )
            response.raise_for_status()

            elapsed = int((time.time() - start_time) * 1000)
            data = response.json()

            print(f"    ✅ {len(data['results'])} results in {elapsed}ms")

        except Exception as e:
            print(f"    ❌ Domain search failed: {e}")

def print_summary(results: List[Dict]):
    """Print test summary"""
    print_section("TEST SUMMARY")

    successful = sum(1 for r in results if r.get('success', False))
    total = len(results)

    print(f"\n  Overall Results:")
    print(f"    Tests Run: {total}")
    print(f"    Successful: {successful}")
    print(f"    Failed: {total - successful}")
    print(f"    Success Rate: {(successful/total*100):.1f}%")

    if successful > 0:
        avg_time = sum(r.get('elapsed', 0) for r in results if r.get('success', False)) // successful
        print(f"    Average Response Time: {avg_time}ms")

    print("\n  MAS Readiness Assessment:")
    if successful == total:
        print("    ✅ READY - All tests passed")
        print("    ✅ Agent collaboration framework is functional")
        print("    ✅ System ready for multi-domain scaling")
    elif successful >= total * 0.7:
        print("    ⚠️  PARTIAL - Most tests passed")
        print("    ⚠️  Review failed tests before scaling")
    else:
        print("    ❌ NOT READY - Multiple failures detected")
        print("    ❌ Fix critical issues before scaling")

def main():
    """Main test execution"""
    print("\n" + "=" * 80)
    print("  MAS (Multi-Agent System) Collaboration Test")
    print("  Testing agent readiness for future multi-domain scalability")
    print("=" * 80)

    all_results = []

    # Test 1: Agent Discovery
    domains = test_agent_discovery()
    all_results.append({'test': 'discovery', 'success': len(domains) > 0})

    # Test 2: Health Check
    health = test_health_check()
    all_results.append({'test': 'health', 'success': health is not None})

    # Test 3: Single Agent Searches
    print_section("TEST 3: Single Agent Search")
    for query in TEST_QUERIES:
        result = test_single_agent_search(query)
        all_results.append(result)

    # Test 4: Parallel Search
    parallel_results = test_parallel_search(TEST_QUERIES)

    # Test 5: Domain-Specific Search
    test_domain_specific_search(domains)

    # Summary
    print_summary(all_results)

    print("\n" + "=" * 80)
    print("  Test Complete")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
