# AI_INDEX.md - 법규 Graph Node 프로젝트 완전 가이드

> **목적**: AI가 이 프로젝트를 빠르게 이해하고 기억할 수 있도록 모든 핵심 로직과 파일을 상세히 문서화
> **마지막 업데이트**: 2025-11-14
> **프로젝트**: 한국 법률 Multi-Agent RAG 검색 시스템

---

## 1. 프로젝트 핵심 개념

### 1.1 한줄 요약
**PDF 법률문서 → Neo4j 그래프 → 벡터 임베딩 → Multi-Agent 검색 시스템**

### 1.2 핵심 아키텍처 (GraphTeam/GraphAgent-Reasoner 논문 기반)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 쿼리 입력                               │
│                    "국토계획법 17조 알려줘"                           │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1: LLM Self-Assessment (GPT-4o)                               │
│   - 5개 Domain별 쿼리 답변 능력 평가                                  │
│   - Combined Score = 0.7×LLM_Confidence + 0.3×Vector_Similarity     │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1.5: Hybrid Search + RNE Graph Expansion                      │
│   [Exact Match] 정규식 "제17조" 패턴 → similarity=1.0               │
│   [Semantic]    OpenAI 3072-dim 벡터 검색                           │
│   [Relationship] CONTAINS 관계 임베딩 검색                           │
│   [RNE]         SemanticRNE 그래프 확장 (threshold=0.75)            │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 2: A2A Collaboration (도메인 간 협업)                          │
│   - GPT-4o가 협업 필요 여부 판단                                     │
│   - asyncio.gather()로 병렬 A2A 요청                                │
│   - 다른 도메인의 결과 수집                                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 3: Result Synthesis (GPT-4o)                                  │
│   - 여러 도메인 결과 통합                                            │
│   - 자연어 답변 생성                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 데이터 흐름

```
[PDF 법률문서]
     ↓ law/STEP/step1_pdf_to_json.py
[JSON 파싱 데이터]
     ↓ law/STEP/step2_json_to_neo4j.py
[Neo4j 그래프] ← LAW → JO → HANG → HO 계층 구조
     ↓ law/STEP/step3_add_hang_embeddings.py
[HANG 노드 + OpenAI 3072-dim 임베딩]
     ↓ law/STEP/step4_initialize_domains.py
[5개 Domain 노드 + K-means 클러스터링]
     ↓ law/STEP/step5_run_relationship_embedding.py
[CONTAINS 관계 + OpenAI 3072-dim 임베딩]
```

---

## 2. Neo4j 그래프 스키마

### 2.1 노드 구조 (핵심!)

```
LAW (법률 전체)
 └─ PYEON (편)
     └─ JANG (장)
         └─ JEOL (절)
             └─ GWAN (관)
                 └─ JO (조) ← 제목만, 임베딩 있음 (3072-dim)
                     └─ HANG (항) ← ⭐ 실제 법률 내용, 임베딩 있음 (3072-dim)
                         └─ HO (호)
                             └─ MOK (목)

Domain (도메인) ← K-means 클러스터링으로 생성, 센트로이드 임베딩 있음 (768-dim)
```

### 2.2 관계 구조

| 관계 | 설명 | 임베딩 |
|------|------|--------|
| `CONTAINS` | 부모→자식 계층 | OpenAI 3072-dim |
| `NEXT` | 같은 레벨 순서 (HANG① → HANG②) | 없음 |
| `CITES` | 타법 인용 | 없음 |
| `BELONGS_TO_DOMAIN` | HANG → Domain 할당 | similarity 속성 |
| `IMPLEMENTS` | 법률 → 시행령 → 시행규칙 | 없음 |

### 2.3 실제 데이터 통계

| 항목 | 개수 |
|------|------|
| LAW 노드 | 3개 (법률, 시행령, 시행규칙) |
| JO 노드 | 1,053개 |
| **HANG 노드** | **1,477개** (⭐ 핵심 검색 대상) |
| HO 노드 | 1,025개 |
| **Domain 노드** | **5개** |
| CONTAINS 관계 | 3,565개 |
| BELONGS_TO_DOMAIN | 1,477개 |

### 2.4 벡터 인덱스

| 인덱스명 | 대상 | 차원 | 모델 |
|---------|------|------|------|
| `hang_embedding_index` | HANG.embedding | 3072 | OpenAI text-embedding-3-large |
| `contains_embedding` | CONTAINS.embedding | 3072 | OpenAI text-embedding-3-large |
| `jo_embedding_index` | JO.embedding | 3072 | OpenAI text-embedding-3-large |

---

## 3. 핵심 클래스 상세

### 3.1 AgentManager (`agents/law/agent_manager.py`)

**역할**: 도메인 관리, 자가 조직화, DomainAgent 인스턴스 생성

```python
class AgentManager:
    """자가 조직화 에이전트 관리자"""
    
    # 임계값 설정
    MIN_AGENT_SIZE = 50      # 미만이면 병합
    MAX_AGENT_SIZE = 500     # 초과하면 분할
    DOMAIN_SIMILARITY_THRESHOLD = 0.70
    
    def __init__(self):
        # Neo4j 연결
        self.neo4j = Neo4jService()
        self.neo4j.connect()
        
        # 도메인 관리
        self.domains: Dict[str, DomainInfo] = {}
        self.node_to_domain: Dict[str, str] = {}
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        
        # LLM 클라이언트
        self.llm_client = OpenAI()
        
        # Neo4j에서 기존 도메인 로드
        loaded_domains = self._load_domains_from_neo4j()
        if loaded_domains:
            self.domains = loaded_domains
            # 각 DomainInfo에 DomainAgent 인스턴스 생성
            for domain in loaded_domains.values():
                domain.agent_instance = self._create_domain_agent_instance(domain)
        else:
            # 도메인 없으면 K-means 클러스터링으로 초기화
            self._initialize_from_existing_hangs(n_clusters=5)
```

**핵심 메서드**:

| 메서드 | 역할 |
|--------|------|
| `process_new_pdf(pdf_path)` | PDF 자동 처리 (파싱→임베딩→도메인할당) |
| `_assign_to_agents(hang_ids, embeddings)` | 자동 도메인 할당 |
| `_kmeans_initial_clustering(hang_ids, embeddings)` | K-means로 초기 클러스터링 |
| `_create_domain_agent_instance(domain)` | DomainAgent 인스턴스 생성 |
| `_split_agent(domain)` | 크기 > 500이면 분할 |
| `_merge_agents(domain_a, domain_b)` | 크기 < 50이면 병합 |
| `_generate_domain_name(hang_ids)` | LLM으로 도메인 이름 생성 |
| `_sync_domain_to_neo4j(domain)` | 메모리 → Neo4j 동기화 |

---

### 3.2 DomainAgent (`agents/law/domain_agent.py`)

**역할**: 도메인별 법률 검색 전문 에이전트

```python
class DomainAgent(BaseWorkerAgent):
    """도메인 에이전트 - 특정 법률 도메인 전문가"""
    
    def __init__(self, agent_slug, agent_config, domain_info):
        # 도메인 정보
        self.domain_id = domain_info['domain_id']
        self.domain_name = domain_info['domain_name']
        self.node_ids = set(domain_info['node_ids'])  # HANG full_id 집합
        self.neighbor_agents = domain_info['neighbor_agents']
        
        # RNE 설정
        self.rne_threshold = agent_config.get('rne_threshold', 0.75)
        
        # Phase 1.5: Lazy 초기화
        self._law_repository = None
        self._semantic_rne = None
        self._kr_sbert_model = None
```

**검색 파이프라인** (`_search_my_domain`):

```python
async def _search_my_domain(self, query: str, limit: int = 30):
    # [1] 쿼리 임베딩 생성
    kr_sbert_embedding = await self._generate_kr_sbert_embedding(query)   # 768-dim
    openai_embedding = await self._generate_openai_embedding(query)       # 3072-dim
    
    # [2] Hybrid Search
    hybrid_results = await self._hybrid_search(query, kr_sbert_embedding, openai_embedding)
    
    # [3] Phase 1.5: RNE Graph Expansion
    expanded_results = await self._rne_graph_expansion(query, hybrid_results[:5], kr_sbert_embedding)
    
    # [4] JO→HANG 확장
    expanded_hangs = await self._expand_jo_to_hangs(hybrid_results, query, openai_embedding)
    
    # [5] 결과 병합 + Score Normalization
    all_results = self._merge_hybrid_and_rne(hybrid_results, expanded_results + expanded_hangs)
    
    # [6] 정보 보강 (law_name, jo_number, hang_number)
    return enrich_hang_results(all_results[:limit])
```

**Hybrid Search 구성**:

| 검색 방식 | 임베딩 | 설명 |
|-----------|--------|------|
| Exact Match | - | 정규식 `제(\d+)조` 패턴 매칭, similarity=1.0 |
| Semantic Vector | OpenAI 3072-dim | `hang_embedding_index` 벡터 검색 |
| Relationship | OpenAI 3072-dim | `contains_embedding` 관계 검색 |
| JO-level | OpenAI 3072-dim | JO 노드 벡터 검색 |

**RRF (Reciprocal Rank Fusion)**:
```python
def _reciprocal_rank_fusion(self, result_lists, k=60):
    """RRF 점수 = Σ 1/(k + rank)"""
    for rank, result in enumerate(result_list, start=1):
        rrf_score = 1.0 / (k + rank)
        rrf_scores[hang_id] += rrf_score
```

---

### 3.3 SemanticRNE (`graph_db/algorithms/core/semantic_rne.py`)

**역할**: 법규용 Range Network Expansion 알고리즘

```python
class SemanticRNE(BaseSpatialAlgorithm):
    """
    알고리즘 개요 (HybridRAG 방식):
    
    Stage 1: Vector Search
      ↓ Neo4j 벡터 인덱스 (top-10)
    Stage 2: Graph Expansion (Priority Queue)
      ↓ 계층 구조 탐색 (부모/형제/자식)
    Stage 3: Reranking
      ↓ 유사도 재정렬
    """
    
    def execute_query(self, query_text, similarity_threshold=0.75, max_results=None):
        # [1] 쿼리 임베딩 (OpenAI 3072-dim)
        query_emb = openai.embeddings.create(input=query_text, model="text-embedding-3-large")
        
        # [2] Stage 1: 벡터 검색
        initial_results = self.repository.vector_search(query_emb, top_k=10)
        
        # [3] Stage 2: RNE 확장 (Dijkstra 변형)
        pq = []  # Priority Queue: (cost, hang_id, expansion_type)
        for hang_id, similarity in initial_results:
            cost = 1 - similarity
            heapq.heappush(pq, (cost, hang_id, 'vector'))
        
        while pq:
            cost, u, exp_type = heapq.heappop(pq)
            if (1 - cost) < similarity_threshold:
                break  # 유사도 임계값 미달
            
            # 이웃 확장
            for v, edge_data in self.repository.get_neighbors(u):
                edge_cost = self._calculate_semantic_cost(edge_data, query_emb)
                # parent/child/cross_law: 비용 0 (자동 포함)
                # sibling: 1 - cosine_similarity
        
        # [4] Stage 3: 결과 정렬
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
```

**엣지 비용 함수**:

| 엣지 타입 | 비용 | 설명 |
|-----------|------|------|
| `parent` | 0 | 상위 JO 자동 포함 |
| `child` | 0 | 하위 HO/MOK 자동 포함 |
| `cross_law` | 0 | 법률→시행령→시행규칙 자동 포함 |
| `sibling` | 1-similarity | 형제 HANG 유사도 계산 |

---

### 3.4 Neo4jService (`graph_db/services/neo4j_service.py`)

**역할**: Neo4j 연결 및 쿼리 실행

```python
class Neo4jService:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "11111111")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    def execute_query(self, query: str, parameters: dict) -> List[Dict]:
        """Cypher 쿼리 실행"""
        with self.get_session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

# 싱글톤 인스턴스
def get_neo4j_service() -> Neo4jService:
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
        _neo4j_service.connect()
    return _neo4j_service
```

---

## 4. 검색 API

### 4.1 법률 검색 API (`agents/law/api/search.py`)

**엔드포인트**: `POST /agents/law/api/search`

**요청**:
```json
{
  "query": "17조 검색",
  "limit": 10,
  "synthesize": true
}
```

**응답**:
```json
{
  "results": [
    {
      "hang_id": "국토의_계획_및_이용에_관한_법률_법률_제17조_제1항",
      "content": "도시·군관리계획은...",
      "similarity": 1.0,
      "stages": ["exact_match"],
      "law_name": "국토의 계획 및 이용에 관한 법률",
      "jo_number": "제17조",
      "hang_number": "제1항"
    }
  ],
  "stats": {
    "domains_queried": 2,
    "a2a_collaboration_triggered": true
  },
  "synthesized_answer": "GPT-4o 생성 답변..."
}
```

---

## 5. 데이터 파이프라인

### 5.1 순차 실행 스크립트 (`law/STEP/`)

```bash
cd law/STEP
python run_all.py  # 전체 자동 실행 (~50분)

# 또는 개별 실행
python step1_pdf_to_json.py      # PDF → JSON (~5분)
python step2_json_to_neo4j.py    # JSON → Neo4j (~3분)
python step3_add_hang_embeddings.py  # HANG 임베딩 (~10분, OpenAI 3072-dim)
python step4_initialize_domains.py   # Domain 초기화 (~5분, K-means)
python step5_run_relationship_embedding.py  # 관계 임베딩 (~25분)

python verify_system.py  # 시스템 검증
```

### 5.2 각 단계 상세

| 단계 | 입력 | 출력 | 핵심 로직 |
|------|------|------|-----------|
| step1 | PDF | JSON | `PDFLawExtractor`, `EnhancedKoreanLawParser` |
| step2 | JSON | Neo4j 노드 | `Neo4jLawLoader`, CONTAINS/NEXT 관계 |
| step3 | Neo4j HANG | 임베딩 | OpenAI text-embedding-3-large (3072-dim) |
| step4 | 임베딩 | Domain 노드 | K-means 클러스터링, LLM 도메인 이름 생성 |
| step5 | Neo4j 관계 | 관계 임베딩 | CONTAINS 관계에 OpenAI 임베딩 추가 |

---

## 6. 파일 경로 인덱스

### 6.1 핵심 파일 (반드시 알아야 함)

| 경로 | 역할 | 핵심 클래스/함수 |
|------|------|-----------------|
| `agents/law/agent_manager.py` | 도메인 관리 | `AgentManager`, `DomainInfo` |
| `agents/law/domain_agent.py` | 도메인 검색 | `DomainAgent._search_my_domain()` |
| `agents/law/api/search.py` | 검색 API | `LawSearchAPIView` |
| `graph_db/services/neo4j_service.py` | DB 연결 | `Neo4jService`, `get_neo4j_service()` |
| `graph_db/algorithms/core/semantic_rne.py` | RNE 알고리즘 | `SemanticRNE.execute_query()` |
| `graph_db/algorithms/repository/law_repository.py` | 법률 Repository | `LawRepository.vector_search()` |

### 6.2 데이터 파이프라인

| 경로 | 역할 |
|------|------|
| `law/STEP/run_all.py` | 전체 자동 실행 |
| `law/STEP/step1_pdf_to_json.py` | PDF 파싱 |
| `law/STEP/step2_json_to_neo4j.py` | Neo4j 로드 |
| `law/STEP/step3_add_hang_embeddings.py` | HANG 임베딩 |
| `law/STEP/step4_initialize_domains.py` | Domain 초기화 |
| `law/core/law_parser.py` | 법률 파서 |
| `law/core/pdf_extractor.py` | PDF 추출 |

### 6.3 WebSocket 채팅

| 경로 | 역할 |
|------|------|
| `chat/consumers.py` | `ChatConsumer` - A2A 통합 채팅 |
| `gemini/consumers/simple_consumer.py` | `SimpleConsumer` - Gemini 채팅 |
| `gemini/consumers/handlers/a2a_handler.py` | `A2AHandler` - 에이전트 라우팅 |

### 6.4 Worker Agent

| 경로 | 역할 |
|------|------|
| `agents/worker_agents/base/base_worker.py` | `BaseWorkerAgent` |
| `agents/worker_agents/implementations/host_agent.py` | Host Agent (조정자) |
| `agents/worker_agents/worker_manager.py` | `WorkerAgentManager` |

---

## 7. 환경 변수

```env
# Neo4j (필수!)
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111
NEO4J_DATABASE=neo4j

# OpenAI (필수! - 임베딩 및 LLM)
OPENAI_API_KEY=sk-xxx

# Gemini (선택 - 음성 대화용)
GEMINI_API_KEY=xxx

# Django
DEBUG=True
SECRET_KEY=your-secret-key
```

---

## 8. 빠른 시작

```bash
# 1. 가상환경 활성화
.venv\Scripts\activate

# 2. Neo4j Desktop 시작 (http://localhost:7474)

# 3. 법률 데이터 파이프라인 (최초 1회)
cd law/STEP
python run_all.py  # ~50분

# 4. Django 서버 (WebSocket 지원)
cd ..
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# 5. 접속
# 채팅: http://localhost:8000/chat/
# 법률 API: POST http://localhost:8000/agents/law/api/search
```

---

## 9. 핵심 알고리즘 요약

### 9.1 Hybrid Search

```
[Exact Match]      → 정규식 패턴 매칭 → similarity=1.0
        ↓
[Semantic Vector]  → OpenAI 3072-dim → hang_embedding_index
        ↓
[Relationship]     → OpenAI 3072-dim → contains_embedding
        ↓
[JO-level]         → OpenAI 3072-dim → JO 노드 검색
        ↓
[RRF Fusion]       → score = Σ 1/(60 + rank)
```

### 9.2 RNE Graph Expansion

```
[시작점: 벡터 검색 top-10]
        ↓
[Priority Queue] (cost = 1 - similarity)
        ↓
[확장 규칙]
  - parent/child/cross_law: cost=0 (자동 포함)
  - sibling: cost = 1 - cosine_similarity
        ↓
[threshold < similarity인 노드만]
        ↓
[결과 정렬]
```

### 9.3 A2A Collaboration

```
[자기 도메인 검색]
        ↓
[결과 품질 평가] (quality_score = 0.7×avg_sim + 0.3×count_score)
        ↓
[quality < 0.6 → GPT-4o 협업 판단]
        ↓
[asyncio.gather() 병렬 A2A 요청]
        ↓
[결과 통합]
```

---

## 10. 디버깅 팁

### 10.1 Neo4j 연결 확인
```python
from graph_db.services import get_neo4j_service
neo4j = get_neo4j_service()
print(neo4j.execute_query("MATCH (h:HANG) RETURN count(h) AS count"))
```

### 10.2 도메인 확인
```python
from agents.law.agent_manager import AgentManager
manager = AgentManager()
for d in manager.domains.values():
    print(f"{d.domain_name}: {d.size()} nodes")
```

### 10.3 검색 테스트
```python
domain = list(manager.domains.values())[0]
results = await domain.agent_instance._search_my_domain("17조 검색")
for r in results[:3]:
    print(f"{r['hang_id']}: {r['similarity']:.3f}")
```

---

**이 문서를 먼저 읽으면 프로젝트 전체를 완전히 파악할 수 있습니다.**
