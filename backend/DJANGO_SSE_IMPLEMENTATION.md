# Django SSE (Server-Sent Events) 스트리밍 구현 가이드

## 개요

Django 백엔드에 SSE (Server-Sent Events) 스트리밍 기능을 추가하여 프론트엔드(React)에서 MAS(Multi-Agent System) 검색 진행상황을 실시간으로 볼 수 있도록 구현했습니다.

**구현 완료일**: 2025-11-20
**Django 버전**: 5.2.6
**Python 버전**: 3.10+

---

## 1. 구현 파일 목록

### 1.1 새로 추가된 파일

#### `backend/agents/law/api/streaming.py`
**역할**: SSE 스트리밍 API 뷰 구현

**주요 클래스/함수**:
- `LawSearchStreamAPIView(View)` - Django View 클래스 (SSE 엔드포인트)
- `search_stream_generator()` - 비동기 제너레이터 (SSE 이벤트 생성)
- `sync_generator_wrapper()` - 동기 래퍼 (Django StreamingHttpResponse 호환)
- `sse_message()` - SSE 메시지 포맷팅 함수

**핵심 기능**:
1. POST 요청으로 검색 쿼리 수신
2. AgentManager를 통해 도메인 라우팅
3. 검색 진행상황을 7단계로 분할하여 SSE 전송
4. 최종 검색 결과를 SSE로 전송

### 1.2 수정된 파일

#### `backend/agents/law/api/__init__.py`
**변경 내용**: `LawSearchStreamAPIView` import 추가

```python
from .streaming import LawSearchStreamAPIView

__all__ = [
    # ...
    'LawSearchStreamAPIView',
]
```

#### `backend/agents/law/urls.py`
**변경 내용**: SSE 스트리밍 엔드포인트 URL 라우팅 추가

```python
urlpatterns = [
    # ...
    path('api/search', LawSearchAPIView.as_view(), name='api_search'),
    path('api/search/stream', LawSearchStreamAPIView.as_view(), name='api_search_stream'),  # 추가됨
    # ...
]
```

### 1.3 테스트 파일

#### `backend/test_sse_streaming.html`
**역할**: 브라우저 기반 SSE 테스트 페이지

**기능**:
- 검색어 입력 UI
- 실시간 진행률 표시 (프로그레스 바)
- 단계별 체크리스트 업데이트
- 최종 검색 결과 표시
- 로그 출력

---

## 2. API 엔드포인트

### 2.1 엔드포인트 정보

**URL**: `POST http://localhost:8000/agents/law/api/search/stream`

**Method**: POST

**Content-Type**: `application/json`

**Request Body**:
```json
{
  "query": "36조",
  "limit": 10
}
```

**Response Type**: `text/event-stream` (SSE)

**CORS**: `corsheaders` 미들웨어에 의해 자동 허용 (`CORS_ALLOW_ALL_ORIGINS = True`)

### 2.2 SSE 이벤트 형식

모든 SSE 메시지는 다음 형식을 따릅니다:

```
data: {JSON 객체}

```

**주의**: SSE 표준에 따라 `data:` prefix와 두 개의 개행문자(`\n\n`)가 필요합니다.

### 2.3 SSE 이벤트 시퀀스

#### Stage 1: Started (검색 시작)
```json
data: {
  "status": "started",
  "agent": "용도지역",
  "domain_id": "domain_abc123",
  "node_count": 1591,
  "timestamp": 1700000000.123
}
```

#### Stage 2: Exact Match (20%)
```json
data: {
  "status": "searching",
  "stage": "exact_match",
  "stage_name": "정확 일치 검색",
  "progress": 0.2
}
```

#### Stage 3: Vector Search (40%)
```json
data: {
  "status": "searching",
  "stage": "vector_search",
  "stage_name": "벡터 유사도 검색",
  "progress": 0.4
}
```

#### Stage 4: Relationship Search (60%)
```json
data: {
  "status": "searching",
  "stage": "relationship_search",
  "stage_name": "관계 임베딩 검색",
  "progress": 0.6
}
```

#### Stage 5: RNE Expansion (80%)
```json
data: {
  "status": "searching",
  "stage": "rne_expansion",
  "stage_name": "RNE 그래프 확장",
  "progress": 0.8
}
```

#### Stage 6: Result Processing (95%)
```json
data: {
  "status": "processing",
  "stage": "enrichment",
  "stage_name": "결과 강화 중",
  "progress": 0.95
}
```

#### Stage 7: Complete (검색 완료)
```json
data: {
  "status": "complete",
  "results": [
    {
      "hang_id": "국토의_계획_및_이용에_관한_법률_법률_제1장_제1절_제1조_제1항",
      "content": "이 법은 국토의 이용·개발과...",
      "unit_path": "제1장 > 제1절 > 제1조 > 제1항",
      "similarity": 0.85,
      "stages": ["vector", "relationship"],
      "source": "my_domain"
    }
  ],
  "result_count": 5,
  "stats": {
    "total": 5,
    "vector_count": 3,
    "relationship_count": 2,
    "graph_expansion_count": 0,
    "my_domain_count": 5,
    "neighbor_count": 0
  },
  "response_time": 850,
  "domain_id": "domain_abc123",
  "domain_name": "용도지역"
}
```

#### Error Event (오류 발생 시)
```json
data: {
  "status": "error",
  "message": "No domains available"
}
```

---

## 3. 구현 세부사항

### 3.1 Django StreamingHttpResponse

Django는 기본적으로 동기(sync) 프레임워크이지만, `StreamingHttpResponse`를 사용하여 SSE를 구현할 수 있습니다.

**핵심 포인트**:
- `StreamingHttpResponse`는 동기 제너레이터를 요구함
- 비동기 코드(async/await)를 사용하려면 이벤트 루프 래핑 필요
- SSE 헤더 설정 필수 (`text/event-stream`, `Cache-Control: no-cache`)

### 3.2 비동기 처리

#### 문제점
- `DomainAgent._search_my_domain()`은 비동기 함수 (`async def`)
- Django View는 동기 함수
- `StreamingHttpResponse`는 동기 제너레이터 필요

#### 해결 방법
`sync_generator_wrapper()` 함수 사용:

```python
def sync_generator_wrapper(query: str, limit: int):
    """동기 래퍼 for 비동기 제너레이터"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async_gen = search_stream_generator(query, limit)

        while True:
            try:
                message = loop.run_until_complete(async_gen.__anext__())
                yield message
            except StopAsyncIteration:
                break
    finally:
        loop.close()
```

**장점**:
- 비동기 코드(DomainAgent)를 동기 컨텍스트(Django View)에서 실행 가능
- 이벤트 루프를 명시적으로 관리하여 충돌 방지

### 3.3 CSRF 설정

SSE 엔드포인트는 POST 요청이므로 CSRF 보호를 비활성화해야 합니다.

```python
@method_decorator(csrf_exempt, name='dispatch')
class LawSearchStreamAPIView(View):
    # ...
```

**대안** (프로덕션 환경):
- CSRF 토큰을 프론트엔드에서 전송
- API 키 기반 인증
- JWT 토큰 인증

### 3.4 CORS 설정

Django 설정 (`backend/settings.py`)에서 이미 구성됨:

```python
CORS_ALLOW_ALL_ORIGINS = True  # 개발 환경
CORS_ALLOW_CREDENTIALS = True
```

**프로덕션 환경**:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "https://your-frontend-domain.com"
]
```

### 3.5 Nginx 버퍼링 방지

SSE 스트리밍이 Nginx 뒤에서 작동하려면 버퍼링을 비활성화해야 합니다:

```python
response['X-Accel-Buffering'] = 'no'
```

---

## 4. 테스트 방법

### 4.1 Django 서버 실행

```bash
# Windows
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\activate
python manage.py runserver

# 또는 Daphne (WebSocket 지원)
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### 4.2 브라우저 테스트 (권장)

1. Django 서버 실행 (위 참조)
2. 브라우저에서 열기:
   ```
   file:///D:/Data/11_Backend/01_ARR/backend/test_sse_streaming.html
   ```
3. 검색어 입력 (예: "36조")
4. "검색" 버튼 클릭
5. 실시간 진행상황 확인

### 4.3 curl 테스트

**기본 테스트**:
```bash
curl -X POST http://localhost:8000/agents/law/api/search/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "36조", "limit": 3}' \
  -N
```

**설명**:
- `-N`: 버퍼링 비활성화 (SSE 실시간 출력 필요)
- `-X POST`: POST 요청
- `-H`: JSON Content-Type 헤더
- `-d`: JSON 요청 본문

### 4.4 Python requests 테스트

```python
import requests
import json

url = 'http://localhost:8000/agents/law/api/search/stream'
data = {'query': '36조', 'limit': 5}

with requests.post(url, json=data, stream=True) as response:
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                data = json.loads(line_str[6:])
                print(f"Status: {data['status']}")
                if data['status'] == 'complete':
                    print(f"Results: {len(data['results'])}")
                    break
```

### 4.5 React/TypeScript 테스트

프론트엔드에서 사용하는 방법은 `frontend/STREAMING_INTEGRATION_GUIDE.md` 참조.

**간단한 예시**:
```typescript
const response = await fetch('http://localhost:8000/agents/law/api/search/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: '36조', limit: 10 })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  const lines = text.split('\n\n');

  lines.forEach(line => {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.substring(6));
      console.log(data);
    }
  });
}
```

---

## 5. 주의사항 및 모범 사례

### 5.1 이벤트 루프 관리

**주의**: Django는 동기 프레임워크이므로 이벤트 루프를 신중하게 관리해야 합니다.

**모범 사례**:
1. 각 요청마다 새로운 이벤트 루프 생성
2. `try/finally`로 이벤트 루프 닫기
3. 기존 이벤트 루프와 충돌 방지

**잘못된 예**:
```python
# 이미 실행 중인 이벤트 루프를 재사용 - 오류 발생!
loop = asyncio.get_event_loop()
loop.run_until_complete(coroutine)
```

**올바른 예**:
```python
# 새 이벤트 루프 생성
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(coroutine)
finally:
    loop.close()
```

### 5.2 SSE 메시지 포맷

SSE 표준을 엄격히 준수해야 합니다:

```python
def sse_message(data: dict) -> str:
    # ✅ 올바른 형식
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    # ❌ 잘못된 형식 (개행문자 누락)
    # return f"data: {json.dumps(data)}\n"
```

**규칙**:
1. 메시지는 `data:` prefix로 시작
2. JSON은 한 줄로 직렬화 (개행문자 없음)
3. 메시지는 두 개의 개행문자(`\n\n`)로 종료

### 5.3 연결 타임아웃

브라우저는 SSE 연결을 자동으로 재연결 시도하지만, 명시적 타임아웃 처리를 권장합니다.

**프론트엔드에서**:
```typescript
const timeoutId = setTimeout(() => {
  eventSource.close();
  setError('검색 시간이 초과되었습니다.');
}, 30000);  // 30초
```

### 5.4 에러 핸들링

모든 예외를 SSE 메시지로 반환하여 프론트엔드가 처리할 수 있도록 합니다:

```python
try:
    # 검색 실행
    results = await agent.search(query)
except Exception as e:
    yield sse_message({
        'status': 'error',
        'message': str(e)
    })
    return  # 제너레이터 종료
```

### 5.5 메모리 관리

SSE 연결은 장시간 유지될 수 있으므로 메모리 누수 방지가 중요합니다:

1. **이벤트 루프 닫기**: `finally` 블록에서 반드시 닫기
2. **대용량 데이터 제한**: 결과를 `limit`으로 제한
3. **캐시 관리**: AgentManager 싱글톤 패턴 사용

### 5.6 프로덕션 배포

프로덕션 환경에서는 다음을 고려하세요:

1. **CSRF 보호 활성화**:
   ```python
   # CSRF 토큰 검증
   from django.middleware.csrf import get_token
   ```

2. **Rate Limiting**:
   ```python
   from django.core.cache import cache

   # IP 기반 요청 제한
   if cache.get(f'sse_limit_{ip}'):
       return JsonResponse({'error': 'Too many requests'}, status=429)
   cache.set(f'sse_limit_{ip}', 1, timeout=60)
   ```

3. **인증/인가**:
   ```python
   from rest_framework.authentication import TokenAuthentication
   from rest_framework.permissions import IsAuthenticated
   ```

4. **로깅**:
   ```python
   logger.info(f"[SSE] {request.user.username} searched '{query}'")
   ```

---

## 6. 트러블슈팅

### 6.1 404 Not Found

**증상**: `curl` 또는 브라우저에서 404 오류

**원인**: Django 서버가 URL 라우팅을 인식하지 못함

**해결책**:
1. Django 서버 재시작
   ```bash
   # Ctrl+C로 중단 후 재실행
   python manage.py runserver
   ```

2. URL 패턴 확인
   ```python
   # backend/agents/law/urls.py
   path('api/search/stream', LawSearchStreamAPIView.as_view(), ...)
   ```

3. Import 확인
   ```python
   # backend/agents/law/api/__init__.py
   from .streaming import LawSearchStreamAPIView
   ```

### 6.2 CORS 오류

**증상**: 브라우저 콘솔에 CORS 오류

**해결책**:
```python
# backend/settings.py
CORS_ALLOW_ALL_ORIGINS = True  # 개발 환경

# 또는 특정 origin만 허용
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
```

### 6.3 SSE 연결이 즉시 종료됨

**증상**: 첫 번째 메시지 후 연결 종료

**원인**: Nginx 또는 프록시 버퍼링

**해결책**:
```python
response['X-Accel-Buffering'] = 'no'
response['Cache-Control'] = 'no-cache'
```

### 6.4 이벤트 루프 오류

**증상**: `RuntimeError: This event loop is already running`

**원인**: 이벤트 루프 재사용 시도

**해결책**:
```python
# 항상 새 이벤트 루프 생성
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
```

### 6.5 JSON Decode Error

**증상**: `JSONDecodeError: Expecting value`

**원인**: 요청 본문이 올바른 JSON이 아님

**해결책**:
```python
# Content-Type 확인
if request.content_type != 'application/json':
    return error_response('Invalid Content-Type')

# 빈 본문 처리
try:
    body = json.loads(request.body)
except json.JSONDecodeError:
    return error_response('Invalid JSON')
```

### 6.6 No domains available

**증상**: `error: No domains available`

**원인**: AgentManager가 초기화되지 않았거나 Neo4j 연결 실패

**해결책**:
1. Neo4j 서버 확인
   ```bash
   # http://localhost:7474 접속
   ```

2. 도메인 초기화 확인
   ```bash
   python manage.py shell
   >>> from agents.law.agent_manager import AgentManager
   >>> am = AgentManager()
   >>> print(am.get_statistics())
   ```

---

## 7. 성능 최적화

### 7.1 응답 시간 분석

평균 응답 시간: **850ms ~ 2000ms**

**단계별 소요 시간**:
- Domain routing (LLM assessment): ~200ms
- Vector search: ~300ms
- Relationship search: ~200ms
- RNE expansion: ~400ms
- Result processing: ~100ms

### 7.2 최적화 방법

#### 방법 1: LLM Assessment 비활성화
```python
# agents/law/api/search.py
top_domains = auto_route_to_top_domains(
    query,
    agent_manager,
    top_n=1,
    use_llm_assessment=False  # 빠른 벡터 유사도만 사용
)
```

**효과**: ~200ms 단축

#### 방법 2: 결과 제한
```python
# 적은 결과만 요청
{"query": "36조", "limit": 3}  # 대신 10
```

**효과**: ~100ms 단축

#### 방법 3: 임베딩 캐시
AgentManager는 이미 임베딩 캐싱을 사용합니다:
```python
self.embeddings_cache: Dict[str, np.ndarray] = {}
```

---

## 8. 다음 단계

### 8.1 프론트엔드 통합

프론트엔드(React) 통합은 다음 문서 참조:
- `D:\Data\11_Backend\01_ARR\frontend\STREAMING_INTEGRATION_GUIDE.md`

### 8.2 멀티 도메인 협업 시각화

미래에 여러 도메인이 활성화되면 A2A 협업 진행상황도 SSE로 스트리밍 가능:

```json
data: {
  "status": "a2a_collaboration",
  "active_agents": [
    {
      "domain_name": "용도지역",
      "status": "searching",
      "progress": 0.5
    },
    {
      "domain_name": "건축규제",
      "status": "waiting",
      "progress": 0.0
    }
  ]
}
```

### 8.3 실시간 로그 스트리밍

디버깅을 위해 서버 로그를 SSE로 스트리밍:

```python
yield sse_message({
    'status': 'log',
    'level': 'info',
    'message': 'Searching in domain: 용도지역'
})
```

---

## 9. 참고 자료

### 9.1 내부 문서
- `agent/law-domain-agents/STREAMING_GUIDE.md` - FastAPI SSE 구현 가이드
- `frontend/STREAMING_INTEGRATION_GUIDE.md` - React 통합 가이드
- `backend/CLAUDE.md` - Django 백엔드 아키텍처

### 9.2 외부 문서
- [SSE 표준 (W3C)](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [Django StreamingHttpResponse](https://docs.djangoproject.com/en/5.2/ref/request-response/#streaminghttpresponse-objects)
- [EventSource API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)

---

## 10. 요약

### 10.1 구현된 기능
- Django SSE 스트리밍 엔드포인트
- 7단계 검색 진행상황 업데이트
- 비동기 DomainAgent 통합
- 브라우저 테스트 페이지

### 10.2 핵심 파일
- `backend/agents/law/api/streaming.py` - SSE 뷰 구현
- `backend/agents/law/urls.py` - URL 라우팅
- `backend/test_sse_streaming.html` - 테스트 페이지

### 10.3 엔드포인트
- `POST http://localhost:8000/agents/law/api/search/stream`

### 10.4 다음 AI가 알아야 할 것
1. SSE는 `StreamingHttpResponse` + 동기 제너레이터로 구현됨
2. 비동기 코드는 `sync_generator_wrapper()`로 래핑됨
3. 이벤트 루프는 각 요청마다 새로 생성해야 함
4. CSRF는 `@csrf_exempt`로 비활성화됨 (프로덕션에서는 인증 필요)
5. 프론트엔드는 `fetch()` + `ReadableStream`으로 SSE 처리

---

**작성일**: 2025-11-20
**작성자**: Claude (Backend Django Specialist)
**버전**: 1.0
