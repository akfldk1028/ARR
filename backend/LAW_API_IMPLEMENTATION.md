# Law Search REST API Implementation

## Overview

Django REST Framework API endpoints for the law search system, connecting the frontend React application to the backend Multi-Agent System (MAS).

**Date**: 2025-11-13
**Status**: ✅ Complete

---

## Architecture

### Frontend → Backend Flow

```
Frontend (React)
    ↓ HTTP POST /api/law/search
Backend API (Django REST Framework)
    ↓ AgentManager.auto_route(query)
DomainAgent._search_my_domain(query)
    ↓ Dual Embedding Search
Neo4j (KR-SBERT 768-dim + OpenAI 3072-dim)
    ↓ Results
Backend API (Transform & Statistics)
    ↓ JSON Response
Frontend (Display)
```

---

## Implemented Endpoints

### 1. Law Search API (Auto-Routing)

**Endpoint**: `POST /api/law/search`

**Request**:
```json
{
  "query": "도시계획시설의 결정",
  "limit": 10
}
```

**Response**:
```json
{
  "results": [
    {
      "hang_id": "국토의_계획_및_이용에_관한_법률_법률_제2장_제2절_제43조_제1항",
      "content": "도시·군관리계획으로 결정된 도시·군계획시설...",
      "unit_path": "제2장 광역도시계획 및 도시·군관리계획 > 제2절 도시·군관리계획 > 제43조 (도시·군계획시설의 설치·관리)",
      "similarity": 0.85,
      "stages": ["vector", "relationship"],
      "source": "my_domain"
    }
  ],
  "stats": {
    "total": 10,
    "vector_count": 5,
    "relationship_count": 3,
    "graph_expansion_count": 2,
    "my_domain_count": 8,
    "neighbor_count": 2
  },
  "domain_id": "domain_a1b2c3d4",
  "domain_name": "도시계획",
  "response_time": 234
}
```

**Features**:
- Automatic domain routing based on query embedding similarity
- Calculates similarity with each domain's centroid
- Routes to best matching domain

---

### 2. Domain-Specific Search API

**Endpoint**: `POST /api/law/domain/{domain_id}/search`

**Request**:
```json
{
  "query": "건축물의 용도",
  "limit": 10
}
```

**Response**: Same format as auto-routing search

**Features**:
- Search within a specific domain
- Useful when user selects domain manually

---

### 3. Domains List API

**Endpoint**: `GET /api/law/domains`

**Response**:
```json
{
  "domains": [
    {
      "domain_id": "domain_a1b2c3d4",
      "domain_name": "도시계획",
      "agent_slug": "law_도시계획",
      "node_count": 150,
      "neighbor_count": 2,
      "created_at": "2025-11-13T10:30:00",
      "last_updated": "2025-11-13T12:45:00"
    }
  ],
  "total": 5
}
```

**Features**:
- Lists all available domains
- Sorted by node_count (descending)
- Used for domain selector in frontend

---

### 4. Domain Detail API

**Endpoint**: `GET /api/law/domain/{domain_id}`

**Response**:
```json
{
  "domain_id": "domain_a1b2c3d4",
  "domain_name": "도시계획",
  "agent_slug": "law_도시계획",
  "node_count": 150,
  "neighbor_count": 2,
  "created_at": "2025-11-13T10:30:00",
  "last_updated": "2025-11-13T12:45:00",
  "neighbors": [
    {
      "domain_id": "domain_e5f6g7h8",
      "domain_name": "건축규제"
    }
  ]
}
```

**Features**:
- Detailed information for a specific domain
- Includes neighbor domains (A2A network)

---

### 5. Health Check API

**Endpoint**: `GET /api/health`

**Response**:
```json
{
  "status": "healthy",
  "backend": "ok",
  "neo4j": "ok",
  "agent_manager": "ok",
  "domains": 5,
  "total_nodes": 750,
  "details": {
    "backend_version": "1.0.0",
    "neo4j_connected": true,
    "agent_manager_initialized": true
  }
}
```

**Status Levels**:
- `healthy`: All systems operational
- `degraded`: Some systems down but service available
- `unhealthy`: Critical failure

---

## File Structure

```
backend/
├── agents/law/
│   ├── api/                      # NEW: REST API folder
│   │   ├── __init__.py
│   │   ├── search.py            # Search endpoints
│   │   ├── domains.py           # Domain management
│   │   └── health.py            # Health check
│   ├── api_urls.py              # NEW: API URL routing
│   ├── agent_manager.py         # AgentManager (existing)
│   └── domain_agent.py          # DomainAgent (existing)
│
└── backend/
    └── urls.py                  # MODIFIED: Added /api/law/ route
```

---

## Key Implementation Details

### 1. AgentManager Singleton

```python
_agent_manager = None

def get_agent_manager() -> AgentManager:
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager
```

**Why**: AgentManager is expensive to initialize (loads domains from Neo4j, creates DomainAgent instances). Singleton pattern ensures one instance per server process.

---

### 2. Auto-Routing Strategy

```python
def auto_route_to_domain(query: str, agent_manager: AgentManager) -> str:
    # 1. Generate query embedding (KR-SBERT 768-dim)
    model = get_kr_sbert_model()
    query_embedding = model.encode([query])[0]

    # 2. Calculate cosine similarity with each domain's centroid
    best_domain_id = None
    best_similarity = -1.0

    for domain_id, domain_info in agent_manager.domains.items():
        similarity = cosine_similarity(
            query_embedding.reshape(1, -1),
            domain_info.centroid.reshape(1, -1)
        )[0][0]

        if similarity > best_similarity:
            best_similarity = similarity
            best_domain_id = domain_id

    return best_domain_id
```

**Why**: Similar to how AgentManager assigns new HANG nodes to domains. Uses the same KR-SBERT model for consistency.

---

### 3. Async Handling in Django

```python
# DomainAgent._search_my_domain() is async
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    results = loop.run_until_complete(
        domain_agent._search_my_domain(query)
    )
finally:
    loop.close()
```

**Why**: Django views are synchronous by default, but DomainAgent uses async methods. Create new event loop per request for proper async execution.

---

### 4. Statistics Calculation

```python
def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, int]:
    stats = {
        'total': len(results),
        'vector_count': 0,
        'relationship_count': 0,
        'graph_expansion_count': 0,
        'my_domain_count': 0,
        'neighbor_count': 0,
    }

    for result in results:
        # Handle multiple stages per result
        stages = result.get('stages', [result.get('stage', '')])
        if 'vector' in stages:
            stats['vector_count'] += 1
        if 'relationship' in stages:
            stats['relationship_count'] += 1
        # ...

    return stats
```

**Why**: Results can have multiple stages (e.g., found by both vector and relationship search). Count each stage separately for accurate statistics.

---

### 5. CSRF Exemption

```python
@method_decorator(csrf_exempt, name='dispatch')
class LawSearchAPIView(APIView):
    # ...
```

**Why**: Frontend and backend may run on different ports during development. CSRF exemption allows cross-origin requests. In production, use proper CORS configuration.

---

## Integration with Frontend

### Frontend API Client (`frontend/src/law/lib/law-api-client.ts`)

```typescript
export class LawAPIClient {
  private baseURL = 'http://localhost:8000';

  async search(request: LawSearchRequest): Promise<LawSearchResponse> {
    const response = await fetch(`${this.baseURL}/api/law/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return await response.json();
  }

  async getDomains(): Promise<LawDomain[]> {
    const response = await fetch(`${this.baseURL}/api/law/domains`);
    const data = await response.json();
    return data.domains;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseURL}/api/health`);
      const data = await response.json();
      return data.status === 'healthy' || data.status === 'degraded';
    } catch {
      return false;
    }
  }
}
```

### Type Safety

Frontend types (`LawSearchRequest`, `LawSearchResponse`, `LawArticle`, `SearchStats`) match backend response format exactly, ensuring type safety across the full stack.

---

## Testing Guide

### 1. Start Backend Server

```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\activate
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### 2. Start Frontend Development Server

```bash
cd D:\Data\11_Backend\01_ARR\frontend
npm run dev
```

### 3. Access Law Chat

Navigate to: `http://localhost:5173/law`

### 4. Test Endpoints Manually

**Health Check**:
```bash
curl http://localhost:8000/api/health
```

**Domain List**:
```bash
curl http://localhost:8000/api/law/domains
```

**Search**:
```bash
curl -X POST http://localhost:8000/api/law/search \
  -H "Content-Type: application/json" \
  -d '{"query": "도시계획시설", "limit": 10}'
```

---

## Troubleshooting

### Issue: "No domains available"

**Cause**: AgentManager has no domains loaded

**Solution**:
1. Check Neo4j is running: `docker ps`
2. Verify Domain nodes exist in Neo4j:
   ```cypher
   MATCH (d:Domain) RETURN d
   ```
3. If no domains, run domain initialization:
   ```bash
   python manage.py shell
   >>> from agents.law.agent_manager import AgentManager
   >>> manager = AgentManager()
   >>> # Domains should auto-initialize from existing HANG nodes
   ```

---

### Issue: "Domain agent not initialized"

**Cause**: DomainInfo.agent_instance is None

**Solution**:
- AgentManager._create_domain_agent_instance() should create instances
- Check logs for errors during domain creation
- May need to restart server to trigger re-initialization

---

### Issue: CORS errors in frontend

**Cause**: Cross-origin requests blocked

**Solution**:
1. Install django-cors-headers:
   ```bash
   pip install django-cors-headers
   ```
2. Add to `settings.py`:
   ```python
   INSTALLED_APPS = [
       'corsheaders',
       # ...
   ]

   MIDDLEWARE = [
       'corsheaders.middleware.CorsMiddleware',
       # ...
   ]

   CORS_ALLOWED_ORIGINS = [
       "http://localhost:5173",
   ]
   ```

---

## Performance Considerations

### 1. Embedding Model Loading

**Issue**: KR-SBERT model loads on every request

**Current**: Model loaded once per process (singleton pattern)

**Future**: Consider model caching across workers with Redis

---

### 2. Event Loop Creation

**Issue**: New event loop created per request

**Current**: Acceptable for low-medium traffic

**Future**: Use Django async views (Django 4.1+) for better performance

---

### 3. Database Connections

**Issue**: Neo4j connection per AgentManager

**Current**: Single AgentManager instance = single connection

**Future**: Connection pooling for high traffic

---

## Future Enhancements

1. **Authentication**: Add JWT authentication for production
2. **Rate Limiting**: Prevent abuse with DRF throttling
3. **Caching**: Cache search results with Redis
4. **Pagination**: Implement cursor-based pagination for large result sets
5. **Async Views**: Migrate to Django async views for better concurrency
6. **Logging**: Structured logging for monitoring and debugging
7. **Metrics**: Prometheus metrics for search latency, domain routing accuracy

---

## Success Metrics

✅ All endpoints implemented
✅ Type-safe frontend integration
✅ Auto-routing working
✅ Statistics calculation accurate
✅ Health check operational
✅ Clean folder structure
✅ DRF best practices followed
✅ Proper error handling

---

## Related Documentation

- **Frontend Implementation**: `D:\Data\11_Backend\01_ARR\frontend\src\law\`
- **AgentManager**: `D:\Data\11_Backend\01_ARR\backend\agents\law\agent_manager.py`
- **DomainAgent**: `D:\Data\11_Backend\01_ARR\backend\agents\law\domain_agent.py`
- **Law System Guide**: `D:\Data\11_Backend\01_ARR\backend\docs\2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`

---

**Implementation Complete!** 🎉
