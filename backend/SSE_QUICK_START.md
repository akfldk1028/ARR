# SSE 스트리밍 빠른 시작 가이드

## 1분 안에 시작하기

### 1. Django 서버 실행
```bash
cd D:\Data\11_Backend\01_ARR\backend
.venv\Scripts\activate
python manage.py runserver
```

### 2. 브라우저 테스트
브라우저에서 열기:
```
file:///D:/Data/11_Backend/01_ARR/backend/test_sse_streaming.html
```

검색어 입력 (예: "36조") → 검색 버튼 클릭 → 실시간 진행상황 확인!

---

## 엔드포인트

**URL**: `POST http://localhost:8000/agents/law/api/search/stream`

**Request**:
```json
{
  "query": "36조",
  "limit": 10
}
```

**Response**: `text/event-stream` (SSE)

---

## curl 테스트

```bash
curl -X POST http://localhost:8000/agents/law/api/search/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "36조", "limit": 3}' \
  -N
```

---

## SSE 이벤트 순서

1. **started** - 검색 시작 (agent 정보)
2. **searching** (exact_match) - 20%
3. **searching** (vector_search) - 40%
4. **searching** (relationship_search) - 60%
5. **searching** (rne_expansion) - 80%
6. **processing** (enrichment) - 95%
7. **complete** - 검색 완료 (결과 반환)

---

## 프론트엔드 통합 (React)

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
  text.split('\n\n').forEach(line => {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.substring(6));
      console.log(data);  // Handle SSE event
    }
  });
}
```

자세한 내용: `frontend/STREAMING_INTEGRATION_GUIDE.md`

---

## 문제 해결

### 404 Not Found
→ Django 서버 재시작 (`Ctrl+C` 후 `python manage.py runserver`)

### CORS 오류
→ 이미 `CORS_ALLOW_ALL_ORIGINS = True`로 설정됨 (개발 환경)

### No domains available
→ Neo4j 서버 확인 (http://localhost:7474)

---

## 상세 문서

**완전한 가이드**: `backend/DJANGO_SSE_IMPLEMENTATION.md`
