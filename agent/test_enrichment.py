"""
Test enrichment functions
"""
import sys
from pathlib import Path

# Add law-domain-agents to path
agent_root = Path(__file__).parent
sys.path.insert(0, str(agent_root / "law-domain-agents"))

from law_utils import enrich_search_result

# Test case: Sample result from search
sample_result = {
    "hang_id": "국토의 계획 및 이용에 관한 법률(법률)::제12장::제2절::제36조::제",
    "content": "용도지역... (sample content)",
    "unit_path": "제12장_제2절_제36조_제",
    "similarity": 0.9,
    "stage": "exact_match"
}

print("Testing enrichment...")
print("=" * 80)
print("\nInput:")
print(sample_result)

enriched = enrich_search_result(sample_result)

print("\nEnriched:")
print(enriched)

print("\nExtracted fields:")
print(f"  law_name: {enriched.get('law_name', 'N/A')}")
print(f"  law_type: {enriched.get('law_type', 'N/A')}")
print(f"  article: {enriched.get('article', 'N/A')}")
