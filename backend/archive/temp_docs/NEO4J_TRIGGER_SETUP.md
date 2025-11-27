# Neo4j APOC Trigger 설정 가이드

## 1. Neo4j 설정 파일 수정

### 설정 파일 위치 찾기

**Windows:**
```
C:\Users\<사용자명>\.Neo4jDesktop\relate-data\dbmss\<dbms-id>\conf\neo4j.conf
```

**Neo4j Desktop 사용 시:**
1. Neo4j Desktop 열기
2. 해당 DBMS 선택
3. "..." 메뉴 → "Open Folder" → "Configuration" 클릭
4. `neo4j.conf` 파일 열기

### 추가할 설정

`neo4j.conf` 파일 끝에 다음 라인 추가:

```properties
# APOC Trigger 활성화
apoc.trigger.enabled=true
apoc.trigger.refresh=60000

# APOC 프로시저 권한 설정
dbms.security.procedures.unrestricted=apoc.*
dbms.security.procedures.allowlist=apoc.*

# HTTP 클라이언트 활성화 (apoc.load.jsonParams 사용)
apoc.import.file.enabled=true
```

## 2. Neo4j 재시작

**Neo4j Desktop:**
1. DBMS 선택
2. "Stop" 버튼 클릭
3. 완전히 중지될 때까지 대기 (약 5-10초)
4. "Start" 버튼 클릭

**명령줄:**
```bash
# 중지
neo4j stop

# 시작
neo4j start
```

## 3. APOC Trigger 등록

Neo4j Browser에서 다음 Cypher 쿼리 실행:

### 3.1 Conversation 생성 트리거

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'conversationCreatedTrigger',
  "
  UNWIND $createdNodes AS node
  WITH node WHERE 'Conversation' IN labels(node)
  CALL apoc.load.jsonParams(
    'http://localhost:8002/api/neo4j-event',
    {
      `Content-Type`: 'application/json'
    },
    apoc.convert.toJson({
      type: 'conversation_created',
      data: {
        conversation_id: node.conversation_id,
        session_id: node.session_id,
        user_id: node.user_id,
        created_at: toString(node.created_at)
      }
    })
  )
  YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

### 3.2 Message 생성 트리거

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'messageCreatedTrigger',
  "
  UNWIND $createdNodes AS node
  WITH node WHERE 'Message' IN labels(node)
  CALL apoc.load.jsonParams(
    'http://localhost:8002/api/neo4j-event',
    {
      `Content-Type`: 'application/json'
    },
    apoc.convert.toJson({
      type: 'message_created',
      data: {
        message_id: node.message_id,
        conversation_id: node.conversation_id,
        role: node.role,
        content: node.content,
        timestamp: toString(node.timestamp)
      }
    })
  )
  YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

### 3.3 Turn 생성 트리거

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'turnCreatedTrigger',
  "
  UNWIND $createdNodes AS node
  WITH node WHERE 'Turn' IN labels(node)
  CALL apoc.load.jsonParams(
    'http://localhost:8002/api/neo4j-event',
    {
      `Content-Type`: 'application/json'
    },
    apoc.convert.toJson({
      type: 'turn_created',
      data: {
        turn_id: node.turn_id,
        turn_number: node.turn_number,
        conversation_id: node.conversation_id,
        timestamp: toString(node.timestamp)
      }
    })
  )
  YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

### 3.4 AgentExecution 생성 트리거

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agentExecutionCreatedTrigger',
  "
  UNWIND $createdNodes AS node
  WITH node WHERE 'AgentExecution' IN labels(node)
  CALL apoc.load.jsonParams(
    'http://localhost:8002/api/neo4j-event',
    {
      `Content-Type`: 'application/json'
    },
    apoc.convert.toJson({
      type: 'agent_execution_created',
      data: {
        execution_id: node.execution_id,
        agent_name: node.agent_name,
        turn_id: node.turn_id,
        status: node.status,
        started_at: toString(node.started_at)
      }
    })
  )
  YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

### 3.5 AgentExecution 완료 트리거

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agentExecutionCompletedTrigger',
  "
  UNWIND $assignedNodeProperties AS props
  WITH props WHERE 'AgentExecution' IN labels(props.node) AND props.key = 'status' AND props.new = 'completed'
  CALL apoc.load.jsonParams(
    'http://localhost:8002/api/neo4j-event',
    {
      `Content-Type`: 'application/json'
    },
    apoc.convert.toJson({
      type: 'agent_execution_completed',
      data: {
        execution_id: props.node.execution_id,
        agent_name: props.node.agent_name,
        completed_at: toString(props.node.completed_at),
        result: props.node.result
      }
    })
  )
  YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

## 4. 트리거 확인

등록된 트리거 목록 확인:

```cypher
CALL apoc.trigger.list() YIELD name, query, paused;
```

특정 트리거 삭제 (필요시):

```cypher
CALL apoc.trigger.remove('neo4j', 'conversationCreatedTrigger');
```

모든 트리거 삭제 (필요시):

```cypher
CALL apoc.trigger.removeAll('neo4j');
```

## 5. 테스트

간단한 Conversation 노드 생성으로 테스트:

```cypher
CREATE (c:Conversation {
  conversation_id: 'test_' + randomUUID(),
  session_id: 'session_test',
  user_id: 'user_test',
  created_at: datetime()
})
RETURN c;
```

**확인 사항:**
1. Django 로그에서 `Received and published Neo4j event: conversation_created` 메시지 확인
2. Kafka 토픽에 이벤트가 발행되었는지 확인
3. WebSocket을 통해 프론트엔드에 이벤트가 전달되는지 확인

## 6. 트러블슈팅

### 트리거가 작동하지 않는 경우

1. **Neo4j 로그 확인:**
   ```
   # Neo4j Desktop: "..." → "Logs" → "Neo4j Logs"
   ```

2. **APOC 설정 확인:**
   ```cypher
   CALL dbms.listConfig()
   YIELD name, value
   WHERE name STARTS WITH 'apoc'
   RETURN name, value;
   ```

3. **Django 서버 실행 확인:**
   - `http://localhost:8002/api/neo4j-event` 엔드포인트가 실행 중인지 확인
   - Daphne 서버가 8002 포트에서 실행 중인지 확인

4. **네트워크 연결 확인:**
   ```bash
   curl -X POST http://localhost:8002/api/neo4j-event \
     -H "Content-Type: application/json" \
     -d '{"type": "test", "data": {}}'
   ```

5. **Kafka 확인:**
   ```bash
   # Kafka 실행 중인지 확인
   docker ps | grep kafka
   ```

## 7. 다음 단계

트리거 설정 후:
1. WebSocket Consumer에 `neo4j_event` 핸들러 추가
2. 프론트엔드에서 WebSocket 연결 및 이벤트 수신 구현
3. End-to-end 테스트 수행
