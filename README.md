# 법규 Graph Node Multi-Agent 검색 시스템

## 프로젝트 개요

한국 법률 문서를 Neo4j 그래프 DB에 저장하고, Multi-Agent System으로 검색하는 풀스택 시스템.

```
[PDF 법률문서] → [Neo4j 그래프] → [Multi-Agent 검색] → [React UI]
```

---

## 프로젝트 구조

```
D:\Data\11_Backend\01_ARR\
├── backend/      ⭐ Django 법규 검색 백엔드
│   ├── agents/law/       Multi-Agent 시스템
│   ├── graph_db/         Neo4j 연결 및 알고리즘
│   ├── law/              법률 API 및 파이프라인
│   └── AI_INDEX.md       전체 시스템 가이드
│
├── frontend/     ⭐ Electron 데스크톱 앱
│   ├── src/law/          법규 검색 UI
│   └── README_PROJECT.md 프론트엔드 가이드
│
└── agent/        AI 에이전트 예제 (학습용)
```

---

## 핵심 아키텍처

### Multi-Agent System (MAS)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 쿼리 입력                               │
│                    "국토계획법 17조 알려줘"                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: LLM Self-Assessment (GPT-4o)                               │
│   - 5개 Domain별 쿼리 답변 능력 평가                                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1.5: Hybrid Search + RNE Graph Expansion                      │
│   [Exact Match] + [Semantic Vector] + [Relationship] + [RNE]        │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2: A2A Collaboration (도메인 간 협업)                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 3: Result Synthesis (GPT-4o)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Neo4j 그래프 스키마

```
LAW (법률)
 └─ JO (조) ← 제목, 임베딩 (3072-dim)
     └─ HANG (항) ← ⭐ 실제 내용, 임베딩 (3072-dim)
         └─ HO (호)

Domain (도메인) ← K-means 클러스터링
```

---

## 빠른 시작

### 1. 백엔드 실행

```bash
cd backend

# 가상환경 활성화
.venv\Scripts\activate

# Neo4j Desktop 시작 (http://localhost:7474)

# 데이터 파이프라인 (최초 1회, ~50분)
cd law/STEP
python run_all.py

# Django 서버
cd ..
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### 2. 프론트엔드 실행

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버
npm run dev

# 접속: http://localhost:5173/law
```

---

## 문서 인덱스

### Backend

| 문서 | 설명 |
|------|------|
| [backend/AI_INDEX.md](./backend/AI_INDEX.md) | 전체 시스템 완전 가이드 |
| [backend/README_INDEX.md](./backend/README_INDEX.md) | README 인덱스 (26개) |
| [backend/TASK.md](./backend/TASK.md) | 작업 목록 |
| [backend/agents/law/README.md](./backend/agents/law/README.md) | Multi-Agent 시스템 |
| [backend/graph_db/README.md](./backend/graph_db/README.md) | Neo4j 알고리즘 |
| [backend/law/README.md](./backend/law/README.md) | 법률 API |

### Frontend

| 문서 | 설명 |
|------|------|
| [frontend/README_PROJECT.md](./frontend/README_PROJECT.md) | 프론트엔드 가이드 |
| [frontend/src/law/README.md](./frontend/src/law/README.md) | 법규 검색 UI |

---

## 기술 스택

### Backend

| 카테고리 | 기술 |
|----------|------|
| Framework | Django 4.x |
| Graph DB | Neo4j |
| Embeddings | OpenAI text-embedding-3-large (3072-dim) |
| LLM | GPT-4o, GPT-4o-mini |
| WebSocket | Django Channels + Daphne |
| Algorithms | Hybrid Search, Semantic RNE, A2A |

### Frontend

| 카테고리 | 기술 |
|----------|------|
| Framework | React 18 + TypeScript |
| Desktop | Electron |
| Build | Vite |
| Styling | Tailwind CSS |
| State | Zustand |

---

## 환경 변수

### Backend (.env)

```env
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111
OPENAI_API_KEY=sk-xxx
```

### Frontend (.env)

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 데이터 통계

| 항목 | 개수 |
|------|------|
| LAW 노드 | 3개 |
| JO 노드 | 1,053개 |
| HANG 노드 | 1,477개 |
| Domain 노드 | 5개 |
| CONTAINS 관계 | 3,565개 |

---

## 읽기 순서 추천

1. **[backend/AI_INDEX.md](./backend/AI_INDEX.md)** - 전체 시스템 이해
2. **[backend/agents/law/README.md](./backend/agents/law/README.md)** - 핵심 검색 로직
3. **[frontend/src/law/README.md](./frontend/src/law/README.md)** - UI 연동

---

**마지막 업데이트**: 2025-11-14
