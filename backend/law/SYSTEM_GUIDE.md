# 법규 Neo4j 연동 시스템 - 완전 학습 가이드

**작성일**: 2025-11-13
**목적**: 다음 AI 또는 개발자가 순차적으로 시스템을 이해할 수 있도록 안내

---

## 🚀 빠른 시작 (순차적 실행)

**처음 시작하는 경우 또는 시스템을 재구축하는 경우:**

```bash
cd law/STEP

# 전체 자동 실행 (약 50-60분)
python run_all.py

# 또는 단계별 실행
python step1_pdf_to_json.py                    # PDF → JSON
python step2_json_to_neo4j.py                  # JSON → Neo4j
python step3_add_hang_embeddings.py            # HANG 임베딩
python step4_initialize_domains.py             # Domain 초기화 ⭐
python step5_run_relationship_embedding.py     # 관계 임베딩

# 검증
python verify_system.py
```

**📂 자세한 실행 가이드**: `law/STEP/README.md`
**📖 완전 설정 가이드**: `docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`

---

## 📚 학습 순서 (순차적으로 읽을 것!)

### **Phase 1: 개요 및 아키텍처 이해**

#### 1.1 전체 구조 파악
```
📄 읽을 파일: law/README.md
📄 읽을 파일: law/neo4j_schema.md
📄 읽을 파일: law/docs/PIPELINE_GUIDE.md
```

**핵심 개념:**
- Multi-Agent RAG 시스템
- Neo4j 그래프 데이터베이스
- 3단계 다층 청킹 (조전체/항단위/호단위)
- A2A (Agent-to-Agent) 프로토콜

**시스템 흐름:**
```
PDF → JSON → Neo4j → Embeddings → Multi-Agent System → 검색
```

---

### **Phase 2: 데이터 파이프라인 (PDF → Neo4j)**

#### 2.1 PDF → JSON 변환
```
📄 읽을 파일: law/scripts/pdf_to_json.py
📄 읽을 파일: law/scripts/pdf_extractor.py
📄 읽을 파일: law/scripts/neo4j_preprocessor.py
```

**핵심 클래스:**
- `PDFLawExtractor`: PDF 텍스트 추출
- `EnhancedKoreanLawParser`: 법률 구조 파싱

**파싱 계층 구조:**
```
LAW (법률)
 └─ PYEON (편)
     └─ JANG (장)
         └─ JEOL (절)
             └─ GWAN (관)
                 └─ JO (조) ← 제목만!
                     └─ HANG (항) ← **실제 내용 여기!**
                         └─ HO (호)
                             └─ MOK (목)
```

**❗ 중요:** JO 노드는 제목만, **HANG 노드가 실제 법률 내용**

**실행 예시:**
```bash
python law/scripts/pdf_to_json.py --pdf "law/data/raw/법률.pdf"
# 출력: law/data/parsed/법률_법률.json
```

#### 2.2 JSON → Neo4j 로드
```
📄 읽을 파일: law/scripts/json_to_neo4j.py
📄 읽을 파일: law/scripts/neo4j_loader.py
📄 읽을 파일: law/core/neo4j_manager.py
```

**핵심 클래스:**
- `Neo4jLawLoader`: Neo4j 데이터 로더

**생성되는 3가지 관계:**
1. **CONTAINS**: 계층적 부모-자식 (LAW → JANG → JO → HANG)
2. **NEXT**: 같은 레벨 순서 (HANG ① → HANG ②)
3. **CITES**: 타법 인용 (HANG → 다른 법률)

**제약조건:**
- UNIQUE: `full_id` (모든 노드 타입)
- NOT NULL: `law_name`, `full_id` (JO, HANG, HO, MOK)

**인덱스:**
- 단일: `law_name`, `law_category`, `unit_number`
- 복합: `(law_name, unit_number)`
- 벡터: `hang_embedding_index`, `contains_embedding`

**실행 예시:**
```bash
python law/scripts/json_to_neo4j.py --json "law/data/parsed/법률_법률.json"
# 출력: Neo4j DB + law/scripts/neo4j/법률_neo4j.json (백업)
```

#### 2.3 샘플 데이터 확인
```
📄 읽을 파일: law/scripts/neo4j/국토의_계획_및_이용에_관한_법률_neo4j.json
```

**데이터 구조 예시:**
```json
{
  "law_name": "국토의 계획 및 이용에 관한 법률",
  "law_type": "시행령",
  "nodes": [
    {
      "labels": ["JANG"],
      "properties": {
        "law_name": "국토의 계획 및 이용에 관한 법률",
        "number": "1",
        "title": "총칙",
        "full_id": "국토의 계획 및 이용에 관한 법률::제1장"
      }
    }
  ],
  "relationships": [...]
}
```

---

### **Phase 3: Embedding 시스템**

#### 3.1 노드 임베딩 (HANG)
```
📄 읽을 파일: add_hang_embeddings.py (프로젝트 루트)
📄 읽을 파일: law/core/embedding_loader.py
```

**모델:** KR-SBERT (`jhgan/ko-sbert-sts`)
- **차원:** 768
- **대상:** HANG 노드의 `content` 속성
- **인덱스:** `hang_embedding_index` (cosine similarity)

**핵심 클래스:**
- `EmbeddingAdder`: HANG 노드 임베딩 추가

**프로세스:**
```python
1. fetch_hang_nodes(batch_size=100)     # HANG 노드 가져오기
2. model.encode(contents, batch_size=32) # 임베딩 생성
3. SET hang.embedding = $embedding       # Neo4j 업데이트
4. CREATE VECTOR INDEX hang_embedding_index # 벡터 인덱스 생성
```

**실행 예시:**
```bash
python add_hang_embeddings.py
# 출력: 1,586개 HANG 노드에 768-dim 임베딩 추가
```

#### 3.3 Domain 노드 초기화 ⭐ 필수!
```
📄 실행 파일: initialize_domains.py (프로젝트 루트)
📄 읽을 파일: agents/law/agent_manager.py
```

**목적:** 기존 HANG 노드로부터 도메인 자동 생성

**프로세스:**
```python
1. AgentManager() 인스턴스 생성
2. Neo4j에서 기존 Domain 노드 확인
3. Domain 없으면 자동 초기화:
   - HANG 노드 1,477개 로드
   - K-means 클러스터링 (k=5)
   - 각 클러스터 → Domain 노드 생성
   - LLM으로 도메인 이름 생성
   - DomainAgent 인스턴스 생성
   - BELONGS_TO_DOMAIN 관계 생성
```

**실행 예시:**
```bash
python initialize_domains.py
# 출력:
#   Domain 노드: 5개 생성
#   BELONGS_TO_DOMAIN 관계: 1,477개 생성
#   각 Domain에 DomainAgent 인스턴스 할당
```

**생성 결과:**
```
Domain 노드 (5개):
  - domain_c283b545: 510 nodes
  - domain_676e7400: 389 nodes
  - domain_3be25bdc: 230 nodes
  - domain_fad24752: 227 nodes
  - domain_09b3af0d: 121 nodes

BELONGS_TO_DOMAIN 관계 (1,477개):
  각 HANG → Domain (유사도 포함)
```

**❗ 중요:** 이 단계를 실행해야 Multi-Agent System이 작동합니다!

#### 3.2 관계 임베딩 (CONTAINS)
```
📄 읽을 파일: law/relationship_embedding/README.md
📄 읽을 파일: law/relationship_embedding/step1_analyze_relationships.py
📄 읽을 파일: law/relationship_embedding/step2_extract_contexts.py
📄 읽을 파일: law/relationship_embedding/step3_generate_embeddings.py
📄 읽을 파일: law/relationship_embedding/step4_update_neo4j.py
📄 읽을 파일: law/relationship_embedding/step5_create_index_and_test.py
📄 읽을 파일: law/relationship_embedding/step10_type_agnostic_search.py
```

**모델:** OpenAI `text-embedding-3-large`
- **차원:** 3,072
- **대상:** CONTAINS 관계의 `context` (부모→자식 의미)
- **인덱스:** `contains_embedding` (cosine similarity)

**핵심 발견:**
- 타입 분류 무시하고 **순수 벡터 검색**이 가장 효과적
- 평균 유사도: 0.7479
- 관련성: 54.3% (타입 기반 대비 2.5배 향상)

**프로세스:**
```bash
# 전체 파이프라인
python law/relationship_embedding/step1_analyze_relationships.py
python law/relationship_embedding/step2_extract_contexts.py
python law/relationship_embedding/step3_generate_embeddings.py
python law/relationship_embedding/step4_update_neo4j.py
python law/relationship_embedding/step5_create_index_and_test.py

# 최종 테스트
python law/relationship_embedding/step10_type_agnostic_search.py
```

**데이터 위치:**
- `law/relationship_embedding/data/relationship_contexts.json` (4.4 MB)
- `law/relationship_embedding/data/relationship_contexts_with_embeddings.json` (311.8 MB)

---

### **Phase 4: Multi-Agent System (MAS)**

#### 4.1 AgentManager (자가 조직화 관리자)
```
📄 읽을 파일: agents/law/agent_manager.py
```

**핵심 클래스:**
- `AgentManager`: 자가 조직화 에이전트 관리자
- `DomainInfo`: 도메인 정보 데이터 클래스

**주요 기능:**
1. **process_new_pdf()**: 새 PDF 자동 처리
   - PDF 추출 → 파싱 → Neo4j 저장 → 임베딩 생성 → 도메인 할당

2. **자동 도메인 생성** (K-means 클러스터링)
   - 클러스터 수: 5~15개 (Silhouette Score로 최적화)
   - 유사도 임계값: 0.70

3. **에이전트 최적화:**
   - **분할**: 도메인 > 500 노드
   - **병합**: 도메인 < 50 노드

4. **A2A 네트워크 구성:**
   - 이웃 도메인 자동 연결
   - Cross-law 관계 기반

**도메인 정보 구조:**
```python
class DomainInfo:
    domain_id: str               # 고유 ID
    domain_name: str            # LLM 생성 이름 (예: "도시계획 및 관리")
    agent_slug: str             # 에이전트 슬러그
    node_ids: Set[str]          # 담당 HANG 노드들
    centroid: np.ndarray        # 중심 벡터 (768-dim)
    neighbor_domains: Set[str]  # A2A 이웃 도메인
    agent_instance: DomainAgent # 에이전트 인스턴스
```

**초기화 흐름:**
```python
1. Neo4j에서 기존 도메인 로드 (_load_domains_from_neo4j)
2. 도메인 없으면 HANG 노드로부터 자동 초기화 (_initialize_from_existing_hangs)
3. K-means 클러스터링 (n_clusters=5)
4. LLM으로 도메인 이름 생성 (OpenAI GPT-4)
5. DomainAgent 인스턴스 생성 (_create_domain_agent_instance)
```

#### 4.2 DomainAgent (도메인 전문 에이전트)
```
📄 읽을 파일: agents/law/domain_agent.py
```

**핵심 클래스:**
- `DomainAgent`: 도메인별 법률 검색 전문 에이전트

**검색 전략 (3단계):**
```python
# Stage 1-A: 노드 벡터 검색 (KR-SBERT 768-dim)
kr_sbert_embedding = generate_kr_sbert_embedding(query)
vector_results = vector_search(kr_sbert_embedding, limit=5)

# Stage 1-B: 관계 벡터 검색 (OpenAI 3072-dim)
openai_embedding = generate_openai_embedding(query)
relationship_results = search_relationships(openai_embedding, limit=5)

# Stage 2: 그래프 확장 (RNE)
expanded_results = graph_expansion(top_result_id, kr_sbert_embedding)

# Stage 3: 리랭킹
final_results = rerank_results(all_results, kr_sbert_embedding)
```

**협업 메커니즘 (A2A):**
```python
1. 자기 도메인 검색 (_search_my_domain)
2. 결과 품질 평가 (_evaluate_results)
3. Quality Score < 0.6 → 이웃 도메인에게 A2A 요청 (_consult_neighbors)
4. 결과 통합 (_merge_results)
5. 응답 생성 (_format_response)
```

**A2A 프로토콜:**
- JSON-RPC 2.0 메시지 포맷
- 이웃 에이전트 목록: `neighbor_agents`
- 비동기 요청/응답

---

### **Phase 5: 검색 알고리즘**

#### 5.1 RNE (Relative Neighbor Expansion)
```
📄 읽을 파일: law/routing/rne_engine.py
```

**목적:** 그래프 탐색 기반 연관 조항 확장

**알고리즘:**
```python
1. 초기 노드 (최고 유사도 HANG)
2. CONTAINS 관계를 따라 이웃 탐색
3. 유사도 >= threshold인 이웃만 확장
4. 반복 (depth 제한)
5. 도달 가능 노드 집합 반환
```

**핵심 함수:**
- `rne_expand(src_id, radius_e, context)`: RNE 확장
- `calculate_edge_cost(segment, regulations, context)`: 엣지 비용 계산

**적용 사례:**
```
질의: "개발행위 허가 요건은?"
→ HANG 노드 "개발행위허가" 발견 (유사도 0.85)
→ RNE 확장: 부모 JO, 이웃 HANG, 하위 HO 탐색
→ 결과: 관련 조항 10개 (계층적 맥락 포함)
```

#### 5.2 INE (Iterative Neighbor Expansion)
```
📄 읽을 파일: graph_db/algorithms/__init__.py
```

**목적:** 반복적 이웃 확장으로 관련 조항 확대

**파라미터:**
- `k`: 확장할 이웃 수 (기본값: 10)
- `threshold`: 유사도 임계값 (기본값: 0.75)

**알고리즘:**
```python
1. 시드 노드 집합 S (초기 검색 결과)
2. 각 노드 s ∈ S:
   - 이웃 노드 N(s) 가져오기
   - 유사도 계산: sim(query, N(s))
   - Top-k 이웃 선택 (sim >= threshold)
3. 새 노드 → S에 추가
4. 수렴할 때까지 반복
```

---

### **Phase 6: 전체 검색 흐름**

#### 6.1 사용자 질의 처리
```
📄 읽을 파일: agents/law/law_coordinator_worker.py (존재한다면)
```

**전체 흐름:**
```
사용자 질의 "개발행위 허가 요건은?"
    ↓
[AgentManager]
    ↓ 쿼리 라우팅 (도메인 분류)
    ↓
[DomainAgent - "도시계획 및 관리"]
    ↓
[Stage 1-A] 노드 벡터 검색 (KR-SBERT 768-dim)
    → HANG 노드 5개 발견
    ↓
[Stage 1-B] 관계 벡터 검색 (OpenAI 3072-dim)
    → CONTAINS 관계 5개 발견 → HANG 노드 변환
    ↓
[Stage 2] 그래프 확장 (RNE)
    → 최고 유사도 HANG 기준 이웃 탐색
    → 연관 조항 5개 추가
    ↓
[Stage 3] 리랭킹
    → 유사도 순 정렬 Top 10
    ↓
[Quality 평가]
    → Score >= 0.6 → 자체 응답
    → Score < 0.6 → 이웃 도메인 요청 (A2A)
    ↓
[응답 생성] (LLM)
    → 핵심 조항 (가장 관련도 높음)
    → 연관 조항 (그래프 확장 결과)
    → 시행령/시행규칙 (CITES 관계)
```

---

### **Phase 7: 고급 주제**

#### 7.1 A2A (Agent-to-Agent) 프로토콜
```
📄 읽을 파일: agents/a2a_client.py
📄 읽을 파일: agents/worker_agents/base/base_worker.py
```

**핵심 개념:**
- JSON-RPC 2.0 메시지 포맷
- 에이전트 간 비동기 통신
- 컨텍스트 공유 (context_id, session_id)

**메시지 구조:**
```json
{
  "jsonrpc": "2.0",
  "method": "search_law",
  "params": {
    "query": "개발행위 허가",
    "domain": "도시계획",
    "context_id": "ctx_123",
    "session_id": "sess_456"
  },
  "id": "req_789"
}
```

#### 7.2 Neo4j 벡터 검색 쿼리
```cypher
-- HANG 노드 벡터 검색 (768-dim)
CALL db.index.vector.queryNodes(
    'hang_embedding_index',
    5,
    $query_embedding_768
) YIELD node, score
WHERE score >= 0.70
RETURN node.full_id, node.content, score
ORDER BY score DESC

-- CONTAINS 관계 벡터 검색 (3072-dim)
CALL db.index.vector.queryRelationships(
    'contains_embedding',
    5,
    $query_embedding_3072
) YIELD relationship, score
MATCH (from)-[relationship]->(to)
WHERE score >= 0.70
RETURN from.full_id, to.full_id, relationship.context, score
ORDER BY score DESC
```

#### 7.3 도메인 클러스터링 알고리즘
```python
# K-means 클러스터링 (Silhouette Score 최적화)
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

best_k = 5
best_score = -1

for k in range(5, 16):  # 5~15개 클러스터
    kmeans = KMeans(n_clusters=k, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    score = silhouette_score(embeddings, labels)

    if score > best_score:
        best_score = score
        best_k = k

# 최적 k로 클러스터링
final_kmeans = KMeans(n_clusters=best_k, random_state=42)
domain_labels = final_kmeans.fit_predict(embeddings)
```

---

## 🔧 실행 가이드

### 1. 전체 파이프라인 실행 (처음부터)

```bash
# 0. 환경 설정
cp .env.example .env
# .env 파일 수정 (NEO4J_PASSWORD, OPENAI_API_KEY 등)

# 1. PDF → JSON
python law/scripts/pdf_to_json.py --pdf "law/data/raw/법률.pdf"

# 2. JSON → Neo4j
python law/scripts/json_to_neo4j.py --json "law/data/parsed/법률_법률.json"

# 3. HANG 노드 임베딩 추가
python add_hang_embeddings.py

# 4. Domain 노드 초기화 (⭐ 필수!)
python initialize_domains.py

# 5. CONTAINS 관계 임베딩 추가 (전체 파이프라인)
cd law/relationship_embedding
python step1_analyze_relationships.py
python step2_extract_contexts.py
python step3_generate_embeddings.py
python step4_update_neo4j.py
python step5_create_index_and_test.py
python step10_type_agnostic_search.py

# 5. AgentManager 초기화 (Django shell)
python manage.py shell
>>> from agents.law.agent_manager import AgentManager
>>> manager = AgentManager()
>>> # 자동으로 도메인 생성 및 DomainAgent 인스턴스화

# 6. 검색 테스트
>>> query = "개발행위 허가 요건은?"
>>> domain_agent = manager.domains['domain_1'].agent_instance
>>> result = await domain_agent._search_my_domain(query)
```

### 2. 기존 시스템에 새 PDF 추가

```bash
# AgentManager가 자동 처리
python manage.py shell
>>> from agents.law.agent_manager import AgentManager
>>> manager = AgentManager()
>>> result = manager.process_new_pdf("law/data/raw/새법률.pdf")
>>> # 자동: 파싱 → Neo4j → 임베딩 → 도메인 할당 → A2A 네트워크 업데이트
```

---

## 📊 데이터 통계

### Neo4j 데이터베이스 (국토계획법 기준)

| 항목 | 개수 |
|------|------|
| **PDF 파일** | 3개 (법률, 시행령, 시행규칙) |
| **총 노드** | 3,981개 (기존 3,976 + Domain 5) |
| **총 관계** | 8,500개 (기존 7,023 + BELONGS_TO_DOMAIN 1,477) |
| **LAW 노드** | 3개 |
| **JANG 노드** | 24개 |
| **JEOL 노드** | 22개 |
| **JO 노드** | 1,053개 (제목만) |
| **HANG 노드** | 1,477개 (실제 내용 + 임베딩) |
| **HO 노드** | 1,025개 |
| **MOK 노드** | 263개 |
| **Domain 노드** | 5개 ⭐ (Multi-Agent System) |
| **CONTAINS 관계** | 3,565개 (관계 임베딩) |
| **BELONGS_TO_DOMAIN 관계** | 1,477개 ⭐ (HANG → Domain) |

### 임베딩 통계

| 항목 | 모델 | 차원 | 개수 | 인덱스 |
|------|------|------|------|--------|
| **노드 임베딩** | KR-SBERT | 768 | 1,477개 | `hang_embedding_index` |
| **관계 임베딩** | OpenAI | 3,072 | 3,565개 | `contains_embedding` |
| **도메인 중심 벡터** | KR-SBERT | 768 | 5개 | (Domain.centroid_embedding) |

### 도메인 분포 (실제 데이터)

| 도메인 ID | HANG 노드 수 | 비율 |
|----------|-------------|------|
| domain_c283b545 | 510개 | 34.5% |
| domain_676e7400 | 389개 | 26.3% |
| domain_3be25bdc | 230개 | 15.6% |
| domain_fad24752 | 227개 | 15.4% |
| domain_09b3af0d | 121개 | 8.2% |
| **합계** | **1,477개** | **100%** |

**도메인 이름:** LLM이 자동 생성 (한글 깨짐으로 표시 불가, Neo4j에서 확인 가능)

---

## 🛠 기술 스택

| 레이어 | 기술 |
|--------|------|
| **언어** | Python 3.12 |
| **프레임워크** | Django 5.2.6 |
| **그래프 DB** | Neo4j 5.x |
| **벡터 검색** | Neo4j Vector Index (HNSW) |
| **노드 Embedding** | KR-SBERT (768-dim) |
| **관계 Embedding** | OpenAI text-embedding-3-large (3,072-dim) |
| **클러스터링** | scikit-learn (K-means, DBSCAN) |
| **그래프 탐색** | RNE, INE (Custom) |
| **LLM** | OpenAI GPT-4 |
| **A2A 프로토콜** | JSON-RPC 2.0 |

---

## 💡 핵심 인사이트

### 1. 이중 임베딩 전략
```
노드 임베딩 (768-dim KR-SBERT)
  ↓ 노드 의미 검색
관계 임베딩 (3072-dim OpenAI)
  ↓ 관계 의미 검색
통합 검색
  ↓ 노드 + 관계 결과 결합
최종 결과
```

**왜 이중 임베딩?**
- 노드: "개발행위 허가"라는 개념
- 관계: "JO → HANG" 계층 관계의 의미
- → 개념 + 구조 모두 활용

### 2. 자가 조직화 (Self-Organizing)
```
새 PDF 추가
  ↓
자동 파싱 & 임베딩
  ↓
도메인 유사도 계산 (cosine similarity)
  ↓
기존 도메인? (sim >= 0.70)
  ├─ Yes → 기존 도메인에 할당
  └─ No → 새 도메인 생성
  ↓
도메인 크기 체크
  ├─ > 500 노드 → 분할 (K-means)
  └─ < 50 노드 → 병합 (최근접 도메인)
  ↓
A2A 네트워크 업데이트
```

### 3. 하이브리드 검색
```
Stage 1: 벡터 검색 (의미적 유사도)
  ├─ 노드 벡터 (KR-SBERT)
  └─ 관계 벡터 (OpenAI)
  ↓
Stage 2: 그래프 탐색 (구조적 연관성)
  └─ RNE/INE 알고리즘
  ↓
Stage 3: 리랭킹 (통합 스코어링)
  └─ 유사도 + 그래프 거리 + 관계 타입
```

### 4. A2A 협업 메커니즘
```
DomainAgent A ("도시계획")
  ↓ 질의: "건축물 높이 제한"
  ↓ 자체 검색 → Quality Score 0.55 (낮음!)
  ↓
A2A 요청 → DomainAgent B ("건축 규제")
  ↓ 검색 결과 반환
  ↓
결과 통합 (A + B)
  ↓ 최종 응답
```

**Quality Score 계산:**
```python
def _evaluate_results(results):
    # 평균 유사도 + 결과 개수 + 다양성
    avg_sim = mean([r['similarity'] for r in results])
    diversity = len(set([r['law_name'] for r in results]))
    return (avg_sim * 0.7) + (min(diversity / 3, 1.0) * 0.3)
```

---

## 🐛 문제 해결

### Neo4j 연결 실패
```bash
# Neo4j Desktop에서 데이터베이스 시작 확인
# http://localhost:7474

# .env 파일 확인
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111
NEO4J_DATABASE=neo4j
```

### 벡터 인덱스 없음 오류
```python
# Neo4j shell
CREATE VECTOR INDEX hang_embedding_index IF NOT EXISTS
FOR (h:HANG) ON (h.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }
}

CREATE VECTOR INDEX contains_embedding IF NOT EXISTS
FOR ()-[r:CONTAINS]-() ON (r.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 3072,
    `vector.similarity_function`: 'cosine'
  }
}
```

### 임베딩 누락
```bash
# HANG 노드 임베딩 확인
python -c "
from graph_db.services.neo4j_service import Neo4jService
neo4j = Neo4jService()
neo4j.connect()
result = neo4j.execute_query('MATCH (h:HANG) WHERE h.embedding IS NULL RETURN count(h)')
print(f'임베딩 없는 HANG 노드: {result[0]['count(h)']}개')
"

# 임베딩 재생성
python add_hang_embeddings.py
```

---

## 📚 참고 문서

### 프로젝트 문서
- `law/README.md`: 전체 개요
- `law/neo4j_schema.md`: Neo4j 스키마 상세
- `law/docs/PIPELINE_GUIDE.md`: 파이프라인 가이드
- `law/docs/chunking_strategy.md`: 청킹 전략
- `law/EMBEDDING_GUIDE.md`: 임베딩 가이드
- `law/relationship_embedding/README.md`: 관계 임베딩 완전 가이드

### 학술적 배경
- **Knowledge Graph Embedding (KGE)**: 그래프 구조를 벡터 공간에 매핑
- **TransE/TransR 모델**: 관계를 벡터로 표현하는 고전적 방법
- **HNSW (Hierarchical Navigable Small World)**: 고속 벡터 유사도 검색 알고리즘
- **A2A 프로토콜**: Google/Linux Foundation Agent 표준

---

## 🎯 다음 단계

1. ✅ 데이터 파이프라인 완성
2. ✅ 노드 + 관계 임베딩 완성
3. ✅ Multi-Agent System 구축
4. ✅ A2A 네트워크 구성
5. ⏭ **실제 법률 질의 테스트 (End-to-End)**
6. ⏭ **Django REST API 엔드포인트 구현**
7. ⏭ **프론트엔드 통합 (React/Vue)**
8. ⏭ **성능 최적화 (캐싱, 배치 처리)**
9. ⏭ **프로덕션 배포 (Docker, K8s)**

---

**작성자**: Claude Code
**최종 업데이트**: 2025-11-13
**프로젝트**: 한국 법률 Multi-Agent RAG 시스템
