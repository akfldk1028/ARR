# Neo4j Advanced Multi-Agent Orchestration Schema

## 개요

Enterprise급 Multi-Agent System을 위한 고급 Neo4j 그래프 스키마 설계.

**기존 스키마 (Phase 1)**: Session/Turn/Message/Agent/AgentExecution 추적
**확장 스키마 (Phase 2)**: Task/Tool/Capability/Decision/Evidence/Policy/Role 추가

**설계 목표:**
- ✅ 블랙보드 패턴 (Blackboard Pattern) - Task 협업
- ✅ 계약망 프로토콜 (Contract Net) - FIT 점수 기반 할당
- ✅ 도구 라우팅 (Tool Routing) - 동적 도구 선택
- ✅ 프로비넌스 추적 (Provenance Tracking) - 의사결정 근거
- ✅ 정책/권한 (Policy/RBAC) - 거버넌스

**참고 자료:**
- W3C PROV Standard for provenance tracking
- PROV-AGENT Framework (2024)
- Neo4j MCP (Model Context Protocol) Integration
- Contract Net Protocol for Multi-Agent Systems

---

## Phase 2 신규 노드 타입

### 7. Task (작업 노드) - 블랙보드 패턴

**용도**: 사용자 요청을 분해된 작업으로 관리. 블랙보드 패턴의 핵심 공유 데이터.

```cypher
(:Task {
  id: String,              // UUID
  turn_id: String,         // 어느 Turn에서 생성되었는지
  description: String,     // 작업 설명
  status: String,          // 'TODO' | 'DOING' | 'DONE'
  priority: Integer,       // 중요도 (1-10)
  deadline: DateTime?,     // 마감 시간
  assigned_to: String?,    // Agent slug (할당된 에이전트)
  created_at: DateTime,
  started_at: DateTime?,
  completed_at: DateTime?
})
```

**관계:**
- `Turn→GENERATED_TASK→Task` - 대화에서 작업 생성
- `Task→NEXT→Task` - 서브태스크 순서
- `AgentExecution→EXECUTED_TASK→Task` - 작업 실행

**쿼리 예시:**
```cypher
// 특정 Turn에서 생성된 모든 Task와 그 의존성
MATCH (t:Turn {id: $turn_id})-[:GENERATED_TASK]->(task:Task)
OPTIONAL MATCH (task)-[:NEXT*]->(subtask:Task)
RETURN task, collect(subtask) as subtasks
```

---

### 8. Tool (도구 노드) - 도구 라우팅

**용도**: 외부 API, 내부 서비스, 함수 등 에이전트가 사용 가능한 도구.

```cypher
(:Tool {
  id: String,              // UUID
  name: String,            // 'web_search', 'database_query', 'api_call'
  type: String,            // 'external_api' | 'internal_service' | 'function'
  endpoint: String?,       // API URL (외부 API인 경우)
  cost: Float,             // 사용 비용 (FIT 점수 계산용)
  availability: Boolean,   // 현재 사용 가능 여부
  description: String,
  created_at: DateTime
})
```

**관계:**
- `Agent→CAN_USE→Tool` - 에이전트가 사용 가능한 도구
- `Task→REQUIRES_TOOL→Tool` - 작업이 특정 도구 필요
- `AgentExecution→USED_TOOL→Tool` - 실행 중 사용한 도구
- `Policy→ALLOWS→Tool` - 정책이 도구 사용 허가

**쿼리 예시:**
```cypher
// Task에 필요한 Tool을 사용 가능한 Agent 찾기
MATCH (task:Task {id: $task_id})-[:REQUIRES_TOOL]->(tool:Tool)
MATCH (agent:Agent)-[:CAN_USE]->(tool)
WHERE agent.is_active = true
RETURN agent, collect(tool) as available_tools
```

---

### 9. Capability (능력 노드) - 능력 매칭

**용도**: 에이전트의 능력/스킬. Contract Net의 FIT 점수 계산 기반.

```cypher
(:Capability {
  id: String,              // UUID
  name: String,            // 'flight_booking', 'data_analysis', 'translation'
  category: String,        // 'domain_knowledge' | 'technical_skill' | 'integration'
  description: String,
  proficiency_level: Integer?,  // 숙련도 (1-10)
  created_at: DateTime
})
```

**관계:**
- `Agent→HAS_CAPABILITY {proficiency: Float, cost: Float}→Capability` - 에이전트 능력
- `Task→REQUIRES_CAPABILITY→Capability` - 작업 필요 능력
- `Capability→NEEDS_TOOL→Tool` - 능력 발휘에 필요한 도구

**FIT 점수 계산 쿼리:**
```cypher
// Task에 가장 적합한 Agent 찾기 (Contract Net Pattern)
MATCH (task:Task {id: $task_id})-[:REQUIRES_CAPABILITY]->(cap:Capability)
MATCH (agent:Agent)-[has:HAS_CAPABILITY]->(cap)
WITH agent,
     avg(has.proficiency) as avg_proficiency,
     avg(has.cost) as avg_cost,
     count(cap) as matched_capabilities
RETURN agent.slug,
       (avg_proficiency * 0.5 + matched_capabilities * 0.3 - avg_cost * 0.2) as fit_score
ORDER BY fit_score DESC
LIMIT 1
```

---

### 10. Decision (의사결정 노드) - 프로비넌스

**용도**: 에이전트의 의사결정 추적. "왜 이 결정을 했는가?"

```cypher
(:Decision {
  id: String,              // UUID
  execution_id: String,    // AgentExecution ID
  decision_type: String,   // 'delegation' | 'tool_selection' | 'response_generation'
  rationale: String,       // 결정 이유 (LLM 생성 설명)
  confidence: Float,       // 결정 확신도 (0.0-1.0)
  timestamp: DateTime,
  metadata: String?        // JSON (추가 컨텍스트)
})
```

**관계:**
- `AgentExecution→MADE_DECISION→Decision` - 실행 중 내린 결정
- `Decision→BASED_ON→Evidence` - 결정 근거
- `Decision→GENERATED→Artifact` - 결정으로 생성된 결과물

**쿼리 예시:**
```cypher
// 특정 delegation 결정의 전체 근거 추적
MATCH (exec:AgentExecution {id: $execution_id})-[:MADE_DECISION]->(d:Decision)
WHERE d.decision_type = 'delegation'
MATCH (d)-[:BASED_ON]->(evidence:Evidence)
RETURN d.rationale, collect({
  type: evidence.type,
  content: evidence.content,
  weight: evidence.weight
}) as evidences
```

---

### 11. Evidence (근거 노드) - 프로비넌스

**용도**: 의사결정의 근거 데이터. W3C PROV 표준 준수.

```cypher
(:Evidence {
  id: String,              // UUID
  type: String,            // 'user_input' | 'semantic_score' | 'agent_capability' | 'tool_availability'
  content: String,         // 실제 근거 데이터 (JSON or Text)
  source: String,          // 근거 출처 ('semantic_router', 'agent_discovery', 'user')
  weight: Float,           // 이 근거의 중요도 (0.0-1.0)
  timestamp: DateTime
})
```

**관계:**
- `Decision→BASED_ON→Evidence` - 결정이 근거에 기반
- `Evidence→DERIVED_FROM→Message` - 근거가 메시지에서 파생
- `Evidence→SUPPORTS→Decision` - 근거가 결정을 뒷받침

**쿼리 예시:**
```cypher
// 잘못된 결정 역추적 (Root Cause Analysis)
MATCH path = (error_decision:Decision {confidence: < 0.3})-[:BASED_ON*]->(root_evidence:Evidence)
WHERE NOT (root_evidence)-[:DERIVED_FROM]->()
RETURN path, root_evidence.source as root_cause
```

---

### 12. Artifact (결과물 노드) - 프로비넌스

**용도**: 에이전트가 생성한 결과물 추적. PROV-AGENT 표준.

```cypher
(:Artifact {
  id: String,              // UUID
  type: String,            // 'response' | 'query' | 'api_call' | 'data'
  content: String,         // 실제 결과물 내용
  format: String?,         // 'text' | 'json' | 'cypher'
  created_at: DateTime,
  created_by: String       // Agent slug
})
```

**관계:**
- `Decision→GENERATED→Artifact` - 결정이 결과물 생성
- `Artifact→DERIVED_FROM→Artifact` - 결과물이 다른 결과물에서 파생 (PROV 표준)
- `AgentExecution→PRODUCED→Artifact` - 실행이 결과물 생산

**프로비넌스 체인 쿼리:**
```cypher
// Artifact의 전체 생성 계보 추적
MATCH path = (final:Artifact {id: $artifact_id})-[:DERIVED_FROM*]->(origin:Artifact)
WHERE NOT (origin)-[:DERIVED_FROM]->()
RETURN path,
       [node in nodes(path) | {
         type: node.type,
         created_by: node.created_by,
         timestamp: node.created_at
       }] as provenance_chain
```

---

### 13. Policy (정책 노드) - 거버넌스

**용도**: 시스템 정책/규칙. 접근 제어, 제약 조건, 비율 제한.

```cypher
(:Policy {
  id: String,              // UUID
  name: String,            // 'max_delegation_depth', 'allowed_tools', 'data_access_rules'
  type: String,            // 'constraint' | 'permission' | 'rate_limit'
  rule: String,            // 정책 내용 (JSON)
  priority: Integer,       // 우선순위 (1-10)
  active: Boolean,
  description: String,
  created_at: DateTime,
  updated_at: DateTime
})
```

**관계:**
- `Agent→MUST_FOLLOW→Policy` - 에이전트가 따라야 할 정책
- `Role→SUBJECT_TO→Policy` - 역할에 적용되는 정책
- `AgentExecution→VIOLATED→Policy` - 정책 위반 (감사 추적)
- `Policy→ALLOWS→Tool` - 정책이 도구 사용 허가

**정책 위반 탐지 쿼리:**
```cypher
// 최근 정책 위반 찾기
MATCH (exec:AgentExecution)-[v:VIOLATED]->(policy:Policy)
WHERE exec.started_at > datetime() - duration({days: 7})
RETURN exec.agent_slug, policy.name, v.violation_reason, exec.started_at
ORDER BY exec.started_at DESC
```

---

### 14. Role (역할 노드) - RBAC

**용도**: 역할 기반 접근 제어 (Role-Based Access Control).

```cypher
(:Role {
  id: String,              // UUID
  name: String,            // 'admin' | 'specialist' | 'worker' | 'observer'
  permissions: String,     // JSON array of permissions
  description: String,
  created_at: DateTime
})
```

**관계:**
- `Agent→HAS_ROLE→Role` - 에이전트의 역할
- `Role→CAN_ACCESS→Tool` - 역할이 접근 가능한 도구
- `Role→CAN_EXECUTE→Capability` - 역할이 실행 가능한 능력
- `Role→SUBJECT_TO→Policy` - 역할에 적용되는 정책

**권한 확인 쿼리:**
```cypher
// Agent가 특정 Tool을 사용할 권한이 있는지 확인
MATCH (agent:Agent {slug: $agent_slug})-[:HAS_ROLE]->(role:Role)
MATCH (role)-[:CAN_ACCESS]->(tool:Tool {name: $tool_name})
OPTIONAL MATCH (agent)-[:MUST_FOLLOW]->(policy:Policy)-[:ALLOWS]->(tool)
RETURN
  CASE
    WHEN policy IS NOT NULL OR role IS NOT NULL THEN true
    ELSE false
  END as has_permission
```

---

## Agent 노드 확장 (기존 노드 업데이트)

기존 Agent 노드에 계약망(Contract Net) 지원을 위한 속성 추가:

```cypher
(:Agent {
  // 기존 속성
  slug: String,
  name: String,
  type: String,
  version: String,
  capabilities: String,  // JSON
  created_at: DateTime,

  // 신규 속성 (Contract Net)
  cost: Float,                    // 사용 비용 (FIT 점수 계산용)
  usage_rate: Float,              // 현재 사용률 (0.0-1.0)
  performance_score: Float,       // 성능 점수 (평균 실행 시간 기반)
  total_executions: Integer,      // 총 실행 횟수
  success_rate: Float             // 성공률 (0.0-1.0)
})
```

---

## 주요 관계 타입 정리

### Phase 1 관계 (기존)
1. `STARTED_SESSION` - User→Session
2. `HAS_TURN` - Session→Turn
3. `INCLUDES_MESSAGE` - Turn→Message
4. `EXECUTED_BY` - Turn→AgentExecution
5. `USED_AGENT` - AgentExecution→Agent
6. `DELEGATED_TO` - AgentExecution→AgentExecution (with semantic_score)

### Phase 2 관계 (신규)

#### 블랙보드 패턴
7. `GENERATED_TASK` - Turn→Task
8. `NEXT` - Task→Task (서브태스크 순서)
9. `EXECUTED_TASK` - AgentExecution→Task

#### 도구 라우팅
10. `CAN_USE` - Agent→Tool
11. `REQUIRES_TOOL` - Task→Tool
12. `USED_TOOL` - AgentExecution→Tool
13. `NEEDS_TOOL` - Capability→Tool

#### 능력 매칭 (Contract Net)
14. `HAS_CAPABILITY {proficiency, cost}` - Agent→Capability
15. `REQUIRES_CAPABILITY` - Task→Capability

#### 프로비넌스 (PROV 표준)
16. `MADE_DECISION` - AgentExecution→Decision
17. `BASED_ON` - Decision→Evidence
18. `GENERATED` - Decision→Artifact
19. `DERIVED_FROM` - Artifact→Artifact (계보 추적)
20. `PRODUCED` - AgentExecution→Artifact
21. `SUPPORTS` - Evidence→Decision

#### 정책/권한 (Governance)
22. `HAS_ROLE` - Agent→Role
23. `MUST_FOLLOW` - Agent→Policy
24. `SUBJECT_TO` - Role→Policy
25. `VIOLATED` - AgentExecution→Policy
26. `ALLOWS` - Policy→Tool
27. `CAN_ACCESS` - Role→Tool
28. `CAN_EXECUTE` - Role→Capability

---

## 인덱스 및 제약조건 (Phase 2)

### 신규 Unique 제약조건
```cypher
CREATE CONSTRAINT task_id_unique IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT tool_id_unique IF NOT EXISTS FOR (t:Tool) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT capability_id_unique IF NOT EXISTS FOR (c:Capability) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT decision_id_unique IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT artifact_id_unique IF NOT EXISTS FOR (a:Artifact) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT policy_id_unique IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT role_id_unique IF NOT EXISTS FOR (r:Role) REQUIRE r.id IS UNIQUE;
```

### 신규 성능 인덱스
```cypher
-- Task 쿼리
CREATE INDEX task_status_idx IF NOT EXISTS FOR (t:Task) ON (t.status);
CREATE INDEX task_turn_idx IF NOT EXISTS FOR (t:Task) ON (t.turn_id);
CREATE INDEX task_assigned_idx IF NOT EXISTS FOR (t:Task) ON (t.assigned_to);
CREATE INDEX task_deadline_idx IF NOT EXISTS FOR (t:Task) ON (t.deadline);

-- Tool 쿼리
CREATE INDEX tool_type_idx IF NOT EXISTS FOR (t:Tool) ON (t.type);
CREATE INDEX tool_name_idx IF NOT EXISTS FOR (t:Tool) ON (t.name);

-- Capability 쿼리
CREATE INDEX capability_category_idx IF NOT EXISTS FOR (c:Capability) ON (c.category);
CREATE INDEX capability_name_idx IF NOT EXISTS FOR (c:Capability) ON (c.name);

-- Decision 쿼리
CREATE INDEX decision_type_idx IF NOT EXISTS FOR (d:Decision) ON (d.decision_type);
CREATE INDEX decision_exec_idx IF NOT EXISTS FOR (d:Decision) ON (d.execution_id);

-- Evidence 쿼리
CREATE INDEX evidence_type_idx IF NOT EXISTS FOR (e:Evidence) ON (e.type);
CREATE INDEX evidence_source_idx IF NOT EXISTS FOR (e:Evidence) ON (e.source);

-- Policy 쿼리
CREATE INDEX policy_type_idx IF NOT EXISTS FOR (p:Policy) ON (p.type);
CREATE INDEX policy_active_idx IF NOT EXISTS FOR (p:Policy) ON (p.active);

-- Role 쿼리
CREATE INDEX role_name_idx IF NOT EXISTS FOR (r:Role) ON (r.name);
```

---

## 실전 쿼리 패턴

### 1. Contract Net: Task를 가장 적합한 Agent에게 할당

```cypher
MATCH (task:Task {id: $task_id})-[:REQUIRES_CAPABILITY]->(cap:Capability)
MATCH (agent:Agent)-[has:HAS_CAPABILITY]->(cap)
WHERE agent.is_active = true
WITH agent, task,
     avg(has.proficiency) as avg_proficiency,
     count(cap) as matched_capabilities
WITH agent, task,
     (avg_proficiency * 0.4 +
      matched_capabilities * 0.3 +
      agent.performance_score * 0.2 -
      agent.cost * 0.1) as fit_score
ORDER BY fit_score DESC
LIMIT 1
CREATE (task)-[:ASSIGNED_TO]->(agent)
SET task.assigned_to = agent.slug,
    task.status = 'DOING'
RETURN agent.slug, fit_score
```

### 2. 프로비넌스: 잘못된 응답의 전체 결정 체인 역추적

```cypher
MATCH (error_message:Message {id: $error_message_id})
MATCH (turn:Turn)-[:INCLUDES_MESSAGE]->(error_message)
MATCH (turn)-[:EXECUTED_BY]->(exec:AgentExecution)
MATCH path = (exec)-[:MADE_DECISION*]->(d:Decision)-[:BASED_ON]->(e:Evidence)
RETURN path,
       [node in nodes(path) | {
         type: labels(node)[0],
         id: node.id,
         details: CASE labels(node)[0]
           WHEN 'Decision' THEN {type: node.decision_type, confidence: node.confidence}
           WHEN 'Evidence' THEN {type: node.type, source: node.source, weight: node.weight}
           ELSE {}
         END
       }] as decision_chain
```

### 3. 블랙보드 패턴: 대기 중인 Task 중 우선순위 높은 것 선택

```cypher
MATCH (task:Task {status: 'TODO'})
WHERE task.deadline IS NOT NULL
  AND task.deadline > datetime()
OPTIONAL MATCH (task)-[:REQUIRES_CAPABILITY]->(cap:Capability)
WITH task, collect(cap.name) as required_capabilities,
     duration.between(datetime(), task.deadline).hours as hours_until_deadline
RETURN task.id, task.description, task.priority,
       required_capabilities, hours_until_deadline
ORDER BY
  task.priority DESC,
  hours_until_deadline ASC
LIMIT 10
```

### 4. 정책 위반 감사: 특정 기간 내 모든 위반 조회

```cypher
MATCH (exec:AgentExecution)-[v:VIOLATED]->(policy:Policy)
WHERE exec.started_at >= datetime($start_date)
  AND exec.started_at <= datetime($end_date)
MATCH (exec)-[:USED_AGENT]->(agent:Agent)
RETURN agent.slug, agent.name,
       policy.name, policy.type,
       v.violation_reason, v.violation_time,
       exec.id as execution_id
ORDER BY v.violation_time DESC
```

### 5. 도구 라우팅: Task에 필요한 모든 Tool과 사용 가능한 Agent

```cypher
MATCH (task:Task {id: $task_id})-[:REQUIRES_TOOL]->(tool:Tool)
MATCH (agent:Agent)-[:CAN_USE]->(tool)
WHERE agent.is_active = true
OPTIONAL MATCH (agent)-[:HAS_ROLE]->(role:Role)-[:CAN_ACCESS]->(tool)
WITH task, tool, agent, role
WHERE role IS NOT NULL OR agent.slug = 'admin'
RETURN tool.name, collect(DISTINCT {
  agent: agent.slug,
  cost: agent.cost,
  availability: tool.availability
}) as available_agents
```

---

## 마이그레이션 전략

### Phase 2 구현 순서

**Step 1: Task + Tool + Capability (핵심 패턴)**
1. 노드 생성 및 제약조건/인덱스
2. Agent 노드에 cost, usage_rate 속성 추가
3. ConversationTracker에 Task/Tool/Capability 메서드 추가
4. FIT 점수 계산 로직 구현

**Step 2: Decision + Evidence + Artifact (프로비넌스)**
1. 노드 생성 및 제약조건/인덱스
2. AgentExecution에 Decision tracking 로직 추가
3. PROV 표준 준수 검증
4. 프로비넌스 쿼리 API 구현

**Step 3: Policy + Role (거버넌스)**
1. 노드 생성 및 제약조건/인덱스
2. 권한 확인 미들웨어 구현
3. 정책 위반 로깅
4. 감사 대시보드

---

## 성능 고려사항

### 슈퍼노드 방지
- Task는 Turn별로 그룹화 (Turn당 평균 1-5개 Task)
- Tool/Capability는 Agent와 다대다 관계이지만, 전체 수량 제한 (Tool < 100, Capability < 50)

### 쿼리 최적화
- `task.status`, `policy.active`, `tool.availability`에 인덱스
- FIT 점수 계산 시 `WHERE` 절로 활성 Agent만 필터링
- 프로비넌스 체인 쿼리는 depth 제한 (최대 10 hop)

### 데이터 정리
- 완료된 Task (DONE 상태) 30일 후 아카이브
- Evidence/Decision은 AgentExecution과 함께 보관
- Policy 버전 관리 (old policy는 비활성화만)

---

## 총 스키마 요약

**노드 타입**: 14개
- Phase 1 (6): User, Session, Turn, Message, Agent, AgentExecution
- Phase 2 (8): Task, Tool, Capability, Decision, Evidence, Artifact, Policy, Role

**관계 타입**: 28개
- 블랙보드: 3개
- 도구 라우팅: 4개
- 능력 매칭: 2개
- 프로비넌스: 6개
- 거버넌스: 7개
- 기본: 6개

**인덱스**: 32개 (Phase 1: 14개 + Phase 2: 18개)
**제약조건**: 14개 (Phase 1: 6개 + Phase 2: 8개)

**지원 패턴**:
✅ A. 블랙보드 패턴 (Task + NEXT + REQUIRES)
✅ B. 계약망 프로토콜 (Capability + HAS_CAPABILITY + FIT 점수)
✅ C. 도구 라우팅 (Tool + CAN_USE + REQUIRES_TOOL)
✅ D. 프로비넌스 추적 (DERIVED_FROM + Evidence + BASED_ON)
✅ E. 정책/권한 (Policy + Role + MUST_FOLLOW)

---

## 참고 문헌

1. W3C PROV-DM: The PROV Data Model
2. PROV-AGENT: Unified Provenance for Tracking AI Agent Interactions (arXiv:2508.02866v1, 2024)
3. Neo4j Model Context Protocol (MCP) Integration (2024-2025)
4. Contract Net Protocol for Multi-Agent Task Allocation
5. Blackboard Pattern for Multi-Agent Collaboration
6. Neo4j Graph Database Best Practices (2024)

---

**작성일**: 2025-10-02
**버전**: 2.0.0
**상태**: Design Phase - Ready for Implementation
