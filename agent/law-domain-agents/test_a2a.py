"""
A2A 프로토콜 테스트
"""

import requests
import json

# 테스트할 도메인 slug (첫 번째 도메인)
SLUG = "domain_domain_09b3af0d"
BASE_URL = "http://localhost:8011"

# JSON-RPC 2.0 메시지
request_payload = {
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
        "message": {
            "parts": [
                {
                    "kind": "text",
                    "text": "도시계획이란 무엇인가요?"
                }
            ]
        }
    },
    "id": "test-001"
}

print("=" * 70)
print("A2A Protocol Test")
print("=" * 70)
print(f"Target: {BASE_URL}/messages/{SLUG}")
print(f"Query: 도시계획이란 무엇인가요?")
print("=" * 70)

try:
    response = requests.post(
        f"{BASE_URL}/messages/{SLUG}",
        json=request_payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

except requests.exceptions.Timeout:
    print("\n❌ Request timeout (30s)")
except Exception as e:
    print(f"\n❌ Error: {e}")
