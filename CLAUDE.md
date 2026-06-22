# ARR (Eigent) - Claude Code Context

## Overview

Multi-agent workforce platform with **land regulation analysis** (건축법규 분석). Originally "Eigent" - a Django + React/Electron application for AI agent orchestration with A2A protocol support.

**Core mission**: AI agent가 토지 정보를 입력받아 건폐율, 용적률, 건축제한 등 모든 관련 규제를 자동 분석. 현재 `law/` (법률 검색) + `land/` (토지 규제 분석) 두 앱이 핵심.

**This project is being integrated into the 25_ACE ecosystem.**

## Architecture

```
ARR/
├── backend/
│   ├── backend/         # Django project settings
│   ├── core/            # Foundation models (Organization, Tag)
│   ├── agents/          # A2A agent system (worker agents, cards, discovery)
│   ├── conversations/   # Chat session management
│   ├── gemini/          # Legacy Gemini voice integration
│   ├── law/             # Law ingestion pipeline (PDF→Neo4j) + search proxy
│   ├── land/            # Land regulation analysis (건폐율/용적률/건축제한)
│   ├── design/          # Building mass optimization (AUA NSGA-II 포팅)
│   ├── graph_db/        # Graph DB algorithms & CDC
│   ├── parser/          # Law document parser utilities
│   ├── src/             # Shared utilities (graph, LLM, entity extraction)
│   ├── cookbook/         # Example implementations
│   ├── docs/            # Documentation
│   └── _inactive/       # Coded but not registered in INSTALLED_APPS
│       ├── authz/       # RBAC models (~180 lines)
│       ├── billing/     # Usage tracking (~600 lines)
│       ├── events/      # Event logging (~700 lines)
│       ├── mcp/         # MCP connector (~800 lines)
│       ├── registry/    # Service registry (~500 lines)
│       └── tasks/       # Background jobs (~250 lines)
├── frontend/            # React 18 + Electron + Vite + TypeScript
│   ├── src/law/         # Law search UI (SSE streaming + 조문 사이드바)
│   ├── src/land/        # Land analysis UI (OpenLayers 2D Map + Panel)
│   ├── src/design/      # Design optimization UI (Map + Controls + Pareto)
│   └── server/          # FastAPI + PostgreSQL (Docker)
```

## Backend (Django)

- **Port**: 8000
- **DB**: SQLite (db.sqlite3) for Django ORM
- **Neo4j**: Optional, for graph features (`bolt://localhost:7687`)
- **Run**: `python manage.py runserver 8000`
- **INSTALLED_APPS**: core, agents, gemini, law, land, design
- **First run**: `python manage.py migrate` (creates SearchLog + LandQuery + ZoningRegulation tables)

### Active Apps
- `core/`: BaseModel, Organization, OrganizationMember, Tag
- `agents/`: Worker agent system with A2A protocol (GeneralWorker, FlightSpecialistWorker)
- `agents/database/neo4j/`: Neo4j service layer (queries, indexes, stats)
- `agents/worker_agents/`: LangGraph-based agent implementations
- `gemini/`: ChatSession, voice integration views
- `law/`: Law search proxy + ingestion pipeline (see below)
- `land/`: Land regulation analysis (see below)
- `design/`: Building mass optimization — AUA/discover NSGA-II 포팅 (see below)

### Land App (토지 규제 분석)

**Purpose**: 땅 정보(PNU 코드 / 주소 / 용도지역 직접입력) → 건폐율/용적률/건축제한 + 관련 법조항

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/land/analyze/` | 메인: PNU/주소/zones → 건폐율+용적률+법조항 |
| POST | `/land/resolve/` | 주소→PNU (Vworld) 또는 PNU 검증 |
| GET | `/land/zones/` | 21개 용도지역 규제 목록 |
| GET | `/land/stats/` | 쿼리 통계 |

**Services** (`land/services/`):
- `pnu_resolver.py`: PNU 19자리 검증/파싱 + Vworld 지오코딩 + **주소→PNU 자동 추출** (level4LC)
- `zoning_mapper.py`: 21개 용도지역 → 건폐율/용적률 (static JSON, 복수 zone시 최엄격 적용)
- `law_enricher.py`: law-domain-agents(:8011) 법조항 검색 (fail-fast)
- `land_api.py`: data.go.kr 토지이용규제정보 (Phase 3 stub)

**Models**: `LandQuery` (audit log), `ZoningRegulation` (static cache, 미사용)

**Static data**: `land/data/zoning_limits.json` — 21개 용도지역 (주거6 + 상업4 + 공업3 + 녹지3 + 관리3 + 농림1 + 자연환경보전1)

**Tests**: 27개 (Django TestCase), `python manage.py test land -v 2`

**Vworld API** (2026-02-24 연동):
- Key: `VWORLD_API_KEY` in `.env` (만료: 2026-08-24)
- 주소→좌표: `api.vworld.kr/req/address` (PARCEL/ROAD)
- **주소→PNU**: `response.refined.structure.level4LC`에서 19자리 PNU 직접 추출 (Phase 3 없이 해결)
- 테스트: 6/6 지번 주소 PNU 추출 성공 (용인 죽전, 서초, 춘천, 나주, 분당, 강남)

**Phase status**:
- Phase 1-2: DONE (2026-02-22)
- Phase 2.5: DONE (2026-02-24) — Vworld API 연동, 주소→PNU 자동 추출
- Phase 3: DONE (2026-02-24) — Vworld Data API 3개 (getLandUseAttr, ladfrlList, getIndvdLandPriceAttr) → 용도지역+면적+공시지가 자동조회
- Phase 4: DONE — MCP tools (arr_land_analyze/resolve/zones/stats) + Frontend /land 페이지
- Phase 5: DONE — 6-agent→3-agent SelectorGroupChat (039_Land_Swarm_Analysis_Team), 41규제(10core+31ext)
- Phase 6: DONE (2026-03-03) — Agent 협업 SSE (`/land/agent-analyze/stream`), AutoGen WS→SSE 릴레이

### Law App (Dual Role)

**Search Proxy** (runtime - proxies to law-domain-agents:8011):

| Method | Endpoint | Proxies To | Logs |
|--------|----------|------------|------|
| POST | `/law/search/` | `:8011/api/search` | SearchLog |
| GET | `/law/search/stream?query=...&limit=...&domain_id=...` | `:8011/api/search` (SSE wrapper) | SearchLog |
| POST | `/law/domain/<id>/search/` | `:8011/api/domain/<id>/search` | SearchLog |
| GET | `/law/domains/` | `:8011/api/domains` | No |
| GET | `/law/health/` | `:8011/api/health` | No |
| GET | `/law/article/?full_id=...` | Neo4j direct (JO→HANG→HO) | No |
| GET | `/law/stats/` | Django DB (SearchLog aggregation) | - |

Field mapping: Client sends `{"q": ..., "limit": ...}` → proxy sends `{"query": ..., "limit": ...}` to law-domain-agents.

**Ingestion Pipeline** (one-time, `law/STEP/run_all.py`):
- PDF → JSON → Neo4j → Embeddings(OpenAI 3072-dim) → Domains → RelEmbeddings
- `law/core/`: parsers, converters, chunkers (imports guarded by try/except in `__init__.py`)

**Open API Downloader** (`law/scripts/law_downloader.py`):
- law.go.kr Open API → structured JSON (조/항/호/목) → compatible with step2
- Requires: `LAW_API_OC` env var (open.law.go.kr 로그인 ID)
- Usage: `python law_downloader.py --oc EMAIL [--list | --force]`
- Targets 10 laws: 국토계획법(3), 건축법(3), 농지법, 산지관리법, 자연공원법, 수도법
- Output: `law/data/api/*.json` (step2 호환 format)

### Design App (매스 최적화) — AUA/discover 포팅 완료

**Purpose**: 대지 polygon 위 건물 매스 파라메트릭 생성 + NSGA-II 유전 알고리즘 최적화

**Origin**: `AUA/discover/src/objects.py` (Danil Nagy, GPL-3.0) → `ARR/backend/design/engine/objects.py` 코드 적응 (import 아님)
- Grasshopper 의존성(GHClient, Context, Logger) 완전 제거
- callback 패턴(`evaluate_fn`)으로 대체, Django async 호환

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/design/jobs/` | 최적화 작업 생성+시작 |
| GET | `/design/jobs/<id>/` | 작업 상태 조회 |
| GET | `/design/jobs/<id>/stream/` | SSE 실시간 진행 (generation 이벤트) |
| POST | `/design/auto-constraints/` | land/ 분석 결과 → GA 제약조건 자동 변환 |
| GET | `/design/pareto/<id>/` | Pareto front 결과 |

**Services** (`design/services/`):
- `site_geometry.py`: Shapely+pyproj 대지 geometry 처리
- `mass_evaluator.py`: 매스 평가 (건폐율, 용적률, 일조 등)
- `constraint_bridge.py`: `land/analyze/` 결과 → GA 제약조건 자동 변환
- `mass_renderer.py`: GeoJSON 매스 렌더링

**Frontend** (`src/design/`): 3-panel (Map | Controls | Pareto), 6 components, 2 hooks, inline hex styles

**Tests**: 24 Django tests, **Dependencies**: shapely>=2.0, pyproj>=3.6

**SiteMapPanel**: placeholder (Cesium 3D 뷰어 미연동 — AUA 포팅과 무관, Vworld Cesium.js 별도 작업)

### Utility Packages (not Django apps)
- `graph_db/`: PageRank, community detection, CDC event handling
- `parser/`: Law document parsing
- `src/`: Graph utilities, LLM integration, entity extraction

### Inactive Apps (_inactive/)
Coded but never registered in INSTALLED_APPS. To activate:
1. Move from `_inactive/` to `backend/`
2. Add to INSTALLED_APPS in `backend/settings.py`
3. Run `python manage.py makemigrations && migrate`

## Frontend (React + Electron)

- **Stack**: React 18 + TypeScript + Vite 5 + Electron + framer-motion + lucide-react
- **Dev**: `npm run dev` → localhost:5173 (Vite + Electron 동시 실행)
- **Route**: `/#/law` (HashRouter)
- **Vite proxy**: `/law/*`, `/land/*` → `http://127.0.0.1:8000` (CORS 회피, 상대 URL 사용)
- **Styling**: Inline styles with hex colors (Tailwind theme CSS 변수 충돌 회피)
- **Law UI** (`src/law/`): 13 files — 검색 채팅 + 조문 원문 사이드바
  - `LawChat.tsx`: Master-detail layout (채팅 + 420px ArticleDetailPanel)
  - `ArticleDetailPanel.tsx`: 카드 클릭 → Neo4j에서 전체 항/호 조회 → 매칭 항 하이라이트
  - `LawArticleCard.tsx`: 선택 상태 지원 (indigo border + glow)
  - `law-api-client.ts`: `getArticle(fullId)` — `GET /law/article/?full_id=...`

## Connection to 25_ACE Ecosystem

```
ACE MCP Server ──arr_law_search──→ ARR :8000/law/search/ ──proxy──→ law-domain-agents :8011
               ──law_search────────────────────────────────direct──→ law-domain-agents :8011
               ──land_analyze──→ ARR :8000/land/analyze/ ──→ zoning_mapper + law_enricher(:8011)
ARR frontend (src/law/) ──fetch──→ ARR :8000/law/search/
ARR frontend (src/land/) ──fetch──→ ARR :8000/land/analyze/
ARR frontend (src/design/) ──fetch──→ ARR :8000/design/jobs/ (AUA NSGA-II 포팅)
```

| Component | ARR | AG (25_ACE) |
|-----------|-----|-------------|
| Law ingestion | `backend/law/STEP/` (PDF→Neo4j) | - |
| Law search proxy | `backend/law/views.py` → :8011 | `AG/agent/law-domain-agents/` port 8011 |
| Law search MCP | - | ACE MCP: `law_search` (direct) + `arr_law_search` (logged via ARR) |
| Land analysis | `backend/land/views.py` | ACE MCP: `arr_land_analyze/resolve/zones/stats` |
| Law search UI | `frontend/src/law/` → :8000 | `AG-frontend/` (SaaS UI) |
| Land UI | `frontend/src/land/` → :8000 | `AG-frontend/` Land page |
| **Design (매스최적화)** | `backend/design/` (AUA NSGA-II 포팅) | - |
| Design UI | `frontend/src/design/` → :8000 | - |
| Agent system | Worker agents (general, flight) | AutoGen Studio teams (039 Land Swarm) |
| Protocol | A2A (JSON-RPC 2.0) | A2A + MCP |

## Law Pipeline Status (2026-02-27 — 18 LAWS LOADED, FULL PIPELINE)

| Step | Status | Detail |
|------|--------|--------|
| Step1 PDF→JSON | DONE | Parser fixed: TOC duplicate bug, HANG→HO→MOK→JO order |
| Step1-alt API→JSON | DONE | 18 laws downloaded via `law/scripts/law_downloader.py` (law.go.kr Open API) |
| Step2 JSON→Neo4j | DONE | LAW 18, HANG 6171, HO 6026, MOK 1284, JO 2431, JANG 96, JEOL 50 (total 16,081) |
| Step3 Embeddings | DONE | ALL 6171 HANG nodes, OpenAI text-embedding-3-large 3072-dim |
| Step4 Domains | DONE | 5 domains (land_use_regulation:2286, national:2004, building:1018, zoning:614, urban:249) |
| Step5 RelEmbeddings | DONE | ALL 16,058 CONTAINS rel embeddings, `contains_embedding` ONLINE |
| Vector indexes | ONLINE | hang, ho, mok, jo, contains (all 3072-dim cosine) |
| Fulltext indexes | ONLINE | hang_content_fulltext (CJK), jo_content_fulltext |

**18 laws**: 6개 법률(국토계획법, 건축법, 농지법, 산지관리법, 자연공원법, 수도법) × 3 types(법률, 시행령, 시행규칙)

**Scripts**:
- `law/scripts/run_step3_standalone.py` — HANG embeddings, `LAW_NEO4J_PASSWORD=11111111`
- `law/scripts/run_step5_incremental.py` — CONTAINS rel embeddings (incremental)
- `law/scripts/law_downloader.py` — law.go.kr Open API, `LAW_API_OC=hanvit4303`

**Pipeline docs**: `law/PIPELINE.md` (full step-by-step guide)

**Neo4j**: `bolt://localhost:7687`, pw=`11111111` (Neo4j Desktop).

## Testing

- `python manage.py test` - runs all Django tests (law + land)
- `python manage.py test land -v 2` - land app tests only (27 tests)
- `C:/Python313/python tests/test_law_pipeline.py -v` (from 25_ACE root) - cross-project connection tests (28 structural + 21 integration + 5 live E2E)
- No Neo4j required for Django tests or structural tests
