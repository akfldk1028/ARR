# Neo4j 이중 경로 패턴 (Dual Path Pattern)

## 개요

이 프로젝트의 Neo4j 구조는 **두 가지 메시지 저장 패턴**을 동시에 사용합니다.

## 두 가지 패턴

### 1. Turn 기반 패턴 (Enterprise Grade)
**경로**: `User -> Session -> Turn -> Message`

**사용 목적**: 실시간 대화 추적 및 상세 분석

**파일**: `agents/database/neo4j/conversation_tracker.py`

**사용처**:
- `chat/consumers.py` (텍스트 채팅 WebSocket)
- `gemini/consumers/simple_consumer.py` (음성 WebSocket)
- 모든 실시간 사용자 대화

**특징**:
- Turn 단위로 대화 구조화 (사용자 입력 → AI 응답 = 1 Turn)
- Turn마다 추가 정보 연결:
  - `AgentExecution` - 어떤 에이전트가 실행되었는가
  - `Decision` - AI가 어떤 결정을 내렸는가
  - `Task` - 어떤 작업이 생성되었는가
  - `Artifact` - 어떤 결과물이 생성되었는가
- 복잡한 multi-agent 상호작용 추적 가능

### 2. 직접 연결 패턴 (Simplified)
**경로**: `Session -> Message` (Turn 없이 직접)

**사용 목적**: 간단한 메시지 저장 (에이전트 간 통신 등)

**파일**: `agents/worker_agents/base/base_worker.py`

**사용처**:
- Worker 에이전트 간 A2A 통신
- 단순 메시지 기록이 필요한 경우

**특징**:
- Turn 개념 불필요한 간단한 메시지 저장
- Context 기반 그룹핑
- 빠른 메시지 저장/조회

## 실제 코드 예시

### 예시 1: Turn 기반 패턴 (WebSocket Consumer)

**파일**: `chat/consumers.py` (Line 45-70)

```python
class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ConversationTracker 사용
        self.conversation_tracker = ConversationTracker(self.neo4j_service)
        self.turn_counter = 0

    async def connect(self):
        # Neo4j Session 생성
        username = self.user_obj.username if self.user_obj else 'anonymous'
        self.neo4j_session_id = self.conversation_tracker.create_session(
            username,
            metadata={'django_session_id': self.session_id, 'agent': 'hostagent'}
        )

    async def _handle_chat_message(self, data):
        user_message = data.get('message', '')

        # Turn 생성 (한 번의 대화 사이클)
        self.turn_counter += 1
        turn_id = self.conversation_tracker.create_turn(
            self.neo4j_session_id,
            self.turn_counter,
            user_message
        )

        # 사용자 메시지 저장
        self.conversation_tracker.add_message(
            session_id=self.neo4j_session_id,
            turn_id=turn_id,
            role='user',
            content=user_message,
            sequence=1
        )

        # AI 응답 처리...
        response = await self.get_ai_response(user_message)

        # AI 응답 메시지 저장 (같은 Turn에)
        self.conversation_tracker.add_message(
            session_id=self.neo4j_session_id,
            turn_id=turn_id,
            role='assistant',
            content=response,
            sequence=2
        )
```

**생성되는 Neo4j 구조**:
```
Session (4154ab68...)
  └─ Turn #1 (b34ea748...)
      ├─ Message #1 (user: "안녕하세요")
      ├─ Message #2 (assistant: "안녕하세요! 무엇을...")
      ├─ AgentExecution (hotel-specialist)
      ├─ Decision (response_generation)
      ├─ Task (generate_response)
      └─ Artifact (assistant_response)
```

### 예시 2: 직접 연결 패턴 (Worker Agent)

**파일**: `agents/worker_agents/base/base_worker.py` (Line 148-176)

```python
class BaseWorkerAgent:
    def _save_message_to_neo4j(self, session_id: str, context_id: str,
                                 message_type: str, content: str, user_name: str):
        """간단한 메시지 저장 - Turn 없이 직접 Session에 연결"""
        try:
            query = """
            MERGE (s:Session {session_id: $session_id})
            MERGE (c:Context {context_id: $context_id})
            MERGE (s)-[:IN_CONTEXT]->(c)
            CREATE (m:Message {
                id: $message_id,
                type: $message_type,
                content: $content,
                user_name: $user_name,
                agent_slug: $agent_slug,
                timestamp: $timestamp
            })
            CREATE (s)-[:HAS_MESSAGE]->(m)  # 직접 연결!
            RETURN m
            """

            self.neo4j_service.execute_query(query, {...})

        except Exception as e:
            logger.error(f"Error saving message: {e}")
```

**사용 시나리오**:
- Worker A가 Worker B에게 메시지 전송
- 에이전트 간 내부 통신 기록
- Context 단위로 메시지 그룹핑

**생성되는 Neo4j 구조**:
```
Session (inter_agent_collab_123)
  ├─ Context (ctx_456)
  ├─ Message (from: general-worker, "항공편 검색해줘")
  └─ Message (from: flight-specialist, "검색 결과: ...")
```

## 두 패턴이 공존하는 이유

### 1. 사용자 대화 (Turn 기반 필수)
**시나리오**: 사용자가 웹 채팅으로 대화

```
사용자: "서울에서 제주도 가는 비행기 예약해줘"
      ↓
Turn #1 생성
      ↓
├─ Message (user)
├─ AgentExecution (general-worker → flight-specialist 라우팅)
├─ Decision (delegation to flight-specialist, confidence: 0.95)
├─ Task (search_flights, priority: 5)
└─ Message (assistant: "대한항공 KE1234...")
```

**왜 Turn이 필요한가?**
- 사용자 입력과 AI 응답을 **한 쌍으로 묶기** 위해
- 어떤 에이전트가 어떤 결정을 내려서 어떤 작업을 했는지 **전체 흐름 추적**
- 나중에 "3번째 대화에서 왜 그런 답변을 했지?" 분석 가능

### 2. 에이전트 간 통신 (직접 연결 충분)
**시나리오**: General Worker → Flight Specialist 내부 통신

```
GeneralWorker: (내부) Flight Specialist에게 요청
      ↓
직접 Message 저장 (Turn 불필요)
      ↓
Session -> Message (agent_to_agent_comm)
```

**왜 Turn이 불필요한가?**
- 에이전트 간 통신은 **도구 호출**에 가까움
- "누가 누구에게 뭘 물어봤다" 기록만 필요
- 복잡한 추적 구조 불필요 (오버헤드)

## Message 노드 구조

**중요**: 모든 Message 노드는 두 경로 모두 지원하도록 설계됨

```json
{
  "id": "9c39b3dd-9e18-4c27...",
  "session_id": "afecf305-dbf9...",  // Session 직접 참조
  "turn_id": "e437b4af-7717...",     // Turn 참조 (있는 경우)
  "role": "user",
  "content": "안녕하세요",
  "timestamp": "2025-10-04T07:26:32.910734Z",
  "sequence": 1
}
```

- `turn_id`가 **있으면**: Turn 기반 패턴으로 저장된 메시지
- `turn_id`가 **없으면**: 직접 연결 패턴으로 저장된 메시지
- `session_id`는 **항상** 있음 (모든 메시지는 세션에 속함)

## 쿼리 예시

### Turn 기반 히스토리 조회
```cypher
MATCH (s:Session {id: $session_id})-[:HAS_TURN]->(t:Turn)
MATCH (t)-[:HAS_MESSAGE]->(m:Message)
RETURN t.sequence as turn_number,
       m.role as role,
       m.content as content
ORDER BY t.sequence, m.sequence
```

### 직접 연결 히스토리 조회
```cypher
MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
RETURN m.content as content,
       m.type as role,
       m.timestamp as timestamp
ORDER BY m.timestamp DESC
LIMIT 50
```

### 통합 조회 (모든 메시지)
```cypher
MATCH (s:Session {id: $session_id})
OPTIONAL MATCH (s)-[:HAS_TURN]->(t:Turn)-[:HAS_MESSAGE]->(tm:Message)
OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(dm:Message)
WHERE NOT EXISTS((t)-[:HAS_MESSAGE]->(dm))  // Turn 기반 메시지 제외
RETURN tm, dm
ORDER BY coalesce(tm.timestamp, dm.timestamp)
```

## 성능 고려사항

### Turn 기반 패턴
- **장점**: 완전한 대화 흐름 추적, 복잡한 분석 가능
- **단점**: 노드/관계 많음, 쓰기 작업 복잡
- **적합**: 사용자 대화, 상세 추적 필요한 경우

### 직접 연결 패턴
- **장점**: 빠른 저장/조회, 간단한 구조
- **단점**: 상세한 흐름 추적 불가
- **적합**: 에이전트 간 통신, 간단한 로깅

## 마이그레이션 가이드

### 기존 코드 확인 방법

**Turn 기반 사용 중인가?**
```python
# ConversationTracker import 있으면 Turn 기반
from agents.database.neo4j import ConversationTracker

tracker = ConversationTracker(service)
turn_id = tracker.create_turn(...)
```

**직접 연결 사용 중인가?**
```python
# 쿼리에 CREATE (s)-[:HAS_MESSAGE]->(m) 있으면 직접 연결
query = """
CREATE (s)-[:HAS_MESSAGE]->(m)
"""
```

### 언제 어떤 패턴을 사용할까?

| 상황 | 패턴 | 이유 |
|------|------|------|
| 사용자 채팅 WebSocket | Turn 기반 | 대화 흐름 추적 필요 |
| 에이전트 간 통신 | 직접 연결 | 간단한 메시지 기록 |
| 상세 분석 필요 | Turn 기반 | AgentExecution, Decision 등 연결 |
| 빠른 로깅 | 직접 연결 | 오버헤드 최소화 |
| 디버깅/추적 | Turn 기반 | 전체 실행 흐름 파악 |

## 결론

**이중 경로 패턴은 버그가 아니라 설계입니다.**

- **Turn 기반**: Enterprise-grade 대화 추적 (사용자 대면)
- **직접 연결**: 효율적인 메시지 로깅 (내부 통신)

두 패턴이 `session_id`로 통합되어 유연한 쿼리를 지원합니다.

---

**작성일**: 2025-10-08
**작성자**: Claude Code
**관련 파일**:
- `agents/database/neo4j/conversation_tracker.py`
- `agents/worker_agents/base/base_worker.py`
- `chat/consumers.py`
- `gemini/consumers/simple_consumer.py`
