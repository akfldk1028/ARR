# Hello LangGraph

## 🎯 무엇을 하는 프로젝트인가요?

시를 작성하는 AI 에이전트입니다. 사용자 피드백을 받아서 시를 개선합니다.

## 🤖 에이전트 설명

- **이름**: Mr. Poet (시인 에이전트)
- **기능**: 주제를 받아 시를 작성하고, 사용자 피드백을 받아 개선
- **프레임워크**: LangGraph
- **LLM 모델**: OpenAI GPT-4o-mini

## 📋 기술 스택

- **LangGraph**: 워크플로우 관리
- **SQLite**: 대화 기록 저장
- **OpenAI**: 언어 모델

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일에 OpenAI API 키를 입력하세요:
```env
OPENAI_API_KEY=your_api_key_here
```

### 2. LangGraph 서버 실행
```bash
uv run langgraph dev
```

### 3. 브라우저에서 접속
```
http://localhost:8123
```

## 💡 사용 예시

1. 주제를 입력 (예: "바다에 대한 시를 써줘")
2. 에이전트가 시를 작성
3. 피드백 제공 (예: "더 감성적으로 써줘")
4. 에이전트가 시를 개선

## 📦 필요한 패키지

이미 설치됨! (uv sync 완료)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
