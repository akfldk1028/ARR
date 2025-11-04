# Agent-to-Agent (A2A) Communication

## 🎯 무엇을 하는 프로젝트인가요?

여러 AI 에이전트가 서로 통신하며 협업하는 시스템입니다. 학생 숙제 도우미 에이전트가 역사 전문가와 철학 전문가 에이전트에게 작업을 위임합니다.

## 🤖 에이전트 구조

### 3개의 에이전트:

1. **HistoryHelperAgent** (포트 8001)
   - Google ADK 기반
   - 역사 관련 질문 답변
   - A2A 프로토콜로 통신

2. **PhilosophyHelperAgent** (포트 8002)
   - LangGraph + FastAPI 기반
   - 철학 관련 질문 답변
   - A2A 프로토콜로 통신

3. **StudentHelperAgent** (메인)
   - 학생 질문을 받아 적절한 전문가 에이전트에 전달
   - 두 에이전트의 응답을 통합

## 📋 기술 스택

- **Google ADK**: Agent Development Kit
- **LangGraph**: 워크플로우 관리
- **FastAPI**: API 서버
- **A2A Protocol**: Agent-to-Agent 통신 프로토콜
- **LiteLLM**: 다양한 LLM 통합

## 🚀 실행 방법

### 1. 환경 변수 설정
`.env` 파일 확인:
```env
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
```

### 2. 에이전트 실행 (3개 터미널 필요)

#### 터미널 1: HistoryHelperAgent 시작
```bash
cd ai-agents-masterclass-master/ai-agents-masterclass-master/a2a
uv run python -m remote_adk_agent.agent
```

#### 터미널 2: PhilosophyHelperAgent 시작
```bash
cd ai-agents-masterclass-master/ai-agents-masterclass-master/a2a
uv run uvicorn langraph_agent.server:app --port 8002
```

#### 터미널 3: StudentHelperAgent 실행
```bash
cd ai-agents-masterclass-master/ai-agents-masterclass-master/a2a
uv run python -c "from user_facing_agent.user_facing_agent.agent import root_agent; root_agent.run('What is the French Revolution?')"
```

## 💡 작동 원리

1. 사용자가 StudentHelperAgent에 질문
2. StudentHelperAgent가 질문 분석 (역사? 철학?)
3. 해당 전문가 에이전트로 요청 전달 (A2A 통신)
4. 전문가 에이전트 응답
5. StudentHelperAgent가 답변 통합 및 반환

## 📦 필요한 패키지

이미 설치됨! (uv sync 완료)

## 🔑 필요한 API 키

- ✅ OpenAI API Key (필수)
- ⚠️ Google API Key (권장)

## 🌟 A2A 프로토콜

- **Agent Card**: 각 에이전트의 능력 설명 (/.well-known/agent-card.json)
- **JSONRPC**: 메시지 전달 프로토콜
- **Remote Agents**: 네트워크를 통한 에이전트 호출
