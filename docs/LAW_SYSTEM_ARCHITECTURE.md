# 법규 검색 시스템 전체 아키텍처 (2026-02-24)

## 한줄 요약

**10개 한국 법률**이 Neo4j 그래프DB에 적재 → 7단계 하이브리드 검색 파이프라인으로 검색 → MCP/REST API로 제공.

---

## 1. 전체 시스템 구조

```
┌──────────────────────────────────────────────────────────────────┐
│                        사용자 / AI Agent                          │
└──────┬──────────────────────┬──────────────────────┬─────────────┘
       │                      │                      │
  AG-frontend            ACE MCP Server          ARR frontend
  (Vite+React)           (57 tools)              (React+Electron)
  :5173                  stdio/:8200             legacy
       │                      │                      │
       │            ┌─────────┴──────────┐           │
       │            │                    │           │
       │      law_search()         arr_law_search()  │
       │      (직접, 빠름)          (프록시, 로그)     │
       │            │                    │           │
       │            │         ┌──────────▼─────────┐ │
       │            │         │  ARR Django :8000   │◄┘
       │            │         │  /law/search/       │
       │            │         │  → SearchLog(SQLite) │
       │            │         └──────────┬─────────┘
       │            │                    │
       │            └───────┬────────────┘
       │                    │
       │         ┌──────────▼───────────────┐
       │         │  law-domain-agents :8011  │
       │         │  (FastAPI + A2A protocol) │
       │         │  LawSearchEngine          │
       │         │  7-stage hybrid search    │
       │         └──────────┬───────────────┘
       │                    │
       │         ┌──────────▼───────────────┐
       │         │  Neo4j :7687              │
       │         │  9,517 nodes, 10 laws     │
       │         │  bolt://localhost:7687     │
       │         │  pw: 11111111             │
       │         └──────────────────────────┘
```

---

## 2. Neo4j에 적재된 법률 (10개)

### 법률 목록

| # | 법률명 | 타입 | HANG수 | 비고 |
|---|--------|------|--------|------|
| 1 | 국토의 계획 및 이용에 관한 법률 | 법률 | 929 | 용도지역, 건폐율, 용적률의 본거지 |
| 2 | 국토의 계획 및 이용에 관한 법률 | 시행령 | 888 | 구체적 수치, 한도 |
| 3 | 국토의 계획 및 이용에 관한 법률 | 시행규칙 | 149 | 서식, 절차 |
| 4 | 건축법 | 법률 | 489 | 건축허가, 건축기준 |
| 5 | 건축법 | 시행령 | 370 | 건축허가 세부, 용도분류 |
| 6 | 건축법 | 시행규칙 | 159 | 건축허가 서식, 신고 |
| 7 | 농지법 | 법률 | 206 | 농지전용, 농지보전 |
| 8 | 산지관리법 | 법률 | 242 | 산지전용, 산지보전 |
| 9 | 자연공원법 | 법률 | 178 | 자연공원 내 행위제한 |
| 10 | 수도법 | 법률 | 333 | 상수원보호구역 |

**합계**: HANG 3,943개 (법조항 항 단위)

### 노드 구조

```
LAW (10)
 └─ JANG (73) — 장
     └─ JEOL (27) — 절 (선택적)
         └─ JO (1,774) — 조 (조문)
             └─ HANG (3,943) — 항 (검색 단위, 임베딩 보유)
                 └─ HO (3,135) — 호
                     └─ MOK (550) — 목

Domain (5) ←── BELONGS_TO_DOMAIN ──── HANG

총 노드: 9,517
```

### 관계(Relationships)

| 관계 | 설명 |
|------|------|
| `CONTAINS` | 계층 포함 (LAW→JANG→JO→HANG→HO→MOK) |
| `NEXT` | 순서 연결 (JO→JO, HANG→HANG) |
| `BELONGS_TO_DOMAIN` | HANG→Domain 소속 |

### 5개 도메인

| Domain ID | 이름 | HANG 수 |
|-----------|------|---------|
| national_land_planning | 국토계획 총론 | 1,526 |
| building_standards | 건축기준 | 1,018 |
| land_use_regulation | 토지이용규제 | 959 |
| zoning_regulation | 용도지역 및 건축규제 | 312 |
| urban_planning | 도시계획 | 128 |

### 인덱스

| 타입 | 이름 | 용도 |
|------|------|------|
| VECTOR | `hang_embedding_index` | 벡터 검색 (OpenAI 3072-dim, cosine) |
| VECTOR | `ho_embedding_index` | HO 벡터 (미사용) |
| VECTOR | `mok_embedding_index` | MOK 벡터 (미사용) |
| VECTOR | `jo_embedding_index` | JO 벡터 (미사용) |
| FULLTEXT | `hang_content_fulltext` | CJK 키워드 검색 (bi-gram analyzer) |
| VECTOR | `contains_embedding` | 관계 임베딩 (step5 미실행, 비어있음) |

---

## 3. 데이터 적재 파이프라인 (Ingestion)

### 데이터 소스 → Neo4j 흐름

```
law.go.kr Open API                  ARR/backend/law/
─────────────────                  ──────────────────
법률 원문 XML/JSON  ──→  law_downloader.py  ──→  data/api/*.json (10개)
                         (OC=hanvit4303)            │
                                                    ▼
                                            json_to_neo4j.py (step2)
                                                    │
                                                    ▼
                                              Neo4j :7687
                                            (LAW→JANG→JO→HANG→HO→MOK)
                                                    │
                                                    ▼
                                            run_step3_standalone.py
                                            (OpenAI embedding 3072-dim)
                                                    │
                                                    ▼
                                            initialize_domains.py (step4)
                                            (5 Domain + BELONGS_TO_DOMAIN)
```

### 각 Step 실행 방법

```bash
# Step 1: 법률 다운로드 (law.go.kr API)
cd ARR/backend/law/scripts
LAW_API_OC=hanvit4303 C:/Python313/python law_downloader.py --force

# Step 2: JSON → Neo4j 적재
cd ARR/backend/law/STEP
C:/Python313/python run_all.py  # 또는 step2만 단독 실행

# Step 3: 임베딩 생성 (OpenAI API 필요, 비용 발생)
LAW_NEO4J_PASSWORD=11111111 C:/Python313/python ARR/backend/law/scripts/run_step3_standalone.py

# Step 4: 도메인 분류
C:/Python313/python AG/agent/law-domain-setup/initialize_domains.py

# Fulltext 인덱스 생성 (한 번만)
C:/Python313/python tests/_create_fulltext_idx.py
```

### 파일 위치

| 파일 | 위치 | 역할 |
|------|------|------|
| 법률 JSON 원본 | `ARR/backend/law/data/api/*.json` | 10개 법률 (law.go.kr) |
| PDF 원본 (legacy) | `ARR/backend/law/data/parsed/` | 국토계획법 3개만 |
| 다운로더 | `ARR/backend/law/scripts/law_downloader.py` | API → JSON |
| Neo4j 적재 | `ARR/backend/law/STEP/step2/json_to_neo4j.py` | JSON → Neo4j |
| 임베딩 | `ARR/backend/law/scripts/run_step3_standalone.py` | OpenAI 3072-dim |
| 도메인 | `AG/agent/law-domain-setup/initialize_domains.py` | 5개 도메인 생성 |
| 파이프라인 문서 | `ARR/backend/law/PIPELINE.md` | Step별 상세 가이드 |

---

## 4. 검색 파이프라인 (7단계)

### 전체 흐름

```
사용자 쿼리: "건폐율"
        │
        ▼
[1] 임베딩 생성 ─── OpenAI text-embedding-3-large (3072-dim)
        │
        ▼
[2] Hybrid Search (4 signals, 각각 법률별 diversity cap)
    ├── Exact Match ──── 조항번호 regex → full_id CONTAINS
    ├── Fulltext CJK ── hang_content_fulltext index, 법률당 max 3개
    ├── Vector Search ── hang_embedding_index, 법률당 max 4개
    └── Relationship ─── contains_embedding (현재 비활성)
        │
        ▼
[3] RRF (Reciprocal Rank Fusion, k=60, 4 signals) → 2x top_k 후보
        │
        ▼
[4] RNE Graph Expansion ── JO 이웃 HANG, cosine >= 0.35
        │
        ▼
[5] Merge (Hybrid + RNE, dedup)
        │
        ▼
[6] MMR Reranking ── λ=0.7, 관련성+다양성 균형 → top_k 선별
        │
        ▼
[7] Hierarchy Expansion ── 법률↔시행령↔시행규칙 인용 교차검색
    (상위 5개 뒤에 삽입)
        │
        ▼
[8] Enrichment ── law_name, law_type, article 추가 → 최종 top_k
        │
        ▼
JSON Response: [{hang_id, content, similarity, stages, law_name, law_type, article}, ...]
```

### 검색 성능 (2026-02-24)

| 쿼리 | limit=15 | limit=40 |
|------|----------|----------|
| 용도지역 | 4 laws (국토+자연+농지+산지) | **6 laws (ALL)** |
| 건폐율 | 3 laws (국토+건축+수도) | 5 laws |
| 건축허가 | 2 laws (건축+국토) | 2 laws |
| 농지전용 | 3 laws (농지+산지+국토) | 3 laws |

### 핵심 코드 파일

| 파일 | 위치 | 역할 |
|------|------|------|
| `law_search_engine.py` | `AG/agent/law-domain-agents/` | 검색 엔진 (7단계 파이프라인) |
| `server.py` | 같은 디렉토리 | FastAPI 서버 (REST + A2A) |
| `domain_agent_factory.py` | 같은 디렉토리 | LawSearchEngine 인스턴스 생성 |
| `domain_manager.py` | 같은 디렉토리 | Neo4j에서 도메인 로드 |
| `law_utils.py` | 같은 디렉토리 | enrichment (law_name, law_type 파싱) |

---

## 5. API 엔드포인트

### law-domain-agents (:8011) — 실제 검색 엔진

| Method | Path | Body | 설명 |
|--------|------|------|------|
| POST | `/api/search` | `{query, limit}` | 전체 도메인 검색 |
| POST | `/api/domain/{id}/search` | `{query, limit}` | 도메인별 검색 |
| GET | `/api/domains` | - | 5개 도메인 목록 |
| GET | `/api/health` | - | 헬스체크 |

### ARR Django (:8000) — 프록시 + 로그

| Method | Path | Body | 설명 |
|--------|------|------|------|
| POST | `/law/search/` | `{q, limit}` | → :8011 프록시 + SearchLog |
| POST | `/law/domain/{id}/search/` | `{q, limit}` | → :8011 도메인 검색 |
| GET | `/law/domains/` | - | → :8011 도메인 목록 |
| GET | `/law/health/` | - | → :8011 헬스체크 |
| GET | `/law/stats/` | - | SearchLog 통계 (Django DB) |
| POST | `/land/analyze/` | `{input, zones, ...}` | 토지 규제 분석 |
| POST | `/land/resolve/` | `{address}` | 주소→PNU (Vworld API) |
| GET | `/land/zones/` | - | 21개 용도지역 규제 목록 |

### Response Format (검색 결과)

```json
{
  "results": [
    {
      "hang_id": "국토의_계획_및_이용에_관한_법률(시행령)_제84조_제1항",
      "content": "법 제77조제1항 및 제2항에 따른 건폐율의 최대한도는...",
      "unit_path": "제6장 > 제84조 > 제1항",
      "similarity": 0.731,
      "stages": ["fulltext_keyword"],
      "law_name": "국토의 계획 및 이용에 관한 법률",
      "law_type": "시행령",
      "article": "제84조"
    }
  ],
  "stats": {
    "total": 15,
    "vector_count": 8,
    "fulltext_keyword_count": 4,
    "hierarchy_expansion_count": 3
  },
  "domain_id": null,
  "domain_name": "전체",
  "response_time": 574
}
```

---

## 6. 환경 설정

### 필수 환경변수

| 변수 | 값 | 용도 |
|------|---|------|
| `NEO4J_PASSWORD` | `11111111` | Neo4j 접속 |
| `OPENAI_API_KEY` | (secret) | 임베딩 생성 + 검색 쿼리 |
| `LAW_API_OC` | `hanvit4303` | law.go.kr API (다운로드 시) |
| `VWORLD_API_KEY` | (in .env) | Vworld 지오코딩 + PNU 추출 (만료: 2026-08-24) |

### 서비스 시작 순서

```bash
# 1. Neo4j Desktop 실행 (bolt://localhost:7687)

# 2. law-domain-agents 시작
cd AG/agent/law-domain-agents
.venv/Scripts/python server.py    # → :8011

# 3. (선택) ARR Django 시작
cd ARR/backend
python manage.py runserver 8000   # → :8000

# 4. 헬스체크
curl http://localhost:8011/api/health
curl http://localhost:8000/law/health/
```

### Neo4j 브라우저 확인

```
http://localhost:7474
ID: neo4j / PW: 11111111
```

유용한 Cypher:
```cypher
-- 전체 LAW 목록
MATCH (l:LAW) RETURN l.full_id, l.law_name, l.law_type ORDER BY l.law_name

-- 노드 수 요약
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt ORDER BY cnt DESC

-- 특정 법률의 조문 구조
MATCH (l:LAW {law_name: '건축법', law_type: '법률'})-[:CONTAINS*]->(j:JO)
RETURN j.full_id, j.title LIMIT 20

-- 도메인별 HANG 수
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
RETURN d.domain_name, count(h) ORDER BY count(h) DESC

-- "건폐율" 포함 조항 검색
CALL db.index.fulltext.queryNodes('hang_content_fulltext', '건폐율')
YIELD node, score
RETURN node.full_id, score LIMIT 10
```

---

## 7. 향후 계획

### 법률 추가 (Phase 5)

현재 10개 → **건축관련법 전체** 확장 예정:
- 주택법, 도시개발법, 도시 및 주거환경정비법, 개발제한구역법
- 경관법, 주차장법, 도로법, 환경영향평가법 등

추가 방법:
1. `law_downloader.py`의 `LAWS_TO_DOWNLOAD`에 법률 추가
2. `--force`로 다운로드
3. step2 → step3 → step4 재실행

### 검색 개선 (잔여)

| 항목 | 상태 | 우선순위 |
|------|------|---------|
| Fulltext CJK 검색 | DONE | - |
| MMR diversity | DONE | - |
| RNE threshold 조정 | DONE | - |
| 법률별 diversity cap | DONE | - |
| Hierarchy expansion | DONE | - |
| Exact match substring 오탐 | TODO | LOW |
| Relationship search (step5) | TODO | LOW |
| limit=15에서 6/6 법률 보장 | TODO | MEDIUM |

### 토지 분석 연동 (Phase 2.5-5)

```
Phase 2.5: DONE (2026-02-24) — Vworld API 연동, 주소→PNU 자동 추출
Phase 3: TODO — data.go.kr API (PNU→용도지역 자동 조회)
Phase 4: TODO — MCP tools + Frontend
Phase 5: TODO — Agent 협업 — 여러 AI agent가 토지 정보 기반 법규 분석
         (건폐율/용적률/건축제한 + 근거 법조항 자동 도출)
```

### Vworld API 연동 (Phase 2.5 — DONE)

토지의 주소를 PNU(필지고유번호 19자리)로 변환하는 기능.

```
주소 입력 → Vworld Geocode API → response.refined.structure.level4LC → 19자리 PNU
```

- **API**: `https://api.vworld.kr/req/address` (PARCEL 타입 우선, fallback ROAD)
- **Key**: `VWORLD_API_KEY` in `ARR/backend/.env` (만료: 2026-08-24)
- **코드**: `ARR/backend/land/services/pnu_resolver.py`
- **PNU 추출**: `level4LC` 필드에서 19자리 코드 직접 추출 (data.go.kr 불필요)
- **테스트**: 6/6 지번 주소 성공 (용인 죽전, 서초, 춘천, 나주, 분당, 강남)
- **제한**: "산" 주소(임야)는 지오코딩 실패 가능

---

## 8. 문서 위치 요약

| 문서 | 위치 | 내용 |
|------|------|------|
| 이 문서 | `ARR/docs/LAW_SYSTEM_ARCHITECTURE.md` | 전체 시스템 구조 |
| 파이프라인 가이드 | `ARR/backend/law/PIPELINE.md` | Step별 실행 방법 |
| 검색 엔진 상세 | `AG/agent/law-domain-agents/SEARCH_PIPELINE_REVIEW.md` | 검색 7단계 분석 |
| 검색 엔진 CLAUDE.md | `AG/agent/law-domain-agents/CLAUDE.md` | 검색 엔진 코드 컨텍스트 |
| ARR CLAUDE.md | `ARR/CLAUDE.md` | ARR Django 전체 컨텍스트 |
| 프로젝트 CLAUDE.md | `CLAUDE.md` | 25_ACE 전체 컨텍스트 |
| 검증 로그 | `tests/search_pipeline_v2_verification.log` | 검색 결과 검증 |
