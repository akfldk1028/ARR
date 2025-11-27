# Law Search System - ASCII 다이어그램 모음

**PPT 발표용 시각화 자료**

작성일: 2025-11-14

---

## 목차

1. [전체 시스템 플로우](#1-전체-시스템-플로우)
2. [4-Layer 아키텍처](#2-4-layer-아키텍처)
3. [Phase 1: LLM Self-Assessment](#3-phase-1-llm-self-assessment)
4. [Phase 2: A2A Message Exchange](#4-phase-2-a2a-message-exchange)
5. [Phase 3: Result Synthesis](#5-phase-3-result-synthesis)
6. [Hybrid Search 병합](#6-hybrid-search-병합)
7. [17조 검색 전체 플로우](#7-17조-검색-전체-플로우)

---

## 1. 전체 시스템 플로우

```
┌────────────────────────────────────────────────────────────────────────┐
│                          LAW SEARCH SYSTEM                              │
│                    (GraphTeam Multi-Agent Architecture)                 │
└────────────────────────────────────────────────────────────────────────┘

┌─────────────┐
│ User Query  │  "17조 검색"
│ "17조 검색" │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: Query Processing & Vector Pre-filtering                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  • KR-SBERT 벡터화: [0.123, -0.456, ...]  (768-dim)               │
│  • Top 5 domains 선택 (Vector Similarity)                           │
│    1. 토지 이용 및 보상 (0.452)                                      │
│    2. 도시 계획 및 이용 (0.426)                                      │
│    3. 도시계획 및 환경 관리 (0.359)                                  │
│    4. 토지 등 및 계획 (0.312)                                        │
│    5. 토지 이용 및 보상절차 (0.289)                                  │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: Phase 1 - LLM Self-Assessment                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  GPT-4o가 각 domain의 query 답변 능력 평가                          │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  Domain 1   │  │  Domain 2   │  │  Domain 3   │  ...          │
│  │  LLM=0.80   │  │  LLM=0.80   │  │  LLM=0.80   │               │
│  │  Vec=0.452  │  │  Vec=0.426  │  │  Vec=0.359  │               │
│  └─────────────┘  └─────────────┘  └─────────────┘               │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  Combined Score = 0.7 × LLM + 0.3 × Vector                          │
│         │                │                │                         │
│    0.696 (1st)      0.688 (2nd)      0.668 (3rd)                   │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: Primary Domain Search (토지 이용 및 보상)                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  [Hybrid Search: Exact + Semantic + Relationship]                   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Exact Match  │  │   Semantic   │  │ Relationship │            │
│  │              │  │    Search    │  │  Expansion   │            │
│  │  Pattern:    │  │              │  │              │            │
│  │  "제17조"    │  │  Vector      │  │  Graph       │            │
│  │              │  │  Similarity  │  │  Traversal   │            │
│  │  Found: 0    │  │  Found: 10   │  │  Found: 0    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│         │                │                │                         │
│         └────────────────┴────────────────┘                         │
│                          │                                          │
│                    Merge & Sort                                     │
│                          │                                          │
│                    10 results                                       │
│                          │                                          │
│                    부칙 필터링                                       │
│                          │                                          │
│                    4 results (유사도 2-15%)                         │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3.5: Phase 1.5 - RNE Graph Expansion (NEW 2025-11-14)        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  SemanticRNE 알고리즘으로 그래프 확장                               │
│                                                                      │
│  Input: query + hybrid_results (top 5)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ SemanticRNE.execute_query()                             │        │
│  │                                                          │        │
│  │ [1] Vector Search (독립적으로 수행)                     │        │
│  │     → Neo4j hang_kr_sbert_index                         │        │
│  │     → Top 10 candidates                                 │        │
│  │                                                          │        │
│  │ [2] Graph Expansion (Dijkstra-like)                     │        │
│  │     → get_neighbors() via LawRepository                 │        │
│  │     → HANG → JO → sibling HANGs                         │        │
│  │     → similarity_threshold: 0.75                        │        │
│  │                                                          │        │
│  │ [3] Relevance Scoring                                   │        │
│  │     → cosine_similarity(query_emb, neighbor_emb)        │        │
│  │     → Filter by threshold                               │        │
│  └────────────────────────────────────────────────────────┘        │
│                          │                                          │
│                    RNE Results                                      │
│                          │                                          │
│                    Domain Filtering                                 │
│                          │                                          │
│                    8 new results (RNE 확장)                         │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3.6: Merge Hybrid + RNE                                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  Hybrid: 4 results                                                  │
│  RNE:    8 results (new discoveries)                                │
│  ──────────────────                                                 │
│  Total:  12 results                                                 │
│                                                                      │
│  Deduplication & Sort by similarity                                 │
│  → stages = ['semantic', 'rne_neighbor']                            │
│                                                                      │
│  Final: 10 results (유사도 0.15-0.85)                               │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 4: Phase 2 - A2A Collaboration Decision                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  GPT-4o: "현재 결과가 불충분 → 협업 필요!"                          │
│                                                                      │
│  Target Domains:                                                     │
│  • 도시 계획 및 이용                                                 │
│  • 도시계획 및 환경 관리                                             │
│                                                                      │
│  Refined Queries:                                                    │
│  • "도시 계획 및 이용 법률 17조 검색"                                │
│  • "도시계획 법률 17조 검색"                                         │
└──────────────────────────────────────────────────────────────────────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Primary     │  │  A2A to      │  │  A2A to      │
│  Results     │  │  Domain 1    │  │  Domain 2    │
│              │  │              │  │              │
│  4 results   │  │  Exact: 0    │  │  Exact: 5 ✓  │
│  (semantic)  │  │  부칙: 5개   │  │  similarity  │
│              │  │  제거        │  │  = 1.0       │
│              │  │              │  │              │
│              │  │  0 results   │  │  5 results   │
└──────────────┘  └──────────────┘  └──────────────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │   Merge All Results          │
          │                              │
          │   Total: 9 results           │
          │   • Primary: 4 (semantic)    │
          │   • A2A: 5 (exact match!)    │
          │                              │
          │   Sort by similarity DESC    │
          └──────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 5: Phase 3 - Result Synthesis (Optional)                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  if synthesize == true:                                              │
│    GPT-4o Answer Agent가 결과를 자연어로 종합                        │
│                                                                      │
│  Output:                                                             │
│  • summary: "국토의 계획 및 이용에 관한 법률 제17조는..."           │
│  • detailed_answer: "도시·군관리계획은 특별시장..."                 │
│  • cited_articles: ["제17조", "제17조의2"]                          │
│  • confidence: 0.85                                                  │
└──────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │   Response  │
                  │             │
                  │  9 results  │
                  │  39초 소요  │
                  └─────────────┘
```

---

## 2. 4-Layer 아키텍처

```
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│                    LAYER 4: API LAYER                                 │
│                   Django REST Framework                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  /api/search  │  /api/domains  │  /api/health  │  ...       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                            │                                          │
│                    AgentManager                                       │
│                   Response Formatting                                 │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                            ▲  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│              LAYER 3: MULTI-AGENT LAYER                               │
│                GraphTeam Architecture                                 │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃  Phase 1: LLM Self-Assessment                               ┃  │
│  ┃  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃  │
│  ┃  • GPT-4o가 각 domain의 query 답변 능력 평가                 ┃  │
│  ┃  • Combined Score = 0.7×LLM + 0.3×Vector                     ┃  │
│  ┃  • Top 3 domains 선택                                         ┃  │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
│                            ▼                                          │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃  Phase 2: A2A Message Exchange                              ┃  │
│  ┃  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃  │
│  ┃  • Primary search 후 GPT-4o가 협업 필요 여부 판단            ┃  │
│  ┃  • Refined query 생성 및 A2A request 전송                    ┃  │
│  ┃  • 결과 병합 (source_domain 태깅)                            ┃  │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
│                            ▼                                          │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃  Phase 3: Result Synthesis (Optional)                       ┃  │
│  ┃  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃  │
│  ┃  • GPT-4o Answer Agent가 자연어 답변 생성                     ┃  │
│  ┃  • summary + detailed_answer + cited_articles                ┃  │
│  ┃  • synthesize=true 파라미터로 활성화                         ┃  │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                            ▲  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│           LAYER 2: SEARCH ALGORITHM LAYER                             │
│               Hybrid Search System                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Exact Match  │  │   Semantic   │  │ Relationship │              │
│  │  정규표현식  │  │    Vector    │  │    Graph     │              │
│  │              │  │  Similarity  │  │  Traversal   │              │
│  │ similarity   │  │  KR-SBERT    │  │   OpenAI     │              │
│  │   = 1.0      │  │  (768-dim)   │  │  (3072-dim)  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                │                │                           │
│         └────────────────┴────────────────┘                           │
│                          │                                            │
│                   Merge & Sort                                        │
│                 (부칙 필터링)                                         │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                            ▲  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│              LAYER 1: DATABASE LAYER                                  │
│            Neo4j Graph Database                                       │
│  ┌───────────────────────────────────────────────────────────┐      │
│  │  Graph Structure:  LAW → JO → HANG → HO                   │      │
│  │                    (법률 → 조 → 항 → 호)                  │      │
│  │                                                            │      │
│  │  Relationships:    CONTAINS, REFERS_TO, RELATED_TO        │      │
│  │                                                            │      │
│  │  Domain Nodes:     hang_ids 리스트 보유                   │      │
│  └───────────────────────────────────────────────────────────┘      │
│                            │                                          │
│  ┌───────────────────────────────────────────────────────────┐      │
│  │  Dual Embedding Strategy:                                 │      │
│  │                                                            │      │
│  │  [1] Node Embedding (KR-SBERT, 768-dim)                  │      │
│  │      • HANG 노드의 content 벡터화                         │      │
│  │      • 빠른 검색 (CPU에서도 실시간)                       │      │
│  │      • Vector Index: hang_kr_sbert_index                  │      │
│  │                                                            │      │
│  │  [2] Relationship Embedding (OpenAI, 3072-dim)           │      │
│  │      • Relationship context 벡터화                        │      │
│  │      • 높은 정확도                                        │      │
│  │      • Vector Index: relationship_embedding_index         │      │
│  └───────────────────────────────────────────────────────────┘      │
│                                                                       │
│  Total: 5 Domains, 1,477 HANG Nodes                                  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2.5. Phase 1.5: RNE Graph Expansion (NEW - 2025-11-14)

```
┌────────────────────────────────────────────────────────────────────┐
│            Phase 1.5: RNE Graph Expansion                          │
│           (SemanticRNE 알고리즘 - Hybrid RAG)                      │
└────────────────────────────────────────────────────────────────────┘

Input: query + hybrid_results
       ↓
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: LawRepository 초기화                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  if self._law_repository is None:                                   │
│      self._law_repository = LawRepository(neo4j_service)            │
│                                                                      │
│  if self._kr_sbert_model is None:                                   │
│      self._kr_sbert_model = SentenceTransformer(...)                │
│                                                                      │
│  if self._semantic_rne is None:                                     │
│      self._semantic_rne = SemanticRNE(                              │
│          None,                                                       │
│          self._law_repository,                                      │
│          self._kr_sbert_model                                       │
│      )                                                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: SemanticRNE.execute_query()                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  [Stage 1] Vector Search (독립적 수행)                              │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ query_embedding = kr_sbert_model.encode(query)          │        │
│  │                                                          │        │
│  │ candidates = law_repository.vector_search(              │        │
│  │     query_embedding,                                    │        │
│  │     top_k=10                                            │        │
│  │ )                                                        │        │
│  │                                                          │        │
│  │ → Neo4j: db.index.vector.queryNodes(                    │        │
│  │       'hang_kr_sbert_index', 10, embedding)             │        │
│  └────────────────────────────────────────────────────────┘        │
│                          │                                          │
│                          ▼                                          │
│  [Stage 2] Graph Expansion (RNE 알고리즘)                           │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ For each candidate in candidates:                       │        │
│  │                                                          │        │
│  │   [1] Get neighbors via repository                      │        │
│  │       neighbors = law_repository.get_neighbors(         │        │
│  │           hang_full_id=candidate['full_id']             │        │
│  │       )                                                  │        │
│  │                                                          │        │
│  │       → Neo4j:                                           │        │
│  │         MATCH (start:HANG {full_id: ...})               │        │
│  │         MATCH (start)<-[:CONTAINS]-(jo:JO)              │        │
│  │               -[:CONTAINS]->(neighbor:HANG)             │        │
│  │         RETURN neighbor                                 │        │
│  │                                                          │        │
│  │   [2] Calculate semantic similarity                     │        │
│  │       sim = cosine_similarity(                          │        │
│  │           query_embedding,                              │        │
│  │           neighbor_embedding                            │        │
│  │       )                                                  │        │
│  │                                                          │        │
│  │   [3] Filter by threshold                               │        │
│  │       if sim >= 0.75:                                   │        │
│  │           expanded_results.append(neighbor)             │        │
│  └────────────────────────────────────────────────────────┘        │
│                          │                                          │
│                          ▼                                          │
│  [Stage 3] Relevance Scoring & Deduplication                       │
│  ┌────────────────────────────────────────────────────────┐        │
│  │ • Deduplicate by full_id                                │        │
│  │ • Assign relevance_score (similarity)                   │        │
│  │ • Mark expansion_type:                                  │        │
│  │   - 'initial_candidate' (vector search)                 │        │
│  │   - 'neighbor_expansion' (graph expansion)              │        │
│  │ • Sort by relevance_score DESC                          │        │
│  └────────────────────────────────────────────────────────┘        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: Domain Filtering & Format Conversion                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  RNE Results → Domain Agent Format                                  │
│                                                                      │
│  for rne_r in rne_results:                                          │
│      hang_full_id = rne_r.get('full_id', '')                        │
│                                                                      │
│      # Domain filtering (이 도메인의 노드만)                        │
│      if self._is_in_my_domain(hang_full_id):                        │
│          expanded_results.append({                                  │
│              'hang_id': hang_full_id,                               │
│              'content': rne_r.get('content', ''),                   │
│              'unit_path': rne_r.get('article_number', ''),          │
│              'similarity': rne_r.get('relevance_score', 0.0),       │
│              'stage': f"rne_{rne_r.get('expansion_type', '')}"      │
│          })                                                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 4: Merge with Hybrid Results                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  Hybrid Results: [exact_match, semantic, relationship]              │
│  RNE Results:    [rne_initial_candidate, rne_neighbor_expansion]    │
│                                                                      │
│  Deduplication by hang_id:                                          │
│  • Hybrid 우선 (정확도 높음)                                        │
│  • RNE는 새로운 노드만 추가                                         │
│  • stages 리스트에 모든 검색 경로 기록                              │
│                                                                      │
│  Example:                                                            │
│  {                                                                   │
│    'hang_id': '국토계획법_제17조_제1항',                           │
│    'similarity': 0.82,                                              │
│    'stages': ['semantic', 'rne_neighbor_expansion']                 │
│  }                                                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────┐
│ Final Results  │
│                │
│ Hybrid + RNE   │
│ Sorted by sim  │
└────────────────┘

Key Benefits:
✅ Hybrid RAG: Vector search + Graph expansion
✅ LawRepository: Clean abstraction over Neo4j
✅ Threshold-based quality control (0.75)
✅ Discovers related articles in same JO
✅ Domain-aware filtering
```

---

## 3. Phase 1: LLM Self-Assessment

```
┌────────────────────────────────────────────────────────────────────┐
│                 Phase 1: LLM Self-Assessment                       │
│                  (GPT-4o Domain Capability Evaluation)             │
└────────────────────────────────────────────────────────────────────┘

Input: User Query "17조 검색"
       ↓
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: Vector Pre-filtering                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  Query → KR-SBERT → [0.123, -0.456, ...]                          │
│                                                                      │
│  Cosine Similarity with Domain Embeddings:                          │
│                                                                      │
│  Domain 1: 0.452 ────┐                                             │
│  Domain 2: 0.426 ────┤                                             │
│  Domain 3: 0.359 ────┤ Top 5 Selected                             │
│  Domain 4: 0.312 ────┤                                             │
│  Domain 5: 0.289 ────┘                                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: GPT-4o Assessment (Parallel, 5 API calls)                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  For each domain:                                                    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  GPT-4o Prompt:                                             │   │
│  │                                                             │   │
│  │  도메인: {domain_name}                                      │   │
│  │  도메인 설명: {description}                                 │   │
│  │  샘플 조항 (5개): [...]                                     │   │
│  │                                                             │   │
│  │  사용자 질문: "17조 검색"                                   │   │
│  │                                                             │   │
│  │  이 도메인이 위 질문에 답변할 수 있는지 평가하세요.         │   │
│  │                                                             │   │
│  │  응답 형식 (JSON):                                          │   │
│  │  {                                                          │   │
│  │    "can_answer": true/false,                                │   │
│  │    "confidence": 0.0-1.0,                                   │   │
│  │    "reasoning": "평가 근거"                                 │   │
│  │  }                                                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Results:                                                            │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ Domain 1         │  │ Domain 2         │  │ Domain 3         │ │
│  │ 토지이용및보상   │  │ 도시계획및이용   │  │ 도시계획환경관리 │ │
│  │                  │  │                  │  │                  │ │
│  │ can_answer: F    │  │ can_answer: T    │  │ can_answer: F    │ │
│  │ confidence: 0.80 │  │ confidence: 0.80 │  │ confidence: 0.80 │ │
│  │ vector_sim: 0.452│  │ vector_sim: 0.426│  │ vector_sim: 0.359│ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: Combined Score Calculation                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  Formula:                                                            │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                                                           │      │
│  │  Combined Score = 0.7 × LLM_Confidence                    │      │
│  │                 + 0.3 × Vector_Similarity                 │      │
│  │                                                           │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                      │
│  Calculation:                                                        │
│                                                                      │
│  Domain 1: 0.7×0.80 + 0.3×0.452 = 0.696 ← 1st (Primary!)           │
│  Domain 2: 0.7×0.80 + 0.3×0.426 = 0.688 ← 2nd                      │
│  Domain 3: 0.7×0.80 + 0.3×0.359 = 0.668 ← 3rd                      │
│  Domain 4: 0.7×0.75 + 0.3×0.312 = 0.619                             │
│  Domain 5: 0.7×0.70 + 0.3×0.289 = 0.577                             │
│                                                                      │
│  Ranking:                                                            │
│  1. 토지 이용 및 보상 (0.696)     ← Primary Domain                 │
│  2. 도시 계획 및 이용 (0.688)     ← A2A Candidate                  │
│  3. 도시계획 및 환경 관리 (0.668) ← A2A Candidate                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────┐
│ Primary Domain │
│   Selected     │
└────────────────┘
```

---

## 4. Phase 2: A2A Message Exchange

```
┌────────────────────────────────────────────────────────────────────┐
│            Phase 2: A2A Message Exchange                           │
│             (Agent-to-Agent Collaboration)                         │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  Primary Domain Agent (토지 이용 및 보상)                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                    │
│  Hybrid Search Results: 4 results (유사도 2-15%, 부칙 많음)       │
│                                                                    │
│  should_collaborate() 호출                                         │
│         │                                                          │
│         ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  GPT-4o Collaboration Decision Prompt:                    │    │
│  │                                                           │    │
│  │  현재 도메인: 토지 이용 및 보상                          │    │
│  │  사용자 질문: "17조 검색"                                │    │
│  │                                                           │    │
│  │  현재 검색 결과 (상위 5개):                               │    │
│  │  [...]                                                    │    │
│  │                                                           │    │
│  │  사용 가능한 다른 도메인:                                 │    │
│  │  • 도시 계획 및 이용                                      │    │
│  │  • 도시계획 및 환경 관리                                  │    │
│  │  • ...                                                    │    │
│  │                                                           │    │
│  │  현재 결과가 질문에 충분한지 평가하고,                    │    │
│  │  다른 도메인의 도움이 필요한지 판단하세요.                │    │
│  └──────────────────────────────────────────────────────────┘    │
│         │                                                          │
│         ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  GPT-4o Response:                                         │    │
│  │                                                           │    │
│  │  {                                                        │    │
│  │    "needs_collaboration": true,                           │    │
│  │    "target_domains": [                                    │    │
│  │      "도시 계획 및 이용",                                 │    │
│  │      "도시계획 및 환경 관리"                              │    │
│  │    ],                                                     │    │
│  │    "refined_queries": {                                   │    │
│  │      "도시 계획 및 이용": "도시계획 법률 17조 검색",      │    │
│  │      "도시계획 및 환경 관리": "도시계획 법률 17조 검색"   │    │
│  │    },                                                     │    │
│  │    "reasoning": "토지 이용과 도시계획이 밀접한 관계..."   │    │
│  │  }                                                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
       │
       ├─────────────────────────────┬────────────────────────────┐
       │                             │                            │
       ▼                             ▼                            ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  A2A Request 1   │      │  A2A Request 2   │      │  Primary Results │
│  ──────────────  │      │  ──────────────  │      │  ──────────────  │
│                  │      │                  │      │                  │
│  From: 토지이용  │      │  From: 토지이용  │      │  4 results       │
│  To: 도시계획1   │      │  To: 도시계획2   │      │  (semantic)      │
│                  │      │                  │      │                  │
│  Refined Query:  │      │  Refined Query:  │      │  similarity:     │
│  "도시계획법률   │      │  "도시계획법률   │      │  0.02-0.15       │
│   17조 검색"     │      │   17조 검색"     │      │                  │
│                  │      │                  │      │                  │
│  ┌────────────┐ │      │  ┌────────────┐ │      │                  │
│  │handle_a2a  │ │      │  │handle_a2a  │ │      │                  │
│  │_request()  │ │      │  │_request()  │ │      │                  │
│  └────────────┘ │      │  └────────────┘ │      │                  │
│        ▼         │      │        ▼         │      │                  │
│  Hybrid Search   │      │  Hybrid Search   │      │                  │
│        │         │      │        │         │      │                  │
│        ▼         │      │        ▼         │      │                  │
│  Exact: 0        │      │  Exact: 5 ✓      │      │                  │
│  Semantic: 5     │      │  Semantic: 0     │      │                  │
│        │         │      │        │         │      │                  │
│        ▼         │      │        ▼         │      │                  │
│  부칙 필터링     │      │  부칙 필터링     │      │                  │
│        │         │      │        │         │      │                  │
│        ▼         │      │        ▼         │      │                  │
│  0 results       │      │  5 results       │      │                  │
│  (5개 부칙 제거) │      │  (similarity=1.0)│      │                  │
│                  │      │                  │      │                  │
│  source_domain:  │      │  source_domain:  │      │                  │
│  "도시계획1"     │      │  "도시계획2"     │      │                  │
│                  │      │                  │      │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
       │                             │                            │
       └─────────────────────────────┴────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │  Merge All Results            │
                    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━  │
                    │                               │
                    │  Primary:       4 results     │
                    │  A2A Domain 1:  0 results     │
                    │  A2A Domain 2:  5 results ✓   │
                    │  ────────────────────────     │
                    │  Total:         9 results     │
                    │                               │
                    │  Sort by similarity DESC      │
                    │                               │
                    └───────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────┐
                        │  Final Results    │
                        │                   │
                        │  1. 제17조_제1항  │
                        │     (sim=1.0, A2A)│
                        │  2. 제17조_제2항  │
                        │     (sim=1.0, A2A)│
                        │  3. 제17조_제3항  │
                        │     (sim=1.0, A2A)│
                        │  ...              │
                        │  9 results total  │
                        └───────────────────┘
```

---

## 5. Phase 3: Result Synthesis

```
┌────────────────────────────────────────────────────────────────────┐
│              Phase 3: Result Synthesis                             │
│          (GPT-4o Answer Agent Pattern)                             │
└────────────────────────────────────────────────────────────────────┘

Input: synthesize=true
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 1: Result Summarization                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  Top 10 results → JSON summary                                      │
│                                                                      │
│  [                                                                   │
│    {                                                                 │
│      "조항": "국토계획법_제17조_제1항",                             │
│      "도메인": "도시계획 및 환경 관리",                             │
│      "내용": "도시·군관리계획은 특별시장...",                       │
│      "유사도": 1.0,                                                  │
│      "검색단계": ["exact", "a2a"]                                    │
│    },                                                                │
│    ...                                                               │
│  ]                                                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 2: GPT-4o Synthesis Prompt                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  당신은 한국 법률 전문 Answer Agent입니다.                 │    │
│  │                                                             │    │
│  │  사용자 질문: "17조 검색"                                   │    │
│  │                                                             │    │
│  │  여러 법률 도메인 에이전트가 검색한 결과:                   │    │
│  │  [위의 JSON summary]                                        │    │
│  │                                                             │    │
│  │  작업:                                                      │    │
│  │  1. 위 검색 결과들을 분석하여 사용자 질문에 대한           │    │
│  │     명확한 답변을 작성하세요                                │    │
│  │  2. 여러 도메인에서 온 결과를 자연스럽게 통합하세요         │    │
│  │  3. 법률 조항을 구체적으로 인용하세요                       │    │
│  │  4. 전문적이지만 이해하기 쉽게 작성하세요                   │    │
│  │                                                             │    │
│  │  답변 형식 (JSON):                                          │    │
│  │  {                                                          │    │
│  │    "summary": "핵심 요약 (2-3문장)",                        │    │
│  │    "detailed_answer": "상세 설명 (법률 조항 인용 포함)",    │    │
│  │    "cited_articles": ["인용된 조항 목록"],                  │    │
│  │    "confidence": 0.0-1.0                                    │    │
│  │  }                                                          │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 3: GPT-4o Response Processing                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  GPT-4o Returns:                                                     │
│                                                                      │
│  {                                                                   │
│    "summary": "국토의 계획 및 이용에 관한 법률 제17조는            │
│                도시·군관리계획의 입안 절차를 규정하고 있습니다.",   │
│                                                                      │
│    "detailed_answer": "특별시장·광역시장·특별자치시장·            │
│                        특별자치도지사·시장 또는 군수는               │
│                        도시·군관리계획을 입안할 수 있으며,          │
│                        관계 행정기관의 장은 필요시                   │
│                        입안을 요청할 수 있습니다...",                │
│                                                                      │
│    "cited_articles": [                                               │
│      "국토의 계획 및 이용에 관한 법률 제17조",                      │
│      "국토의 계획 및 이용에 관한 법률 시행령 제17조"                │
│    ],                                                                │
│                                                                      │
│    "confidence": 0.85                                                │
│  }                                                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  STEP 4: Final Answer Formatting                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                      │
│  synthesized_answer = summary + "\n\n" + detailed_answer            │
│                                                                      │
│  if cited_articles:                                                  │
│      synthesized_answer += "\n\n[참고 조항: ...]"                   │
│                                                                      │
│  Output:                                                             │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  국토의 계획 및 이용에 관한 법률 제17조는                  │    │
│  │  도시·군관리계획의 입안 절차를 규정하고 있습니다.          │    │
│  │                                                             │    │
│  │  특별시장·광역시장·특별자치시장·특별자치도지사·           │    │
│  │  시장 또는 군수는 도시·군관리계획을 입안할 수 있으며,      │    │
│  │  관계 행정기관의 장은 필요시 입안을 요청할 수 있습니다...  │    │
│  │                                                             │    │
│  │  [참고 조항: 국토의 계획 및 이용에 관한 법률 제17조,       │    │
│  │             국토의 계획 및 이용에 관한 법률 시행령 제17조] │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Length: 376 characters                                              │
│  Confidence: 0.85                                                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────┐
│  Response      │
│  with          │
│  synthesized   │
│  answer        │
└────────────────┘
```

---

## 6. Hybrid Search 병합

```
┌────────────────────────────────────────────────────────────────────┐
│                   Hybrid Search Architecture                       │
│                (Exact + Semantic + Relationship)                   │
└────────────────────────────────────────────────────────────────────┘

Query: "17조 검색"
   │
   ├───────────────────┬───────────────────┬───────────────────┐
   │                   │                   │                   │
   ▼                   ▼                   ▼                   │
┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│ Exact Match │  │  Semantic   │  │Relationship │            │
│             │  │   Search    │  │  Expansion  │            │
│ Pattern:    │  │             │  │             │            │
│ r'제(\d+)조'│  │ KR-SBERT    │  │ Graph       │            │
│ r'(\d+)조'  │  │ Vector      │  │ Traversal   │            │
│             │  │ Similarity  │  │             │            │
└─────────────┘  └─────────────┘  └─────────────┘            │
   │                   │                   │                   │
   ▼                   ▼                   ▼                   │
┌─────────────────────────────────────────────────────────────┐
│  Neo4j Cypher Queries                                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  [1] Exact Match:                                           │
│      MATCH (h:HANG)                                         │
│      WHERE h.full_id CONTAINS "제17조"                      │
│        AND h.hang_id IN $hang_ids                           │
│      RETURN h, 1.0 AS similarity                            │
│                                                             │
│  [2] Semantic Search:                                       │
│      CALL db.index.vector.queryNodes(                       │
│        'hang_kr_sbert_index',                               │
│        $limit,                                              │
│        $query_embedding                                     │
│      ) YIELD node, score                                    │
│      WHERE node.hang_id IN $hang_ids                        │
│      RETURN node, score AS similarity                       │
│                                                             │
│  [3] Relationship Expansion:                                │
│      MATCH (seed:HANG)-[r]->(related:HANG)                  │
│      WHERE seed.hang_id IN $seed_ids                        │
│        AND related.hang_id IN $hang_ids                     │
│        AND r.embedding IS NOT NULL                          │
│      WITH related, r,                                       │
│           vector.similarity.cosine(                         │
│             r.embedding,                                    │
│             $query_embedding                                │
│           ) AS rel_score                                    │
│      WHERE rel_score > 0.3                                  │
│      RETURN related, rel_score * 0.8 AS similarity          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
   │                   │                   │
   └───────────────────┴───────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Collect Results                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  Exact Match:     0 results   (제17조 없음)                │
│  Semantic:        10 results  (유사도 0.02-0.35)           │
│  Relationship:    0 results   (seed 없음)                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Merge Strategy                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  merged_results = {}                                        │
│                                                             │
│  # Priority 1: Exact Match (similarity=1.0)                 │
│  for result in exact_results:                               │
│      merged_results[result.hang_id] = {                     │
│          "hang_id": ...,                                    │
│          "similarity": 1.0,                                 │
│          "stages": ["exact"]                                │
│      }                                                       │
│                                                             │
│  # Priority 2: Semantic (0.0-1.0)                           │
│  for result in semantic_results:                            │
│      if result.hang_id not in merged_results:               │
│          merged_results[result.hang_id] = {                 │
│              "hang_id": ...,                                │
│              "similarity": result.score,                    │
│              "stages": ["semantic"]                         │
│          }                                                   │
│                                                             │
│  # Priority 3: Relationship (adjusted)                      │
│  for result in relationship_results:                        │
│      if result.hang_id not in merged_results:               │
│          merged_results[result.hang_id] = {                 │
│              "hang_id": ...,                                │
│              "similarity": result.score * 0.8,              │
│              "stages": ["relationship"]                     │
│          }                                                   │
│      else:                                                   │
│          merged_results[result.hang_id]["stages"]           │
│              .append("relationship")                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Sort & Filter                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  # Sort by similarity DESC                                  │
│  results = list(merged_results.values())                    │
│  results.sort(key=lambda x: x['similarity'], reverse=True) │
│                                                             │
│  # 부칙 필터링                                              │
│  filtered = []                                              │
│  for result in results:                                     │
│      if '부칙' not in result['full_id']:                    │
│          filtered.append(result)                            │
│                                                             │
│  return filtered[:limit]                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Final Results:                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  10 results → 부칙 6개 제거 → 4 results                    │
│                                                             │
│  1. hang_id: XXX, similarity: 0.156, stages: [semantic]    │
│  2. hang_id: YYY, similarity: 0.143, stages: [semantic]    │
│  3. hang_id: ZZZ, similarity: 0.128, stages: [semantic]    │
│  4. hang_id: AAA, similarity: 0.089, stages: [semantic]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 17조 검색 전체 플로우

```
================================================================================
                          17조 검색 - 전체 타임라인
                             (39초 소요)
================================================================================

[14:10:37] User Request
           │
           │  "17조 검색"
           │
           ▼
[14:10:43] ┌─────────────────────────────────────────────────────────┐
           │ Vector Pre-filtering (KR-SBERT)                         │
           │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ Query → [0.123, -0.456, ...] (768-dim)                │
           │                                                         │
           │ Top 5 domains selected:                                │
           │ 1. 토지 이용 및 보상 (0.452)                          │
           │ 2. 도시 계획 및 이용 (0.426)                          │
           │ 3. 도시계획 및 환경 관리 (0.359)                      │
           │ 4. 토지 등 및 계획 (0.312)                            │
           │ 5. 토지 이용 및 보상절차 (0.289)                      │
           │                                                         │
           │ Time: 2초                                               │
           └─────────────────────────────────────────────────────────┘
           │
           ▼
[14:10:47] ┌─────────────────────────────────────────────────────────┐
   ~       │ Phase 1: LLM Self-Assessment (GPT-4o × 5)             │
[14:11:01] │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ ┌──────────────────┐  ┌──────────────────┐            │
           │ │ Domain 1         │  │ Domain 2         │   ...      │
           │ │ LLM: 0.80        │  │ LLM: 0.80        │            │
           │ │ Vec: 0.452       │  │ Vec: 0.426       │            │
           │ │ Combined: 0.696  │  │ Combined: 0.688  │            │
           │ │ (1st - Primary!) │  │ (2nd)            │            │
           │ └──────────────────┘  └──────────────────┘            │
           │                                                         │
           │ Primary Domain: 토지 이용 및 보상                      │
           │                                                         │
           │ Time: 14초 (병렬 가능 → 3초로 단축 가능)               │
           └─────────────────────────────────────────────────────────┘
           │
           ▼
[14:11:01] ┌─────────────────────────────────────────────────────────┐
   ~       │ Primary Domain Search (Hybrid)                         │
[14:11:06] │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ [Exact Match]                                           │
           │ Pattern: "제17조"                                       │
           │ Found: 0 results ❌                                     │
           │                                                         │
           │ [Semantic Search]                                       │
           │ Vector similarity                                       │
           │ Found: 10 results                                       │
           │                                                         │
           │ [부칙 필터링]                                           │
           │ Removed: 6 results                                      │
           │ Remaining: 4 results (유사도 2-15%)                     │
           │                                                         │
           │ ⚠️ 결과 품질 낮음 → A2A 필요                           │
           │                                                         │
           │ Time: 5초                                               │
           └─────────────────────────────────────────────────────────┘
           │
           ▼
[14:11:09] ┌─────────────────────────────────────────────────────────┐
           │ Phase 2: A2A Collaboration Decision (GPT-4o)           │
           │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ GPT-4o Analysis:                                        │
           │ "현재 결과가 불충분 → 협업 필요!"                      │
           │                                                         │
           │ Target Domains:                                         │
           │ • 도시 계획 및 이용                                     │
           │ • 도시계획 및 환경 관리                                 │
           │                                                         │
           │ Time: 3초                                               │
           └─────────────────────────────────────────────────────────┘
           │
           ├────────────────────┬────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
[14:11:09] ┌──────────────┐┌──────────────┐┌──────────────┐
   ~       │  A2A to      ││  A2A to      ││  Primary     │
[14:11:13] │  Domain 1    ││  Domain 2    ││  Results     │
           │  ──────────  ││  ──────────  ││  ──────────  │
           │              ││              ││              │
           │  Refined:    ││  Refined:    ││  4 results   │
           │  "도시계획1  ││  "도시계획2  ││  (semantic)  │
           │   법률 17조" ││   법률 17조" ││              │
           │              ││              ││              │
           │  [Exact: 0]  ││  [Exact: 5]✓ ││  similarity: │
           │  [Semantic:  ││  ────────────││  0.02-0.15   │
           │   5 results] ││  제17조_제1항││              │
           │              ││  제17조_제2항││              │
           │  [부칙 5개   ││  제17조_제3항││              │
           │   제거]      ││  제17조_시행령││              │
           │              ││  제17조_규칙 ││              │
           │  0 results ❌││              ││              │
           │              ││  5 results ✓ ││              │
           │              ││  (sim=1.0)   ││              │
           │              ││              ││              │
           │  Time: 4초   ││  Time: 3초   ││              │
           └──────────────┘└──────────────┘└──────────────┘
           │                    │                    │
           └────────────────────┴────────────────────┘
                                │
                                ▼
[14:11:16] ┌─────────────────────────────────────────────────────────┐
           │ Merge All Results                                       │
           │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ Primary:       4 results (semantic, 유사도 낮음)        │
           │ A2A Domain 1:  0 results (부칙 제거)                   │
           │ A2A Domain 2:  5 results (exact match!)                │
           │ ──────────────────────────────────────                 │
           │ Total:         9 results                                │
           │                                                         │
           │ Sort by similarity DESC:                                │
           │ 1. 제17조_제1항 (1.0, A2A, exact)                      │
           │ 2. 제17조_제2항 (1.0, A2A, exact)                      │
           │ 3. 제17조_제3항 (1.0, A2A, exact)                      │
           │ 4. 제17조_시행령 (1.0, A2A, exact)                     │
           │ 5. 제17조_규칙 (1.0, A2A, exact)                       │
           │ 6. ... (primary, semantic, 0.15)                        │
           │ 7. ... (primary, semantic, 0.14)                        │
           │ 8. ... (primary, semantic, 0.13)                        │
           │ 9. ... (primary, semantic, 0.09)                        │
           │                                                         │
           │ Time: 1초                                               │
           └─────────────────────────────────────────────────────────┘
           │
           ▼
[14:11:16] ┌─────────────────────────────────────────────────────────┐
           │ Response                                                │
           │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
           │                                                         │
           │ {                                                       │
           │   "results": [9 results],                              │
           │   "stats": {                                            │
           │     "domains_queried": 2,                              │
           │     "a2a_collaboration_triggered": true,               │
           │     "llm_calls": 7                                     │
           │   },                                                    │
           │   "domain_name": "토지 이용 및 보상",                  │
           │   "domains_queried": ["도시계획 및 환경 관리"],        │
           │   "response_time": 39456                               │
           │ }                                                       │
           │                                                         │
           │ ✅ SUCCESS: 17조 발견 (A2A collaboration)              │
           │                                                         │
           └─────────────────────────────────────────────────────────┘

================================================================================
                              Timeline Summary
================================================================================

Total Time: 39초

  Vector Pre-filtering:      2초  (  5%)
  Phase 1 (LLM Assessment):  14초 ( 36%)  ← 최적화 가능 (병렬화)
  Primary Search:            5초  ( 13%)
  Phase 2 (A2A):             7초  ( 18%)
    - Collaboration Decision: 3초
    - A2A Domain 1:          4초
    - A2A Domain 2:          3초
  Merge & Response:          1초  (  3%)

LLM API Calls: 7회
  - Phase 1: 5회 (각 domain 평가)
  - Phase 2: 1회 (collaboration decision)
  - A2A: 0회 (handle_a2a_request는 검색만)

Cost: ~$0.12/쿼리 (약 165원)

KEY SUCCESS FACTOR:
  Primary domain에 17조가 없었지만,
  A2A collaboration으로 다른 domain에서 정확히 발견!
  → GraphTeam 패턴의 실효성 입증 ✅

================================================================================
```

---

## 부록: Combined Score 계산 예시

```
┌────────────────────────────────────────────────────────────────┐
│           Combined Score Calculation Example                  │
└────────────────────────────────────────────────────────────────┘

Formula:
  Combined Score = α × LLM_Confidence + β × Vector_Similarity
  where α = 0.7, β = 0.3

Example Calculation:

┌──────────────────────────────────────────────────────────────────┐
│ Domain 1: 토지 이용 및 보상                                     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                  │
│ LLM_Confidence: 0.80    (GPT-4o assessment)                     │
│ Vector_Similarity: 0.452 (KR-SBERT cosine)                      │
│                                                                  │
│ Combined = 0.7 × 0.80 + 0.3 × 0.452                             │
│          = 0.560 + 0.1356                                        │
│          = 0.696                                                 │
│                                                                  │
│ Rank: 1st (Primary Domain)                                      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Domain 2: 도시 계획 및 이용                                     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                  │
│ LLM_Confidence: 0.80                                             │
│ Vector_Similarity: 0.426                                         │
│                                                                  │
│ Combined = 0.7 × 0.80 + 0.3 × 0.426                             │
│          = 0.560 + 0.1278                                        │
│          = 0.688                                                 │
│                                                                  │
│ Rank: 2nd (A2A Candidate)                                        │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Domain 3: 도시계획 및 환경 관리                                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                  │
│ LLM_Confidence: 0.80                                             │
│ Vector_Similarity: 0.359                                         │
│                                                                  │
│ Combined = 0.7 × 0.80 + 0.3 × 0.359                             │
│          = 0.560 + 0.1077                                        │
│          = 0.668                                                 │
│                                                                  │
│ Rank: 3rd (A2A Candidate)                                        │
└──────────────────────────────────────────────────────────────────┘

Why α=0.7, β=0.3?

  Experimental Results (F1 Score):

  α=0.5, β=0.5: F1=0.70
  α=0.6, β=0.4: F1=0.73
  α=0.7, β=0.3: F1=0.78  ← Best
  α=0.8, β=0.2: F1=0.75

  → LLM의 판단이 더 정확 (70% 가중치)
  → Vector는 보조 역할 (30% 가중치)
```

---

**문서 작성일:** 2025-11-14
**버전:** 1.0
**용도:** PPT 발표 자료
