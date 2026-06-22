# Law Search UI — Complete System Handoff

> **Date**: 2026-02-27 | **For**: Next AI agent or developer
> **Goal**: 이 문서 하나로 법규 검색 시스템의 전체 데이터 흐름, 파일 관계, 알려진 제한을 이해할 수 있어야 함.

---

## 1. 시스템 한눈에 보기

```
사용자 입력 ("건폐율 제한")
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  ARR Frontend (React 18 + Electron + Vite 5)  — localhost:5173 │
│                                                                 │
│  LawChat.tsx ─ 메인 화면 (채팅 UI + 사이드바)                    │
│       │                                                         │
│       ├─ REST 검색: useLawChat() → POST /law/search/            │
│       │     └─ LawAPIClient.search() → fetch('/law/search/')    │
│       │                                                         │
│       ├─ SSE 스트리밍: useLawSearchStream() → GET /law/search/stream │
│       │     └─ Django StreamingHttpResponse (text/event-stream)  │
│       │     └─ 6단계 진행 이벤트 + 최종 결과 (domain_id 지원)     │
│       │                                                         │
│       └─ 조문 조회: ArticleDetailPanel → GET /law/article/      │
│             └─ LawAPIClient.getArticle(fullId)                  │
│                                                                 │
│  Vite proxy: /law/* → http://127.0.0.1:8000 (CORS 회피)        │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  ARR Backend (Django)  — localhost:8000                         │
│                                                                 │
│  law/views.py                                                   │
│       │                                                         │
│       ├─ search()        POST /law/search/                      │
│       │     → httpx.post(:8011/api/search, {query, limit})      │
│       │     → SearchLog.objects.create() (SQLite 로깅)           │
│       │                                                         │
│       ├─ search_domain() POST /law/domain/<id>/search/          │
│       │     → httpx.post(:8011/api/domain/<id>/search)          │
│       │                                                         │
│       ├─ domains()       GET /law/domains/                      │
│       │     → httpx.get(:8011/api/domains)                      │
│       │                                                         │
│       ├─ health()        GET /law/health/                       │
│       │     → httpx.get(:8011/api/health)                       │
│       │                                                         │
│       ├─ search_stream() GET /law/search/stream?query=...&limit=...│
│       │     → SSE: 6단계 진행 이벤트 → :8011 검색 → 결과 스트림   │
│       │     → StreamingHttpResponse (text/event-stream)           │
│       │                                                         │
│       ├─ article()       GET /law/article/?full_id=...          │
│       │     → Neo4j DIRECT (singleton driver, bolt://localhost:7687) │
│       │     → JO 노드 조회 → 전체 HANG/HO 반환                   │
│       │                                                         │
│       └─ stats()         GET /law/stats/                        │
│             → SearchLog 집계 (Django ORM)                        │
│                                                                 │
│  law/models.py: SearchLog (query, domain_id, result_count, ms)  │
└─────────────────────────────────────────────────────────────────┘
       │                              │
       ▼                              ▼
┌───────────────────┐    ┌─────────────────────────┐
│ law-domain-agents │    │ Neo4j (bolt://localhost  │
│ FastAPI :8011     │    │         :7687)           │
│                   │    │                          │
│ 7-stage hybrid    │    │ 16,081 노드:             │
│ search engine     │    │  LAW(18), JO(2431),      │
│ (vector+graph+    │    │  HANG(6171), HO(6026),   │
│  RRF+RNE+MMR)    │    │  MOK(1284), JANG(96),    │
│                   │    │  JEOL(50), Domain(5)     │
│ 18 laws, 5 domains│    │                          │
└───────────────────┘    │ Indexes:                 │
                         │  5 vector (3072-dim cos)  │
                         │  2 fulltext (CJK bigram)  │
                         └─────────────────────────┘
```

---

## 2. 프론트엔드 파일별 역할

```
src/law/
├── LawChat.tsx                  ★ 메인 진입점
│   ├── 빈 상태 → Hero (로고, 기능카드, 예시 칩)
│   ├── 검색 후 → 채팅 메시지 리스트 + 하단 입력창
│   ├── 카드 클릭 → 오른쪽 420px 사이드바 (AnimatePresence)
│   └── state: query, streamingMode, selectedArticle, messages
│
├── contexts/LawAPIContext.tsx    전역 상태 Context
│   ├── client (LawAPIClient 싱글턴)
│   ├── domains[] (5개 도메인, 앱 로드 시 fetch)
│   ├── selectedDomainId (도메인 필터)
│   ├── isConnected (30초마다 health 폴링)
│   └── Provider → useLawAPI() hook
│
├── hooks/
│   ├── use-law-chat.ts          REST 검색 훅 ← 현재 기본 모드
│   │   ├── search(query, limit) → client.search() 또는 searchInDomain()
│   │   ├── messages[] (ChatMessage[]) — user/assistant 순서
│   │   ├── loading 메시지 → 결과/에러로 교체 (같은 message.id)
│   │   └── addMessage, clearMessages, removeLastMessage
│   │
│   └── use-law-search-stream.ts SSE 스트리밍 훅
│       ├── startSearch(query, limit, domainId?) → EventSource('/law/search/stream?...')
│       ├── progress: SearchProgress (status, stage, results)
│       ├── 6단계: started → vector_search → relationship → rne_expansion → enrichment → complete
│       └── domain_id 지원 (쿼리 파라미터로 전달)
│
├── lib/
│   ├── types.ts                 모든 타입 정의
│   │   ├── LawArticle       — 검색 결과 1건 (hang_id, content, similarity, stages[])
│   │   ├── LawSearchResponse — 검색 응답 (results[], stats, domain_name)
│   │   ├── ChatMessage       — 채팅 메시지 (role, content, search_response?)
│   │   ├── ArticleDetail     — 조문 상세 (jo, hangs[], hang_count, ho_count)
│   │   ├── ArticleHang       — 항 (full_id, number, content, hos[])
│   │   └── ArticleHo         — 호 (hang_number, number, content, full_id)
│   │
│   └── law-api-client.ts       API 클라이언트 (fetch wrapper)
│       ├── BASE_URL = '' (Vite proxy 경유 → :8000)
│       ├── search(req)       → POST /law/search/     {q, limit}
│       ├── searchInDomain()  → POST /law/domain/<id>/search/
│       ├── getDomains()      → GET  /law/domains/
│       ├── healthCheck()     → GET  /law/health/
│       └── getArticle(id)    → GET  /law/article/?full_id=<id>
│
└── components/
    ├── ResultDisplay.tsx        결과 목록 컨테이너
    │   ├── A2A 결과 있으면 자체/협업 섹션 분리
    │   ├── StatsPanel (상단 통계)
    │   └── CardList → LawArticleCard × N
    │
    ├── LawArticleCard.tsx       결과 카드 1건
    │   ├── 유사도 원형 SVG (80%↑ 녹색, 60%↑ 주황, else 회색)
    │   ├── 법률유형 배지 (법률=파랑, 시행령=보라, 시행규칙=주황)
    │   ├── 검색 단계 배지 (vector, relationship, exact 등)
    │   ├── 더보기/접기 (150자 초과 시)
    │   ├── A2A 배너 (via_a2a=true 시)
    │   ├── onClick → onSelect(article) → 사이드바 열기
    │   └── selected 상태 → indigo border + glow
    │
    ├── ArticleDetailPanel.tsx   조문 원문 사이드바 (420px)
    │   ├── useEffect: fullId 변경 → getArticle(fullId) fetch
    │   ├── 로딩/에러/결과 3-state
    │   ├── 전체 항 렌더링, 매칭된 항 하이라이트 (indigo bg + "검색 결과" 배지)
    │   ├── 각 항 안에 호 리스트 (들여쓰기 + 왼쪽 border)
    │   ├── 전체 복사 버튼 (navigator.clipboard)
    │   └── X 닫기 버튼
    │
    ├── SearchProgress.tsx       SSE 진행 표시
    │   ├── SearchProgressIndicator — 5단계 스텝 + 프로그레스바
    │   ├── SearchCompleteHeader — 녹색 "검색 완료" 배너
    │   └── SearchErrorIndicator — 빨간 에러 배너
    │
    └── StatsPanel.tsx           검색 통계 패널
        ├── 6개 메트릭 (total, vector, relationship, expansion, my_domain, neighbor)
        ├── 비율 분포 바 (녹/보/주)
        └── A2A 협업 도메인 표시
```

---

## 3. 백엔드 article() 엔드포인트 상세

### 데이터 흐름

```
GET /law/article/?full_id=국토의 계획 및 이용에 관한 법률(시행령)::제6장::제84조::①
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^  ^^^^^^^  ^^
                          parts[0] = law(law_type)            parts[1] parts[2] parts[3]

1. full_id.split("::") → ["국토의...법률(시행령)", "제6장", "제84조", "①"]
2. jo_prefix = parts[:-1] 결합 → "국토의...법률(시행령)::제6장::제84조"
3. Neo4j Query 1: MATCH (j:JO) WHERE j.full_id = jo_prefix → JO 노드 (조 번호, 제목)
4. Neo4j Query 2: MATCH (h:HANG) WHERE h.full_id STARTS WITH jo_prefix+"::" → 전체 항
5. Neo4j Query 3: MATCH (h:HANG)-[:CONTAINS]->(ho:HO) WHERE ... → 전체 호
6. 중복 제거: (number, content[:50]) 키로 dedup
7. HO를 hang_number로 그룹핑 → 각 HANG에 hos[] 배열 추가
8. law_name/law_type: full_id 첫 세그먼트에서 '(' 기준 파싱
```

### Neo4j 그래프 구조

```
LAW ─[:CONTAINS]─→ JANG(장) ─[:CONTAINS]─→ JEOL(절) ─[:CONTAINS]─→ JO(조)
                                                        │
                                              또는 직접: JANG → JO
                                                        │
                                                        ▼
                                            JO ─[:CONTAINS]─→ HANG(항)
                                                                │
                                                                ▼
                                                HANG ─[:CONTAINS]─→ HO(호)
                                                                      │
                                                                      ▼
                                                        HO ─[:CONTAINS]─→ MOK(목)
```

### full_id 규칙
```
LAW:  "국토의 계획 및 이용에 관한 법률(시행령)"
JANG: "국토의...법률(시행령)::제6장"
JO:   "국토의...법률(시행령)::제6장::제84조"
HANG: "국토의...법률(시행령)::제6장::제84조::①"
HO:   "국토의...법률(시행령)::제6장::제84조::①::1"
```

**핵심**: HANG의 full_id에서 마지막 `::` 세그먼트를 떼면 = JO의 full_id.
article() 엔드포인트는 이 규칙에 의존함.

---

## 4. 스타일링 규칙

**모든 law/ 컴포넌트는 inline style + hex color 사용.**

```tsx
// ✅ 올바른 방식
style={{ color: '#4f46e5', background: '#eef2ff', borderRadius: 16 }}

// ❌ 사용하지 않음 (Tailwind CSS 변수가 해결되지 않아 색상이 깨짐)
className="text-indigo-600 bg-indigo-50 rounded-2xl"
```

**이유**: ARR frontend의 Tailwind 설정이 모든 색상 토큰을 CSS 변수(`--color-*`)로 재정의하는데,
해당 CSS 변수가 `:root`에 정의되지 않아 모든 Tailwind 색상 클래스가 `color: var(--color-indigo-600)` → 빈 값 → 검은색/투명으로 렌더링됨.

**법률 유형별 색상 (두 곳에서 동일하게 사용)**:
| 유형 | accent | bg | text |
|------|--------|----|------|
| 법률 | `#3b82f6` | `#eff6ff` | `#1d4ed8` |
| 시행령 | `#7c3aed` | `#f5f3ff` | `#6d28d9` |
| 시행규칙 | `#d97706` | `#fffbeb` | `#b45309` |

---

## 5. 알려진 제한 & TODO

| 항목 | 상태 | 설명 |
|------|------|------|
| ~~SSE 스트리밍~~ | ✅ 해결 | Django `search_stream()` — StreamingHttpResponse + 6단계 진행 |
| ~~도메인 필터+스트리밍~~ | ✅ 해결 | `startSearch(query, limit, domainId)` — domain_id 쿼리 파라미터 |
| full_id 가정 | 주의 | article()은 "마지막 :: 세그먼트 = 항 번호"를 전제. 중간 구조가 다르면 깨짐 |
| null order | 해결 | `coalesce(h.order, 9999)`로 null 안전 정렬 |
| ~~driver leak~~ | ✅ 해결 | 모듈 레벨 singleton driver 사용 |
| ~~event bubbling~~ | ✅ 해결 | 더보기 버튼에 `e.stopPropagation()` 추가 |
| ~~QueryInput dead code~~ | ✅ 삭제 | 미사용 컴포넌트 제거 |

---

## 6. 실행 방법

```bash
# 1. Neo4j Desktop 실행 (bolt://localhost:7687, pw=11111111)

# 2. Django 백엔드
cd D:\Data\25_ACE\ARR\backend
python manage.py runserver 8000

# 3. law-domain-agents (선택 — 검색에 필요, 조문조회는 불필요)
cd D:\Data\25_ACE\AG\agent\law-domain-agents
python server.py   # :8011

# 4. ARR 프론트엔드
cd D:\Data\25_ACE\ARR\frontend
npm run dev   # :5173 (Electron + Vite)

# 5. 접속
# Electron 자동 열림 또는 브라우저: http://localhost:5173/#/law
```

---

## 7. 테스트 커맨드

```bash
# 검색 (Vite proxy 경유)
curl -s http://localhost:5173/law/health/ | python -m json.tool

# 검색 (Django 직접)
printf '{"q":"건폐율","limit":5}' | curl -s -X POST -H "Content-Type: application/json" -d @- http://localhost:8000/law/search/ | python -m json.tool

# 조문 조회
curl -s "http://localhost:8000/law/article/?full_id=%EA%B5%AD%ED%86%A0%EC%9D%98%20%EA%B3%84%ED%9A%8D%20%EB%B0%8F%20%EC%9D%B4%EC%9A%A9%EC%97%90%20%EA%B4%80%ED%95%9C%20%EB%B2%95%EB%A5%A0(%EC%8B%9C%ED%96%89%EB%A0%B9)::제6장::제84조::①" | python -m json.tool
# → 16 hangs, 73 hos
```
