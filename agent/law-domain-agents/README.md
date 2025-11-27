# Law Domain Agents - A2A Protocol Implementation

Multi-agent law search system using Agent-to-Agent (A2A) protocol.

## Architecture

```
QueryCoordinator (port 8010)
    ├─> Domain 1: 도시계획 및 이용 (port 8011)
    ├─> Domain 2: 토지이용 및 보상 (port 8012)
    ├─> Domain 3: 토지등 및 계획 (port 8013)
    ├─> Domain 4: 도시계획 및 환경관리 (port 8014)
    └─> Domain 5: 토지이용 및 보상절차 (port 8015)
```

## Features

- **A2A Protocol**: JSON-RPC 2.0 compliant agent-to-agent communication
- **LangGraph Workflows**: Stateful agent workflows with message history
- **Neo4j Graph Search**: Law article search via graph database
- **Semantic Search**: KR-SBERT + OpenAI embeddings
- **RNE Graph Expansion**: Relationship-aware node embedding

## Quick Start

### 1. Install Dependencies

```bash
cd agent/law-domain-agents
uv venv
uv pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Neo4j and OpenAI credentials
```

### 3. Run Domain Agent

```bash
# Terminal 1: Domain 1 Agent
uv run uvicorn domain-1-agent.server:app --port 8011

# Test
curl http://localhost:8011/.well-known/agent-card.json
```

### 4. Test Agent

```bash
# Test health endpoint
curl http://localhost:8011/health

# Test message endpoint (A2A protocol)
curl -X POST http://localhost:8011/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "test-123",
        "contextId": "test-context",
        "role": "user",
        "parts": [
          {"kind": "text", "text": "17조에 대해 알려주세요"}
        ]
      }
    },
    "id": "req-1"
  }'
```

## Project Structure

```
law-domain-agents/
├── README.md                    # This file
├── pyproject.toml               # Project dependencies (uv)
├── .env.example                 # Environment template
├── requirements.txt             # Pip dependencies (generated from pyproject.toml)
│
├── domain-1-agent/              # Domain 1: 도시계획 및 이용
│   ├── __init__.py
│   ├── graph.py                 # LangGraph workflow
│   ├── server.py                # FastAPI A2A server
│   ├── domain_logic.py          # Search logic (Neo4j + RNE)
│   └── config.py                # Configuration
│
├── coordinator/                 # QueryCoordinator (future)
│   └── (to be added later)
│
└── shared/                      # Shared utilities
    ├── __init__.py
    ├── neo4j_client.py          # Neo4j connection
    └── openai_client.py         # OpenAI connection
```

## Development

### Adding New Domain Agent

1. Copy `domain-1-agent/` to `domain-N-agent/`
2. Update domain configuration in `.env`
3. Modify port and domain name in `config.py`
4. Update domain-specific logic in `domain_logic.py`

### Running Multiple Agents

```bash
# Terminal 1: Domain 1
uv run uvicorn domain-1-agent.server:app --port 8011

# Terminal 2: Domain 2
uv run uvicorn domain-2-agent.server:app --port 8012

# Terminal 3: Coordinator
uv run uvicorn coordinator.server:app --port 8010
```

## A2A Protocol Compliance

### Agent Card Endpoint

```
GET /.well-known/agent-card.json
```

Returns agent metadata according to A2A spec.

### Message Endpoint

```
POST /messages
```

Accepts JSON-RPC 2.0 formatted messages:

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "uuid",
      "contextId": "uuid",
      "role": "user",
      "parts": [{"kind": "text", "text": "query"}]
    }
  },
  "id": "request-id"
}
```

## Integration with Backend

This agent system is designed to work alongside the existing Django backend:

- **Backend**: `D:\Data\11_Backend\01_ARR\backend\` - Data pipeline, Neo4j setup
- **Agents**: `D:\Data\11_Backend\01_ARR\agent\law-domain-agents\` - A2A agents

Both systems share the same Neo4j database but are independently deployable.

## Project Status

- [x] Domain 1 Agent (도시계획 및 이용) - Basic structure
- [ ] Domain 1 Agent - Full Neo4j integration
- [ ] Domain 2-5 Agents
- [ ] QueryCoordinator
- [ ] Full A2A integration test
- [ ] Production deployment

## Reference

Based on:
- A2A Protocol: https://a2a.dev
- Pattern: `agent/a2a/langraph_agent/`
- Backend: `backend/agents/law/`

## License

MIT
