"""
도메인 정보 확인 - Neo4j에서 description 조회
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "shared"))

from domain_manager import get_domain_manager

def check_domains():
    print("="*70)
    print("Domain Information Check")
    print("="*70)

    manager = get_domain_manager()
    domains = manager.get_all_domains()

    print(f"\nTotal domains: {len(domains)}\n")

    for domain in domains:
        print(f"Domain: {domain.domain_name}")
        print(f"  ID: {domain.domain_id}")
        print(f"  Description: {domain.description}")
        print(f"  Node count: {domain.node_count}")
        print(f"  Agent slug: {domain.agent_slug()}")
        print()

    print("="*70)

if __name__ == "__main__":
    check_domains()
