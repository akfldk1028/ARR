# Law App (ARR Django)

법률 검색 프록시 + 데이터 적재 파이프라인. 검색 로직은 `law-domain-agents(:8011)`에서 처리하며, 이 앱은 프록시 + 로깅 역할.

## Search Proxy (런타임)

law-domain-agents(:8011)로 프록시하고 SearchLog에 기록.

| Method | Endpoint | Proxies To | Logs |
|--------|----------|------------|------|
| POST | `/law/search/` | `:8011/api/search` | SearchLog |
| POST | `/law/domain/<id>/search/` | `:8011/api/domain/<id>/search` | SearchLog |
| GET | `/law/domains/` | `:8011/api/domains` | No |
| GET | `/law/health/` | `:8011/api/health` | No |
| GET | `/law/stats/` | Django DB (SearchLog 집계) | - |

### Field Mapping

```
Client → ARR:  {"q": "건폐율", "limit": 10}
ARR → :8011:   {"query": "건폐율", "limit": 10}
```

### SearchLog Model

`query`, `domain_id`, `limit`, `result_count`, `response_time_ms`, `source`, `created_at`

## Data Ingestion (2가지 방법)

### A) PDF Pipeline (legacy, 국토계획법 only)

```bash
cd ARR/backend
python law/STEP/run_all.py   # ~60분, $3-5
```

### B) Open API Pipeline (recommended, 10+ laws)

```bash
cd ARR/backend/law/scripts
python law_downloader.py --oc YOUR_EMAIL --list    # 검색 테스트
python law_downloader.py --oc YOUR_EMAIL            # 10개 법률 다운로드
python law_downloader.py --oc YOUR_EMAIL --force    # 기존 파일 덮어쓰기
```

- `LAW_API_OC` env var 또는 `--oc` flag로 인증 (open.law.go.kr 가입 필요)
- Output: `law/data/api/*.json` (step2 호환 format)
- Targets: 국토계획법(3), 건축법(3), 농지법, 산지관리법, 자연공원법, 수도법

### Pipeline Status (2026-02-23)

| Step | Status | Detail |
|------|--------|--------|
| Step1 PDF→JSON | DONE | Parser fixed: HANG→HO→MOK→JO order, HO "1의2." pattern, noise filter |
| Step1-alt API→JSON | NEW | `law_downloader.py` — law.go.kr Open API, structured 조/항/호/목 |
| Step2 JSON→Neo4j | DONE | HANG 1966, HO 1118, MOK 232, JO 920 (total 4236 nodes) |
| Step3 Embeddings | DONE | 1966 HANG, OpenAI text-embedding-3-large, 3072-dim, ~$0.03 |
| Step4 Domains | DONE | 2 domains (용도지역 1838, 도시계획 및 이용 128) |
| Step5 RelEmbeddings | TODO | ~30min, $2-3 |

### Standalone Step3

```bash
LAW_NEO4J_PASSWORD=11111111 python law/scripts/run_step3_standalone.py
```

## Data

```
law/
├── data/
│   ├── raw/       # 원본 PDF (3개 법률)
│   ├── parsed/    # PDF 파싱된 JSON (3개, legacy)
│   └── api/       # API 다운로드 JSON (10개, recommended)
├── STEP/          # PDF 파이프라인 (step1~5 + run_all)
├── scripts/       # 독립 스크립트
│   ├── run_step3_standalone.py   # 임베딩 (Django 불필요)
│   └── law_downloader.py         # law.go.kr Open API 다운로더
├── core/          # 파서, 변환기, 청커 (try/except import guard)
├── models.py      # SearchLog
├── views.py       # 프록시 뷰 (httpx → :8011)
└── urls.py        # /law/* 라우팅
```

## Setup

1. `law` in INSTALLED_APPS (`backend/settings.py`)
2. `path('law/', include('law.urls'))` in `backend/urls.py`
3. `python manage.py migrate` (SearchLog 테이블 생성)
4. law-domain-agents running on port 8011

## Neo4j

```
bolt://localhost:7687, pw=11111111 (Neo4j Desktop) — 법규 데이터 전용
```
