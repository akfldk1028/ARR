# A2A Worker Agent System - Complete Implementation

## Overview
Fully integrated and organized LangGraph-based worker agent system with A2A (Agent-to-Agent) protocol for Django backend. The implementation features clean architecture, worker-to-worker communication, and comprehensive database integration.

## Architecture Summary

### Core Components

#### 1. Django Agent Models (`agents/models.py`)
- Agent entity management with capabilities, system prompts, and metadata
- Organization and tag relationships for agent categorization

#### 2. Worker Agent System (`agents/worker_agents/`)
```
worker_agents/
├── base/
│   └── base_worker.py          # BaseWorkerAgent abstract class
├── implementations/
│   ├── general_worker.py       # General-purpose assistant
│   └── flight_specialist_worker.py  # Flight booking specialist
├── cards/
│   ├── general_worker_card.json     # Agent specifications
│   └── flight_specialist_card.json
├── worker_factory.py          # Factory pattern for worker creation
└── worker_manager.py           # Worker lifecycle management
```

#### 3. Database System (`agents/database/`)
```
database/
└── neo4j/
    ├── service.py              # Core Neo4j service
    ├── indexes.py              # Index management
    ├── stats.py                # Database statistics
    └── queries.py              # Query templates
```

#### 4. A2A Protocol Implementation (`agents/a2a_client.py`)
- Agent card discovery via `/.well-known/agent-card/{slug}.json`
- JSON-RPC 2.0 compliant message formatting
- Worker-to-worker communication client

#### 5. Django Views (`agents/views.py`)
- Agent card endpoints (A2A standard compliant)
- Dual format support: regular JSON and A2A JSON-RPC 2.0
- Chat interface with async processing

## Key Features Implemented

### A2A Protocol Compliance
- **Agent Card Discovery**: Standard `/.well-known/agent-card.json` endpoints
- **JSON-RPC 2.0**: Full protocol compliance for message/send method
- **Bidirectional Communication**: Agents can initiate communication with each other

### Worker Agent Communication
- **Agent Registry**: Automatic discovery and registration of available agents
- **Message Routing**: Context-aware message handling between workers
- **Session Management**: Proper session and context ID tracking

### Integration Achievements
- **Neo4j Integration**: Preserved SK system's graph database functionality
- **LangGraph Migration**: Complete replacement of SemanticKernel with LangGraph
- **Django Compatibility**: Proper async handling within Django's sync framework

## Testing Results

### Worker Communication Test
Successfully tested worker-to-worker communication with:
- **Agent Discovery**: Both agents discoverable via agent cards
- **Message Exchange**: JSON-RPC 2.0 format working correctly
- **Bidirectional Communication**: Both directions (test-agent ↔ flight-specialist)
- **Multi-Agent Collaboration**: Complex travel scenarios handled successfully

### Sample Communication Flow
```json
Request (A2A JSON-RPC 2.0):
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "uuid4-generated",
      "role": "user",
      "parts": [{"text": "Hello! Can you help with flight information?"}],
      "contextId": "inter_agent_collaboration_1"
    }
  },
  "id": "uuid4-generated"
}

Response:
{
  "jsonrpc": "2.0",
  "result": {
    "parts": [{"text": "Of course! I can assist with flight booking..."}],
    "messageId": "uuid4-generated",
    "role": "assistant"
  },
  "id": "request-id"
}
```

## Development Commands

### Create Agents
```bash
python manage.py create_test_agent
python manage.py create_second_agent
```

### Test Communication
```bash
python manage.py test_worker_communication --source-agent test-agent --target-agent flight-specialist
```

### Run Development Server
```bash
python manage.py runserver
```

## Agent Endpoints
- **Agent Card**: `/.well-known/agent-card/{slug}.json`
- **Chat Interface**: `/agents/{slug}/chat/`
- **Agent Status**: `/agents/{slug}/status/`
- **Agent List**: `/agents/list/`

## Maintenance Notes
- **A2A Protocol**: Official standard by Google/Linux Foundation
- **Neo4j**: Requires running instance on localhost:7687
- **Async Handling**: Proper event loop management in Django views
- **Error Handling**: Comprehensive exception handling for network operations
- **Encoding**: UTF-8 support for international content

## Success Metrics
✅ A2A protocol compliance
✅ Worker-to-worker communication
✅ Agent discovery system
✅ Neo4j integration
✅ LangGraph migration
✅ Django async compatibility
✅ Bidirectional messaging
✅ Multi-agent collaboration

The implementation successfully demonstrates a fully functional A2A-compliant multi-agent system with robust worker communication capabilities.

## Law Search Proxy (2026-02-21)

The `law/` Django app serves as a **proxy** to `law-domain-agents` on port 8011. It does NOT implement search logic itself.

### Endpoints
| Method | Path | Proxies To | Logs |
|--------|------|------------|------|
| POST | `/law/search/` | `:8011/api/search` | SearchLog |
| GET | `/law/search/stream?query=&limit=&domain_id=` | `:8011/api/search` (SSE wrapper) | SearchLog |
| POST | `/law/domain/<id>/search/` | `:8011/api/domain/<id>/search` | SearchLog |
| GET | `/law/domains/` | `:8011/api/domains` | No |
| GET | `/law/health/` | `:8011/api/health` | No |
| GET | `/law/article/?full_id=...` | Neo4j direct (JO→HANG→HO) | No |
| GET | `/law/stats/` | Django DB direct | - |

### Field Mapping
Client sends `{"q": ..., "limit": ...}` → proxy sends `{"query": ..., "limit": ...}` to law-domain-agents.

### SearchLog Model
Tracks query, domain_id, limit, result_count, response_time_ms, source. SearchLog.objects.create failure is non-fatal (wrapped in try/except).

### Prerequisites
- `law` in INSTALLED_APPS (settings.py line 55)
- `path('law/', include('law.urls'))` in backend/urls.py
- `python manage.py migrate` to create SearchLog table
- law-domain-agents running on port 8011

### Law Pipeline Status (2026-02-27 — 18 LAWS LOADED, FULL PIPELINE)

| Step | Status | Detail |
|------|--------|--------|
| Step1-alt API→JSON | DONE | 18 laws downloaded (6 법률 × 3 types) |
| Step2 JSON→Neo4j | DONE | LAW 18, HANG 6171, HO 6026, MOK 1284, JO 2431 (total 16,081) |
| Step3 Embeddings | DONE | ALL 6171 HANG nodes, OpenAI text-embedding-3-large 3072-dim |
| Step4 Domains | DONE | 5 domains (land_use:2286, national:2004, building:1018, zoning:614, urban:249) |
| Step5 RelEmbeddings | DONE | ALL 16,058 CONTAINS rel embeddings, `contains_embedding` ONLINE |

**Neo4j**: `bolt://localhost:7687`, pw=`11111111` (Neo4j Desktop). **Pipeline docs**: `law/PIPELINE.md`.

**Scripts** (`law/scripts/`):
- `run_step3_standalone.py` — HANG embeddings, `LAW_NEO4J_PASSWORD=11111111`
- `run_step5_incremental.py` — CONTAINS rel embeddings (incremental, NULL only)
- `law_downloader.py` — `python law_downloader.py --oc hanvit4303 --force` (18개 법률)

## Land Regulation Analysis (2026-02-22)

The `land/` Django app analyzes land parcels for building regulations (건폐율, 용적률, 건축제한).

### Purpose
AI agent가 토지 정보를 입력받아 관련 건축법규를 자동으로 분석. 현재는 static lookup + 법조항 검색, 향후 Agent 협업으로 건축관련법 전체 분석 예정.

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/land/analyze/` | PNU/주소/zones → 건폐율+용적률+법조항 |
| POST | `/land/resolve/` | 주소→PNU (Vworld) 또는 PNU 검증 |
| GET | `/land/zones/` | 21개 용도지역 규제 목록 |
| GET | `/land/stats/` | 쿼리 통계 |

### analyze Request/Response
```json
// Request
{"input": "1168011200101280003", "input_type": "pnu", "zones": ["제1종일반주거지역"], "include_law": true}

// Response
{
  "pnu": {"pnu": "...", "sido": "11", "sigungu": "680", ...},
  "regulation": {"bcr_limit": 60, "far_limit": 200, "zones": [...], "matched": 1, "unmatched": []},
  "land_info": {...},
  "law_articles": {"articles": [...], "total_count": 15, "errors": []},
  "restrictions": ["건폐율 상한: 60%", "용적률 상한: 200%"]
}
```

### Service Layer
- `pnu_resolver.py`: PNU 19자리 검증/파싱 + Vworld 지오코딩 + **주소→PNU 자동 추출** (level4LC, VWORLD_API_KEY env var)
- `zoning_mapper.py`: 21개 용도지역 → 건폐율/용적률 (`land/data/zoning_limits.json`, exact match only)
- `law_enricher.py`: law-domain-agents(:8011) 법조항 검색 (fail-fast, LAW_BACKEND_URL env var)
- `land_api.py`: Vworld Data API 3개 (getLandUseAttr, ladfrlList, getIndvdLandPriceAttr)

### Key Design
- **복수 용도지역**: 가장 엄격한 값 적용 (국토계획법 제76-77조)
- **Exact match only**: 부분 매칭 제거 (ambiguity 방지)
- **Fail-fast**: law_enricher ConnectError 즉시 중단, 3회 연속 실패시 중단
- **Non-fatal audit log**: LandQuery.objects.create 실패해도 응답은 정상 반환

### Models
- `LandQuery`: input_type, raw_input, resolved_pnu, zoning_zones(JSON), bcr/far limits, response_time_ms, error
- `ZoningRegulation`: zone_name(unique), bcr_default, far_default, articles (미사용, admin에서 편집 가능)

### Prerequisites
- `land` in INSTALLED_APPS
- `path('land/', include('land.urls'))` in backend/urls.py
- `python manage.py migrate` to create LandQuery + ZoningRegulation tables
- law-domain-agents on port 8011 (for law_enricher, optional)
- VWORLD_API_KEY env var (for address geocoding, optional)