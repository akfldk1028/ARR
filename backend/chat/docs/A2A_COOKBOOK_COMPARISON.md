# A2A Official Cookbook vs Our Implementation

## 공식 Cookbook 분석

**위치**: `D:\Data\11_Backend\01_ARR\backend\cookbook\a2a_mcp\`

### 핵심 아키텍처

```
공식 Cookbook:
User → Orchestrator Agent → MCP Server (Registry) → Task Agents
                         ↓
                    Planner Agent
```

**우리 시스템:**
```
User → Host Agent (Orchestrator) → Semantic Routing → Specialist Agents
                                 ↓
                         Django DB (Registry)
```

---

## 주요 차이점

### 1. Agent Registry ⭐

**공식 (MCP Server):**
- **장점**:
  - MCP 표준 사용 (Model Context Protocol)
  - `find_agent` tool로 동적 agent 검색
  - Vector embedding으로 semantic matching
  - 중앙화된 registry 서버
- **단점**:
  - 별도 MCP 서버 필요 (port 10100)
  - 복잡한 설정

**우리 (Django DB):**
- **장점**:
  - Django 통합 (별도 서버 불필요)
  - Admin UI로 agent 관리 가능
  - 간단한 설정
- **단점**:
  - MCP 표준 아님
  - Semantic matching이 agent_discovery.py에 하드코딩됨
  - Agent card 캐싱 없음 (매번 HTTP)

**개선 방향:**
→ Django DB 유지하되, MCP-like API 추가 고려 (선택사항)

---

### 2. Agent Card 형식 ⭐⭐⭐

**공식:**
```json
{
    "name": "Air Ticketing Agent",
    "description": "Helps book air tickets given a criteria",
    "url": "http://localhost:10103/",
    "version": "1.0.0",
    "capabilities": {
        "streaming": true,
        "pushNotifications": true,
        "stateTransitionHistory": false
    },
    "skills": [
        {
            "id": "book_air_tickets",
            "name": "Book Air Tickets",
            "description": "Helps with booking air tickets",
            "tags": ["Book air tickets"],
            "examples": ["Book return tickets from SFO to LHR..."]
        }
    ]
}
```

**우리 (현재 - agents/views.py):**
```json
{
    "name": "Flight Specialist Agent",
    "description": "Specialized agent for flight booking",
    "capabilities": ["text", "flight_booking"],
    "skills": [
        {
            "name": "chat",
            "description": "General conversation",
            "type": "chat_completion"
        }
    ],
    "endpoints": {
        "chat": "http://localhost:8004/agents/flight-specialist/chat/",
        "jsonrpc": "http://localhost:8004/agents/flight-specialist/chat/"
    }
}
```

**차이점:**
1. ✅ 공식: `capabilities` 객체 (streaming, pushNotifications, stateTransitionHistory)
   - 우리: `capabilities` 리스트 (간단하지만 표준 아님)

2. ✅ 공식: `skills.examples` 있음 (LLM matching에 사용)
   - 우리: `skills.examples` 없음 → **추가 필요!**

3. ✅ 공식: `skills.tags` 있음
   - 우리: 없음 → **추가 필요!**

4. ✅ 공식: `url` 필드 (agent base URL)
   - 우리: `endpoints` 객체로 분리 (더 명확함, 유지)

**개선:**
Django Agent 모델에 추가:
```python
class Agent(models.Model):
    # ... 기존 필드 ...
    skill_examples = models.JSONField(default=list)  # NEW!
    # 예: ["Book flights from Seoul to Tokyo", "Find cheapest airline tickets"]

    skill_tags = models.JSONField(default=list)  # NEW!
    # 예: ["flight booking", "airline tickets", "travel"]
```

---

### 3. Agent Discovery 방식 ⭐⭐⭐

**공식 (MCP Server + Vector Embedding):**
```python
# MCP Server has a `find_agent` tool
# Uses sentence embeddings to find best matching agent
def find_agent(query: str) -> AgentCard:
    # 1. Embed query
    query_embedding = model.encode(query)

    # 2. Embed all agent cards (name + description + examples)
    agent_embeddings = [
        model.encode(f"{agent.name} {agent.description} {' '.join(agent.skill_examples)}")
        for agent in all_agents
    ]

    # 3. Find most similar
    best_match = max(cosine_similarity(query_embedding, agent_embeddings))

    return best_match_agent
```

**우리 (Hardcoded Categories + LLM Selection):**
```python
# agent_discovery.py
self._categories = {
    'greetings': ["안녕하세요", "hello", ...],  # Hardcoded!
    'flight_booking': ["비행기 예약", ...],     # Hardcoded!
}

# 1. Semantic routing (category 분류)
best_category = semantic_model.predict(query)  # flight_booking

# 2. Agent discovery (HTTP로 agent cards 읽기)
available_agents = await discover_available_agents()  # HTTP 3회!

# 3. LLM selection
selected_agent = await llm.ainvoke("Select best agent for: {query}")
```

**장단점 비교:**

| 방식 | 장점 | 단점 |
|------|------|------|
| 공식 (Vector) | - Agent metadata로 자동 매칭<br>- 새 agent 추가 시 코드 수정 불필요<br>- 더 유연함 | - Vector DB 또는 embedding 연산 필요<br>- MCP Server 의존성 |
| 우리 (Category + LLM) | - Category 기반으로 명확함<br>- LLM으로 최종 판단 (정확도 높음) | - Category 하드코딩됨<br>- 새 agent 추가 시 코드 수정 필요<br>- Agent discovery HTTP 느림 |

**개선 방향:**
1. **Phase 1** (즉시): Category를 Django DB로 이동 (CODE_REVIEW_AND_IMPROVEMENTS.md Phase 2)
2. **Phase 2** (나중): MCP-style vector embedding 고려 (선택사항)

---

### 4. Orchestrator vs Host Agent

**공식 (Orchestrator Agent):**
```python
# orchestrator_agent.py
class OrchestratorAgent:
    def execute(self, user_query):
        # 1. Call Planner Agent to get task plan
        plan = await planner_agent.plan(user_query)

        # 2. For each task in plan:
        for task in plan.tasks:
            # 2a. Find best agent for task
            agent_card = await mcp_server.find_agent(task.query)

            # 2b. Execute task with selected agent
            result = await a2a_client.send(agent_card.url, task)

            # 2c. Store result
            results.append(result)

        # 3. Summarize results
        summary = await llm.summarize(results)
        return summary
```

**우리 (Host Agent):**
```python
# general_worker.py
class GeneralWorkerAgent:
    async def _generate_response(self, user_input, ...):
        # 1. Semantic routing (delegation 여부 결정)
        should_delegate, target_agent = await self.discovery_service.should_delegate_request(user_input)

        if should_delegate:
            # 2. Communicate with specialist
            specialist_response = await self.communicate_with_agent(target_agent, user_input)

            # 3. Return specialist response directly (No summarization!)
            return f"[DELEGATION_OCCURRED:{target_agent}][SPECIALIST_RESPONSE:{specialist_response}]"

        # 4. Or handle directly
        return await self.llm.ainvoke(messages)
```

**차이점:**
1. ✅ 공식: **Planner Agent 분리** (복잡한 multi-step 작업 가능)
   - 우리: Semantic routing only (single delegation만 가능)

2. ✅ 공식: **Task plan 생성** → 여러 agent에게 순차적으로 위임
   - 우리: 한 번만 위임 (specialist → host)

3. ✅ 공식: **Result summarization** (orchestrator가 종합)
   - 우리: Specialist 응답을 그대로 전달 (더 간단, 더 빠름!)

**언제 Planner가 필요한가?**
- ❌ 단순 질문 ("비행기 예약해줘") → Planner 불필요, 우리 방식이 더 빠름
- ✅ 복잡한 작업 ("프랑스 여행 계획 세워줘: 항공편 + 호텔 + 렌터카") → Planner 필요

**우리 시스템에 Planner 추가 여부:**
- **현재**: 불필요 (단순 delegation만 필요)
- **나중**: Multi-agent orchestration 필요하면 추가 고려

---

### 5. A2A Communication

**공식:**
- ADK (Agent Development Kit) 사용
- JSON-RPC 2.0 표준 준수
- Streaming 지원
- Push notifications 지원

**우리:**
- 직접 구현 (`agents/a2a_client.py`)
- JSON-RPC 2.0 표준 준수 ✅
- Streaming 미지원 ❌
- Push notifications 미지원 ❌

**개선 필요 여부:**
- Streaming: ✅ **추가 권장** (UX 개선)
- Push notifications: ⚠️ 선택사항 (복잡한 작업에만 필요)

---

## 우리 시스템 vs 공식 Cookbook 요약

| 항목 | 공식 Cookbook | 우리 시스템 | 개선 필요 |
|------|---------------|-------------|-----------|
| **Registry** | MCP Server (Vector DB) | Django DB | ⚠️ 선택 (MCP는 overkill) |
| **Agent Card** | 표준 형식 (`skills.examples`, `tags`) | 간단한 형식 | ✅ **필수** (examples, tags 추가) |
| **Discovery** | Vector embedding | Semantic routing + LLM | ⚠️ 중간 (Category를 DB로 이동) |
| **Orchestration** | Planner Agent 분리 | Host Agent 내장 | ❌ 불필요 (단순 작업에는 overkill) |
| **Streaming** | 지원 | 미지원 | ✅ **권장** (UX 개선) |
| **Agent 관리** | JSON 파일 | Django Admin | ✅ **더 좋음** (GUI 관리) |

---

## 즉시 적용할 개선사항 (High Priority)

### 1. Agent Card 표준화 (필수!)

**Django 모델 확장:**
```python
# agents/models.py
class Agent(models.Model):
    # ... 기존 필드 ...

    # A2A 표준 필드 추가
    version = models.CharField(max_length=20, default='1.0.0')

    skill_examples = models.JSONField(
        default=list,
        help_text="Examples of what this agent can do. Used for agent discovery."
    )
    # 예: ["Book flights from Seoul to Tokyo", "Find cheapest airline tickets"]

    skill_tags = models.JSONField(
        default=list,
        help_text="Tags for skill categorization. Used for filtering."
    )
    # 예: ["flight booking", "airline tickets", "travel"]

    capabilities_config = models.JSONField(
        default=dict,
        help_text="A2A capabilities: streaming, pushNotifications, etc."
    )
    # 예: {"streaming": false, "pushNotifications": false}
```

**Migration:**
```bash
python manage.py makemigrations agents
python manage.py migrate agents
```

**Agent Card 생성 업데이트 (agents/views.py):**
```python
card_data = {
    "name": agent.name,
    "description": agent.description,
    "url": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/",
    "version": agent.version,
    "capabilities": agent.capabilities_config or {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False
    },
    "skills": [
        {
            "id": agent.slug,
            "name": agent.name,
            "description": agent.description,
            "tags": agent.skill_tags,
            "examples": agent.skill_examples
        }
    ],
    "endpoints": {
        "chat": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/",
        "jsonrpc": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/"
    }
}
```

**기존 Agent 데이터 업데이트:**
```python
# Management command
from agents.models import Agent

Agent.objects.filter(slug='flight-specialist').update(
    version='1.0.0',
    skill_examples=[
        "Book flights from Seoul to Tokyo",
        "Find cheapest airline tickets",
        "비행기 예약해줘",
        "항공편 찾아줘"
    ],
    skill_tags=["flight booking", "airline tickets", "travel", "항공권"],
    capabilities_config={
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False
    }
)
```

---

### 2. Agent Discovery 개선 (중요)

**Option A: 공식처럼 Vector Embedding 사용**
```python
# agents/worker_agents/agent_discovery.py
from sentence_transformers import SentenceTransformer

class AgentDiscoveryService:
    def __init__(self, llm):
        self.llm = llm
        self.model = SentenceTransformer('distiluse-base-multilingual-cased-v2')

    async def find_best_agent(self, query: str) -> str:
        # 1. Get all active agents
        agents = await sync_to_async(list)(
            Agent.objects.filter(status='active')
        )

        # 2. Embed query
        query_embedding = self.model.encode([query])[0]

        # 3. Embed agent cards (name + description + examples)
        agent_embeddings = []
        for agent in agents:
            text = f"{agent.name} {agent.description} {' '.join(agent.skill_examples)}"
            embedding = self.model.encode([text])[0]
            agent_embeddings.append((agent.slug, embedding))

        # 4. Find most similar
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = [
            (slug, cosine_similarity([query_embedding], [emb])[0][0])
            for slug, emb in agent_embeddings
        ]

        best_agent = max(similarities, key=lambda x: x[1])
        return best_agent[0]  # Return slug
```

**Option B: 기존 방식 + DB Categories (간단, 추천!)**
→ 이미 CODE_REVIEW_AND_IMPROVEMENTS.md Phase 2에 있음

---

### 3. Management Commands (유지보수성)

**공식처럼 간편한 agent 관리:**
```bash
# 새 Agent 추가
python manage.py create_agent hotel-specialist \
    --name "Hotel Specialist" \
    --description "Hotel booking expert" \
    --examples "Book hotel in Paris" "Find 5-star hotels" \
    --tags "hotel" "accommodation" \
    --worker-class "agents.worker_agents.implementations.hotel_specialist_worker.HotelSpecialistWorkerAgent"

# Agent 리스트
python manage.py list_agents

# Agent 제거
python manage.py delete_agent hotel-specialist
```

→ 이미 CODE_REVIEW_AND_IMPROVEMENTS.md Phase 5에 있음

---

## 나중에 고려할 개선사항 (Low Priority)

### 1. MCP Server 통합 (선택사항)

**언제 필요?**
- 다른 시스템과 agent 공유 필요할 때
- 표준 MCP 클라이언트 지원 필요할 때

**현재**: 불필요 (Django만으로 충분)

---

### 2. Planner Agent 추가 (선택사항)

**언제 필요?**
- Multi-step 작업 ("프랑스 여행 계획: 항공편 + 호텔 + 렌터카")
- Task dependency 관리 필요할 때

**현재**: 불필요 (단순 delegation만 필요)

**추가 시 구조:**
```python
# agents/worker_agents/implementations/planner_worker.py
class PlannerWorkerAgent(BaseWorkerAgent):
    async def _generate_response(self, user_input, ...):
        # LLM으로 task plan 생성
        plan = await self.llm.ainvoke(f"Create a task plan for: {user_input}")

        # JSON 형태로 반환
        return {
            "tasks": [
                {"type": "flight_booking", "query": "Book flight Seoul to Paris"},
                {"type": "hotel_booking", "query": "Book hotel in Paris 5 days"},
                {"type": "car_rental", "query": "Rent car in Paris"}
            ]
        }
```

---

### 3. Streaming 지원 (권장!)

**공식처럼 SSE (Server-Sent Events) 사용:**
```python
# agents/views.py
async def stream_response(request, agent_slug):
    response = StreamingHttpResponse(
        stream_generator(agent_slug, request.body),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

async def stream_generator(agent_slug, message):
    worker = await worker_manager.get_worker(agent_slug)
    async for chunk in worker.stream_response(message):
        yield f"data: {json.dumps({'text': chunk})}\n\n"
```

**장점:**
- UX 개선 (응답이 점진적으로 표시됨)
- 긴 응답도 빠르게 보임

---

## 최종 권장사항

### 즉시 적용 (High Priority)
1. ✅ **Agent Card 표준화** (skill_examples, skill_tags 추가)
2. ✅ **Semantic Routing 동적화** (Django DB로 categories 이동)
3. ✅ **Management Commands** (create_agent, list_agents, delete_agent)

### 나중에 고려 (Low Priority)
4. ⚠️ **Vector Embedding Discovery** (agent discovery 성능 개선)
5. ⚠️ **Streaming 지원** (UX 개선)
6. ❌ **MCP Server** (현재 불필요)
7. ❌ **Planner Agent** (현재 불필요)

---

## 구현 순서

**Week 1: Agent Card 표준화**
1. Django 모델 확장 (skill_examples, skill_tags)
2. Migration
3. agents/views.py 업데이트 (A2A 표준 형식)
4. 기존 Agent 데이터 업데이트

**Week 2: Discovery 개선**
5. agent_discovery.py 리팩토링 (categories → DB)
6. Agent card 캐싱 추가

**Week 3: Management Commands**
7. create_agent command
8. list_agents command
9. delete_agent command

**Week 4+: 선택사항**
10. Streaming 지원 (UX 개선)
11. Vector embedding discovery (성능 개선)

---

## Cookbook 참조 파일

| 공식 Cookbook | 우리 시스템 | 역할 |
|---------------|-------------|------|
| `orchestrator_agent.py` | `agents/worker_agents/implementations/general_worker.py` | Orchestration |
| `adk_travel_agent.py` | `agents/worker_agents/implementations/flight_specialist_worker.py` | Specialist |
| `mcp/server.py` | `agents/views.py` (Django) | Agent Registry |
| `agent_executor.py` | `agents/worker_agents/worker_manager.py` | Worker Management |
| `agent_cards/*.json` | `agents.models.Agent` (DB) | Agent Metadata |

---

## 결론

### 우리 시스템의 강점
✅ Django 통합 (별도 서버 불필요)
✅ Admin UI (GUI 관리)
✅ 간단한 아키텍처 (Planner 없어도 됨)
✅ 빠른 응답 (No multi-step orchestration)

### 개선 필요
⚠️ Agent Card 표준화 (skill_examples, tags)
⚠️ Semantic Routing 동적화 (DB로 이동)
⚠️ Management Commands (Agent 관리 편의성)

### 공식 Cookbook과의 차이
- 공식은 **복잡한 Multi-agent Orchestration**에 최적화
- 우리는 **단순하고 빠른 Delegation**에 최적화
- **목적이 다르므로 모두 따를 필요 없음!**

### 최종 목표
**간단하고 유지보수하기 쉬운 A2A 시스템**
- Agent 추가/제거가 코드 수정 없이 가능
- A2A 표준 준수 (interoperability)
- Django와 자연스럽게 통합
