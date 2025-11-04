# AI Agents 프로젝트 설정 가이드

이 가이드를 따라 순차적으로 명령어를 실행하면 모든 프로젝트를 설정할 수 있습니다.

---

## 📋 현재 상태 확인

```bash
# 현재 위치로 이동
cd /d/Data/11_Backend/01_ARR/agent

# 프로젝트 목록 확인
ls -la

# 18개 프로젝트 + README_KO.md가 있어야 함
```

**중요**:
- ✅ `.venv` 폴더가 **없어야** 정상입니다 (복사 시 제외됨)
- ✅ 각 프로젝트에 `pyproject.toml`과 `uv.lock` 파일이 있어야 합니다

---

## 1️⃣ 사전 준비

### uv 패키지 매니저 설치 확인

```bash
# uv 버전 확인
uv --version

# 없으면 설치
pip install uv
```

### Python 버전 확인

```bash
# 사용 가능한 Python 버전 확인
uv python list
```

필요한 버전:
- **Python 3.13**: 15개 프로젝트
- **Python 3.11**: 3개 CrewAI 프로젝트 (content-pipeline-agent, job-hunter-agent, news-reader-agent)

---

## 2️⃣ 프로젝트별 설정 (순차 실행)

### 방법 A: 전체 자동 설정 (추천)

```bash
# 현재 위치: /d/Data/11_Backend/01_ARR/agent

# Python 3.13 프로젝트 (14개) 자동 설정
for dir in a2a chatgpt-clone customer-support-agent deep-research-clone deployment email-refiner-agent financial-analyst hello-langgraph multi-agent-architectures my-first-agent tutor-agent workflow-architectures workflow-testing youtube-thumbnail-maker; do
  echo "================================================"
  echo "Setting up $dir (Python 3.13)..."
  echo "================================================"
  cd "$dir"
  uv python pin 3.13
  uv sync
  cd ..
  echo "✓ $dir setup complete!"
  echo ""
done

# Python 3.11 프로젝트 (3개 CrewAI) 자동 설정
for dir in content-pipeline-agent job-hunter-agent news-reader-agent; do
  echo "================================================"
  echo "Setting up $dir (Python 3.11)..."
  echo "================================================"
  cd "$dir"
  uv python pin 3.11
  uv sync
  cd ..
  echo "✓ $dir setup complete!"
  echo ""
done

# YouTube Shorts Maker (Google ADK - Python 3.13)
echo "================================================"
echo "Setting up youtube-shorts-maker (Python 3.13)..."
echo "================================================"
cd youtube-shorts-maker
uv python pin 3.13
uv sync
cd ..
echo "✓ youtube-shorts-maker setup complete!"
```

**예상 소요 시간**: 30-60분 (인터넷 속도에 따라)

---

### 방법 B: 개별 프로젝트 설정

특정 프로젝트만 설정하고 싶을 때:

#### Python 3.13 프로젝트

```bash
cd /d/Data/11_Backend/01_ARR/agent/tutor-agent
uv python pin 3.13
uv sync
cd ..
```

#### Python 3.11 프로젝트 (CrewAI)

```bash
cd /d/Data/11_Backend/01_ARR/agent/content-pipeline-agent
uv python pin 3.11
uv sync
cd ..
```

---

## 3️⃣ API 키 설정

각 프로젝트의 `.env` 파일에 API 키가 이미 설정되어 있습니다.

### OpenAI API Key (이미 설정됨 ✅)

17개 프로젝트에 이미 설정됨:
```
OPENAI_API_KEY=your_openai_api_key_here
```

### 추가 필요한 API 키

#### Google Gemini API Key (4개 프로젝트)

```bash
# 발급: https://makersuite.google.com/app/apikey

# 설정이 필요한 프로젝트
nano /d/Data/11_Backend/01_ARR/agent/financial-analyst/.env
nano /d/Data/11_Backend/01_ARR/agent/youtube-shorts-maker/.env
nano /d/Data/11_Backend/01_ARR/agent/email-refiner-agent/.env
nano /d/Data/11_Backend/01_ARR/agent/a2a/.env
```

각 파일에 추가:
```env
GOOGLE_API_KEY=your_google_api_key_here
```

#### Firecrawl API Key (4개 프로젝트)

```bash
# 발급: https://firecrawl.dev

# 필수 프로젝트
nano /d/Data/11_Backend/01_ARR/agent/content-pipeline-agent/.env
nano /d/Data/11_Backend/01_ARR/agent/job-hunter-agent/.env
nano /d/Data/11_Backend/01_ARR/agent/deep-research-clone/.env

# 선택 프로젝트
nano /d/Data/11_Backend/01_ARR/agent/tutor-agent/.env
```

각 파일에 추가:
```env
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
```

---

## 4️⃣ 프로젝트 실행

### LangGraph 서버 (포트 8001-8010)

```bash
# hello-langgraph
cd /d/Data/11_Backend/01_ARR/agent/hello-langgraph
uv run langgraph dev

# 다른 터미널에서
cd /d/Data/11_Backend/01_ARR/agent/tutor-agent
uv run langgraph dev --port 8002
```

### Streamlit 앱 (웹 UI)

```bash
# ChatGPT Clone
cd /d/Data/11_Backend/01_ARR/agent/chatgpt-clone
uv run streamlit run main.py

# Customer Support Agent
cd /d/Data/11_Backend/01_ARR/agent/customer-support-agent
uv run streamlit run main.py
```

### Python 스크립트

```bash
# My First Agent (Jupyter)
cd /d/Data/11_Backend/01_ARR/agent/my-first-agent
uv run jupyter notebook

# Tutor Agent
cd /d/Data/11_Backend/01_ARR/agent/tutor-agent
uv run python main.py

# Workflow Testing
cd /d/Data/11_Backend/01_ARR/agent/workflow-testing
uv run pytest tests.py -v
```

### Google ADK 프로젝트

```bash
# Financial Analyst
cd /d/Data/11_Backend/01_ARR/agent/financial-analyst
uv run python -m financial_advisor.agent

# YouTube Shorts Maker
cd /d/Data/11_Backend/01_ARR/agent/youtube-shorts-maker
uv run python -m youtube_shorts_maker.agent

# Email Refiner
cd /d/Data/11_Backend/01_ARR/agent/email-refiner-agent
uv run python -m travel_advisor_agent.agent
```

### CrewAI 프로젝트

```bash
# Content Pipeline Agent
cd /d/Data/11_Backend/01_ARR/agent/content-pipeline-agent
uv run python main.py

# Job Hunter Agent
cd /d/Data/11_Backend/01_ARR/agent/job-hunter-agent
uv run python main.py

# News Reader Agent
cd /d/Data/11_Backend/01_ARR/agent/news-reader-agent
uv run python main.py
```

### A2A (Agent-to-Agent) - 3개 터미널 필요

```bash
# 터미널 1: Remote ADK Agent
cd /d/Data/11_Backend/01_ARR/agent/a2a
uv run python -m remote_adk_agent.agent

# 터미널 2: LangGraph Agent Server
cd /d/Data/11_Backend/01_ARR/agent/a2a
uv run uvicorn langraph_agent.server:app --port 8002

# 터미널 3: User Facing Agent
cd /d/Data/11_Backend/01_ARR/agent/a2a
uv run python -c "from user_facing_agent.user_facing_agent.agent import root_agent; root_agent.run('질문')"
```

---

## 5️⃣ 문제 해결

### 패키지 설치 오류

```bash
# 특정 프로젝트 재설치
cd /d/Data/11_Backend/01_ARR/agent/<프로젝트명>
rm -rf .venv
uv sync
```

### Python 버전 오류

```bash
# Python 버전 확인
cd /d/Data/11_Backend/01_ARR/agent/<프로젝트명>
uv python pin 3.13  # 또는 3.11
uv sync
```

### API 키 오류

```bash
# .env 파일 확인
cat /d/Data/11_Backend/01_ARR/agent/<프로젝트명>/.env

# 수정
nano /d/Data/11_Backend/01_ARR/agent/<프로젝트명>/.env
```

### 포트 충돌

```bash
# 사용 중인 포트 확인 (Windows)
netstat -ano | findstr :8000

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID> /F

# 다른 포트 사용
uv run langgraph dev --port 8888
```

---

## 6️⃣ Docker 배포 (선택)

각 프로젝트를 Docker로 배포하려면:

### Dockerfile 생성 (예: tutor-agent)

```bash
cd /d/Data/11_Backend/01_ARR/agent/tutor-agent
```

```dockerfile
# Dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "main.py"]
```

### .dockerignore 생성

```bash
# .dockerignore
.venv/
__pycache__/
*.pyc
*.pyo
.git/
.vscode/
.pytest_cache/
```

### Docker Compose (전체 프로젝트)

```yaml
# /d/Data/11_Backend/01_ARR/agent/docker-compose.yml
version: '3.8'

services:
  tutor-agent:
    build: ./tutor-agent
    ports:
      - "8001:8001"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  chatgpt-clone:
    build: ./chatgpt-clone
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  # 나머지 프로젝트들...
```

### 실행

```bash
cd /d/Data/11_Backend/01_ARR/agent
docker-compose up -d
```

---

## 7️⃣ 프로젝트 구조

```
/d/Data/11_Backend/01_ARR/agent/
├── README_KO.md              # 전체 프로젝트 가이드
├── SETUP_GUIDE.md            # 이 파일 (설정 가이드)
├── docker-compose.yml        # Docker 오케스트레이션 (선택)
│
├── a2a/                      # Agent-to-Agent 통신
├── chatgpt-clone/            # ChatGPT 클론
├── content-pipeline-agent/   # 콘텐츠 파이프라인 (CrewAI/Python 3.11)
├── customer-support-agent/   # 고객 지원
├── deep-research-clone/      # 심층 리서치 (AutoGen)
├── deployment/               # 배포 예제
├── email-refiner-agent/      # 이메일 개선 (Google ADK)
├── financial-analyst/        # 금융 분석 (Google ADK)
├── hello-langgraph/          # LangGraph 입문
├── job-hunter-agent/         # 구직 자동화 (CrewAI/Python 3.11)
├── multi-agent-architectures/ # 멀티 에이전트 패턴
├── my-first-agent/           # 첫 번째 에이전트
├── news-reader-agent/        # 뉴스 리더 (CrewAI/Python 3.11)
├── tutor-agent/              # AI 튜터
├── workflow-architectures/   # 워크플로우 패턴
├── workflow-testing/         # 에이전트 테스트
├── youtube-shorts-maker/     # YouTube Shorts 제작 (Google ADK)
└── youtube-thumbnail-maker/  # 썸네일 생성
```

---

## 8️⃣ 빠른 테스트

### 가장 간단한 프로젝트로 테스트

```bash
# 1. my-first-agent (Jupyter)
cd /d/Data/11_Backend/01_ARR/agent/my-first-agent
uv run jupyter notebook
# 브라우저에서 노트북 실행

# 2. deployment (간단한 스크립트)
cd /d/Data/11_Backend/01_ARR/agent/deployment
uv run python main.py

# 3. hello-langgraph (LangGraph 서버)
cd /d/Data/11_Backend/01_ARR/agent/hello-langgraph
uv run langgraph dev
# http://localhost:8123 접속
```

---

## 9️⃣ 학습 순서 추천

### Phase 1: 기초 (1주)
```bash
cd /d/Data/11_Backend/01_ARR/agent/my-first-agent
cd /d/Data/11_Backend/01_ARR/agent/hello-langgraph
cd /d/Data/11_Backend/01_ARR/agent/chatgpt-clone
```

### Phase 2: 패턴 (2주)
```bash
cd /d/Data/11_Backend/01_ARR/agent/workflow-architectures
cd /d/Data/11_Backend/01_ARR/agent/multi-agent-architectures
cd /d/Data/11_Backend/01_ARR/agent/workflow-testing
```

### Phase 3: 실전 (3주)
```bash
cd /d/Data/11_Backend/01_ARR/agent/customer-support-agent
cd /d/Data/11_Backend/01_ARR/agent/tutor-agent
cd /d/Data/11_Backend/01_ARR/agent/content-pipeline-agent
```

### Phase 4: 고급 (4주)
```bash
cd /d/Data/11_Backend/01_ARR/agent/financial-analyst
cd /d/Data/11_Backend/01_ARR/agent/deep-research-clone
cd /d/Data/11_Backend/01_ARR/agent/a2a
```

---

## 🔟 체크리스트

### 설정 완료 체크

- [ ] uv 설치됨 (`uv --version`)
- [ ] Python 3.13 사용 가능 (`uv python list`)
- [ ] Python 3.11 사용 가능 (`uv python list`)
- [ ] 15개 Python 3.13 프로젝트 설정 완료
- [ ] 3개 Python 3.11 프로젝트 설정 완료
- [ ] OpenAI API Key 확인 (17개 프로젝트)
- [ ] Google API Key 설정 (필요한 경우 4개)
- [ ] Firecrawl API Key 설정 (필요한 경우 4개)
- [ ] 테스트 실행 성공 (최소 1개 프로젝트)

### API 키 체크

- [ ] OpenAI API Key: `sk-proj-FHql...` (이미 설정됨)
- [ ] Google Gemini API Key: ⚠️ 발급 필요
- [ ] Firecrawl API Key: ⚠️ 발급 필요

---

## 📞 도움말

### 각 프로젝트 상세 정보
```bash
cd /d/Data/11_Backend/01_ARR/agent/<프로젝트명>
cat README_KO.md
```

### 전체 프로젝트 개요
```bash
cd /d/Data/11_Backend/01_ARR/agent
cat README_KO.md
```

### 로그 확인
```bash
# 실행 중 오류 로그
uv run python main.py 2>&1 | tee error.log
```

---

**Happy Coding! 🚀**

마지막 업데이트: 2025-10-30
