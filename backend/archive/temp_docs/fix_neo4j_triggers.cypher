// Neo4j Browser에서 실행: 트리거 재설치 스크립트

// ============================================
// 1단계: 기존 트리거 전부 삭제
// :use neo4j 실행 후 아래 명령 실행
// ============================================
CALL apoc.trigger.remove('conversation_created_trigger');
CALL apoc.trigger.remove('message_created_trigger');
CALL apoc.trigger.remove('turn_created_trigger');
CALL apoc.trigger.remove('agent_execution_created_trigger');
CALL apoc.trigger.remove('agent_execution_completed_trigger');

// ============================================
// 2단계: 올바른 문법으로 트리거 재설치
// :use system 실행 후 아래 명령들을 하나씩 실행
// ============================================

// Trigger 1: conversation_created
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
     {method: "POST", "Content-Type": "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);

// Trigger 2: message_created
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
     {method: "POST", "Content-Type": "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);

// Trigger 3: turn_created
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
     {method: "POST", "Content-Type": "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);

// Trigger 4: agent_execution_created
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
     {method: "POST", "Content-Type": "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);

// Trigger 5: agent_execution_completed
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
     {method: "POST", "Content-Type": "application/json"},
     apoc.convert.toJson(payload)
   ) YIELD value
   RETURN value',
  {phase: 'after'}
);

// ============================================
// 3단계: 설치 확인
// ============================================
// :use neo4j
// CALL apoc.trigger.list();

// ============================================
// 실행 순서 요약
// ============================================
// 1. :use neo4j
// 2. CALL apoc.trigger.remove(...) 5개 실행
// 3. :use system
// 4. CALL apoc.trigger.install(...) 5개 실행 (하나씩!)
// 5. :use neo4j
// 6. CALL apoc.trigger.list(); (확인)






  CALL apoc.trigger.install(
    'neo4j',
    'conversation_created_trigger',
    'UNWIND $createdNodes AS node
     WITH node WHERE "Conversation" IN labels(node)
     WITH node, toString(id(node)) AS nodeId
     CALL apoc.export.json.query(
       "MATCH (c:Conversation) WHERE id(c) = $nodeId
  RETURN c",
       null,
       {params: {nodeId: toInteger(nodeId)}, stream: true}
     ) YIELD value
     WITH value
     CALL apoc.custom.asMap(value) YIELD value AS jsonMap
     WITH {event: "conversation_created", data: jsonMap}
  AS payload
     CALL apoc.load.jsonParams(
       "http://localhost:8002/api/neo4j-events/",
       {method: "POST", "Content-Type":
  "application/json"},
       apoc.convert.toJson(payload)
     ) YIELD value
     RETURN value',
    {phase: 'afterAsync'}
  );