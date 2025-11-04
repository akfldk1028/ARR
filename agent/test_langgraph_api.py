import requests
import json

# LangGraph API 테스트
url = "http://localhost:8101/threads"

# 1. Thread 생성
response = requests.post(url)
thread = response.json()
thread_id = thread["thread_id"]
print(f"Thread ID: {thread_id}")

# 2. 메시지 전송
run_url = f"http://localhost:8101/threads/{thread_id}/runs/stream"
data = {
    "assistant_id": "agent",
    "input": {
        "messages": [{
            "role": "user",
            "content": "What is 2+2?"
        }]
    },
    "stream_mode": "values"
}

print("\nSending message: What is 2+2?")
print("\nResponse:")
response = requests.post(run_url, json=data, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
