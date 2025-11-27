# Neo4j 재시작 및 APOC Trigger 설치 가이드

  $env:JAVA_HOME = "C:\Users\SOGANG1\.Neo4jDesktop2\Cache\runtime\zulu21.44.17-ca-jdk21.0.8-win_x64"                                                              

  .\bin\neo4j-admin.bat server unbind
## 현재 상태
✅ apoc.conf 파일 생성 완료 (apoc.trigger.enabled=true)
✅ neo4j.conf 수정 완료 (클러스터 모드 비활성화)
⏳ Neo4j 재시작 필요

## 수정된 설정

### 1. apoc.conf
위치: `C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-47eae030-7034-4425-866b-64e1d6da81f2\conf\apoc.conf`
```conf
apoc.trigger.enabled=true
apoc.trigger.refresh=60000
```

### 2. neo4j.conf
위치: `C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-47eae030-7034-4425-866b-64e1d6da81f2\conf\neo4j.conf`

Line 297:
```conf
initial.server.mode_constraint=NONE
```

Line 357:
```conf
dbms.routing.enabled=false
```

## 재시작 후 확인사항

### 1. Neo4j Desktop에서 데이터베이스 재시작
1. Neo4j Desktop 열기
2. 해당 DBMS 중지 (Stop)
3. 3초 대기
4. 해당 DBMS 시작 (Start)

### 2. Neo4j Browser에서 데이터베이스 선택
```cypher
:use neo4j
```

### 3. APOC 트리거 활성화 확인
```cypher
RETURN apoc.version();
```

예상 결과: `"2025.09.0"`

### 4. APOC Trigger 5개 설치

재시작 후 다음 쿼리를 **순서대로** 실행하세요:

#### Trigger 1: conversation_created
```cypher
CALL apoc.trigger.install(
  'neo4j',
  'conversation_created_trigger',
  'UNWIND $createdNodes AS node
   WITH node WHERE "Conversation" IN labels(node)
   WITH node, toString(id(node)) AS nodeId
   CALL apoc.export.json.query(
     "MATCH (c:Conversation) WHERE id(c) = $nodeId RETURN c",
     null,
     {params: {nodeId: toInteger(nodeId)}, stream: true}
   ) YIELD value
   WITH value
   CALL apoc.custom.asMap(value) YIELD value AS jsonMap
   WITH {event: "conversation_created", data: jsonMap} AS payload
   CALL apoc.load.jsonParams(
     "http://localhost:8002/api/neo4j-events/",
     {method: "POST", `Content-Type`: "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);
```

#### Trigger 2: message_created
```cypher
CALL apoc.trigger.install(
  'neo4j',
  'message_created_trigger',
  'UNWIND $createdNodes AS node
   WITH node WHERE "Message" IN labels(node)
   WITH node, toString(id(node)) AS nodeId
   CALL apoc.export.json.query(
     "MATCH (m:Message) WHERE id(m) = $nodeId RETURN m",
     null,
     {params: {nodeId: toInteger(nodeId)}, stream: true}
   ) YIELD value
   WITH value
   CALL apoc.custom.asMap(value) YIELD value AS jsonMap
   WITH {event: "message_created", data: jsonMap} AS payload
   CALL apoc.load.jsonParams(
     "http://localhost:8002/api/neo4j-events/",
     {method: "POST", `Content-Type`: "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);
```

#### Trigger 3: turn_created
```cypher
CALL apoc.trigger.install(
  'neo4j',
  'turn_created_trigger',
  'UNWIND $createdNodes AS node
   WITH node WHERE "Turn" IN labels(node)
   WITH node, toString(id(node)) AS nodeId
   CALL apoc.export.json.query(
     "MATCH (t:Turn) WHERE id(t) = $nodeId RETURN t",
     null,
     {params: {nodeId: toInteger(nodeId)}, stream: true}
   ) YIELD value
   WITH value
   CALL apoc.custom.asMap(value) YIELD value AS jsonMap
   WITH {event: "turn_created", data: jsonMap} AS payload
   CALL apoc.load.jsonParams(
     "http://localhost:8002/api/neo4j-events/",
     {method: "POST", `Content-Type`: "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);
```

#### Trigger 4: agent_execution_created
```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agent_execution_created_trigger',
  'UNWIND $createdNodes AS node
   WITH node WHERE "AgentExecution" IN labels(node)
   WITH node, toString(id(node)) AS nodeId
   CALL apoc.export.json.query(
     "MATCH (ae:AgentExecution) WHERE id(ae) = $nodeId RETURN ae",
     null,
     {params: {nodeId: toInteger(nodeId)}, stream: true}
   ) YIELD value
   WITH value
   CALL apoc.custom.asMap(value) YIELD value AS jsonMap
   WITH {event: "agent_execution_created", data: jsonMap} AS payload
   CALL apoc.load.jsonParams(
     "http://localhost:8002/api/neo4j-events/",
     {method: "POST", `Content-Type`: "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);
```

#### Trigger 5: agent_execution_completed
```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agent_execution_completed_trigger',
  'UNWIND $assignedNodeProperties AS nodeProps
   WITH nodeProps.node AS node WHERE "AgentExecution" IN labels(node) AND nodeProps.key = "status" AND nodeProps.new = "completed"
   WITH node, toString(id(node)) AS nodeId
   CALL apoc.export.json.query(
     "MATCH (ae:AgentExecution) WHERE id(ae) = $nodeId RETURN ae",
     null,
     {params: {nodeId: toInteger(nodeId)}, stream: true}
   ) YIELD value
   WITH value
   CALL apoc.custom.asMap(value) YIELD value AS jsonMap
   WITH {event: "agent_execution_completed", data: jsonMap} AS payload
   CALL apoc.load.jsonParams(
     "http://localhost:8002/api/neo4j-events/",
     {method: "POST", `Content-Type`: "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);
```

### 5. 설치 확인
```cypher
 :use neo4j
CALL apoc.trigger.list();
```

예상 결과: 5개의 트리거가 모두 나타나야 함
- conversation_created_trigger
- message_created_trigger
- turn_created_trigger
- agent_execution_created_trigger
- agent_execution_completed_trigger

## 문제 해결

### FOLLOWER 오류가 계속 발생하는 경우
로그 파일 확인:
```
C:\Users\SOGANG1\.Neo4jDesktop2\Data\dbmss\dbms-47eae030-7034-4425-866b-64e1d6da81f2\logs\neo4j.log
```

"Resolved endpoints" 메시지에서 localhost:6000이 보이지 않아야 함.

### APOC Trigger 오류가 계속 발생하는 경우
1. Neo4j 완전히 중지
2. 5초 대기
3. Neo4j 재시작
4. `:use neo4j` 실행
5. 다시 트리거 설치 시도




  1. Neo4j Browser에서 테스트 노드 생성:
  :use neo4j

  CREATE (c:Conversation {
    conversation_id: 'test_' + toString(timestamp()),
    session_id: 'test_session',
    created_at: datetime()
  })
  RETURN c;

  이 쿼리를 실행하면:
  1. ✅ APOC Trigger가 자동으로 http://localhost:8002/api/neo4j-events/에 POST 요청
  2. ✅ Django가 Kafka에 neo4j_events 토픽으로 메시지 발행
  3. ✅ Kafka listener가 WebSocket으로 브로드캐스트

  확인 방법

  Python 스크립트나 브라우저 콘솔에서 WebSocket 연결하여 실시간 메시지 확인:
  import websocket
  import json

  ws = websocket.create_connection("ws://localhost:8002/ws/neo4j-events/")
  print("Connected! Waiting for messages...")
  while True:
      result = ws.recv()
      print("Received:", json.loads(result))

  테스트 노드를 생성하면 WebSocket으로 다음과 같은 메시지가 수신되어야 합니다:
  {
    "event": "conversation_created",
    "data": {
      "c": {
        "conversation_id": "test_...",
        "session_id": "test_session",
        "created_at": "..."                                                                                 
      }
    }
  }

  Neo4j Browser에서 테스트 노드를 생성해보세요!