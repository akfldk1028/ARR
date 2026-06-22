# agents

A2A-compliant multi-agent system with LangGraph workers.

## Structure
```
agents/
├── models.py              # Agent model (types: gemini/gpt/claude/custom)
├── views.py               # Agent card endpoints, chat interface
├── urls.py                # /agents/{slug}/chat/, /.well-known/agent-card/
├── a2a_client.py          # A2A JSON-RPC 2.0 client
├── langgraph_agent.py     # LangGraph integration
├── well_known_urls.py     # /.well-known/ discovery
├── database/neo4j/        # Neo4j service layer (queries, indexes, stats)
├── worker_agents/         # Worker implementations
│   ├── base/base_worker.py           # Abstract BaseWorkerAgent
│   ├── implementations/              # GeneralWorker, FlightSpecialistWorker
│   ├── cards/                        # A2A agent card JSONs
│   ├── worker_factory.py             # Factory pattern
│   ├── worker_manager.py             # Lifecycle management
│   ├── conversation_coordinator.py   # Multi-agent coordination
│   └── a2a_streaming.py             # Streaming A2A responses
└── voice/                 # Voice A2A integration (WebSocket)
```

## A2A Endpoints
- `GET /.well-known/agent-card/{slug}.json` - Agent discovery
- `POST /agents/{slug}/chat/` - JSON-RPC 2.0 message/send
- `GET /agents/list/` - All agents

## Dependencies
- `core.models.BaseModel`, `Organization`, `Tag`
- Neo4j (optional, for graph features)
