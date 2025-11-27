# Neo4j APOC Triggers for Real-time Updates

## 사전 준비

Neo4j Browser에서 먼저 실행:
```cypher
:use neo4j
```

---

## Trigger 1: Conversation 생성 감지

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'conversation_created',
  '
  UNWIND $createdNodes AS node
  WITH node WHERE node:Conversation
  CALL apoc.load.jsonParams(
    "http://localhost:8003/api/neo4j-event",
    {`Content-Type`: "application/json"},
    apoc.convert.toJson({
      type: "conversation_created",
      data: {
        conversation_id: node.conversation_id,
        django_session_id: node.django_session_id,
        created_at: toString(node.created_at)
      }
    })
  )
  YIELD value
  RETURN value
  ',
  {phase: 'after'}
);
```

---

## Trigger 2: Message 생성 감지

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'message_created',
  '
  UNWIND $createdNodes AS node
  WITH node WHERE node:Message
  MATCH (c:Conversation)-[:HAS_MESSAGE]->(node)
  CALL apoc.load.jsonParams(
    "http://localhost:8003/api/neo4j-event",
    {`Content-Type`: "application/json"},
    apoc.convert.toJson({
      type: "message_created",
      data: {
        message_id: node.message_id,
        conversation_id: c.conversation_id,
        role: node.role,
        content: node.content
      }
    })
  )
  YIELD value
  RETURN value
  ',
  {phase: 'after'}
);
```

---

## Trigger 3: Turn 생성 감지

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'turn_created',
  '
  UNWIND $createdNodes AS node
  WITH node WHERE node:Turn
  MATCH (c:Conversation)-[:HAS_TURN]->(node)
  CALL apoc.load.jsonParams(
    "http://localhost:8003/api/neo4j-event",
    {`Content-Type`: "application/json"},
    apoc.convert.toJson({
      type: "turn_created",
      data: {
        turn_id: node.turn_id,
        conversation_id: c.conversation_id,
        sequence: node.sequence
      }
    })
  )
  YIELD value
  RETURN value
  ',
  {phase: 'after'}
);
```

---

## Trigger 4: AgentExecution 생성 감지

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agent_execution_created',
  '
  UNWIND $createdNodes AS node
  WITH node WHERE node:AgentExecution
  MATCH (t:Turn)-[:HAS_EXECUTION]->(node)
  CALL apoc.load.jsonParams(
    "http://localhost:8003/api/neo4j-event",
    {`Content-Type`: "application/json"},
    apoc.convert.toJson({
      type: "agent_execution_created",
      data: {
        execution_id: node.execution_id,
        turn_id: t.turn_id,
        agent_slug: node.agent_slug
      }
    })
  )
  YIELD value
  RETURN value
  ',
  {phase: 'after'}
);
```

---

## Trigger 5: AgentExecution 완료 감지

```cypher
CALL apoc.trigger.install(
  'neo4j',
  'agent_execution_completed',
  '
  UNWIND apoc.trigger.propertiesByKey($assignedNodeProperties, "status") AS prop
  WITH prop.node AS node
  WHERE node:AgentExecution AND node.status = "completed"
  CALL apoc.load.jsonParams(
    "http://localhost:8003/api/neo4j-event",
    {`Content-Type`: "application/json"},
    apoc.convert.toJson({
      type: "agent_execution_completed",
      data: {
        execution_id: node.execution_id,
        status: node.status,
        execution_time_ms: node.execution_time_ms
      }
    })
  )
  YIELD value
  RETURN value
  ',
  {phase: 'after'}
);
```

---

## 확인

모든 Trigger 등록 후 확인:

```cypher
CALL apoc.trigger.list();
```

5개의 trigger가 보여야 합니다:
1. conversation_created
2. message_created
3. turn_created
4. agent_execution_created
5. agent_execution_completed

---

## 테스트

Trigger가 제대로 작동하는지 테스트:

```cypher
CREATE (c:Conversation {
  conversation_id: 'test-conv-' + toString(timestamp()),
  django_session_id: 'test-session',
  created_at: datetime()
})
RETURN c;
```

Django 서버 로그와 Kafka Listener 로그에서 이벤트가 수신되는지 확인하세요.
