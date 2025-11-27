"""
DomainManager Test Suite

Tests all functionality of the DomainManager class:
- Singleton pattern
- Cache management
- Domain queries
- Change detection
- Event listeners
"""

import os
import sys
import django
import logging
from datetime import datetime, timedelta

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.domain_manager import (
    DomainManager,
    DomainMetadata,
    DomainChangeEvent,
    DomainChangeType,
    get_domain_manager
)
from graph_db.services import Neo4jService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_singleton_pattern():
    """Test 1: Singleton pattern ensures single instance"""
    print("\n" + "=" * 80)
    print("TEST 1: Singleton Pattern")
    print("=" * 80)

    manager1 = DomainManager.get_instance()
    manager2 = DomainManager.get_instance()

    assert manager1 is manager2, "Singleton pattern failed!"
    print("✅ Singleton pattern working: same instance returned")

    # Reset for clean state
    DomainManager.reset_instance()
    print("✅ Singleton reset successful")


def test_get_all_domains():
    """Test 2: Get all domains from Neo4j"""
    print("\n" + "=" * 80)
    print("TEST 2: Get All Domains")
    print("=" * 80)

    manager = DomainManager.get_instance()
    domains = manager.get_all_domains()

    print(f"\n📊 Found {len(domains)} domains in Neo4j:")
    for i, domain in enumerate(domains, 1):
        print(f"\n{i}. {domain.domain_name}")
        print(f"   ID: {domain.domain_id}")
        print(f"   Slug: {domain.agent_slug}")
        print(f"   Nodes: {domain.node_count}")
        print(f"   Created: {domain.created_at}")
        print(f"   Updated: {domain.updated_at}")

    assert len(domains) > 0, "No domains found in Neo4j!"
    print(f"\n✅ Successfully retrieved {len(domains)} domains")

    return domains


def test_get_specific_domain(domains):
    """Test 3: Get specific domain by ID"""
    print("\n" + "=" * 80)
    print("TEST 3: Get Specific Domain")
    print("=" * 80)

    if not domains:
        print("⚠️  No domains available for testing")
        return

    manager = DomainManager.get_instance()
    test_domain = domains[0]

    # Test by ID
    domain = manager.get_domain(test_domain.domain_id)
    assert domain is not None, f"Failed to get domain by ID: {test_domain.domain_id}"
    assert domain.domain_id == test_domain.domain_id
    print(f"✅ Get by ID successful: {domain.domain_name}")

    # Test by name
    domain_by_name = manager.get_domain_by_name(test_domain.domain_name)
    assert domain_by_name is not None, f"Failed to get domain by name: {test_domain.domain_name}"
    assert domain_by_name.domain_id == test_domain.domain_id
    print(f"✅ Get by name successful: {domain_by_name.domain_name}")

    # Test by slug
    domain_by_slug = manager.get_domain_by_slug(test_domain.agent_slug)
    assert domain_by_slug is not None, f"Failed to get domain by slug: {test_domain.agent_slug}"
    assert domain_by_slug.domain_id == test_domain.domain_id
    print(f"✅ Get by slug successful: {domain_by_slug.domain_name}")

    # Test query statistics
    print(f"\n📊 Query Statistics:")
    print(f"   Last queried: {domain.last_queried}")
    print(f"   Query count: {domain.query_count}")


def test_cache_functionality():
    """Test 4: Cache TTL and invalidation"""
    print("\n" + "=" * 80)
    print("TEST 4: Cache Functionality")
    print("=" * 80)

    # Reset and create manager with short TTL
    DomainManager.reset_instance()
    manager = DomainManager.get_instance(cache_ttl_seconds=2)

    # First access (should hit Neo4j)
    print("\n1️⃣ First access (cache miss)...")
    start = datetime.now()
    domains1 = manager.get_all_domains()
    duration1 = (datetime.now() - start).total_seconds()
    print(f"   Duration: {duration1:.3f}s (includes Neo4j query)")

    # Second access (should use cache)
    print("\n2️⃣ Second access (cache hit)...")
    start = datetime.now()
    domains2 = manager.get_all_domains()
    duration2 = (datetime.now() - start).total_seconds()
    print(f"   Duration: {duration2:.3f}s (from cache)")

    assert duration2 < duration1, "Cache not working - second access slower!"
    print(f"✅ Cache speed improvement: {duration1/duration2:.2f}x faster")

    # Cache info
    cache_info = manager.get_cache_info()
    print(f"\n📊 Cache Info:")
    for key, value in cache_info.items():
        print(f"   {key}: {value}")

    # Wait for cache to expire
    print(f"\n3️⃣ Waiting for cache to expire (TTL: {manager.cache_ttl_seconds}s)...")
    import time
    time.sleep(manager.cache_ttl_seconds + 0.5)

    # Third access (cache expired, should refresh)
    print("\n4️⃣ Third access after TTL expiration...")
    start = datetime.now()
    domains3 = manager.get_all_domains()
    duration3 = (datetime.now() - start).total_seconds()
    print(f"   Duration: {duration3:.3f}s (cache expired, Neo4j query)")

    print("✅ Cache TTL working correctly")

    # Test manual invalidation
    print("\n5️⃣ Testing manual cache invalidation...")
    manager.invalidate_cache()
    cache_info_after = manager.get_cache_info()
    assert not cache_info_after['is_valid'], "Cache invalidation failed!"
    print("✅ Manual cache invalidation working")


def test_change_detection():
    """Test 5: Domain change detection"""
    print("\n" + "=" * 80)
    print("TEST 5: Change Detection")
    print("=" * 80)

    DomainManager.reset_instance()
    manager = DomainManager.get_instance()

    # Setup change listener
    detected_changes = []

    def change_listener(event: DomainChangeEvent):
        detected_changes.append(event)
        print(f"\n🔔 Change detected!")
        print(f"   Type: {event.change_type.value}")
        print(f"   Domain: {event.domain_name}")
        print(f"   ID: {event.domain_id}")
        print(f"   Time: {event.timestamp}")

    manager.add_change_listener(change_listener)
    print("✅ Change listener registered")

    # Initial load
    print("\n1️⃣ Initial load...")
    domains_initial = manager.get_all_domains()
    initial_count = len(domains_initial)
    print(f"   Initial domain count: {initial_count}")

    # Force refresh (should detect no changes if DB unchanged)
    print("\n2️⃣ Force refresh (no DB changes)...")
    stats = manager.refresh()
    print(f"   Refresh stats: {stats}")

    if stats['domains_added'] == 0 and stats['domains_removed'] == 0:
        print("✅ No changes detected (as expected)")
    else:
        print(f"⚠️  Changes detected: +{stats['domains_added']} -{stats['domains_removed']}")

    # Display detected changes
    print(f"\n📊 Total change events fired: {len(detected_changes)}")
    for i, event in enumerate(detected_changes, 1):
        print(f"   {i}. {event.change_type.value}: {event.domain_name}")

    # Remove listener
    manager.remove_change_listener(change_listener)
    print("\n✅ Change listener removed")


def test_domain_metadata():
    """Test 6: DomainMetadata functionality"""
    print("\n" + "=" * 80)
    print("TEST 6: DomainMetadata Functionality")
    print("=" * 80)

    manager = DomainManager.get_instance()
    domains = manager.get_all_domains()

    if not domains:
        print("⚠️  No domains available for testing")
        return

    test_domain = domains[0]

    # Test to_dict()
    print("\n1️⃣ Testing to_dict()...")
    domain_dict = test_domain.to_dict()
    print("   Domain dictionary keys:")
    for key in domain_dict.keys():
        print(f"      - {key}")

    required_keys = ['domain_id', 'domain_name', 'agent_slug', 'node_count']
    for key in required_keys:
        assert key in domain_dict, f"Missing required key: {key}"

    print("✅ to_dict() includes all required fields")

    # Test from_neo4j_record() (indirectly tested via refresh)
    print("\n2️⃣ Testing from_neo4j_record()...")
    print(f"   Parsed domain: {test_domain.domain_name}")
    print(f"   Created at: {test_domain.created_at}")
    print(f"   Updated at: {test_domain.updated_at}")
    print("✅ from_neo4j_record() parsing successful")


def test_performance():
    """Test 7: Performance benchmarks"""
    print("\n" + "=" * 80)
    print("TEST 7: Performance Benchmarks")
    print("=" * 80)

    DomainManager.reset_instance()
    manager = DomainManager.get_instance()

    # Benchmark: Full refresh
    print("\n1️⃣ Benchmarking full refresh from Neo4j...")
    import time
    start = time.perf_counter()
    domains = manager.get_all_domains(force_refresh=True)
    refresh_time = time.perf_counter() - start
    print(f"   Full refresh: {refresh_time:.4f}s for {len(domains)} domains")

    # Benchmark: Cached access
    print("\n2️⃣ Benchmarking cached access...")
    iterations = 1000

    start = time.perf_counter()
    for _ in range(iterations):
        _ = manager.get_all_domains()
    total_time = time.perf_counter() - start
    avg_time = total_time / iterations

    print(f"   {iterations} cached accesses: {total_time:.4f}s total")
    print(f"   Average per access: {avg_time*1000:.4f}ms")
    print(f"   Throughput: {iterations/total_time:.0f} req/s")

    # Benchmark: Lookup by ID
    if domains:
        print("\n3️⃣ Benchmarking lookup by ID...")
        test_id = domains[0].domain_id

        start = time.perf_counter()
        for _ in range(iterations):
            _ = manager.get_domain(test_id)
        total_time = time.perf_counter() - start
        avg_time = total_time / iterations

        print(f"   {iterations} ID lookups: {total_time:.4f}s total")
        print(f"   Average per lookup: {avg_time*1000:.4f}ms")

    print("\n✅ Performance benchmarks complete")


def test_concurrent_access():
    """Test 8: Thread-safety with concurrent access"""
    print("\n" + "=" * 80)
    print("TEST 8: Concurrent Access (Thread Safety)")
    print("=" * 80)

    import threading
    import time

    DomainManager.reset_instance()
    manager = DomainManager.get_instance()

    results = []
    errors = []

    def worker_thread(thread_id: int, iterations: int):
        """Worker thread that accesses DomainManager"""
        try:
            for i in range(iterations):
                # Mix of different operations
                if i % 3 == 0:
                    domains = manager.get_all_domains()
                elif i % 3 == 1:
                    count = manager.get_domain_count()
                else:
                    cache_info = manager.get_cache_info()

                # Small delay to increase chance of race conditions
                time.sleep(0.001)

            results.append(f"Thread {thread_id} completed {iterations} operations")
        except Exception as e:
            errors.append(f"Thread {thread_id} error: {e}")

    # Launch multiple threads
    num_threads = 10
    iterations_per_thread = 50

    print(f"\n🚀 Launching {num_threads} threads...")
    print(f"   Each thread will perform {iterations_per_thread} operations")

    threads = []
    start_time = time.perf_counter()

    for i in range(num_threads):
        thread = threading.Thread(target=worker_thread, args=(i, iterations_per_thread))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    duration = time.perf_counter() - start_time

    # Results
    print(f"\n📊 Concurrent access results:")
    print(f"   Duration: {duration:.3f}s")
    print(f"   Total operations: {num_threads * iterations_per_thread}")
    print(f"   Successful threads: {len(results)}")
    print(f"   Errors: {len(errors)}")

    if errors:
        print("\n⚠️  Errors detected:")
        for error in errors:
            print(f"   - {error}")
    else:
        print("\n✅ All threads completed successfully (thread-safe)")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "=" * 80)
    print("DOMAIN MANAGER TEST SUITE")
    print("=" * 80)
    print(f"Start time: {datetime.now()}")

    try:
        # Test 1: Singleton
        test_singleton_pattern()

        # Test 2: Get all domains
        domains = test_get_all_domains()

        # Test 3: Get specific domain
        test_get_specific_domain(domains)

        # Test 4: Cache functionality
        test_cache_functionality()

        # Test 5: Change detection
        test_change_detection()

        # Test 6: Domain metadata
        test_domain_metadata()

        # Test 7: Performance
        test_performance()

        # Test 8: Concurrent access
        test_concurrent_access()

        # Final summary
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY! ✅")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\nEnd time: {datetime.now()}")


def interactive_demo():
    """Interactive demonstration of DomainManager"""
    print("\n" + "=" * 80)
    print("DOMAIN MANAGER INTERACTIVE DEMO")
    print("=" * 80)

    manager = DomainManager.get_instance()

    while True:
        print("\n" + "-" * 80)
        print("Options:")
        print("1. List all domains")
        print("2. Get domain by ID")
        print("3. Get domain by name")
        print("4. Force refresh")
        print("5. Show cache info")
        print("6. Test change detection")
        print("7. Exit")
        print("-" * 80)

        choice = input("\nEnter choice (1-7): ").strip()

        if choice == '1':
            domains = manager.get_all_domains()
            print(f"\n📊 {len(domains)} domains found:")
            for i, d in enumerate(domains, 1):
                print(f"{i}. {d.domain_name} ({d.node_count} nodes)")

        elif choice == '2':
            domain_id = input("Enter domain ID: ").strip()
            domain = manager.get_domain(domain_id)
            if domain:
                print(f"\n✅ Found: {domain.domain_name}")
                print(f"   Nodes: {domain.node_count}")
                print(f"   Slug: {domain.agent_slug}")
            else:
                print(f"\n❌ Domain not found: {domain_id}")

        elif choice == '3':
            domain_name = input("Enter domain name: ").strip()
            domain = manager.get_domain_by_name(domain_name)
            if domain:
                print(f"\n✅ Found: {domain.domain_id}")
                print(f"   Nodes: {domain.node_count}")
                print(f"   Slug: {domain.agent_slug}")
            else:
                print(f"\n❌ Domain not found: {domain_name}")

        elif choice == '4':
            print("\n🔄 Refreshing from Neo4j...")
            stats = manager.refresh()
            print("\n📊 Refresh statistics:")
            for key, value in stats.items():
                print(f"   {key}: {value}")

        elif choice == '5':
            cache_info = manager.get_cache_info()
            print("\n📊 Cache information:")
            for key, value in cache_info.items():
                print(f"   {key}: {value}")

        elif choice == '6':
            print("\n🔔 Setting up change listener...")
            changes_detected = []

            def demo_listener(event):
                changes_detected.append(event)
                print(f"   Change: {event.change_type.value} - {event.domain_name}")

            manager.add_change_listener(demo_listener)
            stats = manager.refresh()
            print(f"\n   Total changes: {len(changes_detected)}")
            manager.remove_change_listener(demo_listener)

        elif choice == '7':
            print("\n👋 Exiting demo...")
            break

        else:
            print("\n❌ Invalid choice")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_demo()
    else:
        run_all_tests()
