# AI Agents Masterclass - 전체 프로젝트 가이드

## 📚 프로젝트 개요

18개의 AI 에이전트 프로젝트로 구성된 학습 저장소입니다. 다양한 AI 프레임워크(OpenAI Agents, LangGraph, Google ADK, CrewAI, AutoGen)를 활용한 실전 프로젝트를 포함합니다.

---
  📋 프레임워크별 요약

  LangGraph (6개 서버 실행 중)

  - hello-langgraph (포트 8101)
  - tutor-agent (포트 8102)
  - multi-agent-architectures (포트 8103)
  - youtube-thumbnail-maker (포트 8104)
  - a2a/PhilosophyHelperAgent (포트 8002)
  - workflow-architectures (Jupyter)

  Google ADK (4개 검증 완료)

  - a2a/HistoryHelperAgent (포트 8001 실행 중)
  - financial-analyst (로드 확인)
  - youtube-shorts-maker (import 확인)
  - email-refiner-agent (import 확인)

  CrewAI (3개 검증 완료 - Python 3.11)

  - content-pipeline-agent
  - job-hunter-agent
  - news-reader-agent

  Streamlit (2개 실행 중)

  - chatgpt-clone (포트 8501)
  - customer-support-agent (포트 8502)

  기타 프레임워크

  - FastAPI: deployment (포트 8100 실행 중)
  - pytest: workflow-testing (5/5 테스트 통과)
  - AutoGen: deep-research-clone (0.9.7 확인)
  - Jupyter: my-first-agent, workflow-architectures


## 🗂️ 프로젝트 목록 및 난이도

### 🟢 입문 (Beginner)

1. **my-first-agent** - 가장 기본적인 OpenAI 에이전트
2. **hello-langgraph** - LangGraph 입문 (시 작성 봇)

### 🟡 중급 (Intermediate)

3. **chatgpt-clone** - ChatGPT 클론 (Streamlit UI + 다양한 도구)
4. **customer-support-agent** - 고객 지원 (멀티 에이전트 + 음성)
5. **tutor-agent** - AI 튜터 시스템
6. **email-refiner-agent** - 이메일 개선 (Google ADK)
7. **youtube-thumbnail-maker** - 썸네일 자동 생성
8. **workflow-architectures** - 워크플로우 패턴 학습
9. **workflow-testing** - 에이전트 테스트 학습
10. **multi-agent-architectures** - 다중 에이전트 패턴
11. **deployment** - 프로덕션 배포

### 🔴 고급 (Advanced)

12. **financial-analyst** - 금융 분석 (Google ADK + 멀티 에이전트)
13. **youtube-shorts-maker** - YouTube Shorts 자동 제작
14. **content-pipeline-agent** - 콘텐츠 파이프라인 (CrewAI)
15. **job-hunter-agent** - 구직 자동화 (CrewAI)
16. **news-reader-agent** - 뉴스 수집 및 요약 (CrewAI)
17. **deep-research-clone** - 심층 리서치 (AutoGen)
18. **a2a** - Agent-to-Agent 통신

---

## 🛠️ 프레임워크별 분류

### OpenAI Agents
- my-first-agent
- chatgpt-clone
- customer-support-agent
- deployment

### LangGraph
- hello-langgraph
- tutor-agent
- youtube-thumbnail-maker
- workflow-architectures
- workflow-testing
- multi-agent-architectures

### Google ADK
- financial-analyst
- youtube-shorts-maker
- email-refiner-agent
- a2a (hybrid)

### CrewAI
- content-pipeline-agent
- job-hunter-agent
- news-reader-agent

### AutoGen
- deep-research-clone

---

## 🚀 빠른 시작

### 1. 환경 설정 완료 여부 확인

모든 프로젝트의 환경 설정이 완료되었습니다! ✅

- ✅ uv 설치됨
- ✅ Python 3.13 (14개 프로젝트)
- ✅ Python 3.11 (3개 CrewAI 프로젝트)
- ✅ 가상환경 생성 완료
- ✅ 패키지 설치 완료
- ✅ .env 파일 생성 완료

### 2. 필요한 API 키

#### 이미 설정된 API 키:
- ✅ **OpenAI API Key** (17개 프로젝트)

#### 추가 필요한 API 키:
- ⚠️ **Google Gemini API Key** (4개 프로젝트)
  - financial-analyst
  - youtube-shorts-maker
  - email-refiner-agent
  - a2a

- ⚠️ **Firecrawl API Key** (4개 프로젝트)
  - content-pipeline-agent (필수)
  - job-hunter-agent (필수)
  - deep-research-clone (필수)
  - tutor-agent (선택)

---

## 📋 추천 학습 순서

### Phase 1: 기초 (1-2주)
1. my-first-agent → OpenAI 기본
2. hello-langgraph → LangGraph 기본
3. chatgpt-clone → 실용적인 UI

### Phase 2: 패턴 학습 (2-3주)
4. workflow-architectures → 다양한 패턴
5. multi-agent-architectures → 멀티 에이전트
6. workflow-testing → 테스트 방법

### Phase 3: 실전 프로젝트 (3-4주)
7. customer-support-agent → 고객 지원
8. tutor-agent → 교육 시스템
9. content-pipeline-agent → 콘텐츠 자동화

### Phase 4: 고급 프로젝트 (4주+)
10. financial-analyst → 금융 분석
11. deep-research-clone → 심층 리서치
12. a2a → 에이전트 간 통신

---

## 🎯 프로젝트별 실행 명령어

### Python 3.13 프로젝트 (14개)

```bash
# LangGraph 서버
cd hello-langgraph && uv run langgraph dev

# Streamlit 앱
cd chatgpt-clone && uv run streamlit run main.py
cd customer-support-agent && uv run streamlit run main.py

# Python 스크립트
cd my-first-agent && uv run jupyter notebook
cd tutor-agent && uv run python main.py
cd youtube-thumbnail-maker && uv run python graph.py
cd workflow-testing && uv run pytest tests.py
cd multi-agent-architectures && uv run python graph.py
cd deployment && uv run python main.py

# Google ADK 프로젝트
cd financial-analyst && uv run python -m financial_advisor.agent
cd youtube-shorts-maker && uv run python -m youtube_shorts_maker.agent
cd email-refiner-agent && uv run python -m travel_advisor_agent.agent

# A2A (3개 터미널 필요)
cd a2a && uv run python -m remote_adk_agent.agent  # 터미널 1
cd a2a && uv run uvicorn langraph_agent.server:app --port 8002  # 터미널 2
cd a2a && uv run python -c "from user_facing_agent.user_facing_agent.agent import root_agent; root_agent.run('질문')"  # 터미널 3
```

### Python 3.11 프로젝트 (3개 CrewAI)

```bash
cd content-pipeline-agent && uv run python main.py
cd job-hunter-agent && uv run python main.py
cd news-reader-agent && uv run python main.py
```

### AutoGen

```bash
cd deep-research-clone && uv run jupyter notebook
```

---

## 🔑 API 키 발급 방법

### OpenAI API Key ✅
https://platform.openai.com/api-keys

### Google Gemini API Key
https://makersuite.google.com/app/apikey

### Firecrawl API Key
https://firecrawl.dev

---

## 💡 각 프로젝트 상세 정보

각 프로젝트 폴더에 `README_KO.md` 파일이 있습니다!
- 프로젝트 설명
- 에이전트 구조
- 실행 방법
- 필요한 API 키

---

## 📦 설치된 패키지

모든 프로젝트의 패키지가 설치되었습니다!
- 각 프로젝트는 독립적인 가상환경 (.venv) 사용
- Python 3.13 또는 3.11 자동 선택
- uv로 종속성 관리

---

## ⚠️ 특이사항

### CrewAI 프로젝트 (Python 3.11)
- content-pipeline-agent
- job-hunter-agent
- news-reader-agent

**이유**: ChromaDB의 chroma-hnswlib가 Python 3.13용 prebuilt wheel이 없어서 Python 3.11을 사용합니다.

---

## 🎓 학습 리소스

- 각 프로젝트의 README_KO.md
- 프로젝트 코드 주석
- .env 파일 예시

---

## 🆘 문제 해결

### API 키 오류
각 프로젝트의 `.env` 파일에서 API 키를 확인하세요.

### 패키지 오류
```bash
cd <프로젝트-폴더>
uv sync  # 재설치
```

### Python 버전 오류
- 대부분 프로젝트: Python 3.13 사용
- CrewAI 프로젝트: Python 3.11 사용

---

## 🎯 다음 단계

1. **간단한 프로젝트부터 시작** (my-first-agent 또는 hello-langgraph)
2. **API 키 발급** (필요한 것만)
3. **각 프로젝트의 README_KO.md 읽기**
4. **실행 및 실험**

---

## 📞 추가 정보

각 프로젝트 폴더의 `README_KO.md`를 참조하세요!

**Happy Coding! 🚀**
