# QueryCoordinator Agent

**Status**: To be implemented

## Purpose

The QueryCoordinator is the central orchestrator that:
1. Receives user queries
2. Routes them to appropriate domain agents
3. Aggregates responses from multiple domains
4. Synthesizes final answer

## Architecture

```
User Query
    ↓
QueryCoordinator (port 8010)
    ↓
    ├─> Domain 1 Agent (8011) ──┐
    ├─> Domain 2 Agent (8012) ──┤
    ├─> Domain 3 Agent (8013) ──┼─> Parallel Search
    ├─> Domain 4 Agent (8014) ──┤
    └─> Domain 5 Agent (8015) ──┘
    ↓
Synthesis & Ranking
    ↓
Final Response
```

## Implementation Plan

### Phase 1: Basic Routing
- Broadcast query to all domain agents
- Collect responses
- Simple aggregation

### Phase 2: Intelligent Routing
- Query analysis
- Selective routing to relevant domains
- Domain relevance scoring

### Phase 3: Advanced Synthesis
- Multi-agent collaboration (A2A exchange)
- Graph-based result merging
- Confidence scoring

### Phase 4: Learning
- Query history
- Domain performance tracking
- Adaptive routing

## Files to Create

```
coordinator/
├── __init__.py
├── graph.py              # LangGraph workflow
├── server.py             # FastAPI A2A server
├── routing_logic.py      # Domain selection
├── synthesis_logic.py    # Response aggregation
├── config.py             # Configuration
└── a2a_client.py         # Client for domain agents
```

## Integration Points

### With Domain Agents
- A2A protocol for communication
- Agent discovery via agent cards
- Message routing and context management

### With Backend
- Shared Neo4j database
- Shared embedding models
- Common data structures

## Reference

Based on `backend/agents/law/agent_manager.py` (AgentManager class)
