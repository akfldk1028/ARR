# MAS 진행상황 실시간 스트리밍 가이드

## 개요

Law Domain Agents의 검색 진행상황을 프론트엔드에서 실시간으로 볼 수 있는 기능입니다.

## 구현 방법

### 백엔드: Server-Sent Events (SSE)

**새로운 엔드포인트**: `POST /api/search/stream`

```python
from fastapi.responses import StreamingResponse
import json
import asyncio

@app.post("/api/search/stream")
async def search_stream(
    request: LawSearchRequest,
    dm: Annotated[DomainManager, Depends(get_dm)],
    af: Annotated[DomainAgentFactory, Depends(get_af)]
):
    """
    실시간 스트리밍 검색 API

    Event 형식:
    data: {"status": "started", "agent": "용도지역", "timestamp": 1234567890}
    data: {"status": "searching", "stage": "exact_match", "progress": 0.25}
    data: {"status": "searching", "stage": "vector_search", "progress": 0.5}
    data: {"status": "searching", "stage": "relationship_search", "progress": 0.75}
    data: {"status": "searching", "stage": "rne_expansion", "progress": 0.9}
    data: {"status": "complete", "results": [...], "response_time": 850}
    """

    async def event_generator():
        try:
            import time
            start_time = time.time()

            # 1. 검색 시작
            domains = dm.get_all_domains()
            if not domains:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No domains available'})}\n\n"
                return

            domain = domains[0]
            agent = af.get_agent(domain.domain_id) or af.create_agent(domain)

            yield f"data: {json.dumps({
                'status': 'started',
                'agent': domain.domain_name,
                'domain_id': domain.domain_id,
                'node_count': domain.node_count,
                'timestamp': time.time()
            })}\n\n"

            await asyncio.sleep(0.1)  # UI 업데이트 시간

            # 2. Exact Match 검색
            yield f"data: {json.dumps({
                'status': 'searching',
                'stage': 'exact_match',
                'stage_name': '정확 일치 검색',
                'progress': 0.2
            })}\n\n"

            await asyncio.sleep(0.1)

            # 3. Vector Search
            yield f"data: {json.dumps({
                'status': 'searching',
                'stage': 'vector_search',
                'stage_name': '벡터 유사도 검색',
                'progress': 0.4
            })}\n\n"

            await asyncio.sleep(0.1)

            # 4. Relationship Search
            yield f"data: {json.dumps({
                'status': 'searching',
                'stage': 'relationship_search',
                'stage_name': '관계 임베딩 검색',
                'progress': 0.6
            })}\n\n"

            await asyncio.sleep(0.1)

            # 5. RNE Expansion
            yield f"data: {json.dumps({
                'status': 'searching',
                'stage': 'rne_expansion',
                'stage_name': 'RNE 그래프 확장',
                'progress': 0.8
            })}\n\n"

            # 실제 검색 실행
            search_results = agent.search_engine.search(request.query, top_k=request.limit)

            # 6. 결과 변환
            yield f"data: {json.dumps({
                'status': 'processing',
                'stage': 'enrichment',
                'stage_name': '결과 강화 중',
                'progress': 0.95
            })}\n\n"

            articles = []
            for result in search_results:
                articles.append({
                    'hang_id': result.get("hang_id", ""),
                    'content': result.get("content", ""),
                    'unit_path': result.get("unit_path", ""),
                    'similarity': result.get("similarity", 0.0),
                    'stages': [result.get("stage", "unknown")],
                    'law_name': result.get("law_name"),
                    'law_type': result.get("law_type"),
                    'article': result.get("article")
                })

            # 7. 최종 완료
            response_time = int((time.time() - start_time) * 1000)

            yield f"data: {json.dumps({
                'status': 'complete',
                'results': articles,
                'result_count': len(articles),
                'response_time': response_time,
                'domain_id': domain.domain_id,
                'domain_name': domain.domain_name
            })}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )
```

### 프론트엔드: EventSource

#### React/TypeScript 예시

```typescript
import { useEffect, useState } from 'react';

interface SearchProgress {
  status: 'started' | 'searching' | 'processing' | 'complete' | 'error';
  stage?: string;
  stage_name?: string;
  progress?: number;
  agent?: string;
  results?: any[];
  response_time?: number;
  message?: string;
}

export function useLawSearch(query: string) {
  const [progress, setProgress] = useState<SearchProgress | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    if (!query) return;

    setIsSearching(true);
    setProgress({ status: 'started' });

    const eventSource = new EventSource(
      `http://localhost:8011/api/search/stream?query=${encodeURIComponent(query)}&limit=5`
    );

    eventSource.onmessage = (event) => {
      const data: SearchProgress = JSON.parse(event.data);
      setProgress(data);

      if (data.status === 'complete' || data.status === 'error') {
        eventSource.close();
        setIsSearching(false);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      eventSource.close();
      setIsSearching(false);
      setProgress({ status: 'error', message: 'Connection failed' });
    };

    return () => {
      eventSource.close();
      setIsSearching(false);
    };
  }, [query]);

  return { progress, isSearching };
}

// 사용 예시
function SearchComponent() {
  const [query, setQuery] = useState('36조');
  const { progress, isSearching } = useLawSearch(query);

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {isSearching && (
        <div className="progress-indicator">
          <div className="agent-info">
            🤖 Agent: {progress?.agent}
          </div>

          <div className="stage-info">
            📋 {progress?.stage_name || 'Processing...'}
          </div>

          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(progress?.progress || 0) * 100}%` }}
            />
          </div>
        </div>
      )}

      {progress?.status === 'complete' && (
        <div className="results">
          <h3>검색 완료! ({progress.response_time}ms)</h3>
          {progress.results?.map((result, i) => (
            <div key={i} className="result-card">
              <h4>{result.article} - {result.law_name}</h4>
              <p>{result.content.substring(0, 100)}...</p>
              <span>유사도: {(result.similarity * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

#### 바닐라 JavaScript 예시

```javascript
// HTML에서 직접 사용 가능
const eventSource = new EventSource('http://localhost:8011/api/search/stream?query=36조&limit=5');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  console.log('Status:', data.status);
  console.log('Stage:', data.stage_name);
  console.log('Progress:', data.progress);

  // UI 업데이트
  if (data.status === 'started') {
    document.getElementById('agent-name').textContent = data.agent;
  }

  if (data.status === 'searching') {
    document.getElementById('stage').textContent = data.stage_name;
    document.getElementById('progress-bar').style.width = `${data.progress * 100}%`;
  }

  if (data.status === 'complete') {
    console.log('Results:', data.results);
    eventSource.close();
  }
};

eventSource.onerror = (error) => {
  console.error('Connection failed:', error);
  eventSource.close();
};
```

## UI 컴포넌트 예시

### 진행상황 표시 UI

```jsx
<div className="search-progress">
  {/* Agent 정보 */}
  <div className="agent-badge">
    <span className="agent-icon">🤖</span>
    <span className="agent-name">{progress.agent}</span>
    <span className="node-count">{progress.node_count} nodes</span>
  </div>

  {/* 현재 단계 */}
  <div className="current-stage">
    {progress.stage === 'exact_match' && '🎯'}
    {progress.stage === 'vector_search' && '🔍'}
    {progress.stage === 'relationship_search' && '🔗'}
    {progress.stage === 'rne_expansion' && '🌳'}
    {progress.stage === 'enrichment' && '✨'}
    <span>{progress.stage_name}</span>
  </div>

  {/* 프로그레스 바 */}
  <div className="progress-bar">
    <div
      className="progress-fill"
      style={{
        width: `${progress.progress * 100}%`,
        transition: 'width 0.3s ease'
      }}
    />
  </div>

  {/* 단계별 체크리스트 */}
  <ul className="stage-checklist">
    <li className={progress.progress >= 0.2 ? 'done' : ''}>
      ✓ 정확 일치 검색
    </li>
    <li className={progress.progress >= 0.4 ? 'done' : ''}>
      ✓ 벡터 유사도 검색
    </li>
    <li className={progress.progress >= 0.6 ? 'done' : ''}>
      ✓ 관계 임베딩 검색
    </li>
    <li className={progress.progress >= 0.8 ? 'done' : ''}>
      ✓ RNE 그래프 확장
    </li>
    <li className={progress.progress >= 0.95 ? 'done' : ''}>
      ✓ 결과 강화
    </li>
  </ul>
</div>
```

## 멀티 도메인 협업 시각화

미래에 여러 도메인이 활성화되면:

```typescript
interface MultiDomainProgress {
  status: 'routing' | 'parallel' | 'merging' | 'complete';
  coordinator: string;  // "LawCoordinator"
  active_agents: Array<{
    domain_id: string;
    domain_name: string;
    status: 'waiting' | 'searching' | 'done';
    progress: number;
  }>;
  results: any[];
}

// 여러 agent가 동시에 작업하는 모습을 보여줄 수 있음
<div className="multi-agent-view">
  {progress.active_agents.map(agent => (
    <div key={agent.domain_id} className="agent-card">
      <h4>{agent.domain_name}</h4>
      <div className="status">{agent.status}</div>
      <progress value={agent.progress} max={1} />
    </div>
  ))}
</div>
```

## 테스트

### 1. 백엔드 서버 실행
```bash
cd agent/law-domain-agents
python server.py
```

### 2. curl로 테스트
```bash
curl -N http://localhost:8011/api/search/stream?query=36조&limit=5
```

### 3. HTML 테스트 페이지
`test_streaming.html` 생성하여 브라우저에서 열기

## 장점

✅ **실시간 피드백**: 사용자가 진행상황을 실시간으로 볼 수 있음
✅ **투명성**: 어떤 agent가 무슨 작업 중인지 명확
✅ **디버깅 용이**: 어느 단계에서 느린지 확인 가능
✅ **UX 향상**: 대기 중에도 시스템이 작동 중임을 보여줌
✅ **확장 가능**: 멀티 도메인 협업도 같은 방식으로 시각화

## 다음 단계

1. `law_search_engine.py`에 progress callback 추가
2. 실제 검색 진행률을 정확하게 계산
3. LangGraph 통합 시 StateGraph의 각 노드 진행상황 스트리밍
4. 멀티 도메인 parallel search 시각화
