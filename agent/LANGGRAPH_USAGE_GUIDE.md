# LangGraph 사용 가이드

## 서버 접속 방법

LangGraph 서버는 루트 경로(`/`)에서 UI를 제공하지 않습니다. 다음 방법들로 접속하세요:

### 1. LangGraph Studio (권장)
가장 강력하고 사용하기 쉬운 방법입니다.

브라우저에서 다음 URL로 접속:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8101
```

### 2. API 문서 확인
Swagger UI를 통한 API 문서 확인:
```
http://localhost:8101/docs
```

### 3. Python SDK 사용 (프로그래밍 방식)
`test_langgraph_client.py` 파일을 실행:
```bash
cd D:\Data\11_Backend\01_ARR\agent\hello-langgraph
python -m uv run python ../test_langgraph_client.py
```

## 실행 중인 LangGraph 서버

| 프로젝트 | 포트 | 어시스턴트 이름 | 설명 |
|---------|------|---------------|------|
| hello-langgraph | 8101 | mr_poet | 시를 작성하고 피드백을 받는 에이전트 |
| tutor-agent | 8102 | - | 튜터 에이전트 |
| multi-agent-architectures | 8103 | - | 다중 에이전트 아키텍처 |
| youtube-thumbnail-maker | 8104 | - | YouTube 썸네일 제작 |

## 서버 정보 확인
```bash
curl http://localhost:8101/info
```

출력:
```json
{
  "version": "0.4.11",
  "langgraph_py_version": "0.6.6",
  "flags": {
    "assistants": true,
    "crons": false,
    "langsmith": false,
    "langsmith_tracing_replicas": true
  }
}
```

## Python SDK 사용 예제

### 기본 사용법
```python
import asyncio
from langgraph_sdk import get_client

async def main():
    # 서버 연결
    client = get_client(url="http://localhost:8101")

    # 스레드 생성
    thread = await client.threads.create()

    # 메시지 전송 및 응답 스트리밍
    async for chunk in client.runs.stream(
        thread["thread_id"],
        "mr_poet",  # 어시스턴트 이름
        input={"messages": [{"role": "user", "content": "Write a poem about AI"}]},
        stream_mode="updates"
    ):
        print(chunk.event, chunk.data)

asyncio.run(main())
```

### 인터럽트 처리
mr_poet 에이전트는 `get_human_feedback` 도구를 사용하여 사용자 피드백을 받습니다.
인터럽트를 처리하려면 LangGraph Studio UI를 사용하는 것이 가장 쉽습니다.

## 기타 에이전트 접속 방법

### Streamlit 앱 (웹 UI)
- ChatGPT Clone: http://localhost:8501
- Customer Support Agent: http://localhost:8502

### A2A 에이전트 (Agent-to-Agent)
- HistoryHelperAgent: http://localhost:8001
- PhilosophyHelperAgent: http://localhost:8002

### FastAPI
- Deployment: http://localhost:8100/docs

## 문제 해결

### "404 Not Found" 오류
- 루트 경로(`/`)는 지원되지 않습니다
- 위의 접속 방법 중 하나를 사용하세요

### 서버 재시작
```bash
# 서버 중지는 프로세스 종료 후
cd D:\Data\11_Backend\01_ARR\agent\hello-langgraph
python -m uv run langgraph dev --port 8101
```

## 참고 자료
- LangGraph 문서: https://langchain-ai.github.io/langgraph/
- LangSmith: https://smith.langchain.com/
