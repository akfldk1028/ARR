# law/ - 법규 검색 AI 채팅 UI

> **Note (2026-02-27)**: ARR Legacy Frontend. 주력 프론트엔드는 `AG-frontend/`.
> Vite proxy로 Django(:8000)에 연결 — CORS 없이 상대 URL 사용.

## 개요

Django 백엔드의 법규 검색 시스템과 연동되는 React 채팅 UI.
검색 결과 카드 클릭 시 오른쪽 사이드바에 조문 원문(전체 항/호) 표시.

---

## 아키텍처

```
[Frontend :5173]                          [Backend :8000]         [Neo4j :7687]
LawChat.tsx                                Django law proxy
    ↓                                          ↓
useLawChat()        ──REST──→ /law/search/  ──→ :8011/api/search
useLawSearchStream() ──SSE──→ /law/search/stream (via :8011)
LawAPIContext       ──REST──→ /law/domains/ ──→ :8011/api/domains
ArticleDetailPanel  ──REST──→ /law/article/?full_id=... ──→ Neo4j (direct)
                                                              ↑
                                                    JO → 전체 HANG/HO 조회
```

**Vite proxy** (`vite.config.ts`):
- `/law/*` → `http://127.0.0.1:8000`
- `/land/*` → `http://127.0.0.1:8000`

---

## 파일 구조

```
law/
├── LawChat.tsx                  # 메인 채팅 UI (master-detail layout)
├── contexts/
│   └── LawAPIContext.tsx        # API 클라이언트 & 도메인 관리
├── hooks/
│   ├── use-law-chat.ts          # REST API 검색 훅
│   └── use-law-search-stream.ts # SSE 스트리밍 훅
├── lib/
│   ├── types.ts                 # 타입 정의 (LawArticle, ArticleDetail 등)
│   └── law-api-client.ts        # API 클라이언트 (LawAPIClient)
├── components/
│   ├── ResultDisplay.tsx        # 검색 결과 목록
│   ├── LawArticleCard.tsx       # 법률 조항 카드 (클릭→사이드바)
│   ├── ArticleDetailPanel.tsx   # 조문 원문 사이드바 (전체 항/호)
│   ├── HeroSearch.tsx           # 빈 상태 히어로 검색 화면
│   ├── MapPanel.tsx             # 3D Vworld 지도 패널
│   ├── Pill.tsx                 # 상태 배지 컴포넌트
│   ├── SearchProgress.tsx       # 진행상황 표시
│   └── StatsPanel.tsx           # 통계 패널
└── README.md
```

---

## 핵심 기능

### 1. 법규 검색 (REST / SSE)

| 모드 | 프로토콜 | 특징 |
|------|----------|------|
| REST | HTTP POST `/law/search/` | 결과만 반환 (기본) |
| SSE 스트리밍 | GET `/law/search/stream?query=...&limit=...&domain_id=...` | 6단계 실시간 진행 + 결과 |

**SSE 이벤트 흐름**:
```
1. started        → { status: "started", stage: "exact_match", progress: 0.0 }
2. searching      → { status: "searching", stage: "vector_search", progress: 0.2 }
3. searching      → { status: "searching", stage: "relationship_search", progress: 0.4 }
4. processing     → { status: "processing", stage: "rne_expansion", progress: 0.7 }
5. processing     → { status: "processing", stage: "enrichment", progress: 0.9 }
6. complete       → { status: "complete", results: [...], result_count, response_time }
```

### 2. 조문 원문 사이드바 (ArticleDetailPanel)

검색 결과 카드 클릭 → 오른쪽 420px 사이드바에 전체 조문 표시.

**동작**:
1. `LawArticleCard` 클릭 → `selectedArticle` 설정
2. `ArticleDetailPanel`이 `GET /law/article/?full_id=...` 호출
3. Django가 Neo4j에서 JO(조) → 전체 HANG(항) + HO(호) 조회
4. 매칭된 항 하이라이트 (`검색 결과` 배지)
5. 전체 복사 버튼

**API**: `GET /law/article/?full_id=국토의 계획 및 이용에 관한 법률(시행령)::제6장::제84조::①`

**응답**:
```json
{
  "jo_prefix": "국토의 계획 및 이용에 관한 법률(시행령)::제6장::제84조",
  "law_name": "국토의 계획 및 이용에 관한 법률",
  "law_type": "시행령",
  "jo": { "full_id": "...", "number": "제84조", "title": "용적률" },
  "hangs": [
    {
      "full_id": "...::①", "number": "①", "content": "...",
      "hos": [
        { "hang_number": "①", "number": "1", "content": "...", "full_id": "..." }
      ]
    }
  ],
  "hang_count": 16,
  "ho_count": 73
}
```

### 3. Master-Detail 레이아웃

```
┌─────────────────────────────────┬──────────────┐
│  채팅 영역 (flex: 1)           │ 사이드바     │
│  ┌───────────────────────────┐  │ (420px)      │
│  │ user: "건폐율 제한"       │  │              │
│  │ assistant: 10개 결과      │  │ 조문 원문    │
│  │   [카드1] [카드2*] [카드3]│  │ 제84조       │
│  │                           │  │ ① ...        │
│  └───────────────────────────┘  │ ② ...        │
│  [검색창]                       │ ③ ...        │
└─────────────────────────────────┴──────────────┘
                                   * 클릭한 카드
```

---

## 스타일링

**Inline styles with hex colors** — Tailwind theme CSS 변수 충돌 방지.

```tsx
// ✅ 사용 방식 (inline hex)
style={{ color: '#4f46e5', background: '#eef2ff' }}

// ❌ 사용하지 않음 (Tailwind 클래스 — 색상 변수 미해결)
className="text-indigo-600 bg-indigo-50"
```

**법률 유형별 색상**:
- 법률: 파랑 (#3b82f6)
- 시행령: 보라 (#7c3aed)
- 시행규칙: 주황 (#d97706)

---

## 실행

```bash
# 1. 백엔드 (Django + Neo4j)
cd D:\Data\25_ACE\ARR\backend
python manage.py runserver 8000      # Neo4j bolt://localhost:7687 필요

# 2. 프론트엔드 (Vite + Electron)
cd D:\Data\25_ACE\ARR\frontend
npm run dev                           # localhost:5173 (proxy → :8000)

# 3. 접속
# Electron: 자동으로 열림
# 브라우저: http://localhost:5173/#/law
```

---

## 백엔드 엔드포인트

| Method | Path | Description | Backend |
|--------|------|-------------|---------|
| POST | `/law/search/` | 검색 (proxy → :8011) | `law/views.py:search` |
| POST | `/law/domain/<id>/search/` | 도메인 검색 | `law/views.py:search_domain` |
| GET | `/law/domains/` | 도메인 목록 | proxy → :8011 |
| GET | `/law/health/` | 헬스체크 | proxy → :8011 |
| GET | `/law/article/?full_id=...` | 조문 원문 (Neo4j direct) | `law/views.py:article` |
| GET | `/law/stats/` | 검색 통계 | Django DB |
