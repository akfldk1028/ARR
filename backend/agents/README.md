# agents/ - A2A 에이전트 시스템

## 개요
A2A (Agent-to-Agent) 프로토콜 기반의 Multi-Agent 시스템 구현. LangGraph 기반 Worker Agent와 법률 도메인 에이전트를 관리한다.

## 핵심 기능
- A2A 프로토콜 (JSON-RPC 2.0) 기반 에이전트 간 통신
- Worker Agent 팩토리 패턴
- 법률 검색 Multi-Agent System (MAS)
- Agent Card Discovery (`/.well-known/agent-card/`)

---

## 파일 구조 및 역할

### 루트 파일
| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `models.py` | Agent Django 모델 | `Agent` - 에이전트 정의 (타입, 상태, 설정) |
| `views.py` | Agent REST API 엔드포인트 | Agent CRUD, 채팅 인터페이스 |
| `urls.py` | URL 라우팅 | `/agents/` 하위 경로 |
| `a2a_client.py` | A2A 프로토콜 클라이언트 | Agent Card Discovery, JSON-RPC 통신 |
| `well_known_urls.py` | `.well-known` 엔드포인트 | Agent Card 제공 |

### law/ - 법률 Multi-Agent 시스템
| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `agent_manager.py` | 도메인 관리 및 자가 조직화 | `AgentManager` - K-means 클러스터링, 도메인 생성 |
| `domain_agent.py` | 도메인별 법률 검색 에이전트 | `DomainAgent` - Hybrid Search, RNE 확장, A2A 협업 |
| `domain_manager.py` | 도메인 매니저 | 도메인 CRUD |
| `api/search.py` | 법률 검색 API | `LawSearchAPIView` - Phase 1-3 검색 |
| `api/streaming.py` | SSE 스트리밍 | 실시간 검색 결과 스트리밍 |
| `api/domains.py` | 도메인 API | 도메인 목록 조회 |
| `api/health.py` | 헬스체크 | Neo4j/AgentManager 상태 확인 |

### worker_agents/ - Worker Agent 구현
| 파일 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `base/base_worker.py` | Worker 베이스 클래스 | `BaseWorkerAgent` - LangGraph 기반 |
| `worker_factory.py` | Worker 팩토리 | `WorkerFactory` - Worker 생성 |
| `worker_manager.py` | Worker 라이프사이클 관리 | `WorkerAgentManager` |
| `agent_discovery.py` | 에이전트 검색 | Semantic Routing |
| `agent_registry.py` | 에이전트 레지스트리 | 등록/조회 |
| `card_loader.py` | Agent Card 로더 | JSON 카드 파싱 |
| `implementations/host_agent.py` | Host Agent (조정자) | 메시지 라우팅, 전문가 위임 |
| `implementations/law_coordinator_worker.py` | 법률 조정 Worker | 법률 검색 위임 |
| `implementations/flight_specialist_worker.py` | 항공 전문가 | 항공편 검색 |
| `cards/*.json` | Agent Card 정의 | 에이전트 메타데이터 |

### database/ - 데이터베이스 연동
| 파일 | 역할 |
|------|------|
| `neo4j_deprecated/service.py` | Neo4j 서비스 (deprecated) |
| `neo4j_deprecated/queries.py` | Cypher 쿼리 템플릿 |
| `neo4j_deprecated/indexes.py` | 인덱스 관리 |

### management/commands/ - Django 관리 명령어
| 파일 | 역할 |
|------|------|
| `create_test_agent.py` | 테스트 에이전트 생성 |
| `test_worker_communication.py` | Worker 간 통신 테스트 |
| `sync_agent_cards.py` | Agent Card 동기화 |

---

## 의존성
- `core.models`: BaseModel, Organization, Tag
- `graph_db.services`: Neo4j 서비스
- `gemini.consumers`: WebSocket 핸들러

## API 엔드포인트
| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/agents/list/` | GET | 에이전트 목록 |
| `/agents/{slug}/chat/` | POST | 채팅 인터페이스 |
| `/agents/law/api/search` | POST | 법률 검색 |
| `/agents/law/api/domains` | GET | 도메인 목록 |
| `/.well-known/agent-card/{slug}.json` | GET | Agent Card |

## 사용 예시
```python
from agents.law.agent_manager import AgentManager

manager = AgentManager()
result = await manager.search("국토계획법 17조", limit=10)
```
