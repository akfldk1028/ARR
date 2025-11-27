# Backend vs Agent Comparison

Understanding the relationship between `backend/` and `agent/law-domain-agents/`

## Directory Structure Comparison

### Backend (Django)
```
backend/
├── agents/law/
│   ├── agent_manager.py        # QueryCoordinator equivalent
│   ├── domain_agent.py         # DomainAgent base class
│   └── urls.py                 # Django REST endpoints
├── graph_db/
│   ├── services/
│   │   └── neo4j_service.py    # Neo4j service class
│   └── algorithms/
│       └── core/
│           ├── semantic_rne.py # RNE algorithm
│           └── semantic_ine.py # INE algorithm
└── law/
    ├── scripts/                # Data pipeline
    │   ├── pdf_to_json.py
    │   ├── json_to_neo4j.py
    │   └── add_hang_embeddings.py
    └── STEP/
        └── run_all.py          # Automated pipeline
```

### Agent (A2A)
```
agent/law-domain-agents/
├── domain-1-agent/
│   ├── server.py               # FastAPI A2A server
│   ├── graph.py                # LangGraph workflow
│   ├── domain_logic.py         # Search logic
│   └── config.py               # Configuration
├── shared/
│   ├── neo4j_client.py         # Neo4j singleton
│   └── openai_client.py        # OpenAI singleton
├── coordinator/                # Future: QueryCoordinator
└── run_domain_1.py             # Quick launcher
```

## Component Mapping

| Backend Component | Agent Equivalent | Notes |
|-------------------|------------------|-------|
| `agents/law/agent_manager.py` | `coordinator/` (TBD) | Central orchestrator |
| `agents/law/domain_agent.py` | `domain-1-agent/domain_logic.py` | Domain search logic |
| `graph_db/services/neo4j_service.py` | `shared/neo4j_client.py` | Neo4j connection |
| `graph_db/algorithms/core/semantic_rne.py` | `domain_logic.py` (TODO) | RNE algorithm |
| `agents/law/urls.py` (Django REST) | `server.py` (FastAPI A2A) | API endpoints |

## Key Differences

### 1. Framework

**Backend: Django REST Framework**
```python
# backend/agents/law/views.py
from rest_framework.decorators import api_view

@api_view(['POST'])
def search_law(request):
    query = request.data.get('query')
    # ... search logic
    return Response(results)
```

**Agent: FastAPI with A2A Protocol**
```python
# agent/law-domain-agents/domain-1-agent/server.py
from fastapi import FastAPI

@app.post("/messages")
async def handle_message(req: Request):
    # JSON-RPC 2.0 format
    body = await req.json()
    # ... A2A protocol handling
    return {"jsonrpc": "2.0", "result": {...}}
```

### 2. Workflow Engine

**Backend: Manual Workflow**
```python
# backend/agents/law/domain_agent.py
class DomainAgent(BaseWorkerAgent):
    async def _generate_response(self, user_input, ...):
        # Phase 1: Self-assessment
        results = self._search_domain(user_input)

        # Phase 2: A2A collaboration
        if self._needs_collaboration(results):
            neighbor_results = await self._collaborate_with_neighbors()

        # Phase 3: Synthesis
        final_result = self._synthesize_results(results, neighbor_results)
        return final_result
```

**Agent: LangGraph Workflow**
```python
# agent/law-domain-agents/domain-1-agent/graph.py
from langgraph.graph import StateGraph

graph_builder = StateGraph(Domain1State)
graph_builder.add_node("search", search_domain_1)
graph_builder.add_edge(START, "search")
graph_builder.add_edge("search", END)
domain_1_graph = graph_builder.compile()

# Execute workflow
result = domain_1_graph.invoke({"messages": [...]})
```

### 3. Database Access

**Backend: Django ORM + Neo4j Service**
```python
# backend/graph_db/services/neo4j_service.py
class Neo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def execute_query(self, query, params):
        with self.driver.session() as session:
            return session.run(query, params)
```

**Agent: Singleton Pattern**
```python
# agent/law-domain-agents/shared/neo4j_client.py
_neo4j_client = None

def get_neo4j_client():
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client
```

### 4. Configuration

**Backend: Django Settings**
```python
# backend/backend/settings.py
NEO4J_CONFIG = {
    'uri': os.getenv('NEO4J_URI'),
    'user': os.getenv('NEO4J_USER'),
    'password': os.getenv('NEO4J_PASSWORD')
}
```

**Agent: Domain Config Class**
```python
# agent/law-domain-agents/domain-1-agent/config.py
class Domain1Config:
    DOMAIN_ID = os.getenv("DOMAIN_1_ID", "domain_1")
    DOMAIN_PORT = int(os.getenv("DOMAIN_1_PORT", "8011"))

    @classmethod
    def get_agent_card(cls):
        return {...}  # A2A agent card
```

## What's Shared

### 1. Neo4j Database
Both systems use the SAME Neo4j database:
- Same graph structure (LAW → JO → HANG → HO)
- Same embeddings (KR-SBERT, OpenAI)
- Same domain assignments
- Same indexes

### 2. Embedding Models
Both use the SAME models:
- **KR-SBERT**: `snunlp/KR-SBERT-V40K-klueNLI-augSTS`
- **OpenAI**: `text-embedding-3-large`

### 3. Domain Definitions
Both use the SAME 5 domains:
1. 도시계획 및 이용
2. 토지이용 및 보상
3. 토지등 및 계획
4. 도시계획 및 환경관리
5. 토지이용 및 보상절차

### 4. Search Algorithms (Conceptually)
Both implement:
- **INE**: Integrated Node Embedding (semantic search)
- **RNE**: Relationship-aware Node Embedding (graph expansion)
- **Cross-law**: References between laws/regulations

## What's Different

### 1. Purpose

**Backend**
- Data pipeline execution
- Database setup and maintenance
- Django admin interface
- Legacy SemanticKernel agents (being deprecated)

**Agent**
- A2A-compliant agent system
- LangGraph-based workflows
- Standalone microservices
- Modern agent architecture

### 2. Deployment

**Backend**
- Single Django application
- Port 8000
- Requires full Django stack
- Monolithic

**Agent**
- Multiple independent agents
- Ports 8010-8015
- Minimal dependencies
- Microservices architecture

### 3. API Protocol

**Backend**
- Django REST Framework
- Standard HTTP POST
- Custom JSON format

**Agent**
- A2A Protocol (Google/Linux Foundation standard)
- JSON-RPC 2.0
- Agent card discovery
- Standardized message format

### 4. Agent Communication

**Backend**
- In-process method calls
- Shared memory
- Tight coupling

**Agent**
- HTTP-based A2A protocol
- Distributed communication
- Loose coupling
- Can run on different machines

## Data Flow Comparison

### Backend Flow
```
User Request (Django)
    ↓
agents/law/views.py
    ↓
AgentManager (agent_manager.py)
    ↓
DomainAgent (domain_agent.py)
    ↓
Neo4jService
    ↓
Neo4j Database
```

### Agent Flow
```
User Request (A2A)
    ↓
domain-1-agent/server.py (FastAPI)
    ↓
domain-1-agent/graph.py (LangGraph)
    ↓
domain-1-agent/domain_logic.py
    ↓
shared/neo4j_client.py
    ↓
Neo4j Database (SHARED)
```

## Migration Strategy

### Phase 1: Current State
- Backend handles all requests
- Agents in `backend/agents/law/` active
- Django REST API

### Phase 2: Parallel Operation
- Backend continues to serve existing clients
- Agent system runs in parallel
- Both access same Neo4j database
- Gradual migration of features

### Phase 3: Full Migration
- New clients use A2A agents
- Backend becomes data pipeline only
- Legacy endpoints deprecated
- Agent system primary interface

## Running Both Systems

### Start Backend (Django)
```bash
cd D:\Data\11_Backend\01_ARR\backend
python manage.py runserver
# Runs on http://localhost:8000
```

### Start Agent System
```bash
cd D:\Data\11_Backend\01_ARR\agent\law-domain-agents
python run_domain_1.py
# Runs on http://localhost:8011
```

### Both can run simultaneously!
- Backend: Port 8000
- Domain 1 Agent: Port 8011
- Shared: Neo4j database

## Which One to Use?

### Use Backend For:
- Running data pipeline
- Setting up Neo4j database
- Database administration
- Initial data loading

### Use Agent System For:
- A2A-compliant agent development
- Modern agent architecture
- Distributed agent deployment
- LangGraph workflows
- Microservices approach

## Code Reuse Strategy

### What to Port from Backend

1. **Search Logic** (HIGH PRIORITY)
   - `graph_db/algorithms/core/semantic_rne.py` → `domain_logic.py`
   - `graph_db/algorithms/core/semantic_ine.py` → `domain_logic.py`
   - Embedding generation functions

2. **Domain Data** (MEDIUM PRIORITY)
   - Domain initialization logic
   - Node assignment algorithms
   - Statistics computation

3. **Utilities** (LOW PRIORITY)
   - Logging configuration
   - Error handling patterns
   - Validation logic

### What NOT to Port

1. **Django-specific**
   - ORM models
   - Admin interface
   - Middleware

2. **Data Pipeline**
   - PDF parsing
   - JSON conversion
   - Initial database loading

3. **Legacy Code**
   - SemanticKernel agents (deprecated)
   - Old agent implementations

## File Count Summary

### Backend Law System
```bash
backend/
├── agents/law/           # ~10 files
├── graph_db/             # ~20 files
├── law/scripts/          # ~15 files
└── law/STEP/             # ~5 files
Total: ~50 files
```

### Agent System
```bash
agent/law-domain-agents/
├── domain-1-agent/       # 5 files
├── shared/               # 3 files
├── coordinator/          # 1 file (placeholder)
└── root files            # 9 files
Total: 18 files
```

## Lines of Code Comparison

- **Backend Law System**: ~5,000 lines
- **Agent System**: ~1,200 lines (Phase 1)
- **Ratio**: 4:1 (Backend is 4x larger)

Agent system is more focused and streamlined!

## Conclusion

| Aspect | Backend | Agent |
|--------|---------|-------|
| Framework | Django | FastAPI |
| Workflow | Manual | LangGraph |
| Protocol | REST | A2A (JSON-RPC 2.0) |
| Architecture | Monolithic | Microservices |
| Deployment | Single app | Multiple agents |
| Database | Neo4j | Neo4j (SHARED) |
| Purpose | Data + Search | Search only |
| Status | Production | Development |

Both systems complement each other:
- **Backend**: Data foundation
- **Agent**: Modern interface

They share the same data (Neo4j) but serve different purposes.

---

**Recommendation**:
1. Use **Backend** for data pipeline
2. Use **Agent** for user-facing search
3. Run both in parallel during migration
4. Gradually deprecate backend search endpoints
5. Keep backend for data management

This allows smooth transition while maintaining stability.
