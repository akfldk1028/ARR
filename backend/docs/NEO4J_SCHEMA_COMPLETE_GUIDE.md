# Neo4j Multi-Agent System - 완전한 스키마 가이드

## 📋 목차
1. [시스템 개요](#시스템-개요)
2. [노드(Node) 타입 전체 목록](#노드-타입-전체-목록)
3. [관계(Relationship) 타입 전체 목록](#관계-타입-전체-목록)
4. [실제 활용 시나리오](#실제-활용-시나리오)
5. [멀티에이전트와의 통합](#멀티에이전트와의-통합)
6. [쿼리 예제](#쿼리-예제)

---

## 시스템 개요

이 시스템은 **W3C PROV 표준**과 **PROV-AGENT 프레임워크**(2024)를 기반으로 멀티에이전트의 실행, 의사결정, 작업, 산출물을 추적하는 **ENTERPRISE급 그래프 데이터베이스**입니다.

### 핵심 특징
- ✅ **완전한 프로비넌스 추적**: 모든 결과물을 근거와 의사결정까지 역추적 가능
- ✅ **RBAC 거버넌스**: 역할 기반 접근 제어 및 정책 관리
- ✅ **Contract Net Protocol**: FIT 스코어 기반 최적 에이전트 선택
- ✅ **실시간 협업 추적**: Agent-to-Agent 상호작용 기록
- ✅ **감사 가능성**: 모든 실행 이력과 변경 사항 추적

### 아키텍처 계층

```
┌─────────────────────────────────────────────────────┐
│           Phase 1: 대화 추적 (Conversation)          │
│  Session → Turn → Message → AgentExecution          │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Phase 2-1: 작업 관리 (Task/Tool/Capability)        │
│  Task ← Agent → Capability → Tool                   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Phase 2-2: 프로비넌스 (Provenance)                 │
│  Decision → Evidence → Artifact → Lineage           │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Phase 2-3: 거버넌스 (Governance/RBAC)              │
│  Role → Policy → Permission → Audit                 │
└─────────────────────────────────────────────────────┘
```

---

## 노드 타입 전체 목록

### 1. Phase 1: 대화 추적 노드

#### 1.1 Session (세션)
**목적**: 사용자와의 전체 대화 세션 관리

```cypher
(:Session {
  id: String,              // UUID
  user_id: String,         // 사용자 식별자
  started_at: DateTime,    // 세션 시작 시간
  ended_at: DateTime?,     // 세션 종료 시간
  metadata: String         // JSON: 플랫폼, 디바이스 정보 등
})
```

**활용 사례**:
- 사용자별 대화 이력 조회
- 세션 지속 시간 분석
- 사용자 행동 패턴 분석

#### 1.2 Turn (턴)
**목적**: 대화의 개별 턴 (사용자 입력 → 시스템 응답)

```cypher
(:Turn {
  id: String,              // UUID
  session_id: String,      // 소속 세션
  turn_number: Integer,    // 턴 순서
  user_message: String,    // 사용자 입력
  agent_response: String?, // 최종 응답
  created_at: DateTime,
  completed_at: DateTime?
})
```

**활용 사례**:
- 대화 흐름 재구성
- 응답 시간 측정
- 사용자 만족도 분석

#### 1.3 Message (메시지)
**목적**: 턴 내의 개별 메시지 (사용자/에이전트)

```cypher
(:Message {
  id: String,              // UUID
  turn_id: String,
  role: String,            // 'user' | 'assistant' | 'system'
  content: String,         // 메시지 내용
  timestamp: DateTime,
  metadata: String         // JSON: 토큰 수, 모델 정보 등
})
```

**활용 사례**:
- 대화 히스토리 표시
- 컨텍스트 윈도우 관리
- 토큰 사용량 추적

#### 1.4 AgentExecution (에이전트 실행)
**목적**: 에이전트의 개별 실행 기록 (핵심 노드!)

```cypher
(:AgentExecution {
  id: String,                  // UUID
  agent_slug: String,          // 'hostagent', 'flight_specialist'
  turn_id: String,
  started_at: DateTime,
  completed_at: DateTime?,
  status: String,              // 'processing' | 'completed' | 'failed'
  execution_time_ms: Integer,
  error_message: String?,
  metadata: String             // JSON: 입력/출력 데이터
})
```

**활용 사례**:
- 에이전트 성능 모니터링
- 병렬 실행 추적
- 에러 디버깅
- **프로비넌스 체인의 시작점**

---

### 2. Phase 2-1: 작업 관리 노드

#### 2.1 Agent (에이전트)
**목적**: 시스템의 AI 에이전트 정의

```cypher
(:Agent {
  slug: String,                  // 'flight_specialist'
  name: String,
  description: String,
  system_prompt: String,
  model_name: String,
  temperature: Float,
  cost: Float,                   // Contract Net: 비용
  usage_rate: Float,             // Contract Net: 사용률
  performance_score: Float,      // Contract Net: 성능 점수
  created_at: DateTime
})
```

**활용 사례**:
- 에이전트 카탈로그 관리
- FIT 스코어 계산
- 에이전트 선택 최적화

#### 2.2 Task (작업)
**목적**: 에이전트가 수행할 작업 단위

```cypher
(:Task {
  id: String,                    // UUID
  turn_id: String,
  description: String,           // 작업 설명
  status: String,                // 'TODO' | 'DOING' | 'DONE'
  priority: Integer,             // 1-10
  assigned_to: String?,          // agent_slug
  deadline: DateTime?,
  started_at: DateTime?,
  completed_at: DateTime?,
  created_at: DateTime
})
```

**활용 사례**:
- 작업 큐 관리
- 작업 위임 (delegation)
- 진행 상황 추적
- 블랙보드 패턴 구현

#### 2.3 Capability (역량)
**목적**: 에이전트가 보유한 능력 정의

```cypher
(:Capability {
  id: String,                    // UUID
  name: String,                  // 'flight_booking', 'hotel_search'
  category: String,              // 'booking', 'search', 'analysis'
  description: String,
  required_tools: String         // JSON: 필요한 도구 목록
})
```

**활용 사례**:
- Semantic routing (의미론적 라우팅)
- 에이전트 검색 (capability 기반)
- 작업-에이전트 매칭

#### 2.4 Tool (도구)
**목적**: 에이전트가 사용할 수 있는 외부 도구/API

```cypher
(:Tool {
  id: String,                    // UUID
  name: String,                  // 'amadeus_api', 'booking_com'
  type: String,                  // 'api' | 'function' | 'database'
  endpoint: String?,             // API 엔드포인트
  cost: Float,                   // 호출 비용
  availability: Boolean,         // 사용 가능 여부
  rate_limit: Integer?,          // 분당 호출 제한
  metadata: String               // JSON: 인증 정보 등
})
```

**활용 사례**:
- 도구 라우팅
- 비용 최적화
- 가용성 체크

---

### 3. Phase 2-2: 프로비넌스 노드

#### 3.1 Decision (의사결정)
**목적**: 에이전트의 의사결정 기록 (W3C PROV)

```cypher
(:Decision {
  id: String,                    // UUID
  turn_id: String,
  agent_slug: String,
  decision_type: String,         // 'flight_selection', 'delegation'
  description: String,           // 결정 내용
  rationale: String,             // 결정 근거
  confidence: Float,             // 0.0-1.0
  created_at: DateTime,
  metadata: String               // JSON: 추가 컨텍스트
})
```

**활용 사례**:
- 의사결정 추적
- 설명 가능한 AI (Explainable AI)
- 의사결정 감사
- 충돌 감지

#### 3.2 Evidence (근거)
**목적**: 의사결정을 뒷받침하는 근거/증거

```cypher
(:Evidence {
  id: String,                    // UUID
  evidence_type: String,         // 'api_response', 'user_preference'
  content: String,               // 근거 내용
  source: String,                // 'amadeus_api', 'conversation_history'
  confidence_score: Float,       // 신뢰도
  created_at: DateTime,
  metadata: String               // JSON: 원본 데이터
})
```

**활용 사례**:
- 의사결정 검증
- 데이터 출처 추적
- 신뢰도 평가

#### 3.3 Artifact (산출물)
**목적**: 작업의 결과물/중간 산출물

```cypher
(:Artifact {
  id: String,                    // UUID
  task_id: String,
  artifact_type: String,         // 'report', 'data', 'code'
  content: String,               // 산출물 내용
  format: String,                // 'json', 'text', 'binary'
  created_at: DateTime,
  metadata: String               // JSON: 추가 정보
})
```

**활용 사례**:
- 결과물 관리
- 계보 추적 (lineage)
- 버전 관리
- 재사용 가능한 자산

---

### 4. Phase 2-3: 거버넌스 노드

#### 4.1 Role (역할)
**목적**: RBAC의 역할 정의

```cypher
(:Role {
  id: String,                    // UUID
  name: String,                  // 'admin', 'specialist', 'worker'
  permission_level: Integer,     // 100, 50, 20
  description: String,
  permissions: String,           // JSON: ['read', 'write', 'delete']
  created_at: DateTime
})
```

**활용 사례**:
- 권한 관리
- 역할 기반 접근 제어
- 보안 정책 적용

#### 4.2 Policy (정책)
**목적**: 시스템 정책 정의

```cypher
(:Policy {
  id: String,                    // UUID
  policy_type: String,           // 'resource_limit', 'access_control'
  name: String,
  scope: String,                 // 'all_agents', 'worker_agents'
  rules: String,                 // JSON: 정책 규칙
  enforcement_level: String,     // 'mandatory' | 'advisory'
  is_active: Boolean,
  description: String,
  created_at: DateTime
})
```

**활용 사례**:
- 비용 제한
- 데이터 접근 제어
- 컴플라이언스 보장
- 정책 위반 감지

---

## 관계 타입 전체 목록

### Phase 1: 대화 추적 관계

| 관계 | 시작 노드 | 종료 노드 | 속성 | 의미 |
|------|----------|----------|------|------|
| `HAS_TURN` | Session | Turn | - | 세션이 턴을 포함 |
| `HAS_MESSAGE` | Turn | Message | - | 턴이 메시지를 포함 |
| `EXECUTED_BY` | Turn | AgentExecution | - | 턴이 에이전트 실행을 트리거 |
| `USED_AGENT` | AgentExecution | Agent | - | 실행이 특정 에이전트를 사용 |

### Phase 2-1: 작업 관리 관계

| 관계 | 시작 노드 | 종료 노드 | 속성 | 의미 |
|------|----------|----------|------|------|
| `GENERATED_TASK` | Turn | Task | - | 턴이 작업을 생성 |
| `CREATES_TASK` | Decision | Task | - | **NEW!** 의사결정이 작업 생성 |
| `EXECUTED_BY` | Task | AgentExecution | - | **NEW!** 작업이 실행에 의해 수행됨 |
| `HAS_CAPABILITY` | Agent | Capability | `proficiency: Float, cost: Float` | 에이전트가 역량 보유 |
| `REQUIRES_CAPABILITY` | Task | Capability | - | 작업이 역량 필요 |
| `PROVIDES` | Tool | Capability | - | 도구가 역량 제공 |
| `CAN_USE` | Agent | Tool | - | 에이전트가 도구 사용 가능 |
| `REQUIRES_TOOL` | Task | Tool | - | 작업이 도구 필요 |
| `NEXT` | Task | Task | `sequence: Integer` | 작업 순서 (서브태스크) |

### Phase 2-2: 프로비넌스 관계

| 관계 | 시작 노드 | 종료 노드 | 속성 | 의미 |
|------|----------|----------|------|------|
| `HAS_DECISION` | Turn | Decision | - | 턴이 의사결정 포함 |
| `MADE_DECISION` | AgentExecution | Decision | - | **NEW!** 실행이 의사결정 생성 |
| `MADE_BY` | Decision | Agent | - | 의사결정을 만든 에이전트 |
| `SUPPORTED_BY` | Decision | Evidence | `weight: Float` | 의사결정이 근거로 뒷받침됨 |
| `RESULTED_IN` | Decision | Artifact | - | 의사결정이 산출물로 귀결됨 |
| `PRODUCED` | Task | Artifact | - | 작업이 산출물 생성 (기존) |
| `PRODUCED` | AgentExecution | Artifact | - | **NEW!** 실행이 산출물 생성 |
| `DERIVED_FROM` | Artifact | Artifact | `transformation: String` | 산출물이 다른 산출물에서 파생 |

### Phase 2-3: 거버넌스 관계

| 관계 | 시작 노드 | 종료 노드 | 속성 | 의미 |
|------|----------|----------|------|------|
| `HAS_ROLE` | Agent | Role | `granted_by: String, granted_at: DateTime, expires_at: DateTime?` | 에이전트에게 역할 부여 |
| `GOVERNED_BY` | Role | Policy | - | 역할이 정책에 의해 관리됨 |
| `SUBJECT_TO` | Agent | Policy | - | 에이전트가 정책 적용 대상 |

---

## 실제 활용 시나리오

### 시나리오 1: 항공편 예약 요청

```
사용자: "10월 15일 파리행 항공편 예약해줘"

그래프 생성 흐름:
1. Session 생성 (사용자 세션)
2. Turn 생성 (사용자 입력)
3. AgentExecution 생성 (hostagent 실행 시작)
4. Decision 생성 (hostagent: "flight_specialist에게 위임")
   - AgentExecution -[:MADE_DECISION]-> Decision
5. Task 생성 ("항공편 검색")
   - Decision -[:CREATES_TASK]-> Task
6. AgentExecution 생성 (flight_specialist 실행 시작)
7. Task 할당
   - Task -[:EXECUTED_BY]-> AgentExecution
8. Evidence 생성 (Amadeus API 응답)
9. Decision 생성 (flight_specialist: "AF123 선택")
   - AgentExecution -[:MADE_DECISION]-> Decision
   - Decision -[:SUPPORTED_BY]-> Evidence
10. Artifact 생성 (검색 결과)
    - AgentExecution -[:PRODUCED]-> Artifact
```

### 시나리오 2: FIT 스코어 기반 에이전트 선택

```cypher
// 작업에 가장 적합한 에이전트 찾기
MATCH (task:Task {id: $task_id})-[:REQUIRES_CAPABILITY]->(cap:Capability)
MATCH (agent:Agent)-[has:HAS_CAPABILITY]->(cap)
WITH agent, task,
     avg(has.proficiency) as avg_proficiency,
     avg(has.cost) as avg_cost,
     count(cap) as matched_capabilities
WITH agent, task,
     (avg_proficiency * 0.4 +
      matched_capabilities * 0.3 +
      agent.performance_score * 0.2 -
      agent.cost * 0.1) as fit_score
ORDER BY fit_score DESC
LIMIT 1
RETURN agent.slug as best_agent, fit_score
```

**결과 예시**:
- `flight_specialist`: FIT score 0.810
- `general_worker`: FIT score 0.690

### 시나리오 3: 프로비넌스 역추적

```cypher
// 산출물을 생성한 모든 의사결정 추적
MATCH (artifact:Artifact {id: $artifact_id})
MATCH (artifact)<-[:PRODUCED]-(execution:AgentExecution)
MATCH (execution)-[:MADE_DECISION]->(decision:Decision)
MATCH (decision)-[:SUPPORTED_BY]->(evidence:Evidence)
RETURN
  execution.agent_slug as agent,
  decision.decision_type as decision_type,
  decision.rationale as rationale,
  collect(evidence.source) as evidence_sources
```

**결과**: "이 예약 확인서는 flight_specialist가 Amadeus API 데이터를 근거로 AF123을 선택한 결정의 결과입니다"

### 시나리오 4: 정책 위반 체크

```cypher
// 에이전트의 작업이 정책을 위반하는지 확인
MATCH (agent:Agent {slug: $agent_slug})
OPTIONAL MATCH (agent)-[:SUBJECT_TO]->(direct_policy:Policy)
OPTIONAL MATCH (agent)-[:HAS_ROLE]->(role:Role)-[:GOVERNED_BY]->(role_policy:Policy)
WITH agent,
     collect(DISTINCT direct_policy) + collect(DISTINCT role_policy) as all_policies
UNWIND all_policies as policy
WITH policy
WHERE policy IS NOT NULL AND policy.is_active = true
RETURN policy.rules as rules, policy.enforcement_level as enforcement
```

**활용**: 작업 실행 전 권한 체크, 비용 한도 확인

---

## 멀티에이전트와의 통합

### 1. LangGraph 통합

```python
from agents.database.neo4j import (
    ConversationTracker,
    TaskManager,
    ProvenanceTracker,
    GovernanceManager
)

class MultiAgentOrchestrator:
    def __init__(self):
        self.tracker = ConversationTracker(service)
        self.task_mgr = TaskManager(service)
        self.prov = ProvenanceTracker(service)
        self.gov = GovernanceManager(service)

    async def execute_turn(self, user_message: str):
        # 1. Turn 생성
        turn_id = self.tracker.create_turn(session_id, turn_number, user_message)

        # 2. 에이전트 실행 시작
        exec_id = self.tracker.create_agent_execution(
            agent_slug='hostagent',
            turn_id=turn_id
        )

        # 3. LangGraph로 에이전트 실행
        result = await langgraph_agent.run(user_message)

        # 4. 의사결정 기록
        decision_id = self.prov.create_decision(
            turn_id=turn_id,
            agent_slug='hostagent',
            decision_type='delegation',
            description=result.decision,
            rationale=result.reasoning,
            execution_id=exec_id  # 실행과 연결!
        )

        # 5. 작업 생성
        if result.should_delegate:
            task_id = self.task_mgr.create_task(
                turn_id=turn_id,
                description=result.task_description,
                decision_id=decision_id  # 의사결정과 연결!
            )

        # 6. 실행 완료
        self.tracker.complete_agent_execution(exec_id, status='completed')
```

### 2. CrewAI 통합

```python
from crewai import Agent, Task, Crew

class Neo4jCrewIntegration:
    def track_crew_execution(self, crew: Crew):
        # Crew 실행 전: 모든 Agent를 Neo4j에 등록
        for agent in crew.agents:
            self.ensure_agent_exists(agent)

        # Task 실행 시: Neo4j Task 노드 생성
        for task in crew.tasks:
            task_id = self.task_mgr.create_task(
                turn_id=current_turn_id,
                description=task.description,
                priority=task.priority
            )

            # FIT score로 최적 에이전트 선택
            best_agent = self.task_mgr.find_best_agent_for_task(task_id)

            # 작업 할당
            exec_id = self.tracker.create_agent_execution(
                agent_slug=best_agent,
                turn_id=current_turn_id
            )
            self.task_mgr.assign_task_to_agent(
                task_id=task_id,
                agent_slug=best_agent,
                execution_id=exec_id
            )
```

### 3. AutoGen 통합

```python
from autogen import AssistantAgent, UserProxyAgent

class Neo4jAutoGenIntegration:
    def track_autogen_conversation(self, agents: list):
        # 각 메시지마다 Neo4j에 기록
        for agent in agents:
            agent.register_reply(
                trigger=lambda x: True,
                reply_func=self.log_to_neo4j
            )

    def log_to_neo4j(self, recipient, messages, sender, config):
        # AgentExecution 기록
        exec_id = self.tracker.create_agent_execution(
            agent_slug=sender.name,
            turn_id=current_turn_id
        )

        # 메시지 → Decision 변환
        if self.is_decision(messages[-1]):
            decision_id = self.prov.create_decision(
                turn_id=current_turn_id,
                agent_slug=sender.name,
                decision_type='response',
                description=messages[-1]['content'],
                execution_id=exec_id
            )

        return messages
```

### 4. Semantic Routing (의미론적 라우팅)

```python
from semantic_router import Route, RouteLayer

class CapabilityBasedRouter:
    def __init__(self):
        self.routes = self.build_routes_from_neo4j()

    def build_routes_from_neo4j(self):
        # Neo4j에서 Capability 기반 라우트 생성
        query = """
        MATCH (agent:Agent)-[:HAS_CAPABILITY]->(cap:Capability)
        RETURN agent.slug as agent,
               cap.name as capability,
               cap.description as description
        """
        results = service.execute_query(query)

        routes = []
        for r in results:
            route = Route(
                name=r['agent'],
                utterances=[r['description']],
                metadata={'capability': r['capability']}
            )
            routes.append(route)

        return RouteLayer(routes=routes)

    def route_message(self, user_message: str):
        # 사용자 메시지를 가장 적합한 에이전트로 라우팅
        route = self.routes(user_message)
        return route.name  # agent_slug
```

---

## 쿼리 예제

### 1. 에이전트 성능 분석

```cypher
// 에이전트별 평균 실행 시간 및 성공률
MATCH (ae:AgentExecution)-[:USED_AGENT]->(a:Agent)
WHERE ae.completed_at IS NOT NULL
WITH a.slug as agent,
     count(ae) as total_executions,
     avg(ae.execution_time_ms) as avg_time_ms,
     sum(CASE WHEN ae.status = 'completed' THEN 1 ELSE 0 END) as successful,
     sum(CASE WHEN ae.status = 'failed' THEN 1 ELSE 0 END) as failed
RETURN agent,
       total_executions,
       avg_time_ms,
       successful * 100.0 / total_executions as success_rate,
       failed
ORDER BY success_rate DESC
```

### 2. 의사결정 충돌 감지

```cypher
// 같은 턴에서 상충되는 의사결정 찾기
MATCH (t:Turn)-[:HAS_DECISION]->(d1:Decision)
MATCH (t)-[:HAS_DECISION]->(d2:Decision)
WHERE d1.decision_type = d2.decision_type
  AND d1.id < d2.id
  AND d1.description <> d2.description
RETURN t.id as turn_id,
       d1.agent_slug as agent1,
       d1.description as decision1,
       d1.confidence as confidence1,
       d2.agent_slug as agent2,
       d2.description as decision2,
       d2.confidence as confidence2
```

### 3. 산출물 계보 추적

```cypher
// 최종 산출물이 어떤 데이터에서 파생되었는지 추적
MATCH path = (final:Artifact {id: $artifact_id})-[:DERIVED_FROM*0..]->(source:Artifact)
WITH final, source, path
ORDER BY length(path) DESC
RETURN source.artifact_type as source_type,
       source.content as source_content,
       length(path) as depth
```

### 4. 정책 컴플라이언스 감사

```cypher
// 최근 24시간 동안 정책 위반 여부 확인
MATCH (ae:AgentExecution)
WHERE ae.started_at > datetime() - duration({hours: 24})
MATCH (ae)-[:USED_AGENT]->(agent:Agent)
OPTIONAL MATCH (agent)-[:SUBJECT_TO|HAS_ROLE*1..2]-(policy:Policy)
WITH agent.slug as agent,
     count(ae) as executions,
     count(DISTINCT policy) as applicable_policies
RETURN agent,
       executions,
       applicable_policies,
       CASE WHEN applicable_policies > 0 THEN 'compliant' ELSE 'uncovered' END as status
ORDER BY executions DESC
```

### 5. 에이전트 협업 네트워크

```cypher
// 에이전트 간 작업 위임 패턴 분석
MATCH (ae1:AgentExecution)-[:MADE_DECISION]->(d:Decision)-[:CREATES_TASK]->(t:Task)
MATCH (t)-[:EXECUTED_BY]->(ae2:AgentExecution)
MATCH (ae1)-[:USED_AGENT]->(a1:Agent)
MATCH (ae2)-[:USED_AGENT]->(a2:Agent)
WHERE a1.slug <> a2.slug
RETURN a1.slug as delegator,
       a2.slug as executor,
       count(t) as tasks_delegated
ORDER BY tasks_delegated DESC
```

---

## 베스트 프랙티스 (2025 기준)

### 1. 인덱스 및 제약 조건

```cypher
// 필수 제약 조건 생성
CREATE CONSTRAINT unique_agent_slug IF NOT EXISTS
FOR (a:Agent) REQUIRE a.slug IS UNIQUE;

CREATE CONSTRAINT unique_session_id IF NOT EXISTS
FOR (s:Session) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT unique_task_id IF NOT EXISTS
FOR (t:Task) REQUIRE t.id IS UNIQUE;

// 성능 최적화 인덱스
CREATE INDEX agent_execution_status IF NOT EXISTS
FOR (ae:AgentExecution) ON (ae.status);

CREATE INDEX task_status_priority IF NOT EXISTS
FOR (t:Task) ON (t.status, t.priority);

CREATE INDEX decision_type_confidence IF NOT EXISTS
FOR (d:Decision) ON (d.decision_type, d.confidence);
```

### 2. Supernode 회피

❌ **피해야 할 패턴**:
```cypher
// 모든 Task가 하나의 Agent에 연결됨 (Supernode)
(task1:Task)-[:ASSIGNED_TO]->(hostagent:Agent)
(task2:Task)-[:ASSIGNED_TO]->(hostagent:Agent)
(task3:Task)-[:ASSIGNED_TO]->(hostagent:Agent)
...
(task10000:Task)-[:ASSIGNED_TO]->(hostagent:Agent)
```

✅ **권장 패턴**:
```cypher
// AgentExecution을 중간 노드로 사용
(task:Task)-[:EXECUTED_BY]->(ae:AgentExecution)-[:USED_AGENT]->(agent:Agent)
```

### 3. 쿼리 최적화

```cypher
// ❌ 비효율적: 모든 노드 스캔
MATCH (a:Agent)
WHERE a.name CONTAINS 'specialist'
RETURN a

// ✅ 효율적: 인덱스 활용
MATCH (a:Agent {slug: 'flight_specialist'})
RETURN a

// ✅ 효율적: 관계 먼저 필터링
MATCH (t:Turn {id: $turn_id})-[:EXECUTED_BY]->(ae:AgentExecution)
WHERE ae.status = 'completed'
RETURN ae
```

---

## 다음 단계 (Phase 3 계획)

1. **실시간 모니터링**
   - Grafana + Neo4j 통합
   - 에이전트 성능 대시보드
   - 실시간 경고 시스템

2. **머신러닝 통합**
   - Graph Neural Networks (GNN)
   - 에이전트 행동 예측
   - 이상 탐지

3. **확장성 개선**
   - Neo4j Fabric (분산 그래프)
   - 샤딩 전략
   - 캐싱 레이어

4. **고급 분석**
   - PageRank로 중요 에이전트 식별
   - Community Detection으로 협업 그룹 발견
   - 시계열 분석

---

## 참고 자료

- [W3C PROV Ontology](https://www.w3.org/TR/prov-o/)
- [PROV-AGENT Framework (2024)](https://arxiv.org/abs/2508.02866)
- [Neo4j Graph Data Modeling](https://neo4j.com/developer/modeling-designs/)
- [GraphRAG with Neo4j](https://neo4j.com/blog/developer/graphrag-and-agentic-architecture-with-neoconverse/)
- [Multi-Agent Systems Best Practices](https://lekha-bhan88.medium.com/best-practices-for-building-multi-agent-systems-in-ai-3006bf2dd1d6)

---

**작성일**: 2025-10-02
**버전**: 1.0
**상태**: Production Ready ✅
