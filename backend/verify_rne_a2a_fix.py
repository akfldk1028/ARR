"""
Quick Verification of RNE and A2A Fixes

Verifies the code changes without running the full system:
1. Check domain_agent.py - RNE filtering removed
2. Check search.py - A2A statistics added
"""

import os
import re
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def verify_domain_agent_fix():
    """Verify RNE domain filtering has been removed"""
    print("\n" + "="*80)
    print("VERIFICATION 1: domain_agent.py - RNE Cross-Domain Fix")
    print("="*80)

    file_path = r"D:\Data\11_Backend\01_ARR\backend\agents\law\domain_agent.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check for the old domain filtering code (should NOT exist)
    old_pattern = r'if self\._is_in_my_domain\(hang_full_id\):'
    has_old_code = re.search(old_pattern, content[content.find('_rne_graph_expansion'):])

    if has_old_code:
        print("❌ FAIL: Old domain filtering code still exists in RNE method!")
        print(f"   Found at position: {has_old_code.start()}")
        return False

    # Check for the new comment explaining the fix
    new_pattern = r'도메인 필터링 제거.*RNE의 목적'
    has_new_comment = re.search(new_pattern, content, re.DOTALL)

    if not has_new_comment:
        print("⚠️  WARNING: Expected comment about domain filtering removal not found")

    # Check for the updated log message
    log_pattern = r'RNE.*Returned.*cross-domain included'
    has_new_log = re.search(log_pattern, content)

    if has_new_log:
        print("✅ PASS: RNE domain filtering successfully removed!")
        print("   - Old filtering code: NOT FOUND (correct)")
        print("   - New log message: FOUND (cross-domain included)")
        return True
    else:
        print("⚠️  PARTIAL: Domain filtering removed but log message not updated")
        return True


def verify_search_api_fix():
    """Verify A2A statistics tracking has been added"""
    print("\n" + "="*80)
    print("VERIFICATION 2: search.py - A2A Statistics Fix")
    print("="*80)

    file_path = r"D:\Data\11_Backend\01_ARR\backend\agents\law\api\search.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    checks_passed = []
    checks_failed = []

    # Check 1: a2a_collaborating_domains tracking variable
    if "a2a_collaborating_domains = []" in content:
        checks_passed.append("a2a_collaborating_domains tracking variable")
    else:
        checks_failed.append("a2a_collaborating_domains tracking variable")

    # Check 2: via_a2a flag in results
    if "'via_a2a'" in content or "result['via_a2a']" in content:
        checks_passed.append("via_a2a flag for A2A results")
    else:
        checks_failed.append("via_a2a flag for A2A results")

    # Check 3: a2a_collaborating_domains.append()
    if "a2a_collaborating_domains.append" in content:
        checks_passed.append("A2A domain tracking on success")
    else:
        checks_failed.append("A2A domain tracking on success")

    # Check 4: stats['a2a_collaborations']
    if "stats['a2a_collaborations']" in content:
        checks_passed.append("stats['a2a_collaborations'] statistic")
    else:
        checks_failed.append("stats['a2a_collaborations'] statistic")

    # Check 5: stats['a2a_results_count']
    if "stats['a2a_results_count']" in content:
        checks_passed.append("stats['a2a_results_count'] statistic")
    else:
        checks_failed.append("stats['a2a_results_count'] statistic")

    # Check 6: 'a2a_domains' in response metadata
    if "'a2a_domains':" in content:
        checks_passed.append("'a2a_domains' in response metadata")
    else:
        checks_failed.append("'a2a_domains' in response metadata")

    # Check 7: RNE counting in calculate_statistics
    if "'rne_' in stages_str" in content:
        checks_passed.append("RNE result counting in statistics")
    else:
        checks_failed.append("RNE result counting in statistics")

    # Check 8: A2A metadata in transform_results
    if "result.get('via_a2a')" in content:
        checks_passed.append("A2A metadata in transform_results")
    else:
        checks_failed.append("A2A metadata in transform_results")

    # Print results
    print(f"\n✅ PASSED ({len(checks_passed)}/8):")
    for check in checks_passed:
        print(f"   ✓ {check}")

    if checks_failed:
        print(f"\n❌ FAILED ({len(checks_failed)}/8):")
        for check in checks_failed:
            print(f"   ✗ {check}")
        return False
    else:
        print("\n✅ ALL CHECKS PASSED!")
        return True


def main():
    """Run all verifications"""
    print("\n" + "="*80)
    print("RNE and A2A Code Fix Verification")
    print("="*80)

    results = {}

    # Verify domain_agent.py fix
    try:
        results['domain_agent'] = verify_domain_agent_fix()
    except Exception as e:
        print(f"❌ ERROR verifying domain_agent.py: {e}")
        results['domain_agent'] = False

    # Verify search.py fix
    try:
        results['search_api'] = verify_search_api_fix()
    except Exception as e:
        print(f"❌ ERROR verifying search.py: {e}")
        results['search_api'] = False

    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)

    print(f"\n1. domain_agent.py (RNE Cross-Domain): {'✅ PASS' if results['domain_agent'] else '❌ FAIL'}")
    print(f"2. search.py (A2A Statistics):         {'✅ PASS' if results['search_api'] else '❌ FAIL'}")

    all_passed = all(results.values())

    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL FIXES VERIFIED SUCCESSFULLY!")
        print("\nExpected behavior after these fixes:")
        print("  1. RNE will return cross-domain results (e.g., 시행령 from different domain)")
        print("  2. Frontend will show correct A2A collaboration count")
        print("  3. API response will include a2a_domains list")
        print("  4. Statistics will properly count RNE results")
    else:
        print("⚠️  VERIFICATION FAILED - Please review the failed checks above")
    print("="*80)

    return all_passed


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
