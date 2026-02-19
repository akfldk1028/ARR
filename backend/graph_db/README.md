# graph_db/ - Neo4j 그래프 데이터베이스 및 알고리즘

## 개요

Neo4j 연결, 법률 그래프 스키마, RNE/INE 그래프 확장 알고리즘 제공.

---

## 그래프 스키마

### 노드 계층 구조

```
LAW (법률)
 └─ PYEON (편)
     └─ JANG (장)
         └─ JEOL (절)
             └─ GWAN (관)
                 └─ JO (조) ← 제목, 임베딩 (3072-dim)
                     └─ HANG (항) ← ⭐ 실제 내용, 임베딩 (3072-dim)
                         └─ HO (호)
                             └─ MOK (목)

Domain (도메인) ← K-means 클러스터링, 센트로이드 임베딩 (768-dim)
```

### 관계 구조

| 관계 | 방향 | 임베딩 | 설명 |
|------|------|--------|------|
| `CONTAINS` | 부모→자식 | OpenAI 3072-dim | LAW→JO→HANG→HO 계층 |
| `NEXT` | 형제→형제 | 없음 | 같은 레벨 순서 |
| `CITES` | 노드→노드 | 없음 | 타법 인용 |
| `BELONGS_TO_DOMAIN` | HANG→Domain | similarity 속성 | 도메인 할당 |
| `IMPLEMENTS` | 법률→시행령 | 없음 | 위임 관계 |

### 벡터 인덱스

| 인덱스명 | 대상 | 차원 | 모델 |
|---------|------|------|------|
| `hang_embedding_index` | HANG.embedding | 3072 | text-embedding-3-large |
| `contains_embedding` | CONTAINS.embedding | 3072 | text-embedding-3-large |
| `jo_embedding_index` | JO.embedding | 3072 | text-embedding-3-large |

---

## 파일 구조

### services/

| 파일 | 역할 |
|------|------|
| `neo4j_service.py` | Neo4j 연결 싱글톤 |
| `__init__.py` | `Neo4jService`, `get_neo4j_service()` 익스포트 |

### algorithms/

```
algorithms/
├── core/
│   ├── base.py           # BaseSpatialAlgorithm
│   ├── semantic_rne.py   # ⭐ SemanticRNE (법규용 RNE)
│   └── ine.py            # INE (Iterative Network Expansion)
├── domain/
│   ├── context.py        # Context 클래스
│   └── models.py         # 도메인 모델
├── repository/
│   ├── law_repository.py # ⭐ LawRepository (법률 데이터 접근)
│   └── base_repository.py
└── tracking/
    └── provenance.py     # 검색 이력 추적
```

---

## Neo4jService

### 클래스 구조

```python
class Neo4jService:
    """Neo4j 연결 관리"""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "11111111")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = None
    
    def connect(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
    
    def disconnect(self):
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query: str, parameters: dict) -> List[Dict]:
        with self.get_session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]
    
    def execute_write_query(self, query: str, parameters: dict) -> List[Dict]:
        """쓰기 트랜잭션"""
        with self.driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(query, parameters))
            return [record.data() for record in result]

# 싱글톤 인스턴스
def get_neo4j_service() -> Neo4jService:
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
        _neo4j_service.connect()
    return _neo4j_service
```

### 사용 예시

```python
from graph_db.services import get_neo4j_service

neo4j = get_neo4j_service()

# 쿼리 실행
results = neo4j.execute_query("""
    MATCH (h:HANG)
    WHERE h.full_id CONTAINS '제17조'
    RETURN h.full_id AS id, h.content AS content
    LIMIT 10
""", {})

for r in results:
    print(f"{r['id']}: {r['content'][:50]}...")
```

---

## SemanticRNE 알고리즘

### 개요

**법규용 Range Network Expansion** - HybridRAG 방식

```
[도로 RNE]                    [Semantic RNE (법규용)]
비용: baseTime (초)      →    비용: 1 - similarity
반경: e (초)             →    임계값: θ (0.75)
시작점: 단일 노드        →    시작점: 벡터 검색 top-k
확장: SEGMENT 관계       →    확장: 계층 구조 (parent/sibling/child)
```

### 알고리즘 흐름

```
Stage 1: Vector Search
    ↓ Neo4j 벡터 인덱스 (top-10)
    ↓ OpenAI 3072-dim 쿼리 임베딩
    
Stage 2: Graph Expansion (Dijkstra 변형)
    ↓ Priority Queue: (cost, hang_id, expansion_type)
    ↓ cost = 1 - similarity
    ↓ 확장 규칙:
        - parent/child/cross_law: cost = 0 (자동 포함)
        - sibling: cost = 1 - cosine_similarity
    ↓ threshold(0.75) 이상만 결과에 포함
    
Stage 3: Reranking
    ↓ relevance_score 순 정렬
```

### 사용 예시

```python
from graph_db.algorithms.core.semantic_rne import SemanticRNE
from graph_db.algorithms.repository.law_repository import LawRepository
from graph_db.services import get_neo4j_service
from sentence_transformers import SentenceTransformer

# 초기화
neo4j = get_neo4j_service()
repository = LawRepository(neo4j)
model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
rne = SemanticRNE(None, repository, model)

# 검색 실행
results, distances = rne.execute_query(
    query_text="도시계획 수립 절차는?",
    similarity_threshold=0.75,
    max_results=20,
    initial_candidates=10
)

for r in results[:5]:
    print(f"{r['article_number']}: {r['relevance_score']:.4f} ({r['expansion_type']})")
```

### 결과 형식

```python
{
    'hang_id': 123,
    'full_id': '국토의_계획_및_이용에_관한_법률_법률_제17조_제1항',
    'law_name': '국토의 계획 및 이용에 관한 법률',
    'article_number': '제17조 제1항',
    'content': '도시·군관리계획은...',
    'relevance_score': 0.8542,
    'expansion_type': 'vector'  # vector, parent, sibling, child, cross_law
}
```

---

## LawRepository

### 핵심 메서드

| 메서드 | 역할 |
|--------|------|
| `vector_search(query_emb, top_k)` | 벡터 유사도 검색 |
| `get_neighbors(hang_id, context)` | 이웃 노드 조회 (parent/sibling/child) |
| `get_article_info(hang_id)` | 조항 상세 정보 |
| `get_cross_law_articles(hang_id)` | 시행령/시행규칙 연결 |

### vector_search 구현

```python
def vector_search(self, query_embedding: List[float], top_k: int = 10):
    """Neo4j 벡터 인덱스 검색"""
    query = """
    CALL db.index.vector.queryNodes('hang_embedding_index', $top_k, $query_embedding)
    YIELD node, score
    WHERE score >= 0.5
    RETURN id(node) AS hang_id, score AS similarity
    ORDER BY similarity DESC
    """
    results = self.neo4j.execute_query(query, {
        'top_k': top_k,
        'query_embedding': query_embedding
    })
    return [(r['hang_id'], r['similarity']) for r in results]
```

### get_neighbors 구현

```python
def get_neighbors(self, hang_id: int, context=None):
    """이웃 노드 조회 (RNE 확장용)"""
    query = """
    MATCH (h:HANG) WHERE id(h) = $hang_id
    
    // 부모 JO
    OPTIONAL MATCH (h)<-[:CONTAINS]-(parent_jo:JO)
    
    // 형제 HANG
    OPTIONAL MATCH (parent_jo)-[:CONTAINS]->(sibling:HANG)
    WHERE id(sibling) <> $hang_id
    
    // 자식 HO
    OPTIONAL MATCH (h)-[:CONTAINS]->(child:HO)
    
    // 시행령/시행규칙 (cross_law)
    OPTIONAL MATCH (h)<-[:CONTAINS*]-(law:LAW)-[:IMPLEMENTS]->(impl_law:LAW)
                   -[:CONTAINS*]->(cross:HANG)
    
    RETURN parent_jo, collect(sibling) AS siblings, 
           collect(child) AS children, collect(cross) AS cross_laws
    """
    # 결과를 (neighbor_id, edge_data) 형태로 반환
```

---

## 자주 쓰는 Cypher 쿼리

### HANG 검색

```cypher
// 특정 조항 검색
MATCH (h:HANG)
WHERE h.full_id CONTAINS '제17조'
RETURN h.full_id, h.content
LIMIT 10

// 벡터 검색
CALL db.index.vector.queryNodes('hang_embedding_index', 10, $query_embedding)
YIELD node, score
RETURN node.full_id, score
ORDER BY score DESC
```

### 계층 구조 탐색

```cypher
// HANG의 상위 JO 찾기
MATCH (h:HANG {full_id: $hang_id})<-[:CONTAINS]-(jo:JO)
RETURN jo.full_id, jo.title

// LAW → JO → HANG 전체 경로
MATCH path = (law:LAW)-[:CONTAINS*]->(h:HANG)
WHERE h.full_id = $hang_id
RETURN path
```

### 도메인 관련

```cypher
// 도메인별 HANG 개수
MATCH (d:Domain)<-[:BELONGS_TO_DOMAIN]-(h:HANG)
RETURN d.domain_name, count(h) AS hang_count
ORDER BY hang_count DESC

// 특정 도메인의 HANG 목록
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain {domain_id: $domain_id})
RETURN h.full_id, h.content
LIMIT 20
```

---

## 환경 변수

```env
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111
NEO4J_DATABASE=neo4j
```

---

## 의존성

- `neo4j`: Neo4j Python Driver
- `numpy`: 벡터 연산
- `openai`: 임베딩 생성
- `sentence_transformers`: KR-SBERT (형제 유사도)
