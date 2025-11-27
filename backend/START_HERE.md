# 🚀 START HERE - 프로젝트 시작 가이드

**신규 개발자 또는 다음 AI를 위한 필독 문서**

---
  📖 MD 파일 읽는 순서

  🎯 필수 순서 (추천)

  1. START_HERE.md          ← 지금 여기!
     (어디서 시작해야 하는지 전체 안내)
     
  2. CLAUDE.md              ← 프로젝트 전체 이해
     (Django 구조, A2A 프로토콜, 환경 설정)
     
  3. law/STEP/README.md     ← 법률 시스템 바로 실행
     (순차 실행 가이드, 자동화 스크립트)

  📚 상황별로 선택

  법률 시스템 깊이 이해하려면:
  - law/SYSTEM_GUIDE.md (Phase 1-7 학습 가이드)

  처음부터 완전 구축하려면:
  - docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md                                 

  정리된 파일들 확인:
  - archive/README.md                                                                 



## 📖 문서 읽는 순서 (필수!)

### 1️⃣ 프로젝트 전체 이해
**`CLAUDE.md`** (27 KB) - **먼저 읽을 것!**
- 프로젝트 전체 구조
- Django 앱 구성
- A2A 프로토콜
- WebSocket 설정
- 개발 명령어
- 환경 설정

### 2️⃣ 법률 시스템 빠른 실행
**`law/STEP/README.md`** (8.1 KB) - **바로 실행하고 싶다면**
- 순차 실행 가이드 (Step 1-5)
- 자동 실행 방법
- 검증 방법
- 문제 해결

### 3️⃣ 법률 시스템 깊이 이해
**`law/SYSTEM_GUIDE.md`** - **시스템 원리를 알고 싶다면**
- 7단계 학습 가이드
- 데이터 파이프라인
- Multi-Agent System
- 임베딩 전략
- 검색 알고리즘

### 4️⃣ 법률 시스템 완전 설정
**`docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`** - **처음부터 구축한다면**
- 환경 요구사항
- 사전 준비
- 상세 설정 가이드
- 최종 검증

### 5️⃣ 보관된 파일 이해
**`archive/README.md`** - **정리된 파일들 확인**
- 보관된 스크립트 목록
- 보관 이유
- 현재 파일 위치

---

## ⚡ 상황별 빠른 가이드

### 🆕 처음 프로젝트를 접하는 경우
```
1. CLAUDE.md 읽기 (프로젝트 구조 파악)
2. .env 파일 설정
3. Neo4j Desktop 시작
4. law/STEP/README.md 읽고 실행
```

### 🔧 법률 시스템만 실행하고 싶은 경우
```bash
cd law/STEP
python run_all.py  # 전체 자동 실행 (50분)
python verify_system.py  # 검증
```

### 📚 법률 시스템 원리를 이해하고 싶은 경우
```
1. law/SYSTEM_GUIDE.md 읽기 (Phase 1-7)
2. 코드 따라가며 이해
3. law/STEP/README.md로 실습
```

### 🛠️ Django 서버 실행하고 싶은 경우
```bash
# 1. Neo4j Desktop 시작
# 2. 가상환경 활성화
.venv\Scripts\activate

# 3. Daphne ASGI 서버 시작 (WebSocket 지원)
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# 4. 브라우저에서 접속
# http://localhost:8000/chat/  (텍스트 채팅)
# http://localhost:8000/gemini/live-voice/  (음성)
```

### 🐛 문제가 생긴 경우
```
1. CLAUDE.md > "문제 해결" 섹션
2. law/STEP/README.md > "문제 해결" 섹션
3. archive/ 에서 관련 스크립트 확인
```

---

## 📂 주요 디렉토리 구조

```
backend/
├── START_HERE.md           ⭐ 이 파일
├── CLAUDE.md               ⭐ 프로젝트 전체 가이드
├── manage.py               Django 관리 도구
├── db.sqlite3              Django 데이터베이스
│
├── law/                    법률 시스템 (핵심!)
│   ├── STEP/               ⭐ 순차 실행 스크립트
│   │   ├── README.md       ⭐ 실행 가이드
│   │   ├── run_all.py      전체 자동 실행
│   │   └── step*.py        단계별 스크립트
│   ├── SYSTEM_GUIDE.md     ⭐ 시스템 학습 가이드
│   ├── scripts/            원본 스크립트
│   ├── data/               데이터 (PDF, JSON)
│   └── relationship_embedding/  관계 임베딩
│
├── docs/                   문서
│   └── 2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md  ⭐
│
├── agents/                 A2A 에이전트 시스템
│   ├── law/                법률 에이전트
│   │   ├── agent_manager.py     AgentManager
│   │   └── domain_agent.py      DomainAgent
│   └── worker_agents/      Worker 에이전트
│
├── graph_db/               Neo4j 서비스
│   ├── services/
│   └── algorithms/         RNE/INE 알고리즘
│
├── chat/                   텍스트 채팅 (WebSocket)
├── gemini/                 음성 인터페이스
├── backend/                Django 설정
└── archive/                정리된 파일들 (참고용)
```

---

## 🎯 핵심 파일 (반드시 알아야 할)

### 설정 파일
- `.env` - 환경 변수 (NEO4J_*, OPENAI_API_KEY)
- `backend/settings.py` - Django 설정
- `backend/asgi.py` - WebSocket 라우팅

### 법률 시스템
- `agents/law/agent_manager.py` - MAS 관리자
- `agents/law/domain_agent.py` - 도메인 에이전트
- `law/scripts/pdf_to_json.py` - PDF 파싱
- `law/scripts/json_to_neo4j.py` - Neo4j 로드
- `law/scripts/add_hang_embeddings.py` - 임베딩 생성
- `law/scripts/initialize_domains.py` - Domain 초기화

### A2A 에이전트
- `agents/worker_agents/base/base_worker.py` - Worker 베이스
- `agents/a2a_client.py` - A2A 클라이언트
- `agents/worker_agents/implementations/` - 구현체들

### Neo4j
- `graph_db/services/neo4j_service.py` - Neo4j 연결
- `graph_db/algorithms/rne_engine.py` - RNE 알고리즘
- `graph_db/algorithms/ine_engine.py` - INE 알고리즘

---

## 💡 시작 체크리스트

- [ ] CLAUDE.md 읽음
- [ ] Neo4j Desktop 설치 및 실행
- [ ] .env 파일 설정 (NEO4J_*, OPENAI_API_KEY)
- [ ] Python 가상환경 활성화
- [ ] law/STEP/README.md 읽음
- [ ] `python law/STEP/run_all.py` 실행 (선택)
- [ ] `python law/STEP/verify_system.py` 검증 (선택)
- [ ] Django 서버 실행: `daphne -b 0.0.0.0 -p 8000 backend.asgi:application`

---

## 🆘 도움이 필요한 경우

1. **Neo4j 연결 안 됨**
   - Neo4j Desktop에서 데이터베이스 시작 확인
   - .env 파일의 NEO4J_* 변수 확인
   - http://localhost:7474 접속 가능한지 확인

2. **WebSocket 404 에러**
   - `python manage.py runserver` 대신 `daphne` 사용
   - `backend/asgi.py` 라우팅 확인

3. **임베딩 생성 실패**
   - OpenAI API 키 확인
   - 메모리 부족 시 배치 크기 줄이기

4. **법률 시스템 오류**
   - `law/STEP/verify_system.py` 실행하여 상태 확인
   - Neo4j Browser (http://localhost:7474)에서 데이터 확인

---

## 📌 중요 링크

- **Neo4j Browser**: http://localhost:7474
- **텍스트 채팅**: http://localhost:8000/chat/
- **음성 인터페이스**: http://localhost:8000/gemini/live-voice/
- **Django Admin**: http://localhost:8000/admin/

---

**최종 업데이트**: 2025-11-13
**작성자**: Claude AI

**다음 단계**: `CLAUDE.md` 파일을 열어 프로젝트 전체를 이해하세요! 🚀
