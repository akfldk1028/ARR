# Neo4j Real-time System Implementation with Kafka

## ✅ 완료된 작업

### 1. 모듈 구조 설계 (Modular & Maintainable)

```
graph_db/
├── realtime/
│   ├── __init__.py                 # 모듈 exports
│   ├── neo4j_listener.py          # Kafka 리스너 (166 lines, clean)
│   └── handlers.py                 # 이벤트 핸들러 (모듈화, 220 lines)
└── management/
    └── commands/
        └── listen_neo4j.py        # Django management command
```

### 2. 핵심 컴포넌트

#### A. Neo4j Event Listener (`neo4j_listener.py`)
```python
class Neo4jEventListener:
    - connect()                      # Kafka 연결
    - listen()                       # 이벤트 청취
    - close()                        # 안전한 종료
    - handler_registry              # 핸들러에 위임
```

**특징:**
- ✅ Async context manager 지원 (`async with`)
- ✅ Graceful shutdown (Ctrl+C 처리)
- ✅ Error handling & logging
- ✅ Modular design (핸들러 분리)
- ✅ Kafka consumer group 지원

#### B. Event Handler Registry (`handlers.py`)
```python
BaseEventHandler                    # 공통 기능
├── ConversationEventHandler       # Conversation 이벤트
├── MessageEventHandler            # Message 이벤트
├── TurnEventHandler               # Turn 이벤트
└── AgentExecutionEventHandler     # AgentExecution 이벤트

EventHandlerRegistry               # 라우팅 & 관리
└── route_event()                  # Topic → Handler
```

**특징:**
- ✅ 단일 책임 원칙 (SRP): 각 핸들러 독립
- ✅ 개방-폐쇄 원칙 (OCP): 새 이벤트 타입 추가 쉬움
- ✅ 테스트 용이: 각 핸들러 독립적으로 테스트 가능
- ✅ 유지보수 편함: 이벤트 타입별로 코드 분리

#### C. Management Command (`listen_neo4j.py`)
```bash
python manage.py listen_neo4j [--kafka-brokers=localhost:9092] [--group-id=neo4j-listener-group]
```

**특징:**
- ✅ 표준 Django management command
- ✅ 설정 가능한 Kafka broker URLs (comma-separated)
- ✅ Consumer group ID 설정 가능
- ✅ 우아한 shutdown

### 3. 아키텍처 흐름

```
Neo4j APOC Trigger
    ↓ (변경 감지)
Kafka Topics
    ↓ (메시지 전달)
Neo4jEventListener (AIOKafkaConsumer)
    ↓ (토픽 라우팅)
EventHandlerRegistry
    ↓ (그룹별 브로드캐스트)
Django Channels Layer
    ↓ (WebSocket)
프론트엔드 (실시간 업데이트)
```

---

## 🔧 필요한 추가 작업

### 1. Kafka & Zookeeper 설치

#### Windows (Docker 권장)
```bash
# Docker Compose로 Kafka + Zookeeper 실행
docker-compose up -d
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"
```

#### 또는 로컬 설치
```bash
# Windows (Chocolatey)
choco install apache-kafka

# Linux/Mac (Homebrew)
brew install kafka
```

### 2. Python 패키지 설치
```bash
pip install aiokafka
```

### 3. Kafka Topics 생성

```bash
# Topic 생성
kafka-topics --create --topic neo4j.conversation.created --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic neo4j.conversation.updated --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic neo4j.message.created --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic neo4j.turn.created --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic neo4j.agent_execution.created --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics --create --topic neo4j.agent_execution.completed --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Topic 목록 확인
kafka-topics --list --bootstrap-server localhost:9092
```

### 4. Neo4j APOC 설정

#### A. APOC 플러그인 설치
```bash
# Neo4j plugins/ 디렉토리에 다운로드
# https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases
# apoc-5.x.x-extended.jar 다운로드 (Kafka 지원)
```

#### B. `neo4j.conf` 설정
```properties
# APOC 활성화
apoc.trigger.enabled=true
apoc.trigger.refresh=60000

# Kafka Procedures 허용
apoc.export.file.enabled=true
dbms.security.procedures.unrestricted=apoc.*
```

#### C. Neo4j 재시작
```bash
neo4j restart
```

### 5. Neo4j 트리거 등록

#### Conversation Created
```cypher
CALL apoc.trigger.install('neo4j', 'notify_conversation_created',
  "
  UNWIND $createdNodes AS node
  WHERE 'Conversation' IN labels(node)
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.conversation.created',
    '',
    apoc.convert.toJson({
      type: 'conversation_created',
      conversation_id: node.id,
      user_id: node.user_id,
      django_session_id: node.django_session_id,
      agent: node.current_agent,
      timestamp: timestamp()
    })
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

#### Message Created
```cypher
CALL apoc.trigger.install('neo4j', 'notify_message_created',
  "
  UNWIND $createdNodes AS node
  WHERE 'Message' IN labels(node)
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.message.created',
    '',
    apoc.convert.toJson({
      type: 'message_created',
      message_id: node.id,
      conversation_id: node.conversation_id,
      turn_id: node.turn_id,
      role: node.role,
      content: node.content,
      sequence: node.sequence,
      timestamp: node.timestamp
    })
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

#### Turn Created
```cypher
CALL apoc.trigger.install('neo4j', 'notify_turn_created',
  "
  UNWIND $createdNodes AS node
  WHERE 'Turn' IN labels(node)
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.turn.created',
    '',
    apoc.convert.toJson({
      type: 'turn_created',
      turn_id: node.id,
      conversation_id: node.conversation_id,
      sequence: node.sequence,
      user_query: node.user_query,
      timestamp: timestamp()
    })
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

#### AgentExecution Created
```cypher
CALL apoc.trigger.install('neo4j', 'notify_agent_execution_created',
  "
  UNWIND $createdNodes AS node
  WHERE 'AgentExecution' IN labels(node)
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.agent_execution.created',
    '',
    apoc.convert.toJson({
      type: 'agent_execution_created',
      execution_id: node.id,
      agent_slug: node.agent_slug,
      turn_id: node.turn_id,
      status: node.status,
      timestamp: timestamp()
    })
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

#### AgentExecution Completed
```cypher
CALL apoc.trigger.install('neo4j', 'notify_agent_execution_completed',
  "
  UNWIND $assignedNodeProperties AS props
  WITH props.node AS node
  WHERE 'AgentExecution' IN labels(node) AND props.new.status = 'completed'
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.agent_execution.completed',
    '',
    apoc.convert.toJson({
      type: 'agent_execution_completed',
      execution_id: node.id,
      status: node.status,
      execution_time_ms: node.execution_time_ms,
      timestamp: timestamp()
    })
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

### 6. WebSocket Consumer 수정

`chat/consumers.py`에 `neo4j_event` 핸들러 추가:

```python
# chat/consumers.py

async def neo4j_event(self, event):
    """Handle Neo4j CDC events from Django Channels"""
    await self.send(text_data=json.dumps({
        'type': 'neo4j_update',
        'event_type': event['event_type'],
        'data': event['data']
    }))
```

그리고 `connect()` 메소드에서 conversation 그룹에 가입:

```python
async def connect(self):
    # ...기존 코드...

    # Join conversation group for real-time updates
    if self.conversation_id:
        await self.channel_layer.group_add(
            f"conversation_{self.conversation_id}",
            self.channel_name
        )
```

---

## 🚀 실행 방법

### Terminal 1: Kafka & Zookeeper
```bash
# Docker Compose 사용시
docker-compose up -d

# 또는 로컬 Kafka
zookeeper-server-start.sh config/zookeeper.properties
kafka-server-start.sh config/server.properties
```

### Terminal 2: Django 서버
```bash
cd D:\Data\11_Backend\01_ARR\backend
daphne -b 0.0.0.0 -p 8002 backend.asgi:application
```

### Terminal 3: Neo4j Event Listener
```bash
cd D:\Data\11_Backend\01_ARR\backend
python manage.py listen_neo4j --kafka-brokers=localhost:9092
```

**다중 브로커 설정:**
```bash
python manage.py listen_neo4j --kafka-brokers=broker1:9092,broker2:9092,broker3:9092
```

---

## 📊 테스트 시나리오

### 1. 트리거 확인
```cypher
// 설치된 트리거 목록
CALL apoc.trigger.list();

// 특정 트리거 제거 (필요시)
CALL apoc.trigger.remove('notify_conversation_created');
```

### 2. 수동 이벤트 발행 (테스트용)
```bash
# Kafka CLI에서 수동 발행
kafka-console-producer --broker-list localhost:9092 --topic neo4j.conversation.created
> {"type":"conversation_created","conversation_id":"test-123","user_id":"test_user"}
```

### 3. Kafka Consumer로 직접 확인
```bash
# Python 리스너와 별개로 메시지 확인
kafka-console-consumer --bootstrap-server localhost:9092 --topic neo4j.conversation.created --from-beginning
```

### 4. WebSocket 연결 테스트
프론트엔드에서 WebSocket 연결 후:
```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'neo4j_update') {
    console.log('Neo4j Update:', data.event_type, data.data);
    // UI 업데이트
  }
};
```

---

## 🛠️ 유지보수 가이드

### 새 이벤트 타입 추가하기

#### 1. Kafka Topic 생성
```bash
kafka-topics --create --topic neo4j.new_feature.created --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

#### 2. 핸들러 추가 (`handlers.py`)
```python
class NewFeatureEventHandler(BaseEventHandler):
    async def handle_created(self, data: Dict[str, Any]):
        # 로직 구현
        pass
```

#### 3. 레지스트리에 등록 (`handlers.py`)
```python
class EventHandlerRegistry:
    def __init__(self):
        # ...기존 핸들러...
        self.new_feature = NewFeatureEventHandler()

    async def route_event(self, channel: str, data: Dict[str, Any]):
        routing_map = {
            # ...기존 맵핑...
            'neo4j:new_feature:created': self.new_feature.handle_created,
        }
```

#### 4. Neo4j 트리거 추가
```cypher
CALL apoc.trigger.install('neo4j', 'notify_new_feature_created',
  "
  UNWIND $createdNodes AS node
  WHERE 'NewFeature' IN labels(node)
  CALL apoc.kafka.send(
    'localhost:9092',
    'neo4j.new_feature.created',
    '',
    apoc.convert.toJson({...})
  ) YIELD value
  RETURN value
  ",
  {phase: 'afterAsync'}
);
```

#### 5. Listener subscribe 업데이트 (`neo4j_listener.py`)
```python
self.topics = [
    # ...기존 토픽들...
    'neo4j.new_feature.created',
]
```

### Kafka 모니터링

#### Consumer Lag 확인
```bash
kafka-consumer-groups --bootstrap-server localhost:9092 --group neo4j-listener-group --describe
```

#### Topic 메시지 수 확인
```bash
kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic neo4j.conversation.created
```

### 로깅 & 디버깅

```python
# settings.py에 로깅 설정 추가
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'graph_db.realtime': {
            'handlers': ['console'],
            'level': 'DEBUG',  # 디버깅시 DEBUG, 프로덕션에서 INFO
        },
        'aiokafka': {
            'handlers': ['console'],
            'level': 'WARNING',  # Kafka 클라이언트 로그
        },
    },
}
```

---

## ✨ Kafka vs Redis 장점 정리

### Kafka 장점
- ✅ **영속성 (Persistence)**: 메시지가 디스크에 저장되어 유실 방지
- ✅ **재생 가능 (Replay)**: 과거 이벤트 다시 소비 가능
- ✅ **확장성 (Scalability)**: 파티셔닝으로 수평 확장 우수
- ✅ **컨슈머 그룹**: 여러 리스너가 동시에 메시지 처리 가능
- ✅ **프로덕션 검증**: 대용량 실시간 데이터 처리에 검증됨
- ✅ **순서 보장**: 파티션 내 메시지 순서 보장
- ✅ **내결함성 (Fault Tolerance)**: 복제(replication) 지원

### 1. 모듈화 (Modularity)
- ✅ 각 핸들러 독립적
- ✅ 새 이벤트 타입 추가 쉬움
- ✅ 테스트 용이

### 2. 유지보수성 (Maintainability)
- ✅ 명확한 책임 분리
- ✅ 코드 가독성 높음
- ✅ 문서화 잘 됨

### 3. 확장성 (Scalability)
- ✅ Kafka Pub/Sub (여러 서버 가능)
- ✅ Django Channels Layer (분산 가능)
- ✅ 이벤트 기반 아키텍처

### 4. 신뢰성 (Reliability)
- ✅ Graceful shutdown
- ✅ Error handling
- ✅ Async context manager
- ✅ Consumer group offset 관리

---

## 📝 Next Steps

1. ✅ **코드 구현 완료 (Kafka 버전)**
2. ⏳ **Kafka & Zookeeper 설치**
3. ⏳ **Kafka Topics 생성**
4. ⏳ **APOC Extended 플러그인 설치** (Kafka 지원)
5. ⏳ **Neo4j 트리거 등록**
6. ⏳ **WebSocket Consumer 수정**
7. ⏳ **End-to-end 테스트**

현재까지 Kafka 기반 백엔드 코드 구조는 모두 완성되었습니다!

---

## 🔍 트러블슈팅

### 1. Kafka 연결 실패
```bash
# Kafka가 실행 중인지 확인
docker ps | grep kafka

# 로그 확인
docker logs <kafka-container-id>
```

### 2. APOC Kafka 함수 없음
```cypher
// APOC Extended 설치 확인
CALL apoc.help('kafka');
```

APOC Core가 아닌 **APOC Extended**를 설치해야 Kafka 지원됩니다.

### 3. Neo4j 트리거 실행 안 됨
```cypher
// 트리거 활성화 확인
CALL apoc.trigger.list();

// neo4j.conf 확인
apoc.trigger.enabled=true
```

### 4. Consumer Lag 발생
```bash
# Consumer 그룹 리셋 (주의: 메시지 재처리됨)
kafka-consumer-groups --bootstrap-server localhost:9092 --group neo4j-listener-group --reset-offsets --to-latest --all-topics --execute
```
