# README INDEX - 프로젝트 문서 인덱스

> **목적**: 모든 README 파일을 한눈에 파악하고 빠르게 탐색
> **총 README 수**: 26개

---

## 빠른 탐색

| 카테고리 | 핵심 파일 |
|----------|-----------|
| **프로젝트 전체** | [AI_INDEX.md](#ai-index) - 전체 시스템 이해 |
| **핵심 검색** | [agents/law/](#agentslaw) - Multi-Agent 검색 |
| **그래프 DB** | [graph_db/](#graph_db) - Neo4j 알고리즘 |
| **법률 API** | [law/](#law) - REST API 및 파이프라인 |
| **실시간 채팅** | [chat/](#chat), [gemini/](#gemini) |

---

## 1. 프로젝트 루트

### AI_INDEX {#ai-index}
- **경로**: [`AI_INDEX.md`](./AI_INDEX.md)
- **내용**: 전체 시스템 완전 가이드
  - 핵심 아키텍처 (3-Phase MAS)
  - Neo4j 스키마 상세
  - 핵심 클래스 상세 (AgentManager, DomainAgent, SemanticRNE)
  - 데이터 파이프라인
  - API 엔드포인트
  - 환경 변수
  - 디버깅 팁

### 기타 문서
| 파일 | 용도 |
|------|------|
| [`CLAUDE.md`](./CLAUDE.md) | Claude 에이전트 가이드라인 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 아키텍처 개요 |
| [`START_HERE.md`](./START_HERE.md) | 시작 가이드 |
| [`LAW_SEARCH_SYSTEM_ARCHITECTURE.md`](./LAW_SEARCH_SYSTEM_ARCHITECTURE.md) | 법률 검색 아키텍처 |
| [`TASK.md`](./TASK.md) | 작업 목록 및 진행상황 |

---

## 2. 핵심 앱 README

### agents/law/ {#agentslaw}
- **경로**: [`agents/law/README.md`](./agents/law/README.md)
- **중요도**: ⭐⭐⭐ 핵심
- **내용**:
  - Multi-Agent 시스템 아키텍처
  - `AgentManager` 클래스 상세 (자가 조직화)
  - `DomainAgent` 검색 파이프라인
  - Hybrid Search (Exact + Semantic + Relationship + JO)
  - RRF (Reciprocal Rank Fusion)
  - RNE Graph Expansion
  - A2A 협업 프로토콜
  - 점수 정규화 및 패널티

### graph_db/ {#graph_db}
- **경로**: [`graph_db/README.md`](./graph_db/README.md)
- **중요도**: ⭐⭐⭐ 핵심
- **내용**:
  - Neo4j 그래프 스키마
  - 노드 계층 (LAW→JO→HANG→HO)
  - 관계 구조 (CONTAINS, NEXT, CITES, BELONGS_TO_DOMAIN)
  - 벡터 인덱스 (3072-dim)
  - `Neo4jService` 싱글톤
  - `SemanticRNE` 알고리즘 상세
  - `LawRepository` 핵심 메서드
  - Cypher 쿼리 예시

### law/ {#law}
- **경로**: [`law/README.md`](./law/README.md)
- **중요도**: ⭐⭐⭐ 핵심
- **내용**:
  - 검색 REST API 엔드포인트
  - `SearchService`, `VectorService`, `RelationshipService`
  - 데이터 파이프라인 (PDF→Neo4j→임베딩)
  - 점수 계산 로직 (RRF, 정규화, 패널티)
  - Django 모델 (Law, Article, Clause)

---

## 3. 실시간 통신

### chat/ {#chat}
- **경로**: [`chat/README.md`](./chat/README.md)
- **내용**:
  - WebSocket 채팅
  - `ChatConsumer` - A2A 통합 채팅
  - Django Channels 설정

### gemini/ {#gemini}
- **경로**: [`gemini/README.md`](./gemini/README.md)
- **내용**:
  - Gemini Live API 통합
  - `SimpleConsumer` - 음성/텍스트 채팅
  - `A2AHandler` - 에이전트 라우팅
  - 음성 처리 (STT/TTS)

---

## 4. 인프라 및 설정

### config/
- **경로**: [`config/README.md`](./config/README.md)
- **내용**: Django 설정 패키지

### backend/
- **경로**: [`backend/README.md`](./backend/README.md)
- **내용**: Django 프로젝트 설정 (settings, urls, asgi)

### core/
- **경로**: [`core/README.md`](./core/README.md)
- **내용**: 공통 모델, 유틸리티, Organization 멀티테넌시

---

## 5. 지원 앱

### agents/
- **경로**: [`agents/README.md`](./agents/README.md)
- **내용**: Worker Agent 프레임워크

### agents/database/
- **경로**: [`agents/database/README.md`](./agents/database/README.md)
- **내용**: Agent DB 연결 추상화

### agents/worker_agents/cards/
- **경로**: [`agents/worker_agents/cards/README.md`](./agents/worker_agents/cards/README.md)
- **내용**: Agent Card 정의

### conversations/
- **경로**: [`conversations/README.md`](./conversations/README.md)
- **내용**: 대화 히스토리 관리

### live_a2a_bridge/
- **경로**: [`live_a2a_bridge/README.md`](./live_a2a_bridge/README.md)
- **내용**: A2A 실시간 브릿지

### parser/
- **경로**: [`parser/README.md`](./parser/README.md)
- **내용**: 법률 문서 파서

### authz/
- **경로**: [`authz/README.md`](./authz/README.md)
- **내용**: 인증/인가

### tasks/
- **경로**: [`tasks/README.md`](./tasks/README.md)
- **내용**: 비동기 태스크 (Celery)

### mcp/
- **경로**: [`mcp/README.md`](./mcp/README.md)
- **내용**: MCP 프로토콜 통합

### src/
- **경로**: [`src/README.md`](./src/README.md)
- **내용**: 소스 유틸리티

---

## 6. 데이터 파이프라인 하위 문서

### law/STEP/
- **경로**: [`law/STEP/README.md`](./law/STEP/README.md)
- **내용**: 순차 실행 스크립트 (step1~5)

### law/evaluation/
- **경로**: [`law/evaluation/README.md`](./law/evaluation/README.md)
- **내용**: 검색 성능 평가

### law/relationship_embedding/
- **경로**: [`law/relationship_embedding/README.md`](./law/relationship_embedding/README.md)
- **내용**: 관계 임베딩 생성

---

## 7. 아카이브/Deprecated

### archive/
- **경로**: [`archive/README.md`](./archive/README.md)
- **내용**: 이전 버전 백업

### agents/deprecated/
- **경로**: [`agents/deprecated/README.md`](./agents/deprecated/README.md)
- **내용**: 사용 중지된 에이전트

### agents/database/neo4j_deprecated/
- **경로**: [`agents/database/neo4j_deprecated/README.md`](./agents/database/neo4j_deprecated/README.md)
- **내용**: 이전 Neo4j 구현

---

## 파일 트리 (README 위치)

```
backend/
├── AI_INDEX.md ⭐
├── README_INDEX.md (현재 파일)
├── TASK.md
├── agents/
│   ├── README.md
│   ├── law/
│   │   └── README.md ⭐⭐⭐
│   ├── database/
│   │   ├── README.md
│   │   └── neo4j_deprecated/README.md
│   ├── deprecated/README.md
│   └── worker_agents/cards/README.md
├── graph_db/
│   └── README.md ⭐⭐⭐
├── law/
│   ├── README.md ⭐⭐⭐
│   ├── STEP/README.md
│   ├── evaluation/README.md
│   └── relationship_embedding/README.md
├── chat/README.md
├── gemini/
│   ├── README.md
│   └── examples/liveAPI/README.md
├── core/README.md
├── conversations/README.md
├── config/README.md
├── backend/README.md
├── live_a2a_bridge/README.md
├── parser/README.md
├── authz/README.md
├── tasks/README.md
├── mcp/README.md
├── src/README.md
└── archive/
    ├── README.md
    └── backup_.../gemini_WORKING/examples/liveAPI/README.md
```

---

## 읽기 순서 추천

### 프로젝트 처음 접할 때
1. **[AI_INDEX.md](./AI_INDEX.md)** - 전체 시스템 이해
2. **[agents/law/README.md](./agents/law/README.md)** - 핵심 검색 로직
3. **[graph_db/README.md](./graph_db/README.md)** - Neo4j 스키마 및 알고리즘

### 특정 기능 파악할 때
- **검색 API**: `law/README.md` → `agents/law/README.md`
- **데이터 파이프라인**: `law/STEP/README.md`
- **실시간 채팅**: `chat/README.md` → `gemini/README.md`
- **Neo4j 쿼리**: `graph_db/README.md`

---

**마지막 업데이트**: 2025-11-14
