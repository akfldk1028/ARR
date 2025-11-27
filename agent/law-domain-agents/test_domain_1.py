#!/usr/bin/env python3
"""
Test script for Domain 1 Agent

Tests:
1. Agent card endpoint
2. Health endpoint
3. Message endpoint (A2A protocol)
"""

import httpx
import json
import sys
from pathlib import Path

# Add domain-1-agent to path
sys.path.insert(0, str(Path(__file__).parent / "domain-1-agent"))
from config import config


def test_agent_card():
    """Test agent card endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Agent Card Endpoint")
    print("="*60)

    url = f"http://localhost:{config.DOMAIN_PORT}/.well-known/agent-card.json"
    print(f"URL: {url}")

    try:
        response = httpx.get(url, timeout=5.0)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\nAgent Card:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\n✓ Test PASSED")
            return True
        else:
            print(f"\n✗ Test FAILED: Status {response.status_code}")
            return False

    except Exception as e:
        print(f"\n✗ Test FAILED: {e}")
        return False


def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("TEST 2: Health Endpoint")
    print("="*60)

    url = f"http://localhost:{config.DOMAIN_PORT}/health"
    print(f"URL: {url}")

    try:
        response = httpx.get(url, timeout=5.0)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\nHealth Status:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\n✓ Test PASSED")
            return True
        else:
            print(f"\n✗ Test FAILED: Status {response.status_code}")
            return False

    except Exception as e:
        print(f"\n✗ Test FAILED: {e}")
        return False


def test_message():
    """Test message endpoint (A2A protocol)"""
    print("\n" + "="*60)
    print("TEST 3: Message Endpoint (A2A Protocol)")
    print("="*60)

    url = f"http://localhost:{config.DOMAIN_PORT}/messages"
    print(f"URL: {url}")

    # JSON-RPC 2.0 request
    request_data = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "test-msg-001",
                "contextId": "test-context-001",
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": "17조에 대해 알려주세요"
                    }
                ]
            }
        },
        "id": "test-req-001"
    }

    print("\nRequest:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))

    try:
        response = httpx.post(
            url,
            json=request_data,
            timeout=30.0
        )
        print(f"\nStatus: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\n✓ Test PASSED")
            return True
        else:
            print(f"\n✗ Test FAILED: Status {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"\n✗ Test FAILED: {e}")
        return False


def main():
    """Run all tests"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║ Testing Domain 1 Agent                                       ║
║ {config.DOMAIN_NAME:<58} ║
╚══════════════════════════════════════════════════════════════╝

Port: {config.DOMAIN_PORT}

Make sure the agent is running:
  python run_domain_1.py
""")

    results = []

    # Run tests
    results.append(("Agent Card", test_agent_card()))
    results.append(("Health", test_health()))
    results.append(("Message", test_message()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
