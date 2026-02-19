# Frontend SSE 스트리밍 통합 가이드

## 개요

기존 `LawChat.tsx`에 실시간 MAS 진행상황 표시 기능을 추가하는 방법입니다.

## 새로 추가된 파일

### 1. `src/law/hooks/use-law-search-stream.ts`
SSE를 사용한 실시간 검색 진행상황 추적 훅

**주요 기능**:
- EventSource를 사용한 SSE 연결 관리
- 실시간 진행상황 업데이트
- 자동 연결 해제 및 재연결
- 검색 중단 기능

### 2. `src/law/components/SearchProgress.tsx`
진행상황 시각화를 위한 React 컴포넌트

**컴포넌트**:
- `SearchProgressIndicator`: 진행률 표시 (agent badge, progress bar, stage checklist)
- `SearchErrorIndicator`: 에러 표시
- `SearchCompleteHeader`: 완료 헤더

## 중요: 백엔드 차이점

### 현재 상황
- **프론트엔드**: `http://127.0.0.1:8000` (Django 백엔드)
- **SSE 스트리밍 서버**: `http://localhost:8011` (FastAPI 서버)

### 선택지

#### Option A: FastAPI 서버만 사용 (권장)
1. FastAPI 서버 (port 8011)에 SSE 엔드포인트 구현 ✅ (이미 가이드 있음)
2. 프론트엔드를 FastAPI로 전환
3. Django 백엔드 제거 또는 다른 용도로 사용

**장점**:
- 간단한 아키텍처
- SSE 지원이 FastAPI가 더 우수
- 이미 MAS 테스트 완료 (http://localhost:8011)

#### Option B: Django + FastAPI 병행
1. Django (port 8000): 기존 REST API 유지
2. FastAPI (port 8011): SSE 스트리밍 전용
3. 프론트엔드에서 두 서버 모두 사용

**장점**:
- 기존 Django 코드 유지
- 점진적 마이그레이션 가능

**단점**:
- 두 서버 관리 필요
- 복잡도 증가

## 통합 방법 (Option A - FastAPI만 사용)

### Step 1: API Client 수정

`src/law/lib/law-api-client.ts` 수정:

```typescript
// 기존
const API_BASE_URL = import.meta.env.VITE_LAW_BACKEND_URL || 'http://127.0.0.1:8000';

// 변경
const API_BASE_URL = import.meta.env.VITE_LAW_BACKEND_URL || 'http://localhost:8011';
```

### Step 2: API 엔드포인트 경로 수정

FastAPI 서버의 엔드포인트 경로로 변경:

```typescript
// 기존
`${this.baseURL}/agents/law/api/search`

// 변경
`${this.baseURL}/api/search`
```

전체 경로 변경 필요:
- `/agents/law/api/search` → `/api/search`
- `/agents/law/api/domain/{id}/search` → `/api/domain/{id}/search`
- `/agents/law/api/domains` → `/api/domains`
- `/agents/law/api/health` → `/api/health`

### Step 3: LawChat.tsx에 스트리밍 추가

두 가지 검색 모드 지원:

#### 3-1. 토글 버튼 추가

```tsx
import { useLawSearchStream } from './hooks/use-law-search-stream';
import { SearchProgressIndicator, SearchErrorIndicator, SearchCompleteHeader } from './components/SearchProgress';

function LawChatInner() {
  const { domains, domainsLoading, selectedDomainId, setSelectedDomainId, isConnected } = useLawAPI();
  const { messages, isLoading, search, clearMessages } = useLawChat();

  // 스트리밍 모드 상태
  const [streamingMode, setStreamingMode] = useState(true); // 기본값: 스트리밍 활성화

  // 스트리밍 훅
  const { progress, isSearching, startSearch, stopSearch, resetProgress } = useLawSearchStream();

  const handleSearch = (query: string) => {
    if (streamingMode) {
      // SSE 스트리밍 검색
      startSearch(query, 10);
    } else {
      // 기존 REST API 검색
      search(query, 10);
    }
  };

  return (
    <div className="law-chat-container flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        {/* Domain selector */}
        {/* ... */}

        {/* 스트리밍 모드 토글 */}
        <div className="flex items-center gap-2 mt-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={streamingMode}
              onChange={(e) => setStreamingMode(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">실시간 진행상황 표시 (SSE)</span>
          </label>
        </div>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div key={message.id}>
            {/* 기존 메시지 렌더링 */}
            {message.role === 'user' && (
              <div className="bg-blue-100 p-3 rounded-lg">{message.content}</div>
            )}

            {message.role === 'assistant' && (
              <div>
                {/* 스트리밍 모드: 진행상황 표시 */}
                {streamingMode && isSearching && (
                  <SearchProgressIndicator progress={progress!} />
                )}

                {/* 기존 로딩 표시 (non-streaming) */}
                {!streamingMode && message.loading && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                    <span>{message.content}</span>
                  </div>
                )}

                {/* 스트리밍 완료 헤더 */}
                {streamingMode && progress?.status === 'complete' && (
                  <SearchCompleteHeader
                    resultCount={progress.result_count || 0}
                    responseTime={progress.response_time || 0}
                    domainName={progress.domain_name}
                  />
                )}

                {/* 스트리밍 에러 */}
                {streamingMode && progress?.status === 'error' && (
                  <SearchErrorIndicator message={progress.message || '알 수 없는 오류'} />
                )}

                {/* 검색 결과 표시 */}
                {((message.search_response && !message.loading && !message.error) ||
                  (streamingMode && progress?.status === 'complete')) && (
                  <ResultDisplay
                    response={
                      streamingMode
                        ? convertProgressToResponse(progress!)
                        : message.search_response!
                    }
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input Area */}
      {/* ... */}
    </div>
  );
}
```

#### 3-2. Progress → Response 변환 함수

```typescript
/**
 * SearchProgress를 LawSearchResponse 형식으로 변환
 */
function convertProgressToResponse(progress: SearchProgress): LawSearchResponse {
  return {
    results: progress.results || [],
    stats: {
      total: progress.result_count || 0,
      vector_count: 0,
      relationship_count: 0,
      graph_expansion_count: 0,
      my_domain_count: progress.result_count || 0,
      neighbor_count: 0,
    },
    domain_id: progress.domain_id,
    domain_name: progress.domain_name,
    response_time: progress.response_time,
  };
}
```

### Step 4: 환경변수 설정

`.env` 파일 생성 또는 수정:

```bash
# FastAPI 서버 사용
VITE_LAW_BACKEND_URL=http://localhost:8011
```

## 통합 방법 (Option B - Django + FastAPI 병행)

### Step 1: API Client에 스트리밍 메서드 추가

`src/law/lib/law-api-client.ts`에 추가:

```typescript
export class LawAPIClient {
  private baseURL: string;
  private streamingURL: string; // FastAPI 서버

  constructor(baseURL?: string, streamingURL?: string) {
    this.baseURL = baseURL || 'http://127.0.0.1:8000'; // Django
    this.streamingURL = streamingURL || 'http://localhost:8011'; // FastAPI
  }

  // 기존 메서드들 유지...

  /**
   * 스트리밍 검색 URL 생성
   */
  getStreamingSearchURL(query: string, limit: number = 10): string {
    return `${this.streamingURL}/api/search/stream?query=${encodeURIComponent(query)}&limit=${limit}`;
  }
}
```

### Step 2: useLawSearchStream 훅 수정

```typescript
export function useLawSearchStream(client: LawAPIClient): UseLawSearchStreamReturn {
  // ...

  const startSearch = useCallback(
    (query: string, limit: number = 10) => {
      // ...
      const url = client.getStreamingSearchURL(query, limit);
      const eventSource = new EventSource(url);
      // ...
    },
    [client]
  );

  // ...
}
```

### Step 3: LawChat.tsx에서 사용

```tsx
function LawChatInner() {
  const { client, domains, selectedDomainId, isConnected } = useLawAPI();
  const { messages, search, clearMessages } = useLawChat();
  const { progress, isSearching, startSearch } = useLawSearchStream(client);

  // ...
}
```

## 백엔드 SSE 엔드포인트 구현 필요

FastAPI 서버 (port 8011)에 다음 엔드포인트 추가 필요:

```python
@app.post("/api/search/stream")
async def search_stream(request: LawSearchRequest):
    # STREAMING_GUIDE.md 참고
    # agent/law-domain-agents/STREAMING_GUIDE.md 파일 확인
```

**참고 파일**:
- `D:\Data\11_Backend\01_ARR\agent\law-domain-agents\STREAMING_GUIDE.md`
- `D:\Data\11_Backend\01_ARR\agent\law-domain-agents\test_streaming.html` (테스트용 HTML)

## 테스트 순서

### 1. 백엔드 SSE 엔드포인트 구현
```bash
cd D:\Data\11_Backend\01_ARR\agent\law-domain-agents
# server.py에 /api/search/stream 추가
python server.py
```

### 2. test_streaming.html로 먼저 테스트
```bash
# 브라우저에서 열기
start D:\Data\11_Backend\01_ARR\agent\law-domain-agents\test_streaming.html
```

검색어 입력 → 실시간 진행상황 확인

### 3. React 프론트엔드 통합
```bash
cd D:\Data\11_Backend\01_ARR\frontend

# 환경변수 설정
echo VITE_LAW_BACKEND_URL=http://localhost:8011 > .env

# 개발 서버 실행
npm run dev
```

### 4. 동작 확인
1. LawChat 페이지 접속
2. "실시간 진행상황 표시" 체크박스 활성화
3. 검색어 입력 (예: "36조")
4. 실시간 진행상황 확인:
   - Agent badge 표시
   - 진행률 바 증가
   - 단계별 체크리스트 업데이트
   - 최종 결과 표시

## 주의사항

### CORS 설정 필요
FastAPI 서버에 CORS 설정 추가:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### EventSource 브라우저 지원
- 모든 모던 브라우저 지원 (IE 제외)
- Safari, Chrome, Firefox, Edge 모두 지원
- Polyfill 불필요

### 타임아웃 처리
EventSource는 자동 재연결 시도하므로, 서버가 오래 걸리면 문제 없음.
단, 명시적 타임아웃이 필요하면 `setTimeout()` 사용:

```typescript
const startSearch = useCallback((query: string, limit: number = 10) => {
  // ...

  // 30초 타임아웃
  const timeoutId = setTimeout(() => {
    cleanup();
    setProgress({
      status: 'error',
      message: '검색 시간이 초과되었습니다.',
    });
  }, 30000);

  // cleanup 함수에 타임아웃 제거 추가
  // ...
}, []);
```

## 다음 단계

1. ✅ 백엔드 SSE 엔드포인트 구현
2. ✅ test_streaming.html로 테스트
3. ⏳ React 프론트엔드 통합
4. ⏳ 사용자 피드백 수집
5. ⏳ 멀티 도메인 협업 시각화 (미래)

## 문제 해결

### SSE 연결 실패
- FastAPI 서버가 실행 중인지 확인
- CORS 설정 확인
- 브라우저 개발자 도구 → Network 탭에서 EventStream 확인

### 진행상황이 표시되지 않음
- 백엔드에서 `yield` 문이 올바르게 작동하는지 확인
- `data:` prefix가 있는지 확인
- JSON 형식이 올바른지 확인

### 메모리 누수
- 컴포넌트 언마운트 시 EventSource가 제대로 닫히는지 확인
- `useEffect` cleanup 함수 확인
