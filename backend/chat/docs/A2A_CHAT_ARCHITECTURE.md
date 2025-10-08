# A2A Chat System - Architecture & Code Reference

## 개요
텍스트 채팅에 A2A (Agent-to-Agent) 프로토콜을 통합한 시스템.
Semantic routing으로 자동 전문가 위임, 깔끔한 UI/UX.

---

## 핵심 개념

### 1. Host Agent (조정자)
- **역할**: 사용자 요청을 받아 semantic routing으로 적절한 specialist에게 위임
- **구현**: `agents/worker_agents/implementations/general_worker.py`
- **Slug**: `hostagent`

### 2. Specialist Agents (전문가)
- **역할**: 특정 도메인 전문가 (예: 항공편 예약)
- **구현**: `agents/worker_agents/implementations/flight_specialist_worker.py`
- **Slug**: `flight-specialist`, `hotel-specialist` 등

### 3. Semantic Routing
- **역할**: 사용자 요청을 분석해서 어느 specialist에게 보낼지 결정
- **구현**: `agents/worker_agents/agent_discovery.py`
- **모델**: `distiluse-base-multilingual-cased-v2` (한국어 지원)

---

## 전체 흐름

```
User Input ("비행기 예약해줘")
    ↓
WebSocket (chat/consumers.py)
    ↓
A2A Handler (gemini/consumers/handlers/a2a_handler.py)
    ↓
Host Agent (agents/worker_agents/implementations/general_worker.py)
    ↓
Semantic Routing (agents/worker_agents/agent_discovery.py)
    ↓ (score: 0.915 → flight_booking)
Agent Discovery → LLM Selection
    ↓ (selected: flight-specialist)
A2A Client (agents/a2a_client.py)
    ↓ (POST http://localhost:8004/agents/flight-specialist/chat/)
Flight Specialist Agent (agents/worker_agents/implementations/flight_specialist_worker.py)
    ↓
Response → WebSocket → UI
```

---

## 디렉토리 구조 및 의존성

### 1. Chat App (텍스트 채팅 전용)
```
D:\Data\11_Backend\01_ARR\backend\chat\
├── consumers.py              # WebSocket consumer (A2A 통합)
├── templates/chat/
│   └── index.html           # UI (delegation marker 파싱)
├── urls.py
└── views.py
```

**의존성:**
- `agents/` (Worker Agent System)
- `gemini/consumers/handlers/a2a_handler.py` (메시지 라우팅)

---

### 2. Agents App (핵심 A2A 시스템)
```
D:\Data\11_Backend\01_ARR\backend\agents\
├── models.py                 # Django Agent 모델
├── views.py                  # Agent card endpoints (A2A 표준)
├── a2a_client.py            # A2A 통신 클라이언트
├── worker_agents/
│   ├── __init__.py
│   ├── base/
│   │   └── base_worker.py   # BaseWorkerAgent 추상 클래스
│   ├── implementations/
│   │   ├── general_worker.py           # Host Agent (조정자)
│   │   └── flight_specialist_worker.py # Flight Specialist
│   ├── cards/
│   │   ├── general_worker_card.json
│   │   └── flight_specialist_card.json
│   ├── worker_factory.py    # Worker 생성 팩토리
│   ├── worker_manager.py    # Worker 라이프사이클 관리
│   └── agent_discovery.py   # Semantic routing + Agent selection
└── database/
    └── neo4j/
        ├── service.py        # Neo4j 서비스
        ├── indexes.py
        ├── stats.py
        └── queries.py
```

**외부 의존성:**
- `backend/settings.py` (A2A_BASE_URL 설정)
- Neo4j (대화 히스토리 저장)

---

### 3. Gemini App (음성 시스템, 일부 공유 코드)
```
D:\Data\11_Backend\01_ARR\backend\gemini\
└── consumers/
    └── handlers/
        └── a2a_handler.py    # A2A 메시지 라우팅 (chat/에서 재사용)
```

**역할:**
- `A2AHandler`: WebSocket 메시지를 Worker Agent로 전달
- Chat app과 Gemini app 모두 사용

---

## 코드 참조 가이드

### 사용자 요청 처리 과정

#### 1. WebSocket 연결 및 메시지 수신
**파일**: `chat/consumers.py`
```python
class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self):
        self.current_agent_slug = "hostagent"  # Host Agent
        self.a2a_handler = None

    async def connect(self):
        # A2A Handler 초기화
        from gemini.consumers.handlers.a2a_handler import A2AHandler
        self.a2a_handler = A2AHandler(self)

    async def _handle_chat_message(self, data):
        # A2A Handler로 전달
        await self.a2a_handler.handle_text(data)
```

**역할:**
- WebSocket 연결 관리
- A2A Handler 초기화
- 메시지를 A2A Handler로 라우팅

---

#### 2. A2A 메시지 라우팅
**파일**: `gemini/consumers/handlers/a2a_handler.py`
```python
class A2AHandler:
    async def handle_text(self, data):
        # Worker Agent Manager로 요청 전달
        result = await self.worker_manager.process_text_request(
            agent_slug=self.consumer.current_agent_slug,
            user_input=content,
            context_id=context_id,
            session_id=session_id,
            user_name=user_name
        )
```

**역할:**
- Worker Manager 호출
- 응답을 WebSocket으로 전송

---

#### 3. Worker Agent 생성 및 관리
**파일**: `agents/worker_agents/worker_manager.py`
```python
class WorkerAgentManager:
    async def process_text_request(self, agent_slug, user_input, ...):
        # Worker 가져오기 또는 생성
        worker = await self.get_worker(agent_slug)

        # Worker에게 요청 처리 위임
        response = await worker.process_request(user_input, ...)
```

**파일**: `agents/worker_agents/worker_factory.py`
```python
class WorkerAgentFactory:
    WORKER_TYPES = {
        'hostagent': GeneralWorkerAgent,
        'flight-specialist': FlightSpecialistWorkerAgent,
    }

    @classmethod
    def create_worker(cls, agent_slug, agent_config):
        worker_class = cls.WORKER_TYPES.get(agent_slug)
        return worker_class(agent_slug, agent_config)
```

**역할:**
- Worker 인스턴스 캐싱 (세션당 재사용)
- Factory pattern으로 Worker 생성

---

#### 4. Host Agent - Semantic Routing
**파일**: `agents/worker_agents/implementations/general_worker.py`
```python
class GeneralWorkerAgent(BaseWorkerAgent):
    def __init__(self, agent_slug, agent_config):
        self.discovery_service = AgentDiscoveryService(self.llm)

    async def _generate_response(self, user_input, ...):
        # Semantic routing으로 delegation 여부 결정
        should_delegate, target_agent = await self.discovery_service.should_delegate_request(
            user_request=user_input,
            current_agent_slug=self.agent_slug
        )

        if should_delegate and target_agent:
            # Specialist에게 위임
            specialist_response = await self.communicate_with_agent(
                target_agent_slug=target_agent,
                message=f"A user is asking: {user_input}",
                context_id=context_id
            )

            # Delegation marker와 함께 반환
            return f"[DELEGATION_OCCURRED:{target_agent}][SPECIALIST_RESPONSE:{specialist_response}]"

        # 일반 대화는 직접 처리
        return await self.llm.ainvoke(messages)
```

**역할:**
- Semantic routing 서비스 초기화
- Delegation 여부 결정
- Specialist 응답을 marker와 함께 반환

---

#### 5. Semantic Routing 및 Agent Selection
**파일**: `agents/worker_agents/agent_discovery.py`
```python
class AgentDiscoveryService:
    async def should_delegate_request(self, user_request, current_agent_slug):
        # Sentence transformer로 의도 분류
        if not hasattr(self, '_semantic_model'):
            self._semantic_model = SentenceTransformer('distiluse-base-multilingual-cased-v2')

            # 카테고리 정의
            self._categories = {
                'greetings': ["안녕하세요", "hello", ...],
                'flight_booking': ["비행기 예약", "항공편", ...],
                'hotel_booking': ["호텔 예약", ...],
            }

        # 유사도 계산
        user_embedding = self._semantic_model.encode([user_request])
        similarities = {...}  # 각 카테고리별 유사도

        best_category = max(similarities, key=similarities.get)
        best_score = similarities[best_category]

        # 임계값 체크
        if best_category == 'flight_booking' and best_score > 0.2:
            # Agent discovery 및 선택
            available_agents = await self.discover_available_agents()
            selected_agent = await self.select_best_agent_for_task(user_request, available_agents)
            return True, selected_agent

        return False, None
```

**역할:**
- Multilingual sentence transformer로 의도 분류
- Agent card discovery (A2A 프로토콜)
- LLM으로 최적 agent 선택

---

#### 6. A2A 통신
**파일**: `agents/a2a_client.py`
```python
class A2AClient:
    async def send_message(self, message, context_id, session_id):
        # Agent card에서 endpoint 가져오기
        chat_endpoint = self.agent_card.endpoints.get('jsonrpc')

        # JSON-RPC 2.0 포맷
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": str(uuid4()),
                    "role": "user",
                    "parts": [{"text": message}],
                    "contextId": context_id
                }
            },
            "id": str(uuid4())
        }

        # HTTP POST 전송
        response = await client.post(chat_endpoint, json=payload)
        result = response.json()

        # 응답 파싱
        return result["result"]["parts"][0]["text"]
```

**역할:**
- A2A 표준 JSON-RPC 2.0 메시지 생성
- HTTP POST로 specialist에게 전송
- 응답 파싱

---

#### 7. Specialist Agent 처리
**파일**: `agents/worker_agents/implementations/flight_specialist_worker.py`
```python
class FlightSpecialistWorkerAgent(BaseWorkerAgent):
    async def _generate_response(self, user_input, ...):
        # Flight booking 전문 응답 생성
        messages = [
            SystemMessage(content=self.system_prompt),  # Flight 전문 프롬프트
            HumanMessage(content=user_input)
        ]

        response = await self.llm.ainvoke(messages)
        return response.content
```

**역할:**
- Flight booking 전문 시스템 프롬프트 사용
- LLM으로 전문 응답 생성

---

#### 8. Agent Card Endpoints
**파일**: `agents/views.py`
```python
class AgentCardView(View):
    def get(self, request, agent_slug=None):
        agent = get_object_or_404(Agent, slug=agent_slug, status='active')

        card_data = {
            "name": agent.name,
            "description": agent.description,
            "capabilities": agent.capabilities,
            "endpoints": {
                "chat": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/",
                "jsonrpc": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/",
            },
            "skills": [...],
        }

        return JsonResponse(card_data)
```

**역할:**
- A2A 표준 agent card 제공
- `/.well-known/agent-card/{slug}.json` 엔드포인트
- Discovery에서 사용

---

#### 9. UI Delegation Marker 파싱
**파일**: `chat/templates/chat/index.html`
```javascript
case 'chat_response':
    const message = data.message;
    const delegationMatch = message.match(/\[DELEGATION_OCCURRED:(.*?)\]/);
    const specialistMatch = message.match(/\[SPECIALIST_RESPONSE:(.*?)\]/);

    if (delegationMatch && specialistMatch) {
        // Specialist 응답만 표시
        const targetAgent = delegationMatch[1];
        const specialistResponse = specialistMatch[1];

        addMessage('specialist', specialistResponse, {
            agent: 'Flight Specialist',
            agentSlug: targetAgent
        });
    } else {
        // Host Agent 일반 응답
        addMessage('assistant', data.message, {
            agent: 'Host Agent',
            agentSlug: data.agent_slug
        });
    }
```

**역할:**
- Delegation marker 파싱
- Specialist 메시지 분리 표시
- Agent별 avatar 구분 (✈️, 🤖, U)

---

## 설정 파일

### Django Settings
**파일**: `backend/settings.py`
```python
# A2A Configuration
A2A_BASE_URL = "http://localhost:8004"
A2A_SERVER_PORT = 8000

# Installed Apps
INSTALLED_APPS = [
    'agents',     # Worker Agent System
    'chat',       # Text Chat
    'gemini',     # Voice System (A2A Handler 공유)
]
```

**중요:**
- `A2A_BASE_URL`: Agent card endpoints에서 사용
- Port 8004로 고정 (이전 8000 오류 수정됨)

---

## 데이터 흐름

### 1. 일반 대화 (Host Agent 직접 처리)
```
User: "안녕하세요"
  ↓
Semantic Routing: greetings (score: 0.9) → No delegation
  ↓
Host Agent LLM: "안녕하세요! 무엇을 도와드릴까요?"
  ↓
UI: 🤖 Host Agent message
```

### 2. 전문가 위임 (Delegation)
```
User: "비행기 예약해줘"
  ↓
Semantic Routing: flight_booking (score: 0.915) → Delegate!
  ↓
Agent Discovery: 3 agents found
  ↓
LLM Selection: "flight-specialist" 선택
  ↓
A2A Client: POST http://localhost:8004/agents/flight-specialist/chat/
  ↓
Flight Specialist: "항공편 예약을 도와드리겠습니다..."
  ↓
Response: "[DELEGATION_OCCURRED:flight-specialist][SPECIALIST_RESPONSE:...]"
  ↓
UI Parsing: ✈️ Flight Specialist message only
```

---

## 성능 최적화

### 타이밍 분석 (첫 요청)
```
총 ~9초:
  - Worker 생성: 0.5초
  - Semantic model 로딩: 4초 (첫 요청만, 이후 캐시)
  - Semantic routing: 0.01초 (모델 캐시 후)
  - Agent discovery: 1.5초 (3개 agent card HTTP 요청)
  - LLM selection: 0.8초
  - Specialist 처리: 2초
```

### 두 번째 요청 이후
```
총 ~5초:
  - Semantic routing: 0.01초 (모델 캐시됨)
  - Agent discovery: 1.5초
  - LLM selection: 0.8초
  - Specialist 처리: 2초
```

### 최적화 기회
1. **Agent card 캐싱**: 매 요청마다 HTTP로 3개씩 읽음 → 5분 캐시로 1.5초 절약 가능
2. **LLM streaming**: Specialist 응답을 streaming으로 → UX 개선
3. **병렬 처리**: Agent discovery와 semantic routing을 병렬로 → 0.5초 절약 가능

---

## 디버깅 가이드

### 로그 확인
```python
# Semantic routing 로그
agents/worker_agents/agent_discovery.py:194
logger.info(f"Semantic routing: '{user_request[:50]}...' → {best_category} (score: {best_score:.3f})")

# Delegation 로그
agents/worker_agents/implementations/general_worker.py:150
logger.info(f"Delegation successful, total request: {total_time:.2f}s")

# A2A 통신 로그
agents/a2a_client.py:103
logger.info(f"Using endpoint: {chat_endpoint}")
```

### 로그 파일 위치
```
D:\Data\11_Backend\01_ARR\backend\agents\logs\
├── conversation_20251002.log      # 대화 로그
├── agent_communication_20251002.json  # A2A 통신 로그
└── agent_discovery_20251002.log   # Agent discovery 로그
```

### 일반적인 문제

#### 1. Semantic routing이 잘못된 카테고리로 분류
**원인**: 카테고리 예제가 부족하거나 임계값이 너무 낮음
**해결**: `agent_discovery.py:159-173` 카테고리 예제 추가

#### 2. Delegation 실패 (All connection attempts failed)
**원인**:
- Agent card endpoint가 잘못됨
- Specialist agent가 실행 안됨
**해결**:
- `agents/views.py:59` endpoint 확인
- `settings.A2A_BASE_URL` 확인 (8004 맞는지)

#### 3. UI에서 메시지가 안 보임
**원인**: Delegation marker 파싱 실패
**해결**:
- Browser console 확인
- `chat/templates/chat/index.html:392-393` regex 확인

---

## 확장 가이드

### 새로운 Specialist Agent 추가

#### 1. Worker Agent 구현
**파일**: `agents/worker_agents/implementations/hotel_specialist_worker.py`
```python
class HotelSpecialistWorkerAgent(BaseWorkerAgent):
    @property
    def agent_name(self) -> str:
        return "Hotel Specialist Agent"

    @property
    def system_prompt(self) -> str:
        return "You are a hotel booking specialist..."

    async def _generate_response(self, user_input, ...):
        # Hotel booking 전문 로직
        pass
```

#### 2. Factory 등록
**파일**: `agents/worker_agents/worker_factory.py`
```python
WORKER_TYPES = {
    'hostagent': GeneralWorkerAgent,
    'flight-specialist': FlightSpecialistWorkerAgent,
    'hotel-specialist': HotelSpecialistWorkerAgent,  # 추가
}
```

#### 3. Semantic Routing 카테고리 추가
**파일**: `agents/worker_agents/agent_discovery.py`
```python
self._categories = {
    'greetings': [...],
    'flight_booking': [...],
    'hotel_booking': [  # 추가
        "호텔 예약", "숙박 예약", "hotel reservation",
        "accommodation booking", "숙소 찾아주세요"
    ],
}
```

#### 4. Django Agent 모델 생성
```python
python manage.py shell

from agents.models import Agent

Agent.objects.create(
    slug='hotel-specialist',
    name='Hotel Specialist Agent',
    description='Hotel booking specialist',
    agent_type='worker',
    model_name='gpt-3.5-turbo',
    capabilities=['text', 'hotel_booking'],
    system_prompt='You are a hotel booking specialist...',
    status='active'
)
```

#### 5. UI Avatar 추가
**파일**: `chat/templates/chat/index.html`
```javascript
if (meta.agentSlug === 'flight-specialist') avatarText = '✈️';
else if (meta.agentSlug === 'hotel-specialist') avatarText = '🏨';  // 추가
```

---

## 테스트

### 수동 테스트
```bash
# 1. 서버 실행
python -X utf8 -m daphne -p 8004 backend.asgi:application

# 2. 브라우저 접속
http://localhost:8004/chat/

# 3. 테스트 입력
"비행기 예약해줘"  → ✈️ Flight Specialist
"안녕하세요"      → 🤖 Host Agent
"호텔 예약"       → 🏨 Hotel Specialist (추가 후)
```

### Agent Card 확인
```bash
curl http://localhost:8004/.well-known/agent-card.json
curl http://localhost:8004/.well-known/agent-card/flight-specialist.json
```

---

## 참조

### A2A 프로토콜
- **공식 표준**: https://a2a-protocol.org
- **JSON-RPC 2.0**: https://www.jsonrpc.org/specification
- **Agent Card 스펙**: `/.well-known/agent-card.json` 규격

### 주요 라이브러리
- **sentence-transformers**: Semantic routing 모델
- **LangChain**: LLM 추상화
- **Django Channels**: WebSocket 지원
- **Neo4j**: 대화 히스토리 저장

---

## 요약

### 핵심 파일 (반드시 알아야 할 5개)
1. `chat/consumers.py` - WebSocket entry point
2. `gemini/consumers/handlers/a2a_handler.py` - A2A routing
3. `agents/worker_agents/implementations/general_worker.py` - Host Agent
4. `agents/worker_agents/agent_discovery.py` - Semantic routing
5. `agents/a2a_client.py` - A2A 통신

### 핵심 개념
1. **Host Agent**: 조정자 역할, semantic routing으로 delegation
2. **Specialist Agents**: 도메인 전문가
3. **Semantic Routing**: Sentence transformer로 의도 분류
4. **A2A Protocol**: JSON-RPC 2.0 기반 agent 통신
5. **Delegation Marker**: UI에서 파싱해서 specialist 메시지만 표시

### 유지보수 포인트
- **Semantic routing 정확도**: `agent_discovery.py` 카테고리 예제 관리
- **Agent card endpoints**: `agents/views.py` + `settings.A2A_BASE_URL`
- **UI delegation parsing**: `chat/templates/chat/index.html` regex
- **성능**: Agent card 캐싱 고려
