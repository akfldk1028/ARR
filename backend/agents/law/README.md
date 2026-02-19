# agents/law/ - 법률 Multi-Agent 검색 시스템

## 개요

**GraphTeam/GraphAgent-Reasoner 논문 기반** Multi-Agent 법률 검색 시스템.
5개 도메인별 전문 에이전트가 협업하여 법률 조항을 검색.

---

## 핵심 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        AgentManager                          │
│  - 5개 DomainInfo 관리 (domain_id → DomainInfo)              │
│  - 각 DomainInfo에 DomainAgent 인스턴스 포함                  │
│  - K-means 클러스터링으로 도메인 자동 생성                    │
│  - 크기 > 500 → 분할, 크기 < 50 → 병합                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ DomainAgent 1 │   │ DomainAgent 2 │   │ DomainAgent 3 │  ...
│ "도시계획"     │   │ "토지보상"    │   │ "건축규제"    │
│ 510 노드      │   │ 389 노드      │   │ 230 노드      │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ↓
                    [A2A 협업 네트워크]
```

---

## 파일 구조

### 핵심 파일

| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `agent_manager.py` | 도메인 관리, 자가 조직화 | `AgentManager`, `DomainInfo` |
| `domain_agent.py` | 도메인별 검색 에이전트 | `DomainAgent` |
| `domain_manager.py` | 도메인 CRUD | `DomainManager` |
| `utils.py` | 유틸리티 함수 | `enrich_hang_results()` |

### API 디렉토리 (`api/`)

| 파일 | 역할 | 엔드포인트 |
|------|------|-----------|
| `search.py` | 법률 검색 API | `POST /agents/law/api/search` |
| `streaming.py` | SSE 스트리밍 | `GET /agents/law/api/stream` |
| `domains.py` | 도메인 목록 | `GET /agents/law/api/domains` |
| `health.py` | 헬스체크 | `GET /agents/law/api/health` |

---

## AgentManager 상세

### 클래스 구조

```python
class AgentManager:
    """자가 조직화 에이전트 관리자"""
    
    # 임계값
    MIN_AGENT_SIZE = 50      # 미만이면 병합
    MAX_AGENT_SIZE = 500     # 초과하면 분할
    DOMAIN_SIMILARITY_THRESHOLD = 0.70
    OPTIMAL_CLUSTER_RANGE = (5, 15)  # K-means 클러스터 범위
    
    def __init__(self):
        self.domains: Dict[str, DomainInfo] = {}     # domain_id → DomainInfo
        self.node_to_domain: Dict[str, str] = {}     # hang_full_id → domain_id
        self.embeddings_cache: Dict[str, np.ndarray] = {}  # 임베딩 캐시
        self.llm_client = OpenAI()  # 도메인 이름 생성용
```

### DomainInfo 구조

```python
class DomainInfo:
    domain_id: str           # "domain_abc12345"
    domain_name: str         # "도시계획 및 관리"
    agent_slug: str          # "law_도시계획_및_관리"
    node_ids: Set[str]       # HANG full_id 집합
    centroid: np.ndarray     # 768-dim 센트로이드 벡터
    neighbor_domains: Set[str]  # A2A 이웃 도메인 ID
    agent_instance: DomainAgent  # ⭐ DomainAgent 인스턴스
```

### 주요 메서드

| 메서드 | 역할 |
|--------|------|
| `_load_domains_from_neo4j()` | 서버 시작 시 Neo4j에서 도메인 로드 |
| `_initialize_from_existing_hangs(n_clusters=5)` | K-means로 초기 도메인 생성 |
| `_create_domain_agent_instance(domain)` | DomainAgent 인스턴스 동적 생성 |
| `_generate_domain_name(hang_ids)` | GPT-4o-mini로 도메인 이름 생성 |
| `_split_agent(domain)` | 크기 > 500 → K-means로 2분할 |
| `_merge_agents(domain_a, domain_b)` | 작은 도메인 병합 |
| `_sync_domain_to_neo4j(domain)` | 메모리 → Neo4j 동기화 |
| `process_new_pdf(pdf_path)` | 새 PDF 자동 처리 |

---

## DomainAgent 상세

### 검색 파이프라인 (`_search_my_domain`)

```
[1] 쿼리 임베딩 생성
    ├─ KR-SBERT 768-dim (RNE용)
    └─ OpenAI 3072-dim (HANG/관계 검색용)
        ↓
[2] Hybrid Search
    ├─ Exact Match: 정규식 "제(\d+)조" → similarity=1.0
    ├─ Semantic Vector: OpenAI 3072-dim → hang_embedding_index
    ├─ Relationship: OpenAI 3072-dim → contains_embedding
    └─ JO-level: JO 노드 벡터 검색
        ↓
[3] RRF (Reciprocal Rank Fusion)
    score = Σ 1/(60 + rank)
        ↓
[4] RNE Graph Expansion (SemanticRNE)
    - 벡터 검색 top-10으로 시작
    - Priority Queue로 그래프 확장
    - parent/child: 비용 0 (자동 포함)
    - sibling: 1 - cosine_similarity
    - threshold=0.75 이상만
        ↓
[5] JO → HANG 확장
    - JO 결과에서 하위 HANG 가져오기
        ↓
[6] 결과 병합 + Score Normalization
    - Min-Max normalization
    - 제12장(부칙) 페널티 (×0.3)
        ↓
[7] 정보 보강 (enrich_hang_results)
    - law_name, jo_number, hang_number 추가
```

### A2A 협업 메서드

| 메서드 | 역할 |
|--------|------|
| `assess_query_confidence(query)` | GPT-4o로 답변 능력 평가 (0.0~1.0) |
| `should_collaborate(query, results, domains)` | 협업 필요성 판단 |
| `handle_a2a_request(message)` | 다른 도메인 요청 처리 |
| `_consult_neighbors(query)` | asyncio.gather()로 병렬 협업 |

### A2A 협업 플로우

```
[1] 자기 도메인 검색
        ↓
[2] 결과 품질 평가
    quality_score = 0.7 × avg_similarity + 0.3 × count_score
        ↓
[3] quality < 0.6이면 GPT-4o 협업 판단
    {
      "should_collaborate": true,
      "target_domains": ["토지보상", "건축규제"],
      "refined_queries": {"토지보상": "17조 보상 절차"}
    }
        ↓
[4] asyncio.gather()로 병렬 A2A 요청
        ↓
[5] 결과 통합 + 유사도 순 정렬
```

---

## API 사용법

### 법률 검색

```bash
POST /agents/law/api/search
Content-Type: application/json

{
  "query": "국토계획법 17조",
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
      "content": "도시·군관리계획은 특별시장·광역시장...",
      "similarity": 1.0,
      "stages": ["exact_match"],
      "law_name": "국토의 계획 및 이용에 관한 법률",
      "law_type": "법률",
      "jo_number": "제17조",
      "hang_number": "제1항"
    }
  ],
  "stats": {
    "domains_queried": 2,
    "a2a_collaboration_triggered": true,
    "llm_calls": 7
  },
  "synthesized_answer": "국토의 계획 및 이용에 관한 법률 제17조는..."
}
```

### 도메인 목록

```bash
GET /agents/law/api/domains
```

```json
{
  "domains": [
    {"domain_id": "domain_abc", "domain_name": "도시계획", "node_count": 510},
    {"domain_id": "domain_def", "domain_name": "토지보상", "node_count": 389}
  ]
}
```

---

## 사용 예시

### Python에서 검색

```python
from agents.law.agent_manager import AgentManager

# AgentManager 초기화 (Neo4j 연결 + 도메인 로드)
manager = AgentManager()

# 도메인 확인
for domain_id, domain in manager.domains.items():
    print(f"{domain.domain_name}: {domain.size()} nodes")

# 특정 도메인으로 검색
domain = list(manager.domains.values())[0]
results = await domain.agent_instance._search_my_domain("17조 검색")

for r in results[:5]:
    print(f"{r['hang_id']}: {r['similarity']:.3f}")
```

### Django Shell에서 테스트

```bash
python manage.py shell
```

```python
>>> from agents.law.agent_manager import AgentManager
>>> manager = AgentManager()
>>> print(manager.get_statistics())
```

---

## 의존성

- `graph_db.services.Neo4jService`: Neo4j 연결
- `graph_db.algorithms.core.semantic_rne.SemanticRNE`: RNE 알고리즘
- `graph_db.algorithms.repository.law_repository.LawRepository`: 법률 데이터 접근
- `sentence_transformers`: KR-SBERT 임베딩
- `openai`: OpenAI 임베딩 + GPT-4o
- `sklearn.cluster.KMeans`: 도메인 클러스터링
