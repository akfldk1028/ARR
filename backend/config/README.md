# config/ - 프로젝트 설정

## 개요
프로젝트 전역 설정 관리. 에이전트 설정, API 설정, 앱 설정 분리.

## 핵심 기능
- 에이전트 설정 관리
- API 설정 관리
- 앱 설정 관리

---

## 파일 구조 및 역할

| 파일 | 역할 | 설정 항목 |
|------|------|----------|
| `agent_config.py` | 에이전트 설정 | 에이전트 타입, 모델명, 시스템 프롬프트 |
| `api_config.py` | API 설정 | API 키, 엔드포인트, 타임아웃 |
| `app_settings.py` | 앱 설정 | 기능 플래그, 제한값, 캐시 설정 |

---

## 사용 예시

```python
from config.agent_config import AGENT_DEFAULTS
from config.api_config import OPENAI_API_KEY
from config.app_settings import MAX_MESSAGE_LENGTH

# 에이전트 기본 설정
agent = Agent(
    model_name=AGENT_DEFAULTS['model_name'],
    system_prompt=AGENT_DEFAULTS['system_prompt']
)
```

## 환경 변수 연동
```python
# api_config.py
import os

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
NEO4J_URI = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
```

---

## 설정 우선순위
1. 환경 변수 (`.env`)
2. config/ 파일 기본값
3. Django settings.py
