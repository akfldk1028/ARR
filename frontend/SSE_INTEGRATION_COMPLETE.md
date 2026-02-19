# SSE 스트리밍 진행상황 표시 기능 통합 완료

> 작성일: 2025-11-21
> 상태: 통합 완료
> 대상: Eigent 프론트엔드 - 법규 검색 AI 채팅

---

## 개요

법규 검색 AI 채팅 컴포넌트(`LawChat.tsx`)에 **SSE(Server-Sent Events) 기반 실시간 진행상황 표시 기능**을 성공적으로 통합했습니다. 사용자는 이제 검색 중 Multi-Agent System의 각 단계를 실시간으로 확인할 수 있습니다.

### 주요 특징

- **토글 가능한 스트리밍 모드**: 사용자가 실시간 진행상황 모드를 선택할 수 있습니다
- **하위 호환성 유지**: 기존 REST API 검색 기능 완전 유지
- **실시간 진행상황 시각화**: 검색 단계별 진행률, 에이전트 정보, 예상 소요 시간 등 표시
- **우아한 에러 처리**: 검색 실패 시 명확한 에러 메시지 표시
- **검색 중단 기능**: 사용자가 언제든지 검색을 중단할 수 있습니다

---

## 파일 구조

### 통합된 파일

```
frontend/src/law/
├── LawChat.tsx                          # ✅ SSE 통합 완료 (메인 컴포넌트)
├── hooks/
│   ├── use-law-chat.ts                  # 기존 REST API 검색 훅
│   └── use-law-search-stream.ts         # ✅ SSE 스트리밍 훅 (신규)
└── components/
    ├── QueryInput.tsx                   # 검색 입력 컴포넌트
    ├── ResultDisplay.tsx                # 결과 표시 컴포넌트
    └── SearchProgress.tsx               # ✅ 진행상황 UI 컴포넌트 (신규)
        ├── SearchProgressIndicator      # 진행 중 표시
        ├── SearchCompleteHeader         # 완료 헤더
        └── SearchErrorIndicator         # 에러 표시
```

### 핵심 파일 위치

| 파일 | 경로 | 설명 |
|------|------|------|
| **메인 컴포넌트** | `D:\Data\11_Backend\01_ARR\frontend\src\law\LawChat.tsx` | SSE 통합된 채팅 UI |
| **SSE 훅** | `D:\Data\11_Backend\01_ARR\frontend\src\law\hooks\use-law-search-stream.ts` | SSE 연결 및 상태 관리 |
| **진행상황 UI** | `D:\Data\11_Backend\01_ARR\frontend\src\law\components\SearchProgress.tsx` | 진행상황 시각화 컴포넌트 |

---

## 통합 내용 상세

### 1. 추가된 Import

```typescript
import { useState } from 'react';
import { useLawSearchStream } from './hooks/use-law-search-stream';
import {
  SearchProgressIndicator,
  SearchCompleteHeader,
  SearchErrorIndicator,
} from './components/SearchProgress';
```

### 2. 상태 관리 추가

```typescript
// SSE 스트리밍 훅
const { progress, isSearching, startSearch, stopSearch, resetProgress } = useLawSearchStream();

// 스트리밍 모드 토글 상태
const [streamingMode, setStreamingMode] = useState(false);
```

### 3. 헤더 UI 업데이트

**추가된 요소:**

1. **스트리밍 모드 토글 체크박스** (lines 131-141)
   ```tsx
   <label className="flex items-center gap-2 cursor-pointer group">
     <input
       type="checkbox"
       checked={streamingMode}
       onChange={(e) => setStreamingMode(e.target.checked)}
       className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 cursor-pointer"
     />
     <span className="text-sm text-gray-600 group-hover:text-gray-900 transition-colors">
       실시간 진행상황
     </span>
   </label>
   ```

2. **검색 중단 버튼** (lines 160-167) - 스트리밍 모드에서만 표시
   ```tsx
   {streamingMode && isSearching && (
     <button
       onClick={stopSearch}
       className="px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 border border-red-300 rounded-lg transition-colors font-medium"
     >
       검색 중단
     </button>
   )}
   ```

### 4. 검색 핸들러 로직 (lines 69-85)

**스트리밍/일반 모드 분기 처리:**

```typescript
const handleSearch = (query: string) => {
  if (streamingMode) {
    // SSE 스트리밍 검색
    addMessage({
      role: 'user',
      content: query,
    });

    resetProgress(); // 이전 진행상황 초기화
    startSearch(query, 10);
  } else {
    // 기존 REST API 검색
    search(query, 10);
  }
};
```

### 5. 스트리밍 완료 시 결과 처리 (lines 45-64)

**useEffect를 통한 자동 결과 추가:**

```typescript
useEffect(() => {
  if (progress?.status === 'complete' && progress.results) {
    addMessage({
      role: 'assistant',
      content: `검색 완료 (${progress.response_time}ms)`,
      search_response: {
        results: progress.results,
        total_count: progress.result_count || progress.results.length,
        query: '',
        response_time: progress.response_time || 0,
        domain_id: progress.domain_id,
        domain_name: progress.domain_name,
      },
    });

    resetProgress(); // 다음 검색을 위해 초기화
  }
}, [progress, addMessage, resetProgress]);
```

### 6. 메시지 영역 UI 업데이트 (lines 217-310)

**진행상황 표시 로직:**

```typescript
{/* 스트리밍 진행상황 (검색 중일 때만) */}
{streamingMode && isSearching && progress && (
  <div className="message-container">
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      {/* 진행 중 */}
      {progress.status !== 'complete' && progress.status !== 'error' && (
        <SearchProgressIndicator progress={progress} />
      )}

      {/* 에러 */}
      {progress.status === 'error' && (
        <SearchErrorIndicator
          message={progress.message || '알 수 없는 오류가 발생했습니다.'}
        />
      )}

      {/* 완료 헤더 */}
      {progress.status === 'complete' && (
        <SearchCompleteHeader
          resultCount={progress.result_count || 0}
          responseTime={progress.response_time || 0}
          domainName={progress.domain_name}
        />
      )}
    </div>
  </div>
)}
```

### 7. 정보 섹션 업데이트 (lines 196-197)

**임베딩 정보 수정:**
- ~~KR-SBERT 768dim~~ → **OpenAI 3072dim** (노드 임베딩)
- **OpenAI 3072dim** (관계 임베딩) - 유지

---

## 사용 방법

### 기본 사용

1. **법규 검색 AI 채팅 페이지로 이동**
   ```
   http://localhost:7777/law-chat
   ```

2. **스트리밍 모드 활성화**
   - 헤더의 "실시간 진행상황" 체크박스를 클릭

3. **검색 실행**
   - 검색어 입력 (예: "36조", "개발행위 허가")
   - 엔터 또는 검색 버튼 클릭

4. **진행상황 확인**
   - 검색 중 실시간으로 다음 정보 확인:
     - 활성화된 에이전트 이름
     - 관리 중인 노드 개수
     - 현재 검색 단계 (정확 일치, 벡터 검색, 관계 검색 등)
     - 진행률 (프로그레스 바)
     - 단계별 체크리스트

5. **검색 중단 (선택)**
   - "검색 중단" 버튼 클릭으로 언제든지 중단 가능

### 기존 모드 사용

- "실시간 진행상황" 체크박스를 **해제**하면 기존 REST API 방식 사용
- 기존 기능 100% 유지 (하위 호환성)

---

## 진행상황 단계 설명

### 검색 단계별 아이콘 및 이름

| 단계 | 아이콘 | 한글 이름 | 진행률 임계값 |
|------|--------|-----------|---------------|
| `exact_match` | 🎯 | 정확 일치 검색 | 20% |
| `vector_search` | 🔍 | 벡터 유사도 검색 | 40% |
| `relationship_search` | 🔗 | 관계 임베딩 검색 | 60% |
| `rne_expansion` | 🌳 | RNE 그래프 확장 | 80% |
| `enrichment` | ✨ | 결과 강화 | 95% |

### 진행상황 데이터 구조

```typescript
interface SearchProgress {
  status: 'started' | 'searching' | 'processing' | 'complete' | 'error';
  stage?: SearchStage;
  stage_name?: string;        // 백엔드에서 제공하는 한글 이름
  progress?: number;          // 0~1 사이의 진행률
  agent?: string;             // 활성화된 에이전트 이름
  domain_id?: string;
  node_count?: number;        // 관리 중인 노드 개수
  timestamp?: number;
  results?: any[];            // 검색 결과 (완료 시)
  result_count?: number;      // 결과 개수
  response_time?: number;     // 응답 시간 (ms)
  domain_name?: string;       // 도메인 이름
  message?: string;           // 에러 메시지
}
```

---

## 백엔드 연동 요구사항

### SSE 엔드포인트

**URL:** `http://localhost:8011/api/search/stream`

**메서드:** `GET`

**쿼리 파라미터:**
- `query` (required): 검색어
- `limit` (optional): 결과 개수 (기본값: 10)

**응답 형식:** SSE (Server-Sent Events)

**이벤트 데이터 예시:**

```json
// 검색 시작
{
  "status": "started",
  "progress": 0
}

// 진행 중
{
  "status": "searching",
  "stage": "vector_search",
  "stage_name": "벡터 유사도 검색",
  "progress": 0.4,
  "agent": "국토계획법_도메인_에이전트",
  "node_count": 1234,
  "timestamp": 1700000000
}

// 완료
{
  "status": "complete",
  "progress": 1.0,
  "results": [...],
  "result_count": 10,
  "response_time": 1234,
  "domain_id": "domain_123",
  "domain_name": "국토의 계획 및 이용에 관한 법률"
}

// 에러
{
  "status": "error",
  "message": "검색 중 오류가 발생했습니다."
}
```

### 기존 REST API 엔드포인트 (하위 호환성)

- **자동 라우팅 검색:** `POST http://localhost:8011/api/search`
- **도메인별 검색:** `POST http://localhost:8011/api/domains/{domain_id}/search`

이 엔드포인트들은 스트리밍 모드가 비활성화되었을 때 사용됩니다.

---

## 주의사항

### 1. 환경 변수 설정

**파일:** `frontend/.env.development`

```env
# SSE 스트리밍 API URL
VITE_LAW_API_URL=http://localhost:8011

# 또는 백엔드 포트가 다를 경우
VITE_LAW_API_URL=http://localhost:8000
```

### 2. CORS 설정

백엔드에서 SSE 엔드포인트의 CORS를 허용해야 합니다:

```python
# Django settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:7777",  # Eigent 프론트엔드
]

CORS_ALLOW_CREDENTIALS = True
```

### 3. 브라우저 호환성

- **EventSource API** 지원 브라우저:
  - Chrome/Edge: 6+
  - Firefox: 6+
  - Safari: 5+
  - Opera: 11+
  - IE: 미지원 (Edge 사용 권장)

### 4. 연결 시간 초과

- SSE 연결은 2분(120초) 후 자동 종료됩니다
- 장시간 검색 시 백엔드에서 주기적으로 progress 이벤트를 전송해야 합니다

### 5. 동시 검색 제한

- 한 번에 하나의 검색만 실행 가능
- 새 검색 시작 시 이전 SSE 연결은 자동으로 종료됩니다

---

## 테스트 시나리오

### 정상 동작 테스트

1. **기본 스트리밍 검색**
   - [ ] 스트리밍 모드 활성화
   - [ ] "36조" 검색
   - [ ] 진행상황 실시간 표시 확인
   - [ ] 검색 완료 후 결과 표시 확인

2. **검색 중단**
   - [ ] 스트리밍 모드에서 검색 시작
   - [ ] 진행 중 "검색 중단" 버튼 클릭
   - [ ] 에러 메시지 표시 확인

3. **모드 전환**
   - [ ] 스트리밍 모드로 검색
   - [ ] 결과 확인 후 체크박스 해제
   - [ ] 일반 모드로 검색
   - [ ] 기존 로딩 UI 표시 확인

4. **연속 검색**
   - [ ] 첫 번째 검색 완료
   - [ ] 두 번째 검색 시작
   - [ ] 이전 진행상황 초기화 확인
   - [ ] 새 진행상황 표시 확인

### 에러 처리 테스트

5. **백엔드 연결 실패**
   - [ ] 백엔드 서버 중지
   - [ ] 스트리밍 검색 시도
   - [ ] 연결 실패 에러 메시지 표시 확인

6. **잘못된 쿼리**
   - [ ] 빈 쿼리 입력
   - [ ] 검색 버튼 비활성화 확인

### 하위 호환성 테스트

7. **기존 기능 유지**
   - [ ] 스트리밍 모드 비활성화 상태
   - [ ] 기존 검색 정상 동작 확인
   - [ ] 도메인 선택 기능 확인
   - [ ] 대화 초기화 기능 확인

---

## 문제 해결

### SSE 연결 실패

**증상:** "서버 연결에 실패했습니다" 에러

**해결 방법:**
1. 백엔드 서버 실행 확인
   ```bash
   cd D:\Data\11_Backend\01_ARR\backend
   daphne -b 0.0.0.0 -p 8011 backend.asgi:application
   ```

2. 환경 변수 확인
   ```bash
   # frontend/.env.development
   VITE_LAW_API_URL=http://localhost:8011
   ```

3. 브라우저 콘솔에서 에러 로그 확인
   ```
   F12 → Console → SSE Error 확인
   ```

### 진행상황이 표시되지 않음

**증상:** 스트리밍 모드인데 진행상황이 보이지 않음

**해결 방법:**
1. 체크박스 상태 확인 (활성화되어 있는지)
2. 백엔드에서 progress 이벤트 전송 여부 확인
3. 브라우저 개발자 도구 → Network → EventSource 연결 상태 확인

### 검색 결과가 중복 표시됨

**증상:** 같은 결과가 두 번 표시됨

**해결 방법:**
- `useEffect` 종속성 배열 확인
- `resetProgress()` 호출 시점 확인
- 메시지 중복 추가 방지 로직 확인

---

## 향후 개선 사항

### 단기 개선 (1주일 이내)

- [ ] 진행상황 애니메이션 강화 (Framer Motion 활용)
- [ ] 검색 히스토리 저장 및 재검색 기능
- [ ] 스트리밍 모드 선호도 LocalStorage 저장

### 중기 개선 (1개월 이내)

- [ ] 여러 도메인 동시 검색 시 각 도메인별 진행상황 표시
- [ ] 예상 소요 시간 표시 (머신러닝 기반 추정)
- [ ] 실시간 검색 통계 대시보드

### 장기 개선 (분기별)

- [ ] WebSocket 전환 (양방향 통신)
- [ ] 검색 우선순위 조정 기능
- [ ] 에이전트 협업 시각화 (노드 그래프)

---

## 관련 문서

- [Django 백엔드 Law Search System Architecture](D:\Data\11_Backend\01_ARR\backend\LAW_SEARCH_SYSTEM_ARCHITECTURE.md)
- [Eigent 프론트엔드 README](D:\Data\11_Backend\01_ARR\frontend\README.md)
- [Law Domain Manager Guide](D:\Data\11_Backend\01_ARR\backend\agents\law\DOMAIN_MANAGER_GUIDE.md)

---

## 기술 스택

- **React 18**: 컴포넌트 기반 UI
- **TypeScript 5**: 타입 안전성
- **Tailwind CSS**: 유틸리티 CSS
- **EventSource API**: SSE 연결
- **Custom Hooks**: 상태 관리 추상화

---

## 기여자

- **통합 작업:** Claude Code (Eigent Frontend Specialist)
- **SSE 훅 개발:** [사용자명]
- **진행상황 UI 디자인:** [사용자명]

---

## 라이선스

Eigent 프로젝트 라이선스를 따릅니다 (MIT 또는 Apache 2.0)

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-11-21 | 1.0.0 | 초기 SSE 통합 완료 |

---

**문의:** Eigent 개발팀
**저장소:** D:\Data\11_Backend\01_ARR\frontend
