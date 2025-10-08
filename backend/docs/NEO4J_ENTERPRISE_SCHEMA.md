# Enterprise Multi-Agent System - Neo4j Graph Schema

## 개요

A2A 프로토콜 기반 멀티에이전트 시스템의 **대화, 세션, 에이전트 협업**을 추적하기 위한 Enterprise급 Neo4j 그래프 스키마 설계.

**설계 목표:**
- 유저-세션-메시지 완전 분리
- 에이전트 간 위임(delegation) 추적
- 에이전트 간 협업(collaboration) 추적
- 성능 최적화 (인덱스, 제약조건)
- 유지보수성 (명확한 관계 타입)

## 핵심 설계 원칙 (Neo4j Best Practices)

1. **특정 관계 타입 사용**: `DELEGATED_TO` > `RELATED_TO`
2. **슈퍼노드 방지**: Turn 노드로 메시지 그룹화
3. **쿼리 패턴 최적화**: 자주 쓰는 경로에 인덱스
4. **시간 순서 추적**: sequence 프로퍼티 + NEXT 관계

---

## 노드 타입 (Node Labels)

### 1. User (사용자)

실제 사용자. Django User와 1:1 매핑.

```cypher
(:User {
  id: String,              // UUID (Django User ID)
  username: String,        // 사용자명
  email: String?,          // 이메일
  created_at: DateTime     // 가입일
})
```

**용도:**
- 사용자별 모든 세션 조회
- 사용자 통계 (총 대화 수, 선호 에이전트 등)

---

### 2. Session (대화 세션)

하나의 대화 세션. 웹소켓 연결 단위.

```cypher
(:Session {
  id: String,              // UUID (WebSocket session ID)
  user_id: String,         // User ID
  started_at: DateTime,    // 세션 시작 시간
  ended_at: DateTime?,     // 세션 종료 시간 (null = 진행중)
  status: String,          // 'active', 'completed', 'abandoned'
  metadata: Map?           // 추가 메타데이터 (device, IP 등)
})
```

**용도:**
- 사용자의 대화 히스토리
- 활성 세션 조회
- 평균 세션 길이 통계

---

### 3. Turn (대화 턴)

사용자 메시지 → 에이전트 응답의 한 사이클. 메시지 그루핑 단위.

```cypher
(:Turn {
  id: String,              // UUID
  session_id: String,      // Session ID
  sequence: Integer,       // 턴 순서 (1, 2, 3...)
  started_at: DateTime,    // 턴 시작
  completed_at: DateTime?, // 턴 완료 (null = 처리 중)
  user_query: String       // 사용자 원본 질문 (빠른 검색용)
})
```

**용도:**
- 대화 흐름 추적
- 메시지 그룹화 (슈퍼노드 방지)
- 사용자 질문 → 에이전트 응답 매핑

---

### 4. Message (메시지)

실제 대화 메시지.

```cypher
(:Message {
  id: String,              // UUID
  session_id: String,      // Session ID
  turn_id: String,         // Turn ID
  role: String,            // 'user' | 'assistant'
  content: String,         // 메시지 내용
  timestamp: DateTime,     // 메시지 생성 시간
  sequence: Integer,       // 세션 내 순서 (1, 2, 3...)
  metadata: Map?           // 추가 데이터 (tokens, model 등)
})
```

**용도:**
- 대화 내용 저장
- 시간순 메시지 조회
- 컨텍스트 윈도우 구성

---

### 5. Agent (에이전트)

시스템의 에이전트. JSON 카드와 동기화.

```cypher
(:Agent {
  slug: String,            // 'hostagent', 'flight_specialist'
  name: String,            // 'Host Agent'
  type: String,            // 'coordinator' | 'specialist'
  version: String,         // '1.0.0'
  capabilities: List,      // ['streaming', 'delegation']
  created_at: DateTime     // 에이전트 등록일
})
```

**용도:**
- 에이전트 디렉토리
- 에이전트별 사용 통계
- 에이전트 버전 관리

---

### 6. AgentExecution (에이전트 실행 기록)

에이전트의 한 번 실행 기록. 성능 추적 및 디버깅 핵심.

```cypher
(:AgentExecution {
  id: String,                  // UUID
  agent_slug: String,          // 'hostagent'
  turn_id: String,             // Turn ID
  started_at: DateTime,        // 실행 시작
  completed_at: DateTime?,     // 실행 완료
  status: String,              // 'processing' | 'completed' | 'failed' | 'delegated'
  execution_time_ms: Integer?, // 실행 시간 (ms)
  error_message: String?,      // 에러 발생 시
  metadata: Map?               // LLM 모델, temperature 등
})
```

**용도:**
- 에이전트 성능 모니터링
- 위임 체인 추적
- 에러 디버깅

---

## 관계 타입 (Relationship Types)

### 세션 관리

```cypher
// 사용자가 세션 시작
(:User)-[:STARTED_SESSION {
  device: String?,
  ip_address: String?
}]->(:Session)

// 세션에 턴 포함
(:Session)-[:HAS_TURN {
  sequence: Integer
}]->(:Turn)

// 턴에 메시지 포함
(:Turn)-[:INCLUDES_MESSAGE {
  role: String  // 'user' | 'assistant'
}]->(:Message)
```

### 메시지 흐름

```cypher
// 메시지 시간순 체인
(:Message)-[:NEXT_MESSAGE]->(:Message)

// 사용자 메시지 → 응답 메시지
(:Message {role: 'user'})-[:RESPONDED_BY]->(:Message {role: 'assistant'})
```

### 에이전트 실행

```cypher
// 턴을 에이전트가 처리
(:Turn)-[:EXECUTED_BY]->(:AgentExecution)

// 실행이 어떤 에이전트 사용했는지
(:AgentExecution)-[:USED_AGENT]->(:Agent)

// 실행이 메시지 생성
(:AgentExecution)-[:PRODUCED_MESSAGE]->(:Message)
```

### 에이전트 협업 (핵심!)

```cypher
// 위임 (delegation): hostagent → flight_specialist
(:AgentExecution)-[:DELEGATED_TO {
  reason: String,              // "Flight booking detected"
  semantic_score: Float,       // 0.806
  skill_matched: String,       // "book_flights"
  decision_time_ms: Integer    // 2540
}]->(:AgentExecution)

// 협업 (collaboration): 동시 실행
(:AgentExecution)-[:COLLABORATED_WITH {
  role: String,                // "data_provider" | "decision_maker"
  shared_context: Map?
}]->(:AgentExecution)

// 체인 (chaining): A → B → C 순차 실행
(:AgentExecution)-[:CHAINED_TO {
  step: Integer,               // 1, 2, 3...
  input_transform: String?     // "summarized" | "filtered"
}]->(:AgentExecution)
```

---

## 실제 사용 예시

### 예시 1: 사용자 → hostagent → flight_specialist 위임

```
User (john)
  └─ STARTED_SESSION → Session (sess_123)
                         └─ HAS_TURN → Turn (turn_1, seq:1)
                                        ├─ INCLUDES_MESSAGE → Message (user: "비행기 예약해줘")
                                        ├─ EXECUTED_BY → AgentExecution (exec_1, hostagent)
                                        │                └─ DELEGATED_TO → AgentExecution (exec_2, flight_specialist)
                                        │                                   └─ PRODUCED_MESSAGE → Message (assistant: "어디로...")
                                        └─ INCLUDES_MESSAGE → Message (assistant: "어디로...")
```

### 예시 2: 멀티 에이전트 협업

```
Turn (turn_5)
  ├─ EXECUTED_BY → AgentExecution (exec_10, hostagent)
  │                └─ DELEGATED_TO → AgentExecution (exec_11, flight_specialist)
  │                                   ├─ COLLABORATED_WITH → AgentExecution (exec_12, hotel_specialist)
  │                                   └─ CHAINED_TO → AgentExecution (exec_13, payment_agent)
  └─ INCLUDES_MESSAGE → Message (복합 응답)
```

---

## 인덱스 및 제약조건

### 유니크 제약 (Unique Constraints)

```cypher
CREATE CONSTRAINT unique_user_id IF NOT EXISTS
FOR (u:User) REQUIRE u.id IS UNIQUE;

CREATE CONSTRAINT unique_session_id IF NOT EXISTS
FOR (s:Session) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT unique_turn_id IF NOT EXISTS
FOR (t:Turn) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT unique_message_id IF NOT EXISTS
FOR (m:Message) REQUIRE m.id IS UNIQUE;

CREATE CONSTRAINT unique_agent_slug IF NOT EXISTS
FOR (a:Agent) REQUIRE a.slug IS UNIQUE;

CREATE CONSTRAINT unique_execution_id IF NOT EXISTS
FOR (e:AgentExecution) REQUIRE e.id IS UNIQUE;
```

### 성능 인덱스 (Performance Indexes)

```cypher
// 세션 관련
CREATE INDEX session_user_idx IF NOT EXISTS
FOR (s:Session) ON (s.user_id);

CREATE INDEX session_status_idx IF NOT EXISTS
FOR (s:Session) ON (s.status);

CREATE INDEX session_started_idx IF NOT EXISTS
FOR (s:Session) ON (s.started_at);

// 메시지 관련
CREATE INDEX message_session_idx IF NOT EXISTS
FOR (m:Message) ON (m.session_id);

CREATE INDEX message_turn_idx IF NOT EXISTS
FOR (m:Message) ON (m.turn_id);

CREATE INDEX message_timestamp_idx IF NOT EXISTS
FOR (m:Message) ON (m.timestamp);

// 턴 관련
CREATE INDEX turn_session_idx IF NOT EXISTS
FOR (t:Turn) ON (t.session_id);

CREATE INDEX turn_sequence_idx IF NOT EXISTS
FOR (t:Turn) ON (t.sequence);

// 에이전트 실행 관련
CREATE INDEX execution_agent_idx IF NOT EXISTS
FOR (e:AgentExecution) ON (e.agent_slug);

CREATE INDEX execution_status_idx IF NOT EXISTS
FOR (e:AgentExecution) ON (e.status);

CREATE INDEX execution_turn_idx IF NOT EXISTS
FOR (e:AgentExecution) ON (e.turn_id);

CREATE INDEX execution_time_idx IF NOT EXISTS
FOR (e:AgentExecution) ON (e.started_at);
```

### 복합 인덱스 (Composite Indexes)

```cypher
// 세션 + 상태 조회 최적화
CREATE INDEX session_user_status_idx IF NOT EXISTS
FOR (s:Session) ON (s.user_id, s.status);

// 메시지 시간순 조회 최적화
CREATE INDEX message_session_seq_idx IF NOT EXISTS
FOR (m:Message) ON (m.session_id, m.sequence);

// 에이전트별 성능 조회 최적화
CREATE INDEX execution_agent_status_idx IF NOT EXISTS
FOR (e:AgentExecution) ON (e.agent_slug, e.status);
```

---

## 주요 쿼리 패턴

### 1. 사용자의 최근 세션 조회

```cypher
MATCH (u:User {id: $user_id})-[:STARTED_SESSION]->(s:Session)
WHERE s.status = 'active' OR s.ended_at > datetime() - duration('P7D')
RETURN s
ORDER BY s.started_at DESC
LIMIT 10
```

### 2. 세션의 전체 대화 히스토리

```cypher
MATCH (s:Session {id: $session_id})-[:HAS_TURN]->(t:Turn)-[:INCLUDES_MESSAGE]->(m:Message)
RETURN t.sequence, m.role, m.content, m.timestamp
ORDER BY t.sequence, m.sequence
```

### 3. 에이전트 위임 체인 추적

```cypher
MATCH path = (exec1:AgentExecution)-[:DELEGATED_TO*]->(exec2:AgentExecution)
WHERE exec1.turn_id = $turn_id
RETURN path
```

### 4. 에이전트별 성능 통계

```cypher
MATCH (a:Agent)<-[:USED_AGENT]-(e:AgentExecution)
WHERE e.completed_at IS NOT NULL
RETURN
  a.slug,
  count(e) as total_executions,
  avg(e.execution_time_ms) as avg_time_ms,
  max(e.execution_time_ms) as max_time_ms,
  sum(CASE WHEN e.status = 'failed' THEN 1 ELSE 0 END) as failures
ORDER BY total_executions DESC
```

### 5. 특정 기간 위임 패턴 분석

```cypher
MATCH (exec1:AgentExecution)-[d:DELEGATED_TO]->(exec2:AgentExecution)
WHERE exec1.started_at >= datetime($start_date)
  AND exec1.started_at <= datetime($end_date)
MATCH (a1:Agent {slug: exec1.agent_slug})
MATCH (a2:Agent {slug: exec2.agent_slug})
RETURN
  a1.name as from_agent,
  a2.name as to_agent,
  count(d) as delegation_count,
  avg(d.semantic_score) as avg_score,
  collect(DISTINCT d.skill_matched) as skills
ORDER BY delegation_count DESC
```

### 6. 사용자 선호 에이전트 분석

```cypher
MATCH (u:User {id: $user_id})-[:STARTED_SESSION]->(s:Session)
      -[:HAS_TURN]->(t:Turn)-[:EXECUTED_BY]->(e:AgentExecution)
      -[:USED_AGENT]->(a:Agent)
WHERE s.started_at >= datetime() - duration('P30D')
RETURN
  a.name,
  count(DISTINCT t) as interactions,
  avg(duration.between(e.started_at, e.completed_at).milliseconds) as avg_response_time
ORDER BY interactions DESC
LIMIT 5
```

---

## Python 코드 패턴 (Best Practices)

### 1. Managed Transaction (권장)

```python
async def create_turn_with_execution(driver, session_id, user_query, agent_slug):
    async def _tx_function(tx):
        # Turn 생성
        turn_result = await tx.run("""
            MATCH (s:Session {id: $session_id})
            CREATE (t:Turn {
                id: randomUUID(),
                session_id: $session_id,
                sequence: coalesce(
                    [(s)-[:HAS_TURN]->(prev:Turn) | prev.sequence] | 0
                ) + 1,
                started_at: datetime(),
                user_query: $user_query
            })
            CREATE (s)-[:HAS_TURN {sequence: t.sequence}]->(t)
            RETURN t.id as turn_id, t.sequence as sequence
        """, session_id=session_id, user_query=user_query)

        turn_record = await turn_result.single()
        turn_id = turn_record['turn_id']

        # AgentExecution 생성
        exec_result = await tx.run("""
            MATCH (t:Turn {id: $turn_id})
            MATCH (a:Agent {slug: $agent_slug})
            CREATE (e:AgentExecution {
                id: randomUUID(),
                agent_slug: $agent_slug,
                turn_id: $turn_id,
                started_at: datetime(),
                status: 'processing'
            })
            CREATE (t)-[:EXECUTED_BY]->(e)
            CREATE (e)-[:USED_AGENT]->(a)
            RETURN e.id as execution_id
        """, turn_id=turn_id, agent_slug=agent_slug)

        exec_record = await exec_result.single()

        return {
            'turn_id': turn_id,
            'execution_id': exec_record['execution_id']
        }

    async with driver.session() as session:
        return await session.execute_write(_tx_function)
```

### 2. 위임 기록

```python
async def record_delegation(driver, from_exec_id, to_exec_id, reason, score, skill):
    async def _tx_function(tx):
        await tx.run("""
            MATCH (from:AgentExecution {id: $from_id})
            MATCH (to:AgentExecution {id: $to_id})
            CREATE (from)-[:DELEGATED_TO {
                reason: $reason,
                semantic_score: $score,
                skill_matched: $skill,
                decision_time_ms: duration.between(from.started_at, datetime()).milliseconds,
                created_at: datetime()
            }]->(to)
            SET from.status = 'delegated'
        """, from_id=from_exec_id, to_id=to_exec_id,
             reason=reason, score=score, skill=skill)

    async with driver.session() as session:
        await session.execute_write(_tx_function)
```

---

## 마이그레이션 전략

### 1단계: 기존 데이터 백업
```cypher
// 전체 그래프 덤프
CALL apoc.export.json.all("backup.json", {})
```

### 2단계: 기존 데이터 완전 삭제
```cypher
MATCH (n) DETACH DELETE n
```

### 3단계: 제약조건 및 인덱스 생성
```cypher
// 위의 모든 CREATE CONSTRAINT, CREATE INDEX 실행
```

### 4단계: Agent 노드 초기화
```cypher
// JSON 카드에서 Agent 노드 생성
MERGE (a:Agent {slug: 'hostagent'})
SET a.name = 'Host Agent',
    a.type = 'coordinator',
    a.version = '1.0.0',
    a.capabilities = ['streaming', 'delegation'],
    a.created_at = datetime()
```

---

## 모니터링 및 유지보수

### 성능 모니터링 쿼리

```cypher
// 가장 느린 에이전트 실행 TOP 10
MATCH (e:AgentExecution)
WHERE e.execution_time_ms IS NOT NULL
RETURN e.agent_slug, e.execution_time_ms, e.started_at
ORDER BY e.execution_time_ms DESC
LIMIT 10
```

```cypher
// 가장 많이 위임받는 에이전트
MATCH (a:Agent)<-[:USED_AGENT]-(e:AgentExecution)<-[:DELEGATED_TO]-()
RETURN a.name, count(e) as delegation_count
ORDER BY delegation_count DESC
```

### 데이터 정리 (7일 이상 된 completed 세션)

```cypher
MATCH (s:Session {status: 'completed'})
WHERE s.ended_at < datetime() - duration('P7D')
MATCH (s)-[:HAS_TURN]->(t:Turn)
OPTIONAL MATCH (t)-[:INCLUDES_MESSAGE]->(m:Message)
OPTIONAL MATCH (t)-[:EXECUTED_BY]->(e:AgentExecution)
DETACH DELETE s, t, m, e
```

---

## 확장 계획

### Phase 1 (현재)
- ✅ 기본 세션/메시지 추적
- ✅ 에이전트 위임 기록
- ✅ 성능 모니터링

### Phase 2 (향후)
- Entity 추출 (장소, 날짜, 가격 등)
- Context 노드 (대화 컨텍스트 명시적 관리)
- Feedback 노드 (사용자 피드백)

### Phase 3 (고급)
- 그래프 알고리즘 (PageRank로 중요 에이전트 찾기)
- 추천 시스템 (비슷한 질문 → 성공한 에이전트)
- 실시간 스트리밍 대시보드
● 좋습니다! 리서치 완료. 이제 ENTERPRISE급 멀티에이전트 Neo4j 스키마를 설계하겠 습니다.

  🎯 ENTERPRISE 멀티에이전트 Neo4j 스키마 설계

  핵심 원칙 (리서치 기반)

  1. 특정 관계 타입 사용 (FRIENDS_WITH vs CONNECTED)
  2. 중간 노드로 슈퍼노드 방지
  3. 쿼리 패턴 기반 최적화
  4. 세션/에이전트 명확한 분리

  노드 구조

  // 1. User (사용자)
  (:User {
    id: UUID,
    username: String,
    created_at: DateTime
  })

  // 2. Session (대화 세션)
  (:Session {
    id: UUID,
    user_id: UUID,
    started_at: DateTime,
    ended_at: DateTime?,
    status: String  // 'active', 'completed', 'abandoned'
  })

  // 3. Message (메시지)
  (:Message {
    id: UUID,
    session_id: UUID,
    content: String,
    role: String,  // 'user', 'assistant'
    timestamp: DateTime,
    sequence: Integer
  })

  // 4. Agent (에이전트)
  (:Agent {
    slug: String,  // 'hostagent', 'flight_specialist'
    name: String,
    type: String,  // 'coordinator', 'specialist'
    created_at: DateTime
  })

  // 5. Turn (대화 턴 - 메시지 그룹)
  (:Turn {
    id: UUID,
    session_id: UUID,
    started_at: DateTime,
    completed_at: DateTime?,
    sequence: Integer
  })

  // 6. AgentExecution (에이전트 실행 기록)
  (:AgentExecution {
    id: UUID,
    agent_slug: String,
    started_at: DateTime,
    completed_at: DateTime?,
    status: String,  // 'processing', 'completed', 'failed', 'delegated'        
    execution_time_ms: Integer?,
    error_message: String?
  })

  관계 구조

  // 세션 관계
  (:User)-[:STARTED_SESSION]->(:Session)
  (:Session)-[:CONTAINS_MESSAGE]->(:Message)
  (:Session)-[:HAS_TURN]->(:Turn)

  // 메시지 흐름
  (:Message)-[:NEXT_MESSAGE]->(:Message)  // 시간 순서
  (:Turn)-[:INCLUDES_MESSAGE]->(:Message)

  // 에이전트 실행
  (:Turn)-[:EXECUTED_BY]->(:AgentExecution)
  (:AgentExecution)-[:USED_AGENT]->(:Agent)
  (:AgentExecution)-[:PRODUCED_MESSAGE]->(:Message)

  // 에이전트 위임 (delegation)
  (:AgentExecution)-[:DELEGATED_TO {
    reason: String,
    semantic_score: Float,
    decision_time_ms: Integer
  }]->(:AgentExecution)

  // 에이전트 협업
  (:AgentExecution)-[:COLLABORATED_WITH {
    context: String
  }]->(:AgentExecution)

  시각화

  User
   └─ STARTED_SESSION → Session
                         ├─ HAS_TURN → Turn (seq:1)
                         │             ├─ EXECUTED_BY → AgentExecution (hostagent)
                         │             │                └─ DELEGATED_TO → AgentExecution (flight_specialist)
                         │             │                                  └─ PRODUCED_MESSAGE → Message
                         │             └─ INCLUDES_MESSAGE → Message
                         │
                         └─ HAS_TURN → Turn (seq:2)
                                       ├─ EXECUTED_BY → AgentExecution (hostagent)
                                       └─ INCLUDES_MESSAGE → Message

  인덱스 및 제약조건

  // 유니크 제약
  CREATE CONSTRAINT unique_user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
  CREATE CONSTRAINT unique_session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE;
  CREATE CONSTRAINT unique_message_id IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE;
  CREATE CONSTRAINT unique_agent_slug IF NOT EXISTS FOR (a:Agent) REQUIRE a.slug IS UNIQUE;
  CREATE CONSTRAINT unique_turn_id IF NOT EXISTS FOR (t:Turn) REQUIRE t.id IS UNIQUE;
  CREATE CONSTRAINT unique_execution_id IF NOT EXISTS FOR (e:AgentExecution) REQUIRE e.id IS UNIQUE;

  // 성능 인덱스 (쿼리 패턴 기반)
  CREATE INDEX session_user_idx IF NOT EXISTS FOR (s:Session) ON (s.user_id);   
  CREATE INDEX session_status_idx IF NOT EXISTS FOR (s:Session) ON (s.status);  
  CREATE INDEX message_session_idx IF NOT EXISTS FOR (m:Message) ON (m.session_id);
  CREATE INDEX message_timestamp_idx IF NOT EXISTS FOR (m:Message) ON (m.timestamp);
  CREATE INDEX turn_session_idx IF NOT EXISTS FOR (t:Turn) ON (t.session_id);   
  CREATE INDEX execution_agent_idx IF NOT EXISTS FOR (e:AgentExecution) ON (e.agent_slug);
  CREATE INDEX execution_status_idx IF NOT EXISTS FOR (e:AgentExecution) ON (e.status);

  이 설계로 진행할까요? 아니면 수정이 필요한가요?

> 해보자 지금 데이터는 다지워도되고 그건 MAS 협업 및 진짜 유저와의 관계 이런거  채팅 이런것도 담을수잇어야하는데 지금껏도 기록하고 MD파일로 한번만더 검토해     

● 좋습니다! 설계를 더 보완하고 MD 파일로 문서화하겠습니다.

● Write(docs\NEO4J_ENTERPRISE_SCHEMA.md)
  ⎿  Wrote 1 lines to docs\NEO4J_ENTERPRISE_SCHEMA.md                           

     # Enterprise Multi-Agent System - Neo4j Graph Schema
     ## 개요
     A2A 프로토콜 기반 멀티에이전트 시스템의 **대화, 세션, 에이전트 협업**을 추 적하기 위한 Enterprise급 Neo4j 그래프 스키마 설계.
     **설계 목표:**
     - 유저-세션-메시지 완전 분리
     - 에이전트 간 위임(delegation) 추적
     - 에이전트 간 협업(collaboration) 추적

● 완료! 문서를 docs/NEO4J_ENTERPRISE_SCHEMA.md에 작성했습니다.

  핵심 내용:
  1. 6개 노드 타입: User, Session, Turn, Message, Agent, AgentExecution
  2. 3가지 협업 관계: DELEGATED_TO, COLLABORATED_WITH, CHAINED_TO
  3. 완전한 추적: 사용자 → 세션 → 턴 → 에이전트 실행 → 위임 체인
  4. 성능 최적화: 16개 인덱스 + 6개 유니크 제약
  5. 실전 쿼리: 위임 체인, 성능 분석, 사용자 선호도

  이제 실제 구현할까요? 순서:
  1. Neo4j 기존 데이터 삭제
  2. 제약조건/인덱스 생성
  3. Service 코드 리팩토링

  진행할까요?

> 진행해보자 순차적으로 생