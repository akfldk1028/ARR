# law/ - 법률 검색 API 및 데이터 파이프라인

## 개요

법률 검색 REST API, 관계 검색, 벡터 검색, 데이터 파이프라인 제공.

---

## 파일 구조

```
law/
├── views.py         # ⭐ 검색 API 엔드포인트
├── urls.py          # URL 라우팅
├── models.py        # Django 모델 (Law, Article, Clause 등)
├── serializers.py   # DRF 직렬화
├── admin.py         # 관리자 페이지
├── services/        # 비즈니스 로직
│   ├── search_service.py      # 검색 오케스트레이션
│   ├── vector_service.py      # 벡터 검색
│   └── relationship_service.py # 관계 검색
├── pipeline/        # 데이터 파이프라인
│   ├── pdf_extractor.py       # PDF 텍스트 추출
│   ├── structure_parser.py    # 조항 구조 파싱
│   └── embedding_generator.py # 임베딩 생성
└── SYSTEM_GUIDE.md  # 상세 시스템 가이드
```

---

## 핵심 API 엔드포인트

### 1. 통합 검색 API

```http
POST /api/law/search/
Content-Type: application/json

{
  "query": "도시계획 수립 절차",
  "limit": 20,
  "include_a2a": true,
  "domain_ids": ["domain_1", "domain_2"]
}
```

**응답:**

```json
{
  "results": [
    {
      "hang_id": 12345,
      "full_id": "국토의_계획_및_이용에_관한_법률_법률_제17조_제1항",
      "law_name": "국토의 계획 및 이용에 관한 법률",
      "article_number": "제17조 제1항",
      "content": "도시·군관리계획은...",
      "score": 0.8542,
      "source": "domain_1",
      "expansion_type": "vector"
    }
  ],
  "meta": {
    "total_results": 25,
    "search_time_ms": 342,
    "domains_searched": ["domain_1", "domain_2"],
    "a2a_collaboration": true
  }
}
```

### 2. 벡터 검색 API

```http
POST /api/law/vector-search/
Content-Type: application/json

{
  "query": "건축물 높이 제한",
  "top_k": 10,
  "threshold": 0.7
}
```

### 3. 관계 검색 API

```http
POST /api/law/relationship-search/
Content-Type: application/json

{
  "hang_id": "국토의_계획_및_이용에_관한_법률_법률_제17조_제1항",
  "relationship_types": ["CITES", "IMPLEMENTS"],
  "depth": 2
}
```

### 4. 파이프라인 API

```http
POST /api/law/pipeline/process-pdf/
Content-Type: multipart/form-data

file: [PDF 파일]
options: {"auto_domain_assignment": true}
```

---

## 검색 서비스 구조

### SearchService

```python
class SearchService:
    """검색 오케스트레이션"""
    
    def __init__(self):
        self.agent_manager = AgentManager()
        self.vector_service = VectorService()
        self.relationship_service = RelationshipService()
    
    async def search(self, query: str, limit: int = 20, include_a2a: bool = True):
        """통합 검색"""
        
        # 1. 관련 도메인 식별
        relevant_domains = await self._find_relevant_domains(query)
        
        # 2. 각 도메인 에이전트에 검색 요청
        tasks = []
        for domain_id in relevant_domains:
            agent = self.agent_manager.get_agent(domain_id)
            tasks.append(agent.search(query, limit=limit))
        
        # 3. 병렬 실행
        domain_results = await asyncio.gather(*tasks)
        
        # 4. A2A 협업 (필요시)
        if include_a2a:
            a2a_results = await self._trigger_a2a_collaboration(
                query, domain_results, relevant_domains
            )
            domain_results.extend(a2a_results)
        
        # 5. 결과 병합 및 정렬
        merged = self._merge_and_rank(domain_results)
        return merged[:limit]
```

### VectorService

```python
class VectorService:
    """벡터 검색 서비스"""
    
    def __init__(self):
        self.neo4j = get_neo4j_service()
        self.openai = OpenAI()
    
    async def search(self, query: str, top_k: int = 10, threshold: float = 0.7):
        """벡터 유사도 검색"""
        
        # 1. 쿼리 임베딩 생성
        embedding = await self._generate_embedding(query)
        
        # 2. Neo4j 벡터 인덱스 검색
        results = self.neo4j.execute_query("""
            CALL db.index.vector.queryNodes('hang_embedding_index', $top_k, $embedding)
            YIELD node, score
            WHERE score >= $threshold
            RETURN node.full_id AS full_id, 
                   node.content AS content,
                   score
            ORDER BY score DESC
        """, {'top_k': top_k, 'embedding': embedding, 'threshold': threshold})
        
        return results
```

### RelationshipService

```python
class RelationshipService:
    """관계 검색 서비스"""
    
    def __init__(self):
        self.neo4j = get_neo4j_service()
    
    def find_related(self, hang_id: str, rel_types: List[str], depth: int = 1):
        """관련 조항 검색"""
        
        # CITES: 인용 관계
        # IMPLEMENTS: 시행령/시행규칙 관계
        # CONTAINS: 상위/하위 조항
        
        query = f"""
            MATCH (h:HANG {{full_id: $hang_id}})
            MATCH path = (h)-[r:{"|".join(rel_types)}*1..{depth}]-(related)
            RETURN DISTINCT related.full_id AS full_id,
                   related.content AS content,
                   type(r) AS relationship
        """
        return self.neo4j.execute_query(query, {'hang_id': hang_id})
```

---

## 데이터 파이프라인

### 전체 흐름

```
[PDF 파일]
    ↓ pdf_extractor.py
[텍스트 추출]
    ↓ structure_parser.py
[조항 구조 파싱 (LAW→JO→HANG→HO)]
    ↓ Neo4j 저장
[그래프 노드/관계 생성]
    ↓ embedding_generator.py
[OpenAI 임베딩 생성 (3072-dim)]
    ↓ AgentManager._assign_to_agents()
[도메인 할당 (K-means)]
```

### 파이프라인 사용 예시

```python
from law.pipeline import PDFProcessor

processor = PDFProcessor()

# 전체 파이프라인 실행
result = await processor.process(
    pdf_path='건축법.pdf',
    auto_domain=True
)

print(f"추출된 조항: {result['total_articles']}")
print(f"생성된 임베딩: {result['embeddings_created']}")
print(f"할당된 도메인: {result['domain_assignments']}")
```

---

## 점수 계산 로직

### Hybrid Search 점수 병합

```python
def _reciprocal_rank_fusion(self, result_lists, k=60):
    """RRF (Reciprocal Rank Fusion)"""
    
    scores = defaultdict(float)
    
    for result_list in result_lists:
        for rank, result in enumerate(result_list):
            hang_id = result['hang_id']
            # RRF 공식: 1 / (k + rank)
            scores[hang_id] += 1.0 / (k + rank + 1)
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 점수 정규화

```python
def _normalize_scores(self, results):
    """Min-Max 정규화"""
    
    if not results:
        return results
    
    scores = [r['score'] for r in results]
    min_score, max_score = min(scores), max(scores)
    
    if max_score == min_score:
        for r in results:
            r['normalized_score'] = 1.0
    else:
        for r in results:
            r['normalized_score'] = (r['score'] - min_score) / (max_score - min_score)
    
    return results
```

### 패널티 적용

```python
def _apply_penalties(self, results):
    """특정 조건에 패널티 적용"""
    
    PENALTIES = {
        '제12장': 0.5,    # 벌칙 관련
        '부칙': 0.3,      # 부칙
        '폐지': 0.2,      # 폐지 조항
    }
    
    for result in results:
        full_id = result['full_id']
        
        for pattern, penalty in PENALTIES.items():
            if pattern in full_id:
                result['score'] *= penalty
                result['penalty_reason'] = pattern
                break
    
    return sorted(results, key=lambda x: x['score'], reverse=True)
```

---

## Django 모델

### Law (법률)

```python
class Law(models.Model):
    name = models.CharField(max_length=200)
    law_type = models.CharField(max_length=50)  # 법률, 시행령, 시행규칙
    effective_date = models.DateField()
    neo4j_id = models.IntegerField(null=True)
```

### Article (조)

```python
class Article(models.Model):
    law = models.ForeignKey(Law, on_delete=models.CASCADE)
    article_number = models.CharField(max_length=50)
    title = models.CharField(max_length=500)
    neo4j_id = models.IntegerField(null=True)
```

### Clause (항)

```python
class Clause(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    clause_number = models.CharField(max_length=50)
    content = models.TextField()
    neo4j_id = models.IntegerField(null=True)
    embedding_generated = models.BooleanField(default=False)
```

---

## URL 라우팅

```python
# law/urls.py
urlpatterns = [
    path('search/', SearchView.as_view(), name='law-search'),
    path('vector-search/', VectorSearchView.as_view(), name='vector-search'),
    path('relationship-search/', RelationshipSearchView.as_view(), name='relationship-search'),
    path('pipeline/process-pdf/', PipelineView.as_view(), name='process-pdf'),
    path('articles/<str:full_id>/', ArticleDetailView.as_view(), name='article-detail'),
]
```

---

## 환경 변수

```env
# OpenAI (임베딩)
OPENAI_API_KEY=sk-...

# Neo4j (그래프 DB)
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111

# 검색 설정
SEARCH_DEFAULT_LIMIT=20
VECTOR_SIMILARITY_THRESHOLD=0.7
RNE_SIMILARITY_THRESHOLD=0.75
```

---

## 의존성

- `djangorestframework`: REST API
- `openai`: 임베딩 생성
- `neo4j`: 그래프 DB 연결
- `PyPDF2` / `pdfplumber`: PDF 추출
- `numpy`: 벡터 연산
