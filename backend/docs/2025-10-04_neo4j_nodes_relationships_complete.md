# 2025-10-04: Neo4j 노드와 관계 완전 가이드

## Overview
Multi-Agent 시스템의 모든 대화, 에이전트 실행, 결정, 작업, 산출물을 Neo4j 그래프 데이터베이스에 추적 및 저장합니다. 이 문서는 각 노드와 관계가 **언제, 어떻게, 왜** 생성되는지를 상세히 설명합니다.

## Status: ✅ COMPLETE

---

## 🏗️ 전체 아키텍처

### 3계층 구조 (Three-Level Architecture)

```
LEVEL 1: 대화 흐름 (Conversation Flow)
├─ User (사용자)
├─ Session (대화 세션)
├─ Turn (대화 턴)
└─ Message (메시지)

LEVEL 2: 에이전트 실행 (Agent Execution)
├─ Agent (에이전트 정의)
└─ AgentExecution (실행 기록)

LEVEL 3: 결정과 산출물 (Decision & Artifacts)
├─ Decision (결정 사항)
├─ Task (작업)
└─ Artifact (산출물)

ADVANCED: 거버넌스 & 도구 (Governance & Tools)
├─ Evidence (증거)
├─ Tool (도구)
├─ Capability (능력)
├─ Role (역할)
└─ Policy (정책)
```

### 실제 생성 순서 (a2a_handler.py:36-233)

```python
# 사용자 메시지 "비행기 예약해줘" 입력 시:

1. Turn 생성               # Line 47-52
2. User Message 생성        # Line 55-63
3. AgentExecution 생성      # Line 89-117
4. (Agent 처리 중...)       # Line 120
5. AgentExecution 완료      # Line 124-139
6. Assistant Message 생성   # Line 143-155
7. Decision 생성           # Line 170-180
8. Task 생성               # Line 183-190
9. Task 할당               # Line 193-198
10. Artifact 생성          # Line 201-213
```

---

## 📦 노드 타입 상세 설명

### 1. User (사용자)

**목적**: 시스템을 사용하는 사용자 정보 저장

**속성**:
- `id` (String): 사용자 고유 ID
- `name` (String, optional): 사용자 이름
- `email` (String, optional): 이메일

**생성 시점**: Session 생성 시 자동으로 MERGE됨

**생성 위치**: `conversation_tracker.py:28`
```python
MERGE (u:User {id: $user_id})
```

**관계**:
- `(User)-[:STARTED_SESSION]->(Session)` - 사용자가 세션 시작

**예시**:
```cypher
// 사용자 노드 생성 (자동)
MERGE (u:User {id: "user123"})
```

---

### 2. Session (대화 세션)

**목적**: 하나의 대화 세션 추적 (브라우저 탭 하나 = 세션 하나)

**속성**:
- `id` (String): Session UUID
- `user_id` (String): 사용자 ID
- `started_at` (DateTime): 세션 시작 시간
- `ended_at` (DateTime, optional): 세션 종료 시간
- `status` (String): 'active' | 'completed' | 'abandoned'
- `metadata` (JSON): 추가 메타데이터

**생성 시점**: 사용자가 채팅 페이지에 처음 접속할 때

**생성 위치**: `conversation_tracker.py:24-49`
```python
def create_session(self, user_id: str, metadata: Dict[str, Any] = None) -> str:
    session_id = str(uuid4())
    query = """
    MERGE (u:User {id: $user_id})
    CREATE (s:Session {
        id: $session_id,
        user_id: $user_id,
        started_at: datetime($started_at),
        status: 'active',
        metadata: $metadata
    })
    CREATE (u)-[:STARTED_SESSION]->(s)
    RETURN s.id as session_id
    """
```

**호출 위치**: `simple_consumer.py:68-73` (WebSocket 연결 시)

**관계**:
- `(User)-[:STARTED_SESSION]->(Session)` - 사용자가 세션 시작
- `(Session)-[:HAS_TURN]->(Turn)` - 세션에 여러 턴 포함

**예시**:
```cypher
// 세션 시작
MATCH (u:User {id: "user123"})
CREATE (s:Session {
    id: "sess-uuid-1234",
    user_id: "user123",
    started_at: datetime(),
    status: 'active'
})
CREATE (u)-[:STARTED_SESSION]->(s)
```

---

### 3. Turn (대화 턴)

**목적**: 사용자 질문 → 에이전트 응답의 한 사이클 (한 턴)

**속성**:
- `id` (String): Turn UUID
- `session_id` (String): 속한 세션 ID
- `sequence` (Integer): 턴 순서 (1, 2, 3, ...)
- `started_at` (DateTime): 턴 시작 시간
- `completed_at` (DateTime, optional): 턴 완료 시간
- `user_query` (String): 사용자 질문 내용

**생성 시점**: 사용자가 메시지를 보낼 때마다

**생성 위치**: `conversation_tracker.py:51-77`
```python
def create_turn(self, session_id: str, sequence: int, user_query: str) -> str:
    turn_id = str(uuid4())
    query = """
    MATCH (s:Session {id: $session_id})
    CREATE (t:Turn {
        id: $turn_id,
        session_id: $session_id,
        sequence: $sequence,
        started_at: datetime($started_at),
        user_query: $user_query
    })
    CREATE (s)-[:HAS_TURN]->(t)
    RETURN t.id as turn_id
    """
```

**호출 위치**: `a2a_handler.py:47-52`
```python
# 사용자 메시지 받으면 즉시 Turn 생성
self.consumer.turn_counter += 1
turn_id = self.conversation_tracker.create_turn(
    session_id=self.neo4j_session_id,
    sequence=self.consumer.turn_counter,
    user_query=content
)
```

**관계**:
- `(Session)-[:HAS_TURN]->(Turn)` - 세션에 턴 포함
- `(Turn)-[:HAS_MESSAGE]->(Message)` - 턴에 메시지들 포함
- `(Turn)-[:EXECUTED_BY]->(AgentExecution)` - 턴을 처리한 에이전트 실행
- `(Turn)-[:GENERATED_TASK]->(Task)` - 턴에서 생성된 작업
- `(Turn)-[:HAS_DECISION]->(Decision)` - 턴에서 내린 결정

**예시**:
```cypher
// 첫 번째 턴 생성
MATCH (s:Session {id: "sess-uuid-1234"})
CREATE (t:Turn {
    id: "turn-uuid-001",
    session_id: "sess-uuid-1234",
    sequence: 1,
    started_at: datetime(),
    user_query: "비행기 예약해줘"
})
CREATE (s)-[:HAS_TURN]->(t)
```

---

### 4. Message (메시지)

**목적**: 대화의 각 메시지 저장 (사용자 메시지, 에이전트 응답)

**속성**:
- `id` (String): Message UUID
- `session_id` (String): 속한 세션 ID
- `turn_id` (String): 속한 턴 ID
- `role` (String): 'user' | 'assistant'
- `content` (String): 메시지 내용
- `timestamp` (DateTime): 메시지 생성 시간
- `sequence` (Integer): 메시지 순서 (1: user, 2: assistant)
- `metadata` (JSON): 추가 메타데이터

**생성 시점**:
1. User Message: 사용자가 메시지 보낼 때 (`a2a_handler.py:55-63`)
2. Assistant Message: 에이전트 응답 생성 후 (`a2a_handler.py:143-155`)

**생성 위치**: `conversation_tracker.py:79-119`
```python
def add_message(
    self,
    session_id: str,
    turn_id: str,
    role: str,
    content: str,
    sequence: int,
    metadata: Dict[str, Any] = None
) -> str:
    message_id = str(uuid4())
    query = """
    MATCH (t:Turn {id: $turn_id})
    CREATE (m:Message {
        id: $message_id,
        session_id: $session_id,
        turn_id: $turn_id,
        role: $role,
        content: $content,
        timestamp: datetime($timestamp),
        sequence: $sequence,
        metadata: $metadata
    })
    CREATE (t)-[:HAS_MESSAGE]->(m)
    RETURN m.id as message_id
    """
```

**호출 위치**:
- User Message: `a2a_handler.py:55-63`
- Assistant Message: `a2a_handler.py:143-155`

**관계**:
- `(Turn)-[:HAS_MESSAGE]->(Message)` - 턴에 메시지 포함

**예시**:
```cypher
// User Message
MATCH (t:Turn {id: "turn-uuid-001"})
CREATE (m1:Message {
    id: "msg-uuid-001",
    turn_id: "turn-uuid-001",
    role: "user",
    content: "비행기 예약해줘",
    timestamp: datetime(),
    sequence: 1
})
CREATE (t)-[:HAS_MESSAGE]->(m1)

// Assistant Message
MATCH (t:Turn {id: "turn-uuid-001"})
CREATE (m2:Message {
    id: "msg-uuid-002",
    turn_id: "turn-uuid-001",
    role: "assistant",
    content: "비행기 예약을 도와드리겠습니다...",
    timestamp: datetime(),
    sequence: 2,
    metadata: '{"agent_slug": "flight-specialist"}'
})
CREATE (t)-[:HAS_MESSAGE]->(m2)
```

---

### 5. Agent (에이전트 정의)

**목적**: 시스템의 각 에이전트 정의 (hostagent, flight-specialist, hotel-specialist 등)

**속성**:
- `slug` (String): 에이전트 고유 식별자 (예: "flight-specialist")
- `name` (String): 에이전트 이름
- `description` (String): 설명
- `version` (String): 버전
- `capabilities` (String[]): 능력 목록
- `cost` (Float): 실행 비용
- `performance_score` (Float): 성능 점수

**생성 시점**: Agent Card 동기화 시 (수동 또는 자동)

**생성 위치**: `management/commands/sync_agent_cards.py` (Django management command)

**관계**:
- `(AgentExecution)-[:USED_AGENT]->(Agent)` - 실행이 어느 에이전트를 사용했는지
- `(Agent)-[:HAS_CAPABILITY]->(Capability)` - 에이전트의 능력
- `(Agent)-[:CAN_USE]->(Tool)` - 에이전트가 사용할 수 있는 도구
- `(Agent)-[:HAS_ROLE]->(Role)` - 에이전트의 역할
- `(Agent)-[:SUBJECT_TO]->(Policy)` - 에이전트에 적용되는 정책
- `(Decision)-[:MADE_BY]->(Agent)` - 결정을 내린 에이전트

**예시**:
```cypher
// Flight Specialist Agent 등록
MERGE (a:Agent {slug: "flight-specialist"})
SET a.name = "Flight Specialist",
    a.description = "항공편 검색 및 예약 전문 에이전트",
    a.version = "1.0.0",
    a.cost = 0.05,
    a.performance_score = 0.95
```

---

### 6. AgentExecution (에이전트 실행)

**목적**: 특정 턴에서 에이전트가 실행된 기록 추적

**속성**:
- `id` (String): AgentExecution UUID
- `agent_slug` (String): 실행한 에이전트
- `turn_id` (String): 속한 턴 ID
- `started_at` (DateTime): 실행 시작 시간
- `completed_at` (DateTime, optional): 실행 완료 시간
- `status` (String): 'processing' | 'completed' | 'failed'
- `execution_time_ms` (Integer): 실행 시간 (밀리초)
- `error_message` (String, optional): 에러 메시지
- `metadata` (JSON): 추가 메타데이터

**생성 시점**: 에이전트가 처리 시작할 때

**생성 위치**: `a2a_handler.py:89-117` (직접 Cypher 쿼리 실행)
```python
# AgentExecution 노드 생성
exec_query = """
MATCH (t:Turn {id: $turn_id})
MERGE (a:Agent {slug: $agent_slug})
CREATE (ae:AgentExecution {
    id: $execution_id,
    agent_slug: $agent_slug,
    turn_id: $turn_id,
    started_at: datetime($started_at),
    status: 'processing',
    metadata: $metadata
})
CREATE (t)-[:EXECUTED_BY]->(ae)
CREATE (ae)-[:USED_AGENT]->(a)
RETURN ae.id as execution_id
"""
```

**업데이트 위치**: `a2a_handler.py:124-139` (완료 후 상태 업데이트)
```python
# AgentExecution 완료
update_query = """
MATCH (ae:AgentExecution {id: $execution_id})
SET ae.completed_at = datetime($completed_at),
    ae.status = $status,
    ae.execution_time_ms = $execution_time_ms,
    ae.error_message = $error_message
RETURN ae.id
"""
```

**관계**:
- `(Turn)-[:EXECUTED_BY]->(AgentExecution)` - 턴을 처리한 실행
- `(AgentExecution)-[:USED_AGENT]->(Agent)` - 실행이 사용한 에이전트
- `(AgentExecution)-[:MADE_DECISION]->(Decision)` - 실행 중 내린 결정
- `(AgentExecution)-[:PRODUCED]->(Artifact)` - 실행이 생성한 산출물
- `(Task)-[:EXECUTED_BY]->(AgentExecution)` - 작업을 실행한 실행 기록
- `(AgentExecution)-[:DELEGATED_TO]->(AgentExecution)` - 에이전트 간 위임

**예시**:
```cypher
// AgentExecution 생성 (flight-specialist)
MATCH (t:Turn {id: "turn-uuid-001"})
MERGE (a:Agent {slug: "flight-specialist"})
CREATE (ae:AgentExecution {
    id: "exec-uuid-001",
    agent_slug: "flight-specialist",
    turn_id: "turn-uuid-001",
    started_at: datetime(),
    status: 'processing',
    metadata: '{"user_query": "비행기 예약해줘", "routing_confidence": 0.976}'
})
CREATE (t)-[:EXECUTED_BY]->(ae)
CREATE (ae)-[:USED_AGENT]->(a)

// AgentExecution 완료
MATCH (ae:AgentExecution {id: "exec-uuid-001"})
SET ae.completed_at = datetime(),
    ae.status = 'completed',
    ae.execution_time_ms = 2350
```

---

### 7. Decision (결정)

**목적**: 에이전트가 내린 결정 사항 기록 (어떤 결정을 왜 내렸는지)

**속성**:
- `id` (String): Decision UUID
- `turn_id` (String): 속한 턴 ID
- `agent_slug` (String): 결정을 내린 에이전트
- `decision_type` (String): 결정 유형 (예: 'response_generation', 'delegation', 'tool_selection')
- `description` (String): 결정 내용
- `rationale` (String): 결정 이유
- `confidence` (Float): 확신도 (0.0 ~ 1.0)
- `created_at` (DateTime): 결정 시간
- `metadata` (JSON): 추가 메타데이터

**생성 시점**: 에이전트 응답 생성 완료 후

**생성 위치**: `provenance_tracker.py:26-123`
```python
def create_decision(
    self,
    turn_id: str,
    agent_slug: str,
    decision_type: str,
    description: str,
    rationale: str = None,
    confidence: float = None,
    metadata: Dict[str, Any] = None,
    execution_id: str = None
) -> str:
    decision_id = str(uuid4())

    # If execution_id provided, link Decision to AgentExecution
    if execution_id:
        query = """
        MATCH (t:Turn {id: $turn_id})
        MATCH (a:Agent {slug: $agent_slug})
        MATCH (ae:AgentExecution {id: $execution_id})
        CREATE (d:Decision {
            id: $decision_id,
            turn_id: $turn_id,
            agent_slug: $agent_slug,
            decision_type: $decision_type,
            description: $description,
            rationale: $rationale,
            confidence: $confidence,
            created_at: datetime($created_at),
            metadata: $metadata
        })
        CREATE (t)-[:HAS_DECISION]->(d)
        CREATE (d)-[:MADE_BY]->(a)
        CREATE (ae)-[:MADE_DECISION]->(d)
        RETURN d.id as decision_id
        """
```

**호출 위치**: `a2a_handler.py:170-180`
```python
# Decision 생성
decision_id = self.provenance_tracker.create_decision(
    turn_id=turn_id,
    agent_slug=self.consumer.current_agent_slug,
    decision_type='response_generation',
    description=f'Generated response for user query: {content[:50]}...',
    rationale='Processed user request and generated appropriate response using A2A protocol',
    confidence=1.0,
    metadata={'response_length': len(result['response'])},
    execution_id=execution_id
)
```

**관계**:
- `(Turn)-[:HAS_DECISION]->(Decision)` - 턴에서 내린 결정
- `(Decision)-[:MADE_BY]->(Agent)` - 결정을 내린 에이전트
- `(AgentExecution)-[:MADE_DECISION]->(Decision)` - 실행 중 내린 결정
- `(Decision)-[:CREATES_TASK]->(Task)` - 결정으로 생성된 작업
- `(Decision)-[:RESULTED_IN]->(Artifact)` - 결정의 결과물
- `(Decision)-[:SUPPORTED_BY]->(Evidence)` - 결정을 뒷받침하는 증거

**예시**:
```cypher
// Decision 생성
MATCH (t:Turn {id: "turn-uuid-001"})
MATCH (a:Agent {slug: "flight-specialist"})
MATCH (ae:AgentExecution {id: "exec-uuid-001"})
CREATE (d:Decision {
    id: "dec-uuid-001",
    turn_id: "turn-uuid-001",
    agent_slug: "flight-specialist",
    decision_type: "response_generation",
    description: "Generated response for user query: 비행기 예약해줘...",
    rationale: "Processed user request and generated appropriate response using A2A protocol",
    confidence: 1.0,
    created_at: datetime(),
    metadata: '{"response_length": 145}'
})
CREATE (t)-[:HAS_DECISION]->(d)
CREATE (d)-[:MADE_BY]->(a)
CREATE (ae)-[:MADE_DECISION]->(d)
```

---

### 8. Task (작업)

**목적**: 에이전트가 수행해야 할 작업 단위

**속성**:
- `id` (String): Task UUID
- `turn_id` (String): 속한 턴 ID
- `description` (String): 작업 설명
- `status` (String): 'TODO' | 'DOING' | 'DONE'
- `priority` (Integer): 우선순위 (1-10)
- `deadline` (DateTime, optional): 마감 시간
- `assigned_to` (String, optional): 할당된 에이전트
- `created_at` (DateTime): 작업 생성 시간
- `started_at` (DateTime, optional): 작업 시작 시간
- `completed_at` (DateTime, optional): 작업 완료 시간

**생성 시점**: Decision 생성 직후

**생성 위치**: `task_manager.py:25-106`
```python
def create_task(
    self,
    turn_id: str,
    description: str,
    priority: int = 5,
    deadline: datetime = None,
    status: str = 'TODO',
    decision_id: str = None
) -> str:
    task_id = str(uuid4())

    # If decision_id provided, link Task to Decision
    if decision_id:
        query = """
        MATCH (t:Turn {id: $turn_id})
        MATCH (d:Decision {id: $decision_id})
        CREATE (task:Task {
            id: $task_id,
            turn_id: $turn_id,
            description: $description,
            status: $status,
            priority: $priority,
            deadline: $deadline,
            created_at: datetime($created_at)
        })
        CREATE (t)-[:GENERATED_TASK]->(task)
        CREATE (d)-[:CREATES_TASK]->(task)
        RETURN task.id as task_id
        """
```

**호출 위치**: `a2a_handler.py:183-190`
```python
# Task 생성
task_id = self.task_manager.create_task(
    turn_id=turn_id,
    description=f'Generate response for: {content[:100]}...',
    priority=5,
    status='DONE',
    decision_id=decision_id
)
```

**할당 위치**: `a2a_handler.py:193-198`
```python
# Task를 AgentExecution에 할당
self.task_manager.assign_task_to_agent(
    task_id=task_id,
    agent_slug=self.consumer.current_agent_slug,
    execution_id=execution_id
)
```

**관계**:
- `(Turn)-[:GENERATED_TASK]->(Task)` - 턴에서 생성된 작업
- `(Decision)-[:CREATES_TASK]->(Task)` - 결정으로 생성된 작업
- `(Task)-[:EXECUTED_BY]->(AgentExecution)` - 작업을 실행한 에이전트
- `(Task)-[:PRODUCED]->(Artifact)` - 작업이 생성한 산출물
- `(Task)-[:REQUIRES_TOOL]->(Tool)` - 작업에 필요한 도구
- `(Task)-[:REQUIRES_CAPABILITY]->(Capability)` - 작업에 필요한 능력
- `(Task)-[:NEXT]->(Task)` - 순차 작업 (subtask)

**예시**:
```cypher
// Task 생성
MATCH (t:Turn {id: "turn-uuid-001"})
MATCH (d:Decision {id: "dec-uuid-001"})
CREATE (task:Task {
    id: "task-uuid-001",
    turn_id: "turn-uuid-001",
    description: "Generate response for: 비행기 예약해줘...",
    status: "DONE",
    priority: 5,
    created_at: datetime()
})
CREATE (t)-[:GENERATED_TASK]->(task)
CREATE (d)-[:CREATES_TASK]->(task)

// Task 할당
MATCH (task:Task {id: "task-uuid-001"})
MATCH (ae:AgentExecution {id: "exec-uuid-001"})
SET task.assigned_to = "flight-specialist",
    task.status = "DOING",
    task.started_at = datetime()
CREATE (task)-[:EXECUTED_BY]->(ae)
```

---

### 9. Artifact (산출물)

**목적**: 에이전트가 생성한 결과물 (응답, 데이터, 파일 등)

**속성**:
- `id` (String): Artifact UUID
- `task_id` (String): 속한 작업 ID
- `artifact_type` (String): 산출물 유형 (예: 'assistant_response', 'search_result', 'booking_confirmation')
- `content` (String): 산출물 내용
- `format` (String): 형식 ('text', 'json', 'binary', etc.)
- `created_at` (DateTime): 생성 시간
- `metadata` (JSON): 추가 메타데이터

**생성 시점**: Task 완료 후

**생성 위치**: `provenance_tracker.py:189-270`
```python
def create_artifact(
    self,
    task_id: str,
    artifact_type: str,
    content: str,
    format: str = "text",
    metadata: Dict[str, Any] = None,
    execution_id: str = None
) -> str:
    artifact_id = str(uuid4())

    # If execution_id provided, link Artifact to AgentExecution
    if execution_id:
        query = """
        MATCH (t:Task {id: $task_id})
        MATCH (ae:AgentExecution {id: $execution_id})
        CREATE (a:Artifact {
            id: $artifact_id,
            task_id: $task_id,
            artifact_type: $artifact_type,
            content: $content,
            format: $format,
            created_at: datetime($created_at),
            metadata: $metadata
        })
        CREATE (t)-[:PRODUCED]->(a)
        CREATE (ae)-[:PRODUCED]->(a)
        RETURN a.id as artifact_id
        """
```

**호출 위치**: `a2a_handler.py:201-213`
```python
# Artifact 생성
artifact_id = self.provenance_tracker.create_artifact(
    task_id=task_id,
    artifact_type='assistant_response',
    content=result['response'],
    format='text',
    metadata={
        'agent_slug': self.consumer.current_agent_slug,
        'agent_name': result.get('agent_name', 'AI'),
        'response_length': len(result['response'])
    },
    execution_id=execution_id
)
```

**관계**:
- `(Task)-[:PRODUCED]->(Artifact)` - 작업이 생성한 산출물
- `(AgentExecution)-[:PRODUCED]->(Artifact)` - 실행이 생성한 산출물
- `(Decision)-[:RESULTED_IN]->(Artifact)` - 결정의 결과물
- `(Artifact)-[:DERIVED_FROM]->(Artifact)` - 산출물 파생 관계

**예시**:
```cypher
// Artifact 생성
MATCH (task:Task {id: "task-uuid-001"})
MATCH (ae:AgentExecution {id: "exec-uuid-001"})
CREATE (a:Artifact {
    id: "artifact-uuid-001",
    task_id: "task-uuid-001",
    artifact_type: "assistant_response",
    content: "비행기 예약을 도와드리겠습니다. 출발지와 도착지, 날짜를 알려주세요.",
    format: "text",
    created_at: datetime(),
    metadata: '{"agent_slug": "flight-specialist", "response_length": 45}'
})
CREATE (task)-[:PRODUCED]->(a)
CREATE (ae)-[:PRODUCED]->(a)
```

---

## 🔗 관계(Relationship) 완전 가이드

### Level 1: 대화 흐름 관계

#### 1. STARTED_SESSION

**관계**: `(User)-[:STARTED_SESSION]->(Session)`

**목적**: 사용자가 대화 세션을 시작했음을 나타냄

**생성 시점**: Session 생성 시

**생성 위치**: `conversation_tracker.py:36`
```cypher
CREATE (u)-[:STARTED_SESSION]->(s)
```

**예시**:
```cypher
MATCH (u:User {id: "user123"}), (s:Session {id: "sess-uuid-1234"})
CREATE (u)-[:STARTED_SESSION]->(s)
```

---

#### 2. HAS_TURN

**관계**: `(Session)-[:HAS_TURN]->(Turn)`

**목적**: 세션에 포함된 대화 턴들

**생성 시점**: Turn 생성 시

**생성 위치**: `conversation_tracker.py:63`
```cypher
CREATE (s)-[:HAS_TURN]->(t)
```

**예시**:
```cypher
MATCH (s:Session {id: "sess-uuid-1234"}), (t:Turn {id: "turn-uuid-001"})
CREATE (s)-[:HAS_TURN]->(t)
```

---

#### 3. HAS_MESSAGE

**관계**: `(Turn)-[:HAS_MESSAGE]->(Message)`

**목적**: 턴에 포함된 메시지들 (사용자 질문 + 에이전트 응답)

**생성 시점**: Message 생성 시

**생성 위치**: `conversation_tracker.py:102`
```cypher
CREATE (t)-[:HAS_MESSAGE]->(m)
```

**예시**:
```cypher
// User Message
MATCH (t:Turn {id: "turn-uuid-001"}), (m:Message {id: "msg-uuid-001"})
CREATE (t)-[:HAS_MESSAGE]->(m)

// Assistant Message
MATCH (t:Turn {id: "turn-uuid-001"}), (m:Message {id: "msg-uuid-002"})
CREATE (t)-[:HAS_MESSAGE]->(m)
```

---

### Level 2: 에이전트 실행 관계

#### 4. EXECUTED_BY (Turn → AgentExecution)

**관계**: `(Turn)-[:EXECUTED_BY]->(AgentExecution)`

**목적**: 이 턴을 어느 에이전트 실행이 처리했는지

**생성 시점**: AgentExecution 생성 시

**생성 위치**: `a2a_handler.py:100`
```cypher
CREATE (t)-[:EXECUTED_BY]->(ae)
```

**예시**:
```cypher
MATCH (t:Turn {id: "turn-uuid-001"}), (ae:AgentExecution {id: "exec-uuid-001"})
CREATE (t)-[:EXECUTED_BY]->(ae)
```

---

#### 5. USED_AGENT

**관계**: `(AgentExecution)-[:USED_AGENT]->(Agent)`

**목적**: 실행이 어느 에이전트를 사용했는지

**생성 시점**: AgentExecution 생성 시

**생성 위치**: `a2a_handler.py:101`
```cypher
CREATE (ae)-[:USED_AGENT]->(a)
```

**예시**:
```cypher
MATCH (ae:AgentExecution {id: "exec-uuid-001"}), (a:Agent {slug: "flight-specialist"})
CREATE (ae)-[:USED_AGENT]->(a)
```

---

#### 6. DELEGATED_TO

**관계**: `(AgentExecution)-[:DELEGATED_TO]->(AgentExecution)`

**목적**: 한 에이전트가 다른 에이전트에게 작업을 위임했음

**속성**:
- `reason` (String): 위임 이유
- `semantic_score` (Float): 시맨틱 매칭 점수
- `skill_matched` (String): 매칭된 스킬
- `decision_time_ms` (Integer): 결정 시간
- `delegated_at` (DateTime): 위임 시점

**생성 시점**: Agent-to-Agent 위임 발생 시

**생성 위치**: `conversation_tracker.py:183-217`
```python
def create_delegation(
    self,
    from_execution_id: str,
    to_execution_id: str,
    reason: str,
    semantic_score: float = None,
    skill_matched: str = None,
    decision_time_ms: int = None
):
    query = """
    MATCH (from:AgentExecution {id: $from_execution_id})
    MATCH (to:AgentExecution {id: $to_execution_id})
    CREATE (from)-[d:DELEGATED_TO {
        reason: $reason,
        semantic_score: $semantic_score,
        skill_matched: $skill_matched,
        decision_time_ms: $decision_time_ms,
        delegated_at: datetime($delegated_at)
    }]->(to)
    RETURN d
    """
```

**예시**:
```cypher
// hostagent → flight-specialist 위임
MATCH (from:AgentExecution {agent_slug: "hostagent"}),
      (to:AgentExecution {agent_slug: "flight-specialist"})
CREATE (from)-[:DELEGATED_TO {
    reason: "Flight booking requires specialist",
    semantic_score: 0.976,
    skill_matched: "flight_booking",
    decision_time_ms: 450,
    delegated_at: datetime()
}]->(to)
```

---

### Level 3: 결정과 산출물 관계

#### 7. HAS_DECISION

**관계**: `(Turn)-[:HAS_DECISION]->(Decision)`

**목적**: 턴에서 내린 결정들

**생성 시점**: Decision 생성 시

**생성 위치**: `provenance_tracker.py:71`
```cypher
CREATE (t)-[:HAS_DECISION]->(d)
```

**예시**:
```cypher
MATCH (t:Turn {id: "turn-uuid-001"}), (d:Decision {id: "dec-uuid-001"})
CREATE (t)-[:HAS_DECISION]->(d)
```

---

#### 8. MADE_BY

**관계**: `(Decision)-[:MADE_BY]->(Agent)`

**목적**: 결정을 내린 에이전트

**생성 시점**: Decision 생성 시

**생성 위치**: `provenance_tracker.py:72`
```cypher
CREATE (d)-[:MADE_BY]->(a)
```

**예시**:
```cypher
MATCH (d:Decision {id: "dec-uuid-001"}), (a:Agent {slug: "flight-specialist"})
CREATE (d)-[:MADE_BY]->(a)
```

---

#### 9. MADE_DECISION

**관계**: `(AgentExecution)-[:MADE_DECISION]->(Decision)`

**목적**: 실행 중 내린 결정

**생성 시점**: Decision 생성 시 (execution_id 제공된 경우)

**생성 위치**: `provenance_tracker.py:73`
```cypher
CREATE (ae)-[:MADE_DECISION]->(d)
```

**예시**:
```cypher
MATCH (ae:AgentExecution {id: "exec-uuid-001"}), (d:Decision {id: "dec-uuid-001"})
CREATE (ae)-[:MADE_DECISION]->(d)
```

---

#### 10. CREATES_TASK

**관계**: `(Decision)-[:CREATES_TASK]->(Task)`

**목적**: 결정으로 인해 생성된 작업

**생성 시점**: Task 생성 시 (decision_id 제공된 경우)

**생성 위치**: `task_manager.py:64`
```cypher
CREATE (d)-[:CREATES_TASK]->(task)
```

**예시**:
```cypher
MATCH (d:Decision {id: "dec-uuid-001"}), (task:Task {id: "task-uuid-001"})
CREATE (d)-[:CREATES_TASK]->(task)
```

---

#### 11. GENERATED_TASK

**관계**: `(Turn)-[:GENERATED_TASK]->(Task)`

**목적**: 턴에서 생성된 작업

**생성 시점**: Task 생성 시

**생성 위치**: `task_manager.py:63` (with decision_id) or `task_manager.py:90` (without)
```cypher
CREATE (t)-[:GENERATED_TASK]->(task)
```

**예시**:
```cypher
MATCH (t:Turn {id: "turn-uuid-001"}), (task:Task {id: "task-uuid-001"})
CREATE (t)-[:GENERATED_TASK]->(task)
```

---

#### 12. EXECUTED_BY (Task → AgentExecution)

**관계**: `(Task)-[:EXECUTED_BY]->(AgentExecution)`

**목적**: 작업을 실행한 에이전트 실행

**생성 시점**: Task 할당 시 (execution_id 제공된 경우)

**생성 위치**: `task_manager.py:124`
```cypher
CREATE (task)-[:EXECUTED_BY]->(ae)
```

**예시**:
```cypher
MATCH (task:Task {id: "task-uuid-001"}), (ae:AgentExecution {id: "exec-uuid-001"})
CREATE (task)-[:EXECUTED_BY]->(ae)
```

---

#### 13. PRODUCED (Task → Artifact)

**관계**: `(Task)-[:PRODUCED]->(Artifact)`

**목적**: 작업이 생성한 산출물

**생성 시점**: Artifact 생성 시

**생성 위치**: `provenance_tracker.py:227` (with execution_id) or `provenance_tracker.py:254` (without)
```cypher
CREATE (t)-[:PRODUCED]->(a)
```

**예시**:
```cypher
MATCH (task:Task {id: "task-uuid-001"}), (a:Artifact {id: "artifact-uuid-001"})
CREATE (task)-[:PRODUCED]->(a)
```

---

#### 14. PRODUCED (AgentExecution → Artifact)

**관계**: `(AgentExecution)-[:PRODUCED]->(Artifact)`

**목적**: 실행이 생성한 산출물

**생성 시점**: Artifact 생성 시 (execution_id 제공된 경우)

**생성 위치**: `provenance_tracker.py:228`
```cypher
CREATE (ae)-[:PRODUCED]->(a)
```

**예시**:
```cypher
MATCH (ae:AgentExecution {id: "exec-uuid-001"}), (a:Artifact {id: "artifact-uuid-001"})
CREATE (ae)-[:PRODUCED]->(a)
```

---

#### 15. RESULTED_IN

**관계**: `(Decision)-[:RESULTED_IN]->(Artifact)`

**목적**: 결정의 결과로 생성된 산출물

**생성 시점**: 명시적으로 연결 필요 시

**생성 위치**: `provenance_tracker.py:299-318`
```python
def link_decision_to_artifact(self, decision_id: str, artifact_id: str):
    query = """
    MATCH (d:Decision {id: $decision_id})
    MATCH (a:Artifact {id: $artifact_id})
    CREATE (d)-[:RESULTED_IN]->(a)
    RETURN d, a
    """
```

**예시**:
```cypher
MATCH (d:Decision {id: "dec-uuid-001"}), (a:Artifact {id: "artifact-uuid-001"})
CREATE (d)-[:RESULTED_IN]->(a)
```

---

### Advanced: 거버넌스 & 도구 관계

#### 16. SUPPORTED_BY

**관계**: `(Decision)-[:SUPPORTED_BY {weight: Float}]->(Evidence)`

**목적**: 결정을 뒷받침하는 증거

**속성**:
- `weight` (Float): 증거의 가중치

**생성 시점**: Evidence 생성 후 Decision과 연결 시

**생성 위치**: `provenance_tracker.py:164-185`
```python
def link_evidence_to_decision(self, decision_id: str, evidence_id: str, weight: float = 1.0):
    query = """
    MATCH (d:Decision {id: $decision_id})
    MATCH (e:Evidence {id: $evidence_id})
    CREATE (d)-[s:SUPPORTED_BY {weight: $weight}]->(e)
    RETURN d, e
    """
```

**예시**:
```cypher
MATCH (d:Decision {id: "dec-uuid-001"}), (e:Evidence {id: "ev-uuid-001"})
CREATE (d)-[:SUPPORTED_BY {weight: 0.9}]->(e)
```

---

#### 17. DERIVED_FROM

**관계**: `(Artifact)-[:DERIVED_FROM {transformation: String}]->(Artifact)`

**목적**: 산출물의 파생 관계 (A 산출물이 B 산출물에서 파생됨)

**속성**:
- `transformation` (String): 변환 방법
- `created_at` (DateTime): 파생 시점

**생성 시점**: 산출물 변환/파생 시

**생성 위치**: `provenance_tracker.py:272-297`
```python
def link_artifact_derivation(
    self,
    derived_artifact_id: str,
    source_artifact_id: str,
    transformation: str = None
):
    query = """
    MATCH (derived:Artifact {id: $derived_artifact_id})
    MATCH (source:Artifact {id: $source_artifact_id})
    CREATE (derived)-[d:DERIVED_FROM {
        transformation: $transformation,
        created_at: datetime($created_at)
    }]->(source)
    RETURN derived, source
    """
```

**예시**:
```cypher
// JSON 응답을 텍스트로 변환
MATCH (text:Artifact {id: "artifact-text-001"}),
      (json:Artifact {id: "artifact-json-001"})
CREATE (text)-[:DERIVED_FROM {
    transformation: "json_to_text",
    created_at: datetime()
}]->(json)
```

---

#### 18. REQUIRES_TOOL

**관계**: `(Task)-[:REQUIRES_TOOL]->(Tool)`

**목적**: 작업 수행에 필요한 도구

**생성 시점**: Tool 요구사항 설정 시

**생성 위치**: `task_manager.py:243-258`
```python
def require_tool_for_task(self, task_id: str, tool_name: str):
    query = """
    MATCH (task:Task {id: $task_id})
    MATCH (tool:Tool {name: $tool_name})
    MERGE (task)-[:REQUIRES_TOOL]->(tool)
    RETURN task, tool
    """
```

**예시**:
```cypher
MATCH (task:Task {description: "Search flights"}), (tool:Tool {name: "FlightSearchAPI"})
CREATE (task)-[:REQUIRES_TOOL]->(tool)
```

---

#### 19. CAN_USE

**관계**: `(Agent)-[:CAN_USE]->(Tool)`

**목적**: 에이전트가 사용할 수 있는 도구

**생성 시점**: 에이전트-도구 등록 시

**생성 위치**: `task_manager.py:226-241`
```python
def register_agent_tool(self, agent_slug: str, tool_name: str):
    query = """
    MATCH (agent:Agent {slug: $agent_slug})
    MATCH (tool:Tool {name: $tool_name})
    MERGE (agent)-[:CAN_USE]->(tool)
    RETURN agent, tool
    """
```

**예시**:
```cypher
MATCH (a:Agent {slug: "flight-specialist"}), (t:Tool {name: "FlightSearchAPI"})
CREATE (a)-[:CAN_USE]->(t)
```

---

#### 20. HAS_CAPABILITY

**관계**: `(Agent)-[:HAS_CAPABILITY {proficiency: Float, cost: Float}]->(Capability)`

**목적**: 에이전트의 능력

**속성**:
- `proficiency` (Float): 숙련도 (0.0 ~ 1.0)
- `cost` (Float): 능력 사용 비용

**생성 시점**: 능력 할당 시

**생성 위치**: `task_manager.py:293-318`
```python
def assign_capability_to_agent(
    self,
    agent_slug: str,
    capability_name: str,
    proficiency: float = 0.8,
    cost: float = 0.1
):
    query = """
    MATCH (agent:Agent {slug: $agent_slug})
    MATCH (cap:Capability {name: $capability_name})
    MERGE (agent)-[has:HAS_CAPABILITY]->(cap)
    SET has.proficiency = $proficiency,
        has.cost = $cost
    RETURN agent, cap
    """
```

**예시**:
```cypher
MATCH (a:Agent {slug: "flight-specialist"}), (c:Capability {name: "flight_booking"})
CREATE (a)-[:HAS_CAPABILITY {proficiency: 0.95, cost: 0.05}]->(c)
```

---

#### 21. REQUIRES_CAPABILITY

**관계**: `(Task)-[:REQUIRES_CAPABILITY]->(Capability)`

**목적**: 작업 수행에 필요한 능력

**생성 시점**: Capability 요구사항 설정 시

**생성 위치**: `task_manager.py:320-335`
```python
def require_capability_for_task(self, task_id: str, capability_name: str):
    query = """
    MATCH (task:Task {id: $task_id})
    MATCH (cap:Capability {name: $capability_name})
    MERGE (task)-[:REQUIRES_CAPABILITY]->(cap)
    RETURN task, cap
    """
```

**예시**:
```cypher
MATCH (task:Task {description: "Book flight"}), (c:Capability {name: "flight_booking"})
CREATE (task)-[:REQUIRES_CAPABILITY]->(c)
```

---

#### 22. HAS_ROLE

**관계**: `(Agent)-[:HAS_ROLE {granted_by: String, granted_at: DateTime, expires_at: DateTime}]->(Role)`

**목적**: 에이전트의 역할 (RBAC)

**속성**:
- `granted_by` (String): 역할 부여자
- `granted_at` (DateTime): 부여 시점
- `expires_at` (DateTime, optional): 만료 시점

**생성 시점**: 역할 할당 시

**생성 위치**: `governance_manager.py:59-101`
```python
def assign_role_to_agent(
    self,
    agent_slug: str,
    role_name: str,
    granted_by: str = "system",
    expires_at: datetime = None
):
    query = """
    MATCH (agent:Agent {slug: $agent_slug})
    MATCH (role:Role {name: $role_name})
    MERGE (agent)-[has:HAS_ROLE]->(role)
    SET has.granted_by = $granted_by,
        has.granted_at = datetime($granted_at)
    """
```

**예시**:
```cypher
MATCH (a:Agent {slug: "flight-specialist"}), (r:Role {name: "specialist"})
CREATE (a)-[:HAS_ROLE {
    granted_by: "system",
    granted_at: datetime()
}]->(r)
```

---

#### 23. GOVERNED_BY

**관계**: `(Role)-[:GOVERNED_BY]->(Policy)`

**목적**: 역할에 적용되는 정책

**생성 시점**: 정책을 역할에 연결 시

**생성 위치**: `governance_manager.py:146-165`
```python
def attach_policy_to_role(self, role_name: str, policy_id: str):
    query = """
    MATCH (role:Role {name: $role_name})
    MATCH (policy:Policy {id: $policy_id})
    MERGE (role)-[:GOVERNED_BY]->(policy)
    RETURN role, policy
    """
```

**예시**:
```cypher
MATCH (r:Role {name: "specialist"}), (p:Policy {name: "response_time_limit"})
CREATE (r)-[:GOVERNED_BY]->(p)
```

---

#### 24. SUBJECT_TO

**관계**: `(Agent)-[:SUBJECT_TO]->(Policy)`

**목적**: 에이전트에 직접 적용되는 정책

**생성 시점**: 정책을 에이전트에 직접 연결 시

**생성 위치**: `governance_manager.py:167-186`
```python
def attach_policy_to_agent(self, agent_slug: str, policy_id: str):
    query = """
    MATCH (agent:Agent {slug: $agent_slug})
    MATCH (policy:Policy {id: $policy_id})
    MERGE (agent)-[:SUBJECT_TO]->(policy)
    RETURN agent, policy
    """
```

**예시**:
```cypher
MATCH (a:Agent {slug: "flight-specialist"}), (p:Policy {name: "cost_limit"})
CREATE (a)-[:SUBJECT_TO]->(p)
```

---

#### 25. NEXT

**관계**: `(Task)-[:NEXT]->(Task)`

**목적**: 순차 작업 (subtask 순서)

**생성 시점**: Subtask 연결 시

**생성 위치**: `task_manager.py:169-184`
```python
def link_subtasks(self, parent_task_id: str, child_task_id: str):
    query = """
    MATCH (parent:Task {id: $parent_task_id})
    MATCH (child:Task {id: $child_task_id})
    CREATE (parent)-[:NEXT]->(child)
    RETURN parent, child
    """
```

**예시**:
```cypher
MATCH (t1:Task {description: "Search flights"}),
      (t2:Task {description: "Book selected flight"})
CREATE (t1)-[:NEXT]->(t2)
```

---

## 🔄 실제 코드 흐름 (Complete Flow)

### 시나리오: "비행기 예약해줘" 입력 처리

#### 파일: `gemini/consumers/handlers/a2a_handler.py:36-233`

```python
async def handle_text(self, data):
    content = "비행기 예약해줘"

    # ===== STEP 1: Turn 생성 (Line 47-52) =====
    self.consumer.turn_counter += 1  # Turn counter: 1
    turn_id = self.conversation_tracker.create_turn(
        session_id=self.neo4j_session_id,
        sequence=1,
        user_query=content
    )
    # Result: Turn 노드 생성, (Session)-[:HAS_TURN]->(Turn) 관계 생성

    # ===== STEP 2: User Message 생성 (Line 55-63) =====
    user_msg_id = self.conversation_tracker.add_message(
        session_id=self.neo4j_session_id,
        turn_id=turn_id,
        role='user',
        content=content,
        sequence=1
    )
    # Result: Message 노드 생성, (Turn)-[:HAS_MESSAGE]->(Message) 관계 생성

    # ===== STEP 3: Semantic Routing (Line 69) =====
    routing_result = await self._analyze_intent_with_similarity(content, 'hostagent')
    # Result: {
    #   'should_delegate': True,
    #   'target_agent': 'flight-specialist',
    #   'confidence': 0.976
    # }

    # ===== STEP 4: AgentExecution 생성 (Line 89-117) =====
    execution_id = str(uuid4())
    # Direct Cypher query:
    exec_query = """
    MATCH (t:Turn {id: $turn_id})
    MERGE (a:Agent {slug: 'flight-specialist'})
    CREATE (ae:AgentExecution {
        id: $execution_id,
        agent_slug: 'flight-specialist',
        status: 'processing'
    })
    CREATE (t)-[:EXECUTED_BY]->(ae)
    CREATE (ae)-[:USED_AGENT]->(a)
    """
    # Result: AgentExecution 노드 생성, 관계 2개 생성

    # ===== STEP 5: Agent 처리 (Line 120) =====
    result = await self._process_with_a2a(content)
    # Result: {
    #   'success': True,
    #   'response': '비행기 예약을 도와드리겠습니다. 출발지와 도착지를...',
    #   'agent_name': 'Flight Specialist'
    # }

    # ===== STEP 6: AgentExecution 완료 (Line 124-139) =====
    update_query = """
    MATCH (ae:AgentExecution {id: $execution_id})
    SET ae.completed_at = datetime(),
        ae.status = 'completed',
        ae.execution_time_ms = 2350
    """
    # Result: AgentExecution 상태 업데이트

    # ===== STEP 7: Assistant Message 생성 (Line 143-155) =====
    assistant_msg_id = self.conversation_tracker.add_message(
        session_id=self.neo4j_session_id,
        turn_id=turn_id,
        role='assistant',
        content=result['response'],
        sequence=2
    )
    # Result: Message 노드 생성 (assistant), (Turn)-[:HAS_MESSAGE]->(Message)

    # ===== STEP 8: Decision 생성 (Line 170-180) =====
    decision_id = self.provenance_tracker.create_decision(
        turn_id=turn_id,
        agent_slug='flight-specialist',
        decision_type='response_generation',
        description='Generated response for user query',
        confidence=1.0,
        execution_id=execution_id
    )
    # Result: Decision 노드 생성, 관계 3개 생성:
    #   (Turn)-[:HAS_DECISION]->(Decision)
    #   (Decision)-[:MADE_BY]->(Agent)
    #   (AgentExecution)-[:MADE_DECISION]->(Decision)

    # ===== STEP 9: Task 생성 (Line 183-190) =====
    task_id = self.task_manager.create_task(
        turn_id=turn_id,
        description='Generate response for: 비행기 예약해줘',
        status='DONE',
        decision_id=decision_id
    )
    # Result: Task 노드 생성, 관계 2개 생성:
    #   (Turn)-[:GENERATED_TASK]->(Task)
    #   (Decision)-[:CREATES_TASK]->(Task)

    # ===== STEP 10: Task 할당 (Line 193-198) =====
    self.task_manager.assign_task_to_agent(
        task_id=task_id,
        agent_slug='flight-specialist',
        execution_id=execution_id
    )
    # Result: 관계 1개 생성:
    #   (Task)-[:EXECUTED_BY]->(AgentExecution)

    # ===== STEP 11: Artifact 생성 (Line 201-213) =====
    artifact_id = self.provenance_tracker.create_artifact(
        task_id=task_id,
        artifact_type='assistant_response',
        content=result['response'],
        format='text',
        execution_id=execution_id
    )
    # Result: Artifact 노드 생성, 관계 2개 생성:
    #   (Task)-[:PRODUCED]->(Artifact)
    #   (AgentExecution)-[:PRODUCED]->(Artifact)
```

### 생성된 그래프 구조 (시각화)

```
(User {id: "user123"})
  |
  [:STARTED_SESSION]
  |
  v
(Session {id: "sess-uuid-1234", status: "active"})
  |
  [:HAS_TURN]
  |
  v
(Turn {id: "turn-uuid-001", sequence: 1, user_query: "비행기 예약해줘"})
  |
  +--- [:HAS_MESSAGE] ---> (Message {role: "user", content: "비행기 예약해줘", sequence: 1})
  |
  +--- [:HAS_MESSAGE] ---> (Message {role: "assistant", content: "비행기 예약을...", sequence: 2})
  |
  +--- [:EXECUTED_BY] ---> (AgentExecution {id: "exec-uuid-001", status: "completed", execution_time_ms: 2350})
  |                            |
  |                            +--- [:USED_AGENT] ---> (Agent {slug: "flight-specialist"})
  |                            |
  |                            +--- [:MADE_DECISION] ---> (Decision {decision_type: "response_generation"})
  |                            |                              |
  |                            |                              +--- [:MADE_BY] ---> (Agent {slug: "flight-specialist"})
  |                            |                              |
  |                            |                              +--- [:CREATES_TASK] ---> (Task {status: "DONE"})
  |                            |                                                          |
  |                            +--- [:PRODUCED] ---> (Artifact {artifact_type: "assistant_response"})
  |                                                       ^
  |                                                       |
  +--- [:GENERATED_TASK] ---> (Task) --- [:PRODUCED] ----+
  |                            |
  +--- [:HAS_DECISION] --------+--- [:EXECUTED_BY] ---> (AgentExecution)
```

---

## 📊 노드와 관계 요약표

### 노드 총 14개

| 노드 타입 | 생성 시점 | 주요 파일 | 라인 번호 |
|----------|----------|----------|----------|
| User | Session 생성 시 | conversation_tracker.py | 28 |
| Session | WebSocket 연결 시 | conversation_tracker.py | 24-49 |
| Turn | 메시지 수신 시 | conversation_tracker.py | 51-77 |
| Message | 메시지 생성 시 | conversation_tracker.py | 79-119 |
| Agent | Agent Card 동기화 시 | sync_agent_cards.py | - |
| AgentExecution | 에이전트 시작 시 | a2a_handler.py | 89-117 |
| Decision | 응답 생성 후 | provenance_tracker.py | 26-123 |
| Task | Decision 후 | task_manager.py | 25-106 |
| Artifact | Task 완료 후 | provenance_tracker.py | 189-270 |
| Evidence | 증거 수집 시 | provenance_tracker.py | 127-162 |
| Tool | Tool 등록 시 | task_manager.py | 188-224 |
| Capability | Capability 등록 시 | task_manager.py | 262-291 |
| Role | 역할 생성 시 | governance_manager.py | 25-57 |
| Policy | 정책 생성 시 | governance_manager.py | 105-144 |

### 관계 총 25개

| 관계 타입 | 시작 노드 | 끝 노드 | 생성 시점 | 주요 파일 | 라인 번호 |
|----------|----------|---------|----------|----------|----------|
| STARTED_SESSION | User | Session | Session 생성 | conversation_tracker.py | 36 |
| HAS_TURN | Session | Turn | Turn 생성 | conversation_tracker.py | 63 |
| HAS_MESSAGE | Turn | Message | Message 생성 | conversation_tracker.py | 102 |
| EXECUTED_BY | Turn | AgentExecution | AgentExecution 생성 | a2a_handler.py | 100 |
| USED_AGENT | AgentExecution | Agent | AgentExecution 생성 | a2a_handler.py | 101 |
| DELEGATED_TO | AgentExecution | AgentExecution | 에이전트 위임 | conversation_tracker.py | 196 |
| HAS_DECISION | Turn | Decision | Decision 생성 | provenance_tracker.py | 71 |
| MADE_BY | Decision | Agent | Decision 생성 | provenance_tracker.py | 72 |
| MADE_DECISION | AgentExecution | Decision | Decision 생성 | provenance_tracker.py | 73 |
| CREATES_TASK | Decision | Task | Task 생성 | task_manager.py | 64 |
| GENERATED_TASK | Turn | Task | Task 생성 | task_manager.py | 63 |
| EXECUTED_BY | Task | AgentExecution | Task 할당 | task_manager.py | 124 |
| PRODUCED | Task | Artifact | Artifact 생성 | provenance_tracker.py | 227 |
| PRODUCED | AgentExecution | Artifact | Artifact 생성 | provenance_tracker.py | 228 |
| RESULTED_IN | Decision | Artifact | 명시적 연결 | provenance_tracker.py | 308 |
| SUPPORTED_BY | Decision | Evidence | Evidence 연결 | provenance_tracker.py | 174 |
| DERIVED_FROM | Artifact | Artifact | 산출물 파생 | provenance_tracker.py | 282 |
| REQUIRES_TOOL | Task | Tool | Tool 요구사항 | task_manager.py | 248 |
| CAN_USE | Agent | Tool | Tool 등록 | task_manager.py | 231 |
| HAS_CAPABILITY | Agent | Capability | Capability 할당 | task_manager.py | 304 |
| REQUIRES_CAPABILITY | Task | Capability | Capability 요구 | task_manager.py | 325 |
| HAS_ROLE | Agent | Role | 역할 할당 | governance_manager.py | 71 |
| GOVERNED_BY | Role | Policy | 정책-역할 연결 | governance_manager.py | 155 |
| SUBJECT_TO | Agent | Policy | 정책-에이전트 연결 | governance_manager.py | 176 |
| NEXT | Task | Task | Subtask 연결 | task_manager.py | 174 |

---

## 📁 관련 파일 정리

### 1. Neo4j Core 파일

| 파일 경로 | 설명 | 주요 클래스/함수 |
|----------|------|-----------------|
| `agents/database/neo4j/service.py` | Neo4j 연결 서비스 | Neo4jService, get_neo4j_service() |
| `agents/database/neo4j/conversation_tracker.py` | 대화 추적 (Level 1) | ConversationTracker |
| `agents/database/neo4j/task_manager.py` | 작업 관리 (Phase 2) | TaskManager |
| `agents/database/neo4j/provenance_tracker.py` | 출처 추적 (Phase 2-2) | ProvenanceTracker |
| `agents/database/neo4j/governance_manager.py` | 거버넌스 (Phase 2-3) | GovernanceManager |
| `agents/database/neo4j/indexes.py` | 인덱스 관리 | create_all_indexes() |
| `agents/database/neo4j/stats.py` | 통계 조회 | get_database_stats() |

### 2. 실행 흐름 파일

| 파일 경로 | 설명 | 노드 생성 순서 |
|----------|------|---------------|
| `gemini/consumers/simple_consumer.py` | WebSocket Consumer | Session 생성 (연결 시) |
| `gemini/consumers/handlers/a2a_handler.py` | A2A 핸들러 | Turn → Message → AgentExecution → Decision → Task → Artifact |

### 3. 테스트 & 검증 파일

| 파일 경로 | 설명 |
|----------|------|
| `test_neo4j_clean.py` | 데이터베이스 초기화 |
| `test_neo4j_verify.py` | 그래프 구조 검증 |

---

## 🎯 핵심 포인트

### 1. 3계층 아키텍처
- **Level 1 (대화)**: User → Session → Turn → Message
- **Level 2 (실행)**: Agent, AgentExecution
- **Level 3 (결정/산출물)**: Decision → Task → Artifact

### 2. 중요한 관계들
- `(Turn)-[:EXECUTED_BY]->(AgentExecution)` - 턴 처리
- `(AgentExecution)-[:MADE_DECISION]->(Decision)` - 결정 기록
- `(Decision)-[:CREATES_TASK]->(Task)` - 작업 생성
- `(AgentExecution)-[:PRODUCED]->(Artifact)` - 산출물 생성

### 3. 추적 가능성 (Traceability)
- 사용자 질문 → 응답까지 전체 흐름 추적 가능
- 어느 에이전트가 언제 어떤 결정을 내렸는지 기록
- 산출물의 출처 (provenance) 완전 추적

### 4. 확장성
- Tool, Capability를 통한 Contract Net Protocol
- Role, Policy를 통한 RBAC 거버넌스
- Evidence를 통한 결정 검증

---

## 🔍 쿼리 예시

### 1. 특정 세션의 전체 대화 흐름 조회
```cypher
MATCH (s:Session {id: $session_id})-[:HAS_TURN]->(t:Turn)
OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
OPTIONAL MATCH (t)-[:EXECUTED_BY]->(ae:AgentExecution)
RETURN s, t, m, ae
ORDER BY t.sequence, m.sequence
```

### 2. 에이전트 실행 → 결정 → 작업 → 산출물 체인
```cypher
MATCH (ae:AgentExecution {id: $execution_id})
OPTIONAL MATCH (ae)-[:MADE_DECISION]->(d:Decision)
OPTIONAL MATCH (d)-[:CREATES_TASK]->(task:Task)
OPTIONAL MATCH (ae)-[:PRODUCED]->(a:Artifact)
RETURN ae, d, task, a
```

### 3. 에이전트 성능 통계
```cypher
MATCH (ae:AgentExecution {agent_slug: $agent_slug})
WHERE ae.status = 'completed'
RETURN
  count(ae) as total_executions,
  avg(ae.execution_time_ms) as avg_time,
  min(ae.execution_time_ms) as min_time,
  max(ae.execution_time_ms) as max_time
```

### 4. 위임 체인 추적
```cypher
MATCH path = (start:AgentExecution)-[:DELEGATED_TO*]->(end:AgentExecution)
WHERE start.agent_slug = 'hostagent'
RETURN path
```

---

## 📝 최종 정리

이 문서는 Multi-Agent 시스템의 Neo4j 그래프 구조를 완전히 설명합니다:

1. **14개 노드 타입** - 대화, 실행, 결정, 산출물, 거버넌스
2. **25개 관계 타입** - 모든 연결과 의미
3. **실제 코드 위치** - 각 노드/관계가 생성되는 정확한 파일과 라인 번호
4. **실행 흐름 예시** - "비행기 예약해줘" 시나리오의 완전한 추적

이 시스템은 **W3C PROV Standard**와 **Blackboard Pattern**, **Contract Net Protocol**, **RBAC**를 구현하여 enterprise-grade 추적성과 거버넌스를 제공합니다.

---

**Created**: 2025-10-04
**Status**: COMPLETE
**Related Docs**:
- `2025-10-04_semantic_routing_system_complete.md`
- `NEO4J_SCHEMA_COMPLETE_GUIDE.md`
- `NEO4J_ENTERPRISE_SCHEMA.md`
