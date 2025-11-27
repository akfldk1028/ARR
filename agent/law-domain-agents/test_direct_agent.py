"""
직접 도메인 에이전트 테스트 - 상태 전달 확인
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    os.system('chcp 65001 > nul')

sys.path.insert(0, str(Path(__file__).parent / "shared"))

import asyncio
from domain_manager import get_domain_manager
from domain_agent_factory import get_agent_factory

async def test_direct_agent():
    print("="*70)
    print("Direct Domain Agent Test")
    print("="*70)

    # Get domain manager
    domain_manager = get_domain_manager()
    domains = domain_manager.get_all_domains()

    print(f"\nAvailable domains: {len(domains)}")
    for domain in domains:
        print(f"  - {domain.domain_name} ({domain.node_count} nodes)")

    # Get agent factory
    factory = get_agent_factory()

    # Test with first domain (국토 계획 및 이용)
    test_domain = domains[0]
    print(f"\nTesting with: {test_domain.domain_name}")

    # Create agent
    agent = factory.create_agent(test_domain)

    # Test query
    query = "용도지역이란 무엇인가요?"
    print(f"Query: {query}\n")

    # Invoke agent
    response = await agent.ainvoke(query)

    print(f"\nResponse:")
    print(response)

    print("\n" + "="*70)
    print("Test complete")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(test_direct_agent())
