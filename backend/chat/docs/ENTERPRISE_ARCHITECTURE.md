# ENTERPRISE A2A Architecture - JSON Cards + Dual Routing System

## Executive Summary

### User Requirements (ENTERPRISE-Grade)
1. **유지보수가 제일중요해** - Maintainability is MOST important
2. **JSON CARD는 무조건잇어야하지** - JSON cards MUST exist as source of truth
3. **복잡한 Multi-agent Orchestration** - Must support complex multi-agent orchestration
4. **속도를 유지하면서** - While maintaining current speed (5-9 seconds)

### Solution Overview
**Hybrid Architecture** combining:
- ✅ JSON agent cards as **source of truth** (not Django DB)
- ✅ **Dual routing system**: Fast path (semantic) + Complex path (orchestrator/planner)
- ✅ Django DB as **query cache** synced from JSON cards
- ✅ **A2A standard compliance** with Google/Linux Foundation official format
- ✅ **Enterprise maintainability** with no hardcoded categories or agent types

---

## Current System Problems

### Problem 1: JSON Cards Exist But Are IGNORED ❌

**Current Broken Flow:**
```
JSON Cards (agents/worker_agents/cards/*.json)
    ↓ [IGNORED]
Django Agent Model (agents/models.py)
    ↓ [SOURCE OF TRUTH]
AgentCardView (agents/views.py) → Generates cards from DB
    ↓
Worker Factory → Hardcoded WORKER_TYPES
```

**Why This Is Wrong:**
- JSON cards exist but are decoration only
- Django views **generate** agent cards from DB (should **serve** JSON files)
- Worker factory has **hardcoded** agent types (not maintainable)
- Cannot add/remove agents without code changes (not ENTERPRISE-grade)

### Problem 2: Only Simple Delegation (No Complex Orchestration)

**Current Flow:**
```
User: "서울에서 도쿄 비행기 예약하고 호텔도 알아봐줘"
    ↓
hostagent (semantic routing)
    ↓
flight-specialist (only handles flights)
    ❌ Hotel booking is lost!
```

**Missing Capability:**
- Cannot handle multi-step tasks requiring multiple specialists
- No task planning/decomposition agent
- No parallel specialist coordination
- Official cookbook has Orchestrator → Planner → Multiple Specialists

### Problem 3: Hardcoded Categories in Semantic Routing

**Location:** `agents/worker_agents/agent_discovery.py:200`
```python
self._categories = {
    'greetings': [...],
    'flight_booking': [...],
    'hotel_booking': [...]  # Hardcoded!
}
```

**Why This Is Wrong:**
- Adding new specialist requires code change
- Not maintainable at ENTERPRISE scale
- Categories should come from agent card `skills` field

---

## Enterprise Architecture Design

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    WebSocket Consumer                        │
│                  (chat/consumers.py)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Complexity Detection  │
              │ (Query Analyzer)      │
              └──────────┬────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌─────────────────┐            ┌─────────────────────┐
│   FAST PATH     │            │   COMPLEX PATH      │
│  (Simple Query) │            │ (Multi-step Task)   │
│   5-9 seconds   │            │   10-15 seconds     │
└─────────────────┘            └─────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐            ┌─────────────────────┐
│   hostagent     │            │  orchestrator       │
│ (Semantic Route)│            │    (Entry Point)    │
└────────┬────────┘            └──────────┬──────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────┐            ┌─────────────────────┐
│  Specialist     │            │   planner           │
│ (Single Agent)  │            │ (Task Breakdown)    │
└─────────────────┘            └──────────┬──────────┘
                                           │
                                           ▼
                              ┌────────────────────────┐
                              │  Multiple Specialists  │
                              │  (Parallel Execution)  │
                              │  - flight-specialist   │
                              │  - hotel-specialist    │
                              │  - car-rental          │
                              └────────────────────────┘

                    ┌──────────────────────────┐
                    │   JSON CARDS             │
                    │   (Source of Truth)      │
                    │  *.json files in cards/  │
                    └────────────┬─────────────┘
                                 │ sync on startup
                                 ▼
                    ┌──────────────────────────┐
                    │   Django Agent Model     │
                    │   (Query Cache)          │
                    │  - Fast lookups          │
                    │  - Admin UI              │
                    │  - Neo4j integration     │
                    └──────────────────────────┘
```

### Core Principles

1. **JSON Cards as Source of Truth**
   - All agent definitions in JSON format (A2A standard)
   - Loaded and synced to Django DB on startup
   - DB is cache only, not source of truth

2. **Dual Routing System**
   - **Fast Path**: Simple queries → semantic routing → single specialist (80% of queries)
   - **Complex Path**: Multi-step tasks → orchestrator → planner → multiple specialists (20% of queries)

3. **Dynamic Discovery**
   - Worker factory reads JSON cards (no hardcoding)
   - Semantic routing reads skills from cards (no hardcoded categories)
   - Add new agents by adding JSON file + restart

4. **A2A Standard Compliance**
   - Official agent card format
   - JSON-RPC 2.0 protocol
   - MCP-compatible discovery

---

## JSON Card Standardization

### Official A2A Format (Required Fields)

Based on cookbook at `D:\Data\11_Backend\01_ARR\backend\cookbook\a2a_mcp\agent_cards\`:

```json
{
  "name": "Flight Specialist Agent",
  "description": "Helps with booking air tickets given a criteria",
  "url": "http://localhost:8004/agents/flight-specialist",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "defaultInputModes": ["text", "text/plain"],
  "defaultOutputModes": ["text", "text/plain"],
  "skills": [
    {
      "id": "book_flights",
      "name": "Book Air Tickets",
      "description": "Helps with booking air tickets given a criteria",
      "tags": ["flight", "airline", "booking", "비행기", "항공권"],
      "examples": [
        "Book return tickets from Seoul to Tokyo",
        "서울에서 도쿄 비행기 예약해줘",
        "Find flights from SFO to LHR starting June 24"
      ]
    }
  ]
}
```

### Hybrid Format (A2A + Django Compatibility)

Our cards need **both** official A2A fields AND Django-specific fields:

```json
{
  // ========== A2A OFFICIAL STANDARD ==========
  "name": "Flight Specialist Agent",
  "description": "Specialized agent for flight booking and travel information",
  "url": "http://localhost:8004/agents/flight-specialist",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "defaultInputModes": ["text", "text/plain"],
  "defaultOutputModes": ["text", "text/plain"],
  "skills": [
    {
      "id": "book_flights",
      "name": "Book Air Tickets",
      "description": "Search and book flights between cities",
      "tags": ["flight", "airline", "booking", "비행기", "항공권", "예약"],
      "examples": [
        "서울에서 도쿄 비행기 예약해줘",
        "Book flights from Seoul to Tokyo",
        "Find airline tickets SFO to LHR"
      ]
    },
    {
      "id": "airline_info",
      "name": "Airline Information",
      "description": "Provide airline information and recommendations",
      "tags": ["airline", "information", "항공사", "정보"],
      "examples": [
        "대한항공 정보 알려줘",
        "Which airlines fly to Tokyo?",
        "Best airlines for international flights"
      ]
    }
  ],

  // ========== DJANGO CUSTOM EXTENSIONS ==========
  "django": {
    "agent_type": "specialist",
    "worker_class": "FlightSpecialistWorkerAgent",
    "model_config": {
      "provider": "openai",
      "model_name": "gpt-3.5-turbo",
      "temperature": 0.3,
      "max_tokens": 1024
    },
    "neo4j_enabled": true,
    "a2a_enabled": true
  }
}
```

### Key Changes from Current Cards

**Current (Wrong):**
- Missing: `url`, `capabilities` object, `defaultInputModes/OutputModes`
- Skills missing: `id`, `tags`, `examples`
- Custom fields at root level (not organized)

**New (Enterprise):**
- ✅ All A2A official fields at root level
- ✅ Skills with proper `id`, `tags`, `examples` for discovery
- ✅ Django-specific fields in `"django"` section (clear separation)
- ✅ `url` field for A2A endpoint discovery
- ✅ `tags` for semantic routing (replaces hardcoded categories)

---

## Dual Routing System Implementation

### Query Complexity Detection

**Location:** `chat/consumers.py` (new method)

```python
class ChatConsumer(AsyncWebsocketConsumer):

    async def _detect_query_complexity(self, user_message: str) -> str:
        """
        Determine if query needs simple delegation or complex orchestration

        Returns:
            'simple' - Fast path (semantic routing)
            'complex' - Complex path (orchestrator → planner)
        """
        # Indicators of complex multi-step tasks
        complex_indicators = [
            # Multiple service requests
            r'(비행기|flight).*(호텔|hotel)',
            r'(호텔|hotel).*(렌트카|rental)',
            r'(예약|book).*(그리고|and).*(예약|book)',

            # Sequential planning
            r'(먼저|first).*(다음|then|next)',
            r'(plan|계획).*(trip|여행)',

            # Multiple locations/dates
            r'(\d+박\s*\d+일)|(\d+\s*nights)',
            r'(왕복|round.?trip)',
        ]

        for pattern in complex_indicators:
            if re.search(pattern, user_message, re.IGNORECASE):
                logger.info(f"Complex query detected: {user_message[:50]}...")
                return 'complex'

        logger.info(f"Simple query detected: {user_message[:50]}...")
        return 'simple'
```

### Fast Path Flow (Current System - Enhanced)

**When:** Simple, single-purpose queries (80% of traffic)

**Flow:**
1. User: "서울에서 도쿄 비행기 예약해줘"
2. WebSocket → ChatConsumer → Complexity Detection → **SIMPLE**
3. hostagent (semantic routing using skill tags from JSON cards)
4. Delegate to flight-specialist
5. Return response (5-9 seconds)

**Code Location:** `agents/worker_agents/implementations/general_worker.py`

**Enhancement Needed:**
```python
# OLD: Hardcoded categories
self._categories = {
    'flight_booking': ["비행기 예약", "book flight", ...]
}

# NEW: Load from JSON card skills
async def _load_categories_from_cards(self):
    """Load semantic categories from agent card skills"""
    cards_dir = Path(__file__).parent.parent / 'cards'

    self._categories = {}

    for card_file in cards_dir.glob('*_card.json'):
        with open(card_file) as f:
            card = json.load(f)

        agent_slug = card_file.stem.replace('_card', '')

        for skill in card.get('skills', []):
            skill_id = skill['id']

            # Create category from skill tags and examples
            if skill_id not in self._categories:
                self._categories[skill_id] = []

            # Add tags as category examples
            self._categories[skill_id].extend(skill.get('tags', []))

            # Add examples as category examples
            self._categories[skill_id].extend(skill.get('examples', []))

    logger.info(f"Loaded {len(self._categories)} categories from JSON cards")
```

### Complex Path Flow (New - Orchestrator Pattern)

**When:** Multi-step tasks requiring multiple specialists (20% of traffic)

**Flow:**
1. User: "서울에서 도쿄 3박4일 여행 계획해줘. 비행기랑 호텔 예약하고 관광지 추천도 해줘"
2. WebSocket → ChatConsumer → Complexity Detection → **COMPLEX**
3. orchestrator agent (new) - Analyzes full request
4. Calls planner agent (new) - Breaks down into tasks:
   ```
   Task 1: Book round-trip flight Seoul → Tokyo
   Task 2: Book hotel 3 nights in Tokyo
   Task 3: Recommend tourist attractions in Tokyo
   ```
5. orchestrator executes specialists in parallel:
   - flight-specialist (Task 1)
   - hotel-specialist (Task 2)
   - general-assistant (Task 3)
6. Aggregate results and return (10-15 seconds)

**New Agents Needed:**

#### 1. Orchestrator Agent

**File:** `agents/worker_agents/implementations/orchestrator_worker.py`

```python
class OrchestratorWorkerAgent(BaseWorkerAgent):
    """
    Orchestrator agent that coordinates complex multi-agent workflows
    Inspired by official A2A cookbook orchestrator pattern
    """

    async def _generate_response(self, user_input: str, context_id: str,
                                 session_id: str, user_name: str) -> str:
        logger.info(f"Orchestrator processing complex request: {user_input}")

        # Step 1: Call planner to break down tasks
        planner_response = await self.communicate_with_agent(
            target_agent_slug='planner',
            message=f"Break down this request into executable tasks: {user_input}",
            context_id=context_id
        )

        # Parse planner response to get task list
        tasks = self._parse_planner_response(planner_response)
        logger.info(f"Planner generated {len(tasks)} tasks")

        # Step 2: Execute specialists in parallel
        specialist_results = await asyncio.gather(*[
            self._execute_task(task, context_id)
            for task in tasks
        ])

        # Step 3: Aggregate results
        final_response = self._aggregate_results(tasks, specialist_results)

        return final_response

    async def _execute_task(self, task: dict, context_id: str) -> str:
        """Execute a single task by delegating to appropriate specialist"""
        target_agent = task['agent_slug']
        task_description = task['description']

        result = await self.communicate_with_agent(
            target_agent_slug=target_agent,
            message=task_description,
            context_id=context_id
        )

        return result
```

#### 2. Planner Agent (LangGraph-based)

**File:** `agents/worker_agents/implementations/planner_worker.py`

```python
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI

class PlannerWorkerAgent(BaseWorkerAgent):
    """
    Task planner agent using LangGraph
    Breaks down complex requests into actionable tasks
    """

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # Initialize LangGraph planner
        self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        self.graph = self._build_planning_graph()

    def _build_planning_graph(self) -> StateGraph:
        """Build LangGraph for task planning"""
        graph = StateGraph(MessagesState)

        # Define planning steps
        graph.add_node("analyze", self._analyze_request)
        graph.add_node("decompose", self._decompose_tasks)
        graph.add_node("assign", self._assign_agents)

        # Define flow
        graph.add_edge("analyze", "decompose")
        graph.add_edge("decompose", "assign")
        graph.set_entry_point("analyze")
        graph.set_finish_point("assign")

        return graph.compile()

    async def _generate_response(self, user_input: str, context_id: str,
                                 session_id: str, user_name: str) -> str:
        """Generate task breakdown plan"""

        # Run planning graph
        result = await self.graph.ainvoke({
            "messages": [HumanMessage(content=user_input)]
        })

        # Extract task plan from graph result
        task_plan = self._extract_task_plan(result)

        # Return as JSON for orchestrator
        return json.dumps(task_plan, ensure_ascii=False)
```

---

## Implementation Phases

### Phase 1: Standardize JSON Cards (Week 1) 🔧

**Goal:** Make JSON cards the source of truth

**Tasks:**
1. Update all JSON cards to A2A official format
   - Add `url`, `capabilities`, `defaultInputModes/OutputModes`
   - Standardize `skills` with `id`, `tags`, `examples`
   - Move Django-specific fields to `"django"` section

2. Create card loader utility
   ```python
   # agents/worker_agents/card_loader.py
   class AgentCardLoader:
       @staticmethod
       def load_all_cards() -> Dict[str, dict]:
           """Load all JSON cards from cards/ directory"""

       @staticmethod
       def sync_to_database(cards: Dict[str, dict]):
           """Sync JSON cards to Django Agent model"""
   ```

3. Update `agents/views.py` to serve JSON files directly
   ```python
   class AgentCardView(APIView):
       def get(self, request, slug):
           # OLD: Generate from Django DB
           # agent = Agent.objects.get(slug=slug)
           # return JsonResponse({...from DB...})

           # NEW: Serve JSON file directly
           card_path = CARDS_DIR / f"{slug}_card.json"
           with open(card_path) as f:
               return JsonResponse(json.load(f))
   ```

4. Create management command for sync
   ```bash
   python manage.py sync_agent_cards
   ```

**Verification:**
- ✅ All cards follow A2A standard format
- ✅ Cards served from JSON files (not DB)
- ✅ Django DB synced as cache for queries

### Phase 2: Dynamic Semantic Routing (Week 2) 🎯

**Goal:** Remove hardcoded categories, read from JSON cards

**Tasks:**
1. Update `agent_discovery.py` to load categories from cards
   - Read `skills[].tags` and `skills[].examples` from JSON
   - Build semantic categories dynamically
   - Cache in memory (reload on restart)

2. Update worker factory to read JSON cards
   ```python
   # agents/worker_agents/worker_factory.py
   class WorkerFactory:
       @classmethod
       def create_worker(cls, agent_slug: str):
           # OLD: Hardcoded WORKER_TYPES
           # worker_class = WORKER_TYPES.get(agent_slug)

           # NEW: Load from JSON card
           card = AgentCardLoader.load_card(agent_slug)
           worker_class_name = card['django']['worker_class']
           worker_class = cls._import_worker_class(worker_class_name)
           return worker_class(agent_slug, card)
   ```

3. Add startup card loading in Django app config
   ```python
   # agents/apps.py
   class AgentsConfig(AppConfig):
       def ready(self):
           # Load and cache all agent cards on startup
           from .worker_agents.card_loader import AgentCardLoader
           AgentCardLoader.cache_all_cards()
   ```

**Verification:**
- ✅ No hardcoded categories or agent types
- ✅ Adding new agent = add JSON file + restart
- ✅ Semantic routing uses skill tags from cards

### Phase 3: Orchestrator & Planner (Week 3-4) 🚀

**Goal:** Enable complex multi-agent orchestration

**Tasks:**
1. Create `orchestrator_worker.py` and `planner_worker.py`
2. Create corresponding JSON cards:
   - `orchestrator_card.json`
   - `planner_card.json`

3. Add complexity detection to ChatConsumer
   ```python
   # chat/consumers.py
   async def _handle_chat_message(self, data):
       user_message = data.get('message', '')

       # Detect query complexity
       complexity = await self._detect_query_complexity(user_message)

       if complexity == 'simple':
           # Fast path: semantic routing (current flow)
           await self.a2a_handler.handle_text(data)
       else:
           # Complex path: orchestrator
           await self._handle_complex_query(user_message)
   ```

4. Implement parallel specialist execution in orchestrator

**Verification:**
- ✅ Simple queries use fast path (5-9s)
- ✅ Complex queries use orchestrator path (10-15s)
- ✅ Multi-specialist coordination works
- ✅ Results properly aggregated

### Phase 4: Performance Optimization (Week 5) ⚡

**Goal:** Maintain speed while adding features

**Tasks:**
1. Implement card caching
   - Load JSON cards once on startup
   - Reload only on file change (watchdog)

2. Implement agent discovery caching
   - Cache semantic routing decisions (5 min TTL)
   - Cache agent card lookups

3. Optimize orchestrator parallel execution
   - Use `asyncio.gather()` for concurrent specialist calls
   - Add timeout protection (45s max)

4. Add performance monitoring
   ```python
   # Timing breakdown
   - Complexity detection: <0.1s
   - Semantic routing: 2-3s (model cached)
   - Specialist response: 3-5s
   - Total (simple): 5-9s

   - Orchestrator analysis: 1-2s
   - Planner breakdown: 2-3s
   - Parallel specialists: 5-7s (max of parallel, not sum)
   - Result aggregation: 1-2s
   - Total (complex): 10-15s
   ```

**Verification:**
- ✅ Simple queries maintain 5-9s speed
- ✅ Complex queries complete in 10-15s
- ✅ No performance regression

---

## Migration Guide

### Step-by-Step Migration

#### Step 1: Update hostagent JSON Card

**File:** `agents/worker_agents/cards/hostagent_card.json`

**Before:**
```json
{
  "name": "Host Agent",
  "agent_type": "hostagent",
  "capabilities": ["text", "conversation"],
  "skills": [
    {
      "name": "semantic_routing",
      "description": "Analyze user intent"
    }
  ]
}
```

**After:**
```json
{
  "name": "Host Agent",
  "description": "Primary coordination agent with semantic routing",
  "url": "http://localhost:8004/agents/hostagent",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "defaultInputModes": ["text", "text/plain"],
  "defaultOutputModes": ["text", "text/plain"],
  "skills": [
    {
      "id": "semantic_routing",
      "name": "Semantic Intent Routing",
      "description": "Analyze user intent and route to specialists",
      "tags": ["routing", "coordination", "delegation"],
      "examples": [
        "User asks about flights - route to flight specialist",
        "User asks about hotels - route to hotel specialist"
      ]
    }
  ],
  "django": {
    "agent_type": "coordinator",
    "worker_class": "GeneralWorkerAgent",
    "model_config": {
      "provider": "openai",
      "model_name": "gpt-3.5-turbo",
      "temperature": 0.7,
      "max_tokens": 2048
    }
  }
}
```

#### Step 2: Update flight-specialist JSON Card

**File:** `agents/worker_agents/cards/flight_specialist_card.json`

**Add skills with tags for semantic routing:**
```json
{
  "skills": [
    {
      "id": "book_flights",
      "name": "Book Air Tickets",
      "description": "Search and book flights between cities",
      "tags": [
        "flight", "flights", "airline", "airlines", "booking",
        "비행기", "항공권", "예약", "항공", "비행"
      ],
      "examples": [
        "서울에서 도쿄 비행기 예약해줘",
        "Book flights from Seoul to Tokyo",
        "Find airline tickets from SFO to LHR",
        "대한항공 도쿄행 알아봐줘",
        "Show me flights to New York next week"
      ]
    }
  ]
}
```

#### Step 3: Create Card Loader

**File:** `agents/worker_agents/card_loader.py`

```python
import json
from pathlib import Path
from typing import Dict
from django.conf import settings

class AgentCardLoader:
    """Load and manage agent cards from JSON files"""

    CARDS_DIR = Path(__file__).parent / 'cards'
    _card_cache: Dict[str, dict] = {}

    @classmethod
    def load_card(cls, agent_slug: str) -> dict:
        """Load a single agent card by slug"""
        if agent_slug in cls._card_cache:
            return cls._card_cache[agent_slug]

        card_path = cls.CARDS_DIR / f"{agent_slug}_card.json"

        if not card_path.exists():
            raise FileNotFoundError(f"Agent card not found: {card_path}")

        with open(card_path, encoding='utf-8') as f:
            card = json.load(f)

        # Add base URL if not present
        if 'url' not in card:
            card['url'] = f"{settings.A2A_BASE_URL}/agents/{agent_slug}"

        cls._card_cache[agent_slug] = card
        return card

    @classmethod
    def load_all_cards(cls) -> Dict[str, dict]:
        """Load all agent cards from cards directory"""
        cards = {}

        for card_file in cls.CARDS_DIR.glob('*_card.json'):
            agent_slug = card_file.stem.replace('_card', '')
            cards[agent_slug] = cls.load_card(agent_slug)

        return cards

    @classmethod
    def sync_to_database(cls):
        """Sync all JSON cards to Django Agent model"""
        from agents.models import Agent

        cards = cls.load_all_cards()

        for agent_slug, card in cards.items():
            # Get or create Agent model
            agent, created = Agent.objects.get_or_create(slug=agent_slug)

            # Update from card
            agent.name = card['name']
            agent.description = card.get('description', '')
            agent.version = card.get('version', '1.0.0')

            # Store full card as JSON
            agent.card_data = card
            agent.save()

            action = "Created" if created else "Updated"
            print(f"{action} agent: {agent_slug} - {agent.name}")
```

#### Step 4: Create Management Command

**File:** `agents/management/commands/sync_agent_cards.py`

```python
from django.core.management.base import BaseCommand
from agents.worker_agents.card_loader import AgentCardLoader

class Command(BaseCommand):
    help = 'Sync JSON agent cards to Django database'

    def handle(self, *args, **options):
        self.stdout.write('Loading agent cards from JSON files...')

        cards = AgentCardLoader.load_all_cards()
        self.stdout.write(f'Found {len(cards)} agent cards')

        self.stdout.write('Syncing to database...')
        AgentCardLoader.sync_to_database()

        self.stdout.write(self.style.SUCCESS('Successfully synced agent cards'))
```

**Usage:**
```bash
python manage.py sync_agent_cards
```

#### Step 5: Update Agent Model

**File:** `agents/models.py`

Add field to store full card data:

```python
from django.db import models
from django.contrib.postgres.fields import JSONField  # or models.JSONField in Django 3.1+

class Agent(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=50, default='1.0.0')

    # Store full card data from JSON
    card_data = models.JSONField(default=dict, blank=True)

    # Existing fields...
    capabilities = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Migration:**
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py sync_agent_cards
```

---

## Performance Strategy

### Speed Targets

| Path | Target | Breakdown |
|------|--------|-----------|
| **Fast Path** | 5-9s | Complexity: 0.1s + Routing: 2-3s + Specialist: 3-5s |
| **Complex Path** | 10-15s | Complexity: 0.1s + Orchestrator: 1-2s + Planner: 2-3s + Specialists (parallel): 5-7s + Aggregate: 1-2s |

### Optimization Techniques

#### 1. Card Caching
```python
# Load once on startup, cache in memory
class AgentCardLoader:
    _card_cache: Dict[str, dict] = {}
    _last_load_time = None

    @classmethod
    def load_card(cls, slug: str) -> dict:
        if slug in cls._card_cache:
            return cls._card_cache[slug]  # Cache hit

        # Load from file and cache
        card = cls._load_from_file(slug)
        cls._card_cache[slug] = card
        return card
```

#### 2. Model Caching (Semantic Routing)
```python
# agents/worker_agents/agent_discovery.py
class AgentDiscoveryService:
    def __init__(self, llm):
        self.llm = llm

        # Load model ONCE and cache (current implementation)
        if not hasattr(self, '_semantic_model'):
            self._semantic_model = SentenceTransformer(
                'distiluse-base-multilingual-cased-v2'
            )
            # First request: ~7-9s (model download)
            # Subsequent: ~2-3s (cached)
```

#### 3. Parallel Specialist Execution
```python
# agents/worker_agents/implementations/orchestrator_worker.py
async def _execute_tasks_parallel(self, tasks: List[dict]) -> List[str]:
    """Execute multiple specialist tasks in parallel"""

    # Run all specialists concurrently
    results = await asyncio.gather(*[
        self.communicate_with_agent(
            target_agent_slug=task['agent'],
            message=task['description'],
            context_id=self.context_id
        )
        for task in tasks
    ], return_exceptions=True)

    # Time = max(individual times), not sum!
    # 3 specialists @ 5s each = 5s total (not 15s)
    return results
```

#### 4. Request Timeout Protection
```python
# Prevent slow requests from blocking
specialist_response = await asyncio.wait_for(
    self.communicate_with_agent(...),
    timeout=45.0  # Max 45 seconds
)
```

### Performance Monitoring

Add timing logs to track performance:

```python
import time

class ChatConsumer(AsyncWebsocketConsumer):
    async def _handle_chat_message(self, data):
        start_time = time.time()

        # Complexity detection
        complexity_start = time.time()
        complexity = await self._detect_query_complexity(data['message'])
        logger.info(f"⏱ Complexity detection: {time.time() - complexity_start:.2f}s")

        if complexity == 'simple':
            # Fast path
            path_start = time.time()
            await self.a2a_handler.handle_text(data)
            total_time = time.time() - start_time
            logger.info(f"⏱ FAST PATH total: {total_time:.2f}s")
        else:
            # Complex path
            path_start = time.time()
            await self._handle_complex_query(data['message'])
            total_time = time.time() - start_time
            logger.info(f"⏱ COMPLEX PATH total: {total_time:.2f}s")
```

---

## Testing the New Architecture

### Test 1: Simple Query (Fast Path)

**Input:**
```
서울에서 도쿄 비행기 예약해줘
```

**Expected Flow:**
1. Complexity detection → SIMPLE (0.1s)
2. hostagent semantic routing → flight_booking category (2-3s)
3. Delegate to flight-specialist (3-5s)
4. **Total: 5-9 seconds** ✅

**Verify:**
- Only flight-specialist responds
- No orchestrator or planner involved
- Single WebSocket message to UI

### Test 2: Complex Query (Complex Path)

**Input:**
```
서울에서 도쿄 3박4일 여행 계획해줘. 비행기랑 호텔 예약하고 맛집도 추천해줘
```

**Expected Flow:**
1. Complexity detection → COMPLEX (0.1s)
2. Orchestrator analyzes request (1-2s)
3. Planner breaks down:
   - Task 1: Book round-trip flight Seoul-Tokyo
   - Task 2: Book hotel 3 nights Tokyo
   - Task 3: Recommend restaurants in Tokyo
4. Execute specialists in parallel (5-7s max):
   - flight-specialist (5s)
   - hotel-specialist (6s)
   - restaurant-specialist (4s)
   - **Parallel time = 6s** (not 15s!)
5. Aggregate results (1-2s)
6. **Total: 10-15 seconds** ✅

**Verify:**
- All three specialists respond
- Results aggregated properly
- UI shows combined response

### Test 3: Adding New Agent

**Scenario:** Add a new `restaurant-specialist` agent

**Steps:**
1. Create `restaurant_specialist_card.json`:
   ```json
   {
     "name": "Restaurant Specialist",
     "url": "http://localhost:8004/agents/restaurant-specialist",
     "skills": [
       {
         "id": "recommend_restaurants",
         "tags": ["restaurant", "맛집", "음식점", "food"],
         "examples": ["도쿄 맛집 추천해줘", "Best sushi in Tokyo"]
       }
     ],
     "django": {
       "worker_class": "RestaurantSpecialistWorkerAgent"
     }
   }
   ```

2. Create `restaurant_specialist_worker.py`:
   ```python
   class RestaurantSpecialistWorkerAgent(BaseWorkerAgent):
       # Implementation
   ```

3. Sync to database:
   ```bash
   python manage.py sync_agent_cards
   ```

4. Restart server:
   ```bash
   python -X utf8 -m daphne -p 8004 backend.asgi:application
   ```

5. Test:
   ```
   User: "도쿄 맛집 추천해줘"
   → hostagent semantic routing (reads tags from card)
   → restaurant-specialist responds
   ```

**NO CODE CHANGES REQUIRED** ✅

---

## Benefits Summary

### ✅ Maintainability (User's #1 Priority)

1. **JSON Cards as Source of Truth**
   - All agent definitions in one place (JSON files)
   - No hardcoded categories or agent types
   - Easy to add/remove/modify agents

2. **Clear Separation of Concerns**
   - A2A standard fields at root level
   - Django-specific fields in `"django"` section
   - Worker implementations separate from config

3. **Dynamic Discovery**
   - Worker factory reads JSON cards
   - Semantic routing reads skill tags
   - No code changes to add agents

### ✅ Complex Orchestration Support

1. **Dual Routing System**
   - Fast path for simple queries (80%)
   - Complex path for multi-step tasks (20%)

2. **Orchestrator Pattern**
   - Breaks down complex requests
   - Coordinates multiple specialists
   - Parallel execution for speed

3. **Official A2A Compliance**
   - Follows Google/Linux Foundation standard
   - Compatible with MCP servers
   - Industry-standard agent cards

### ✅ Performance Maintained

1. **Speed Targets Met**
   - Fast path: 5-9 seconds (unchanged)
   - Complex path: 10-15 seconds (acceptable for multi-step)

2. **Optimization Strategies**
   - Card caching (load once)
   - Model caching (semantic routing)
   - Parallel specialist execution
   - Timeout protection

### ✅ Enterprise-Grade

1. **Scalability**
   - Add agents without code changes
   - Dynamic category loading
   - Horizontal scaling ready

2. **Monitoring**
   - Performance timing logs
   - Error handling and fallbacks
   - Request tracing

3. **Standards Compliance**
   - A2A official format
   - JSON-RPC 2.0 protocol
   - MCP-compatible discovery

---

## Next Steps

### Immediate Actions (This Week)

1. **Review This Architecture**
   - Confirm dual routing approach
   - Validate JSON card format
   - Approve implementation phases

2. **Start Phase 1: Standardize JSON Cards**
   - Update hostagent_card.json to A2A format
   - Update flight_specialist_card.json
   - Update hotel_specialist_card.json
   - Create card_loader.py utility

3. **Create Management Command**
   - Implement sync_agent_cards command
   - Test JSON → DB sync
   - Verify no data loss

### Phase Rollout Timeline

| Phase | Duration | Goal | Status |
|-------|----------|------|--------|
| **Phase 1** | Week 1 | Standardize JSON cards, make them source of truth | 🔜 Ready to start |
| **Phase 2** | Week 2 | Dynamic semantic routing, remove hardcoding | ⏳ Pending Phase 1 |
| **Phase 3** | Week 3-4 | Orchestrator & Planner for complex tasks | ⏳ Pending Phase 2 |
| **Phase 4** | Week 5 | Performance optimization & monitoring | ⏳ Pending Phase 3 |

---

## Conclusion

This ENTERPRISE architecture satisfies all user requirements:

1. ✅ **유지보수가 제일중요해** - JSON cards as source of truth, no hardcoding, clear separation
2. ✅ **JSON CARD는 무조건잇어야하지** - JSON cards are now PRIMARY source, not decoration
3. ✅ **복잡한 Multi-agent Orchestration** - Orchestrator → Planner → Multiple specialists pattern
4. ✅ **속도를 유지하면서** - Dual routing maintains 5-9s for simple, 10-15s for complex

**Key Innovation:** Hybrid approach combines our fast semantic routing with official cookbook's complex orchestration pattern, giving best of both worlds.

**Ready to implement Phase 1?** Start with standardizing JSON cards and creating the card loader utility.
