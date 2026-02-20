# Law Search API - Quick Start Guide

**Semantic RNE/INE 법규 검색 시스템**

---

## 빠른 시작

### 1. 서버 시작
```bash
# Neo4j 실행 (Neo4j Desktop)
# 가상환경 활성화
.\.venv\Scripts\activate

# Daphne ASGI 서버 시작
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### 2. API 호출

#### SemanticRNE (범위 기반 검색)
```bash
# 도시계획 관련 조항 검색 (유사도 0.75 이상)
curl "http://localhost:8000/law/search/rne/?q=도시계획+수립&threshold=0.75"
```

#### SemanticINE (Top-k 검색)
```bash
# 도시계획 관련 상위 5개 조항
curl "http://localhost:8000/law/search/ine/?q=도시계획&k=5"
```

#### 통계
```bash
curl "http://localhost:8000/law/stats/"
```

---

## API 엔드포인트

### 1. `/law/search/rne/` - SemanticRNE

**파라미터**:
- `q`: 검색 쿼리 (필수)
- `threshold`: 유사도 임계값 (기본: 0.75)
- `max_results`: 최대 결과 수 (기본: 무제한)
- `initial_candidates`: 초기 후보 수 (기본: 10)

**예시**:
```bash
GET /law/search/rne/?q=건축물+건축&threshold=0.70&max_results=20
```

**응답**:
```json
{
    "query": "건축물 건축",
    "algorithm": "SemanticRNE",
    "threshold": 0.70,
    "results": [
        {
            "hang_id": 6924,
            "full_id": "국토의 계획 및 이용에 관한 법률::제13조::제1항",
            "law_name": "국토의 계획 및 이용에 관한 법률",
            "article_number": "제13조제1항",
            "content": "...",
            "similarity": 0.8923,
            "expansion_type": "vector"
        }
    ],
    "count": 15,
    "execution_time_ms": 51.44
}
```

### 2. `/law/search/ine/` - SemanticINE

**파라미터**:
- `q`: 검색 쿼리 (필수)
- `k`: 결과 개수 (기본: 5)
- `initial_candidates`: 초기 후보 수 (기본: 20)

**예시**:
```bash
GET /law/search/ine/?q=용도지역&k=10
```

**응답**:
```json
{
    "query": "용도지역",
    "algorithm": "SemanticINE",
    "k": 10,
    "results": [
        {
            "hang_id": 6924,
            "article_number": "제13조제1항",
            "content": "...",
            "similarity": 0.8923,
            "rank": 1
        }
    ],
    "count": 10,
    "execution_time_ms": 45.2
}
```

### 3. `/law/stats/` - 통계

**예시**:
```bash
GET /law/stats/
```

**응답**:
```json
{
    "total_hangs": 746,
    "hangs_with_embedding": 746,
    "embedding_dimension": 768,
    "total_jos": 422,
    "total_hos": 298,
    "vector_index": "hang_embedding_index",
    "algorithm_info": {
        "semantic_rne": "Range-based search",
        "semantic_ine": "k-NN search"
    }
}
```

---

## RNE vs INE 선택 가이드

| 시나리오 | 사용할 알고리즘 | URL |
|---------|----------------|-----|
| "도시계획 관련 모든 조항" | SemanticRNE | `/law/search/rne/` |
| "도시계획 관련 상위 5개" | SemanticINE | `/law/search/ine/` |
| 탐색적 검색 (넓은 범위) | SemanticRNE | `/law/search/rne/` |
| 정확한 Top-k 필요 | SemanticINE | `/law/search/ine/` |

---

## Python 예시

```python
import requests

# SemanticRNE
response = requests.get(
    "http://localhost:8000/law/search/rne/",
    params={
        "q": "도시계획 수립",
        "threshold": 0.75,
        "max_results": 10
    }
)
data = response.json()
print(f"Found {data['count']} articles in {data['execution_time_ms']}ms")

for article in data['results'][:5]:
    print(f"{article['article_number']}: {article['similarity']:.4f}")

# SemanticINE
response = requests.get(
    "http://localhost:8000/law/search/ine/",
    params={"q": "건축 허가", "k": 5}
)
data = response.json()

for article in data['results']:
    print(f"#{article['rank']}: {article['article_number']} ({article['similarity']:.4f})")
```

---

## JavaScript 예시

```javascript
// SemanticRNE
async function searchRNE(query, threshold = 0.75) {
    const params = new URLSearchParams({
        q: query,
        threshold: threshold
    });

    const response = await fetch(
        `http://localhost:8000/law/search/rne/?${params}`
    );
    const data = await response.json();

    console.log(`Found ${data.count} articles in ${data.execution_time_ms}ms`);
    return data.results;
}

// SemanticINE
async function searchINE(query, k = 5) {
    const params = new URLSearchParams({
        q: query,
        k: k
    });

    const response = await fetch(
        `http://localhost:8000/law/search/ine/?${params}`
    );
    const data = await response.json();

    data.results.forEach(article => {
        console.log(`#${article.rank}: ${article.article_number} (${article.similarity.toFixed(4)})`);
    });
    return data.results;
}

// 사용
searchRNE("도시계획 수립");
searchINE("건축 허가", 10);
```

---

## 성능

- **SemanticRNE**: 평균 51ms (10개 결과)
- **SemanticINE**: 평균 45ms (5개 결과)
- **정확도**: 100% (Neo4j Ground Truth)
- **환각률**: 0% (LLM 추측 없음)

---

## 트러블슈팅

### 서버 연결 실패
```bash
# Neo4j가 실행 중인지 확인
# Neo4j Desktop에서 데이터베이스 "Start" 버튼 클릭

# Daphne 서버 실행 확인
# 터미널에서 다음 메시지가 보여야 함:
# [INFO] Starting server at tcp:port=8000:interface=0.0.0.0
```

### 임베딩이 없는 경우
```bash
cd law/scripts
python add_embeddings.py
# 746개 HANG 노드에 768-dim 임베딩 추가
```

### API 404 오류
```bash
# URL 확인:
# ✅ http://localhost:8000/law/search/rne/
# ❌ http://localhost:8000/law/rne/  (잘못됨)
```

---

## 더 알아보기

- **전체 문서**: `docs/2025-10-30-SEMANTIC_RNE_INE_IMPLEMENTATION_SUMMARY.md`
- **알고리즘 상세**: `docs/2025-10-30-RNE_INE_ALGORITHM_PAPER.md`
- **LLM 비교**: `docs/2025-10-30-ALGORITHM_VS_LLM_COMPARISON.md`

---

**버전**: 1.0.0
**작성일**: 2025-10-30
**Status**: ✅ Production Ready
