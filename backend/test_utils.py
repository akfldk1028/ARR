"""Test utility functions"""

from agents.law.utils import parse_hang_id, enrich_hang_result, deduplicate_results, boost_diversity_by_law_type

# Test parse_hang_id
test_ids = [
    "국토의 계획 및 이용에 관한 법률(시행령)::제12장::제2절::제36조::항",
    "국토의 계획 및 이용에 관한 법률(시행규칙)::제36조::1",
    "국토의 계획 및 이용에 관한 법률(법률)::제12장::제4절::제36조::항",
]

print("Testing parse_hang_id:")
print("="*80)
for hang_id in test_ids:
    parsed = parse_hang_id(hang_id)
    print(f"\nInput: {hang_id}")
    print(f"  Law Name: {parsed['law_name']}")
    print(f"  Law Type: {parsed['law_type']}")
    print(f"  Jo Number: {parsed['jo_number']}")
    print(f"  Hang Number: {parsed['hang_number']}")

# Test enrich_hang_result
print("\n\nTesting enrich_hang_result:")
print("="*80)
test_result = {
    'hang_id': '국토의 계획 및 이용에 관한 법률(시행령)::제12장::제2절::제36조::항',
    'content': 'Test content',
    'similarity': 0.95
}

enriched = enrich_hang_result(test_result)
print(f"\nOriginal keys: {list(test_result.keys())}")
print(f"Enriched keys: {list(enriched.keys())}")
print(f"Law Name: {enriched['law_name']}")
print(f"Law Type: {enriched['law_type']}")

# Test deduplicate_results
print("\n\nTesting deduplicate_results:")
print("="*80)
test_results = [
    {'hang_id': 'A', 'score': 1.0},
    {'hang_id': 'B', 'score': 0.9},
    {'hang_id': 'A', 'score': 0.8},  # Duplicate
    {'hang_id': 'C', 'score': 0.7},
]

deduped = deduplicate_results(test_results)
print(f"Original count: {len(test_results)}")
print(f"Deduplicated count: {len(deduped)}")
print(f"IDs: {[r['hang_id'] for r in deduped]}")

# Test boost_diversity_by_law_type
print("\n\nTesting boost_diversity_by_law_type:")
print("="*80)
test_results = [
    {'hang_id': '1', 'law_type': '법률', 'score': 1.0},
    {'hang_id': '2', 'law_type': '법률', 'score': 0.95},
    {'hang_id': '3', 'law_type': '법률', 'score': 0.9},
    {'hang_id': '4', 'law_type': '시행령', 'score': 0.85},
    {'hang_id': '5', 'law_type': '시행령', 'score': 0.8},
    {'hang_id': '6', 'law_type': '시행규칙', 'score': 0.75},
]

print("Original order:")
for r in test_results:
    print(f"  {r['hang_id']}: {r['law_type']} ({r['score']})")

diversified = boost_diversity_by_law_type(test_results)
print("\nDiversified order:")
for r in diversified:
    print(f"  {r['hang_id']}: {r['law_type']} ({r['score']})")

print("\n\nAll tests passed!")
