# law/ - 법규 검색 AI 채팅 UI

## 개요

Django 백엔드의 Multi-Agent 법규 검색 시스템과 연동되는 React 프론트엔드.

---

## 백엔드 연동

```
[Frontend]                              [Backend]
LawChat.tsx                             Django (port 8000)
    ↓                                       ↓
useLawSearchStream() ──SSE──→ /agents/law/api/search/stream
useLawChat()        ──REST──→ /agents/law/api/search
LawAPIContext       ──REST──→ /agents/law/api/domains
```

**백엔드 URL**: `http://127.0.0.1:8000`

---

## 파일 구조

```
law/
├── LawChat.tsx              # 메인 채팅 컴포넌트
├── contexts/
│   └── LawAPIContext.tsx    # API 클라이언트 & 도메인 관리
├── hooks/
│   ├── use-law-chat.ts      # REST API 검색 훅
│   └── use-law-search-stream.ts  # SSE 스트리밍 훅
└── components/
    ├── QueryInput.tsx       # 검색 입력 폼
    ├── ResultDisplay.tsx    # 검색 결과 표시
    ├── LawArticleCard.tsx   # 법률 조항 카드
    ├── SearchProgress.tsx   # 진행상황 표시
    └── StatsPanel.tsx       # 통계 패널
```

---

## 핵심 컴포넌트

### LawChat.tsx

메인 채팅 인터페이스.

```tsx
export default function LawChat() {
  return (
    <LawAPIProvider>
      <LawChatInner />
    </LawAPIProvider>
  );
}
```

**주요 기능:**
- 도메인 선택 (전체 자동 라우팅 / 특정 도메인)
- 스트리밍 모드 토글
- 메시지 히스토리
- 검색 중단

---

## Hooks

### useLawSearchStream (SSE 스트리밍)

```typescript
const { progress, isSearching, startSearch, stopSearch } = useLawSearchStream('http://127.0.0.1:8000');

// 검색 시작
startSearch("17조 검색", 10);

// 진행상황 확인
console.log(progress?.stage);      // 'exact_match' | 'vector_search' | 'rne_expansion' 등
console.log(progress?.progress);   // 0.0 ~ 1.0
console.log(progress?.status);     // 'started' | 'searching' | 'complete' | 'error'
```

**SearchProgress 타입:**

```typescript
interface SearchProgress {
  status: 'started' | 'searching' | 'processing' | 'complete' | 'error';
  stage?: 'exact_match' | 'vector_search' | 'relationship_search' | 'rne_expansion' | 'enrichment';
  stage_name?: string;      // 한글 단계 이름
  progress?: number;        // 0 ~ 1
  agent?: string;           // 활성 에이전트 이름
  domain_id?: string;
  domain_name?: string;
  results?: any[];          // 완료 시 결과
  result_count?: number;
  response_time?: number;   // ms
  message?: string;         // 에러 메시지
}
```

### useLawChat (REST API)

```typescript
const { messages, isLoading, search, clearMessages } = useLawChat();

// 검색
search("17조 검색", 10);

// 메시지 히스토리
messages.forEach(msg => {
  console.log(msg.role);              // 'user' | 'assistant'
  console.log(msg.content);
  console.log(msg.search_response);   // 검색 결과
});
```

---

## Context

### LawAPIContext

전역 상태 관리.

```tsx
function MyComponent() {
  const {
    client,           // API 클라이언트
    domains,          // 도메인 목록
    domainsLoading,   // 로딩 상태
    selectedDomainId, // 선택된 도메인
    setSelectedDomainId,
    isConnected,      // 백엔드 연결 상태
    refreshDomains,   // 도메인 새로고침
  } = useLawAPI();
  
  // ...
}
```

---

## 컴포넌트

### QueryInput

```tsx
<QueryInput 
  onSearch={(query) => startSearch(query, 10)} 
  isLoading={isSearching} 
/>
```

### ResultDisplay

```tsx
<ResultDisplay 
  response={{
    results: [...],
    total_count: 10,
    response_time: 342,
    domain_name: '도시계획'
  }} 
/>
```

### SearchProgress

```tsx
// 진행 중
<SearchProgressIndicator progress={progress} />

// 완료
<SearchCompleteHeader 
  resultCount={10} 
  responseTime={342} 
  domainName="도시계획" 
/>

// 에러
<SearchErrorIndicator message="서버 연결 실패" />
```

### LawArticleCard

```tsx
<LawArticleCard 
  article={{
    hang_id: '국토의_계획_및_이용에_관한_법률_법률_제17조_제1항',
    content: '도시·군관리계획은...',
    law_name: '국토의 계획 및 이용에 관한 법률',
    jo_number: '제17조',
    hang_number: '제1항',
    similarity: 0.95
  }} 
/>
```

---

## 검색 모드

| 모드 | 프로토콜 | 특징 |
|------|----------|------|
| **REST** | HTTP POST | 결과만 반환 |
| **SSE 스트리밍** | EventSource | 실시간 진행상황 표시 |

### SSE 이벤트 흐름

```
1. started       → 검색 시작
2. searching     → exact_match 단계
3. searching     → vector_search 단계
4. searching     → relationship_search 단계
5. processing    → rne_expansion 단계
6. processing    → enrichment 단계
7. complete      → 결과 반환
```

---

## 라우팅

```tsx
// frontend/src/routers/index.tsx
{
  path: '/law',
  element: <LawChat />
}
```

**접속**: `http://localhost:5173/law` (개발 모드)

---

## 백엔드 실행

프론트엔드 사용 전 백엔드 필수 실행:

```bash
cd D:\Data\11_Backend\01_ARR\backend
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

---

## 의존성

- `react`: UI 프레임워크
- `react-router-dom`: 라우팅
- `tailwindcss`: 스타일링

---

## 관련 백엔드 파일

| 백엔드 | 역할 |
|--------|------|
| `agents/law/api/search.py` | 검색 API |
| `agents/law/domain_agent.py` | 도메인 에이전트 |
| `agents/law/agent_manager.py` | 에이전트 관리 |
