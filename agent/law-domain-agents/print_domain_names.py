"""
Print domain names to debug keyword matching
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "shared"))

from domain_manager import get_domain_manager

if __name__ == "__main__":
    manager = get_domain_manager()
    domains = manager.get_all_domains()

    print("Domain names in Neo4j:")
    print("=" * 70)
    for i, domain in enumerate(domains, 1):
        print(f"\n{i}. {repr(domain.domain_name)}")
        print(f"   Length: {len(domain.domain_name)}")
        print(f"   Has '법률': {'법률' in domain.domain_name}")
        print(f"   Has '시행령': {'시행령' in domain.domain_name}")
        print(f"   Has '시행규칙': {'시행규칙' in domain.domain_name}")
        print(f"   Has '국토': {'국토' in domain.domain_name}")
        print(f"   Has '계획': {'계획' in domain.domain_name}")
