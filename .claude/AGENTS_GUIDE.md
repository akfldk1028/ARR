# 🤖 Claude Code 서브에이전트 사용 가이드

프로젝트가 점점 커지고 복잡해짐에 따라 전문화된 서브에이전트들을 만들었습니다.

## 📋 생성된 에이전트들

### 1. **law-system-specialist** 🔵
**전문 분야:** 법률 검색 시스템

**언제 사용하나요?**
- Neo4j 그래프 데이터베이스 작업
- 검색 알고리즘 (RNE, INE) 디버깅
- 데이터 파이프라인 (PDF → JSON → Neo4j)
- Multi-Agent System (DomainAgent, AgentManager)
- 임베딩 관리 (KR-SBERT, OpenAI)
- 법률 검색 기능 테스트

**빠른 호출:** `/law` + 작업 내용

**예시:**
```
/law Neo4j에서 HANG 노드가 몇 개인지 확인하고 싶어
/law RNE 알고리즘이 어떻게 작동하는지 설명해줘
/law 데이터 파이프라인을 처음부터 실행하는 방법 알려줘
```

---

### 2. **backend-django-specialist** 🟣
**전문 분야:** Django 백엔드

**언제 사용하나요?**
- Django 설정 및 구성
- ASGI/WebSocket 설정 (Daphne)
- A2A 프로토콜 엔드포인트
- Django 앱 관리
- 데이터베이스 마이그레이션
- 관리 명령어 작성

**빠른 호출:** `/django` + 작업 내용

**예시:**
```
/django WebSocket이 404 에러가 나는데 도와줘
/django 새로운 Django 앱을 만들고 싶어
/django A2A 프로토콜 엔드포인트가 제대로 작동하는지 확인해줘
/django 비동기 뷰를 어떻게 작성하는지 알려줘
```

---

### 3. **agent-frameworks-specialist** 🟢
**전문 분야:** AI 에이전트 프레임워크 예제 (학습용)

**중요:** agent/ 디렉토리는 **학습용 예제 모음**입니다! 실제 프로덕션 코드는 backend/에 있습니다.

---

### 4. **eigent-frontend-specialist** 🟠
**전문 분야:** Eigent Multi-Agent Workforce 데스크톱 앱

**언제 사용하나요?**
- Eigent 데스크톱 애플리케이션 (Electron + React + TypeScript)
- CAMEL-AI 기반 Multi-Agent Workforce UI
- frontend/src/law/ 법률 검색 통합
- Eigent 컴포넌트 (AddWorker, ChatBox, WorkFlow)
- Django 백엔드와의 연결

**빠른 호출:** `/frontend` + 작업 내용

**예시:**
```
/frontend Eigent 앱 구조 설명해줘
/frontend src/law/ 디렉토리가 뭐야?
/frontend AddWorker 컴포넌트 어떻게 작동해?
/frontend 백엔드랑 어떻게 통신해?
```

**중요:** frontend/ 디렉토리는 **Eigent 데스크톱 앱**입니다! (일반 웹 프론트가 아님)

---

### 5. **project-orchestrator** 🟡
**전문 분야:** 전체 프로젝트 조율

**언제 사용하나요?**
- 프레임워크 비교 및 선택
- 예제 코드 이해
- 학습 경로 추천

**빠른 호출:** `/examples` + 작업 내용

**예시:**
```
/examples agent 디렉토리에 어떤 프레임워크들이 있어?
/examples LangGraph 예제 중 초보자용은 뭐야?
/examples tutor-agent가 어떻게 작동하나요?
/examples CrewAI와 LangGraph 뭐가 달라?
```

**중요:** agent/ 디렉토리는 **학습용 예제 모음**입니다! 실제 프로덕션 코드는 backend/에 있습니다.

---

### 4. **project-orchestrator** 🟡
**전문 분야:** 전체 프로젝트 조율

**언제 사용하나요?**
- 시스템 전체 아키텍처 이해
- Cross-cutting 기능 계획
- agent/, backend/, frontend/ 디렉토리 조율
- 아키텍처 결정
- 어떤 에이전트를 써야 할지 모를 때

**빠른 호출:** `/overview` + 작업 내용

**예시:**
```
/overview 프로젝트 전체 구조를 설명해줘
/overview 프론트엔드와 백엔드를 연결하는 기능을 만들고 싶어
/overview 어떤 에이전트를 사용해야 할지 모르겠어
/overview 새 기능을 추가하려면 어떤 순서로 해야 해?
```

---

## 🚀 사용 방법

### 방법 1: 슬래시 커맨드 (권장)

가장 빠른 방법입니다:

```
/law [작업 내용]
/django [작업 내용]
/examples [작업 내용]
/frontend [작업 내용]
/overview [작업 내용]
```

### 방법 2: 직접 요청

에이전트 이름을 언급하면 Claude Code가 자동으로 인식합니다:

```
law-system-specialist를 사용해서 Neo4j 데이터 검증해줘
backend-django-specialist로 WebSocket 설정 확인해줘
```

### 방법 3: 자연어로 질문

특정 주제를 언급하면 Claude Code가 적절한 에이전트를 자동 선택합니다:

```
"Neo4j에서 임베딩이 제대로 생성되었는지 확인하고 싶어"
→ law-system-specialist 자동 호출

"Django ASGI 설정을 어떻게 하나요?"
→ backend-django-specialist 자동 호출

"LangGraph에서 조건부 라우팅 예제를 보여줘"
→ agent-frameworks-specialist 자동 호출
```

---

## 📊 에이전트 선택 플로우차트

```
질문이 있나요?
│
├─ "어떤 에이전트를 써야 할지 모르겠어" → /overview
│
├─ 법률 시스템 관련인가요?
│  ├─ Neo4j, 임베딩, 검색 알고리즘 → /law
│  └─ Django 백엔드 → /django
│
├─ 에이전트 프레임워크 학습인가요?
│  └─ agent/ 예제들 (OpenAI, LangGraph, CrewAI 등) → /examples
│
├─ Eigent 프론트엔드 관련인가요?
│  ├─ Eigent 데스크톱 앱, src/law/ 통합 → /frontend
│  └─ 백엔드 통합 → backend-frontend-integrator (기존)
│
└─ 전체 시스템 조율 → /overview
```

---

## 💡 실전 예시

### 시나리오 1: 법률 검색 테스트
```
/law 17조 검색이 제대로 작동하는지 테스트하고 싶어. test_17jo_domain.py를 어떻게 실행하나요?
```

### 시나리오 2: Django 앱 추가
```
/django 새로운 Django 앱을 만들고 settings.py에 추가하는 전체 과정을 알려줘
```

### 시나리오 3: 프레임워크 예제 학습
```
/examples agent 디렉토리에 있는 LangGraph 예제들 알려줘
/examples CrewAI 프레임워크가 뭐고 어떤 예제가 있어?
```

### 시나리오 4: 전체 시스템 이해
```
/overview 이 프로젝트의 데이터 플로우를 처음부터 끝까지 설명해줘
```

### 시나리오 5: 복잡한 작업 (여러 에이전트 협업)
```
/overview 프론트엔드에서 법률 검색 결과를 표시하는 새 기능을 만들고 싶어. 어떤 순서로 진행해야 해?

→ project-orchestrator가:
  1. 전체 계획 수립
  2. law-system-specialist에게 검색 API 확인 요청
  3. backend-django-specialist에게 REST 엔드포인트 구현 요청
  4. eigent-frontend-specialist에게 UI 컴포넌트 분석 요청
  5. backend-frontend-integrator에게 통합 작업 요청
```

---

## 🎯 각 에이전트의 강점

| 에이전트 | 주요 강점 | 파일 경로 참조 능력 |
|---------|---------|------------------|
| law-system-specialist | Neo4j, 검색 알고리즘, 임베딩 | ⭐⭐⭐⭐⭐ backend/law/, graph_db/ |
| backend-django-specialist | Django 설정, ASGI, A2A | ⭐⭐⭐⭐⭐ backend/backend/, agents/ |
| agent-frameworks-specialist | 다양한 프레임워크 예제 학습 | ⭐⭐⭐⭐⭐ agent/ (18+ 예제) |
| eigent-frontend-specialist | Eigent 데스크톱, law 통합 | ⭐⭐⭐⭐⭐ frontend/ (Electron+React) |
| project-orchestrator | 전체 조율, 아키텍처 | ⭐⭐⭐⭐⭐ 모든 디렉토리 |

---

## 🔧 에이전트 설정 파일 위치

모든 에이전트는 다음 위치에 정의되어 있습니다:

```
.claude/
├── agents/
│   ├── law-system-specialist.md
│   ├── backend-django-specialist.md
│   ├── agent-frameworks-specialist.md
│   ├── eigent-frontend-specialist.md
│   ├── project-orchestrator.md
│   ├── backend-frontend-integrator.md (기존)
│   └── agent-project-integrator.md (기존)
└── commands/
    ├── law.md
    ├── django.md
    ├── examples.md
    ├── frontend.md
    └── overview.md
```

---

## 📚 관련 문서

- **프로젝트 시작:** `backend/START_HERE.md`
- **Django 설정:** `backend/CLAUDE.md`
- **법률 시스템:** `backend/law/SYSTEM_GUIDE.md`
- **LangGraph:** `agent/LANGGRAPH_USAGE_GUIDE.md`
- **아키텍처:** `backend/LAW_SEARCH_SYSTEM_ARCHITECTURE.md`

---

## 🆘 도움이 필요한 경우

**어떤 에이전트를 써야 할지 모르겠다면:**
```
/overview 어떤 에이전트를 사용해야 할지 모르겠어. [작업 내용]
```

**에이전트가 제대로 작동하지 않는다면:**
1. Claude Code 재시작
2. `.claude/agents/` 디렉토리 확인
3. 슬래시 커맨드 대신 직접 에이전트 이름 언급

---

**최종 업데이트:** 2025-11-14
**생성된 에이전트:** 5개 (law-system-specialist, backend-django-specialist, agent-frameworks-specialist, eigent-frontend-specialist, project-orchestrator)
**생성된 슬래시 커맨드:** 5개 (/law, /django, /examples, /frontend, /overview)

**프로젝트 구조:**
- agent/ → 학습용 예제 (agent-frameworks-specialist)
- backend/ → Django 법률 검색 (law-system-specialist, backend-django-specialist)
- frontend/ → Eigent 데스크톱 앱 (eigent-frontend-specialist)

---

## ✅ 빠른 체크리스트

- [ ] `/law` 커맨드로 법률 시스템 에이전트 테스트
- [ ] `/django` 커맨드로 Django 에이전트 테스트
- [ ] `/examples` 커맨드로 프레임워크 예제 에이전트 테스트
- [ ] `/frontend` 커맨드로 Eigent 프론트엔드 에이전트 테스트
- [ ] `/overview` 커맨드로 프로젝트 전체 이해

**이제 프로젝트가 아무리 커져도 전문화된 에이전트들이 도와줄 거예요! 🚀**
