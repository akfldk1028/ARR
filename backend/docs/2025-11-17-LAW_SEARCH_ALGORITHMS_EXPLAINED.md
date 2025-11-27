# 법률 검색 시스템 알고리즘 완전 가이드 (PPT 제작용)

**작성일**: 2025-11-17
**목적**: PPT 발표 자료 준비를 위한 명확하고 구조화된 알고리즘 설명
**시스템**: Multi-Agent Law Search System with GraphTeam/GraphAgent-Reasoner Architecture

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [전체 검색 플로우](#2-전체-검색-플로우)
3. [Phase 0: Domain Routing](#3-phase-0-domain-routing)
4. [Phase 1: Hybrid Search](#4-phase-1-hybrid-search)
5. [Phase 1.5: RNE Graph Expansion](#5-phase-15-rne-graph-expansion)
6. [Phase 2: A2A Collaboration](#6-phase-2-a2a-collaboration)
7. [Phase 3: Result Synthesis](#7-phase-3-result-synthesis)
8. [실제 예시: "21조" 검색 전체 추적](#8-실제-예시-21조-검색-전체-추적)
9. [알고리즘 비교표](#9-알고리즘-비교표)
10. [코드 위치 참조](#10-코드-위치-참조)
11. [PPT 슬라이드 구성 제안](#11-ppt-슬라이드-구성-제안)

---

## 1. 시스템 개요

### 1.1 핵심 특징

**Multi-Agent Law Search System**은 GraphTeam/GraphAgent-Reasoner 논문을 기반으로 구현된 한국 법률 전문 검색 시스템입니다.

```
┌─────────────────────────────────────────────────┐
│     Multi-Agent Law Search System               │
│                                                  │
│  5개 도메인 에이전트 협업                         │
│  - 도시 계획 및 이용                             │
│  - 토지 이용 및 관리                             │
│  - 토지 이용 및 보상절차                         │
│  - 건축 및 시설 규제                             │
│  - 환경 및 재해 관리                             │
│                                                  │
│  검색 기술: Hybrid + RNE + A2A                  │
│  데이터: Neo4j Graph DB (1,477 HANG 노드)       │
└─────────────────────────────────────────────────┘
```

### 1.2 기술 스택

| 컴포넌트 | 기술 |
|---------|------|
| **Graph DB** | Neo4j (localhost:7474) |
| **임베딩 (노드)** | KR-SBERT (768-dim) |
| **임베딩 (관계)** | OpenAI text-embedding-3-large (3072-dim) |
| **LLM 추론** | GPT-4o (Self-Assessment, A2A, Synthesis) |
| **Backend** | Django REST Framework |
| **Agent 프레임워크** | LangGraph (GraphTeam 패턴) |

### 1.3 데이터 구조

```
Neo4j Graph Structure:

(LAW:법률) -[:HAS_JO]-> (JO:조) -[:HAS_HANG]-> (HANG:항) -[:HAS_HO]-> (HO:호)
    │                                    │
    └─[:IMPLEMENTS]→ (시행령/시행규칙)   └─[:BELONGS_TO_DOMAIN]→ (Domain)
                                         └─[:CONTAINS {embedding}]→ (관계 임베딩)

통계:
- 전체 HANG 노드: 1,477개
- 도메인: 5개
- 노드 임베딩: KR-SBERT (768-dim)
- 관계 임베딩: OpenAI (3072-dim)
- 벡터 인덱스: 2개 (hang_embedding_index, contains_embedding)
```

---

## 2. 전체 검색 플로우

### 2.1 High-Level Overview

```
[사용자 쿼리]
    ↓
┌─────────────────────────────────────────┐
│ Phase 0: Domain Routing                 │
│ - Vector Similarity (30%)               │
│ - LLM Assessment (70%)                  │
│ → Primary Domain 선택                   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Phase 1: Primary Domain Search          │
│                                          │
│  [Hybrid Search]                         │
│  ├─ Exact Match (정규식)                │
│  ├─ Vector Search (KR-SBERT 768-dim)    │
│  ├─ Relationship Search (OpenAI 3072-dim)│
│  └─ RRF 병합                            │
│                                          │
│  [RNE Graph Expansion]                   │
│  ├─ Stage 1: Vector Search (초기 10개)  │
│  ├─ Stage 2: Graph Expand (이웃 탐색)   │
│  └─ Stage 3: Merge & Deduplicate        │
│                                          │
│  [부칙 필터링]                           │
│  └─ 제4절 부칙 제거                     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Phase 2: A2A Collaboration (선택적)      │
│                                          │
│  [GPT-4o Collaboration Decision]         │
│  ├─ Primary 결과 품질 평가              │
│  ├─ 협업 필요성 판단                    │
│  └─ Target 도메인 선택 (최대 2개)       │
│                                          │
│  [A2A Message Exchange]                  │
│  ├─ Refined Query 생성                  │
│  ├─ Target 도메인 에이전트에 요청       │
│  └─ A2A 결과 수신 및 병합               │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Phase 3: Result Synthesis (선택적)       │
│                                          │
│  [GPT-4o Natural Language Synthesis]     │
│  ├─ 모든 결과 종합 분석                 │
│  ├─ 자연어 답변 생성                    │
│  └─ 참고 조항 인용                      │
└─────────────────────────────────────────┘
    ↓
[최종 결과 반환]
- results: 조항 리스트
- stats: 검색 통계
- synthesized_answer: 자연어 답변 (선택적)
```

### 2.2 처리 시간

| Phase | 평균 시간 | 주요 작업 |
|-------|---------|----------|
| Phase 0 | 3-5초 | 5개 도메인 GPT-4o 평가 (병렬) |
| Phase 1 | 8-12초 | Hybrid Search + RNE 확장 |
| Phase 2 | 20-30초 | A2A 협업 (2개 도메인) |
| Phase 3 | 5-8초 | GPT-4o 결과 종합 |
| **총** | **40-55초** | 전체 파이프라인 |

---

## 3. Phase 0: Domain Routing

### 3.1 목적

5개 도메인 중 사용자 쿼리에 가장 적합한 Primary Domain을 자동으로 선택합니다.

### 3.2 알고리즘

**Hybrid Domain Routing = Vector Similarity (30%) + LLM Self-Assessment (70%)**

```python
# 파일: agents/law/api/search.py (line 250-389)

def auto_route_to_top_domains(query, agent_manager, top_n=3):
    """
    [1] Vector Similarity Pre-filtering (Fast)
        - 쿼리를 KR-SBERT로 임베딩 (768-dim)
        - 각 도메인의 centroid와 코사인 유사도 계산
        - Top 5 후보 선택

    [2] LLM Self-Assessment (Accurate)
        - 각 도메인 에이전트가 GPT-4o로 자기 평가
        - Confidence score (0-1) 반환
        - 판단 근거 (reasoning) 생성

    [3] Combined Score 계산
        - Combined = (LLM * 0.7) + (Vector * 0.3)
        - Top N 도메인 반환
    """
```

### 3.3 LLM Self-Assessment 프롬프트

```python
# 파일: agents/law/domain_agent.py (line 891-974)

prompt = f"""You are a specialized legal domain agent for "{domain_name}".

Your domain information:
- Domain name: {domain_name}
- Total articles: {len(node_ids)}
- Sample article IDs: [대표 조항들]

User query: "{query}"

Task: Assess if you can answer this query with high confidence.

Consider:
1. Does the query relate to topics in your domain?
2. Do you have relevant legal articles for this query?
3. Can you extract specific article numbers from the query?

Respond in JSON format:
{
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation in Korean",
  "can_answer": true/false,
  "relevant_articles": ["article numbers if identifiable"]
}
"""
```

### 3.4 실제 예시: "21조" 쿼리

```
Domain Routing 결과 (Top 3):

1. 토지 이용 및 관리
   - Vector Similarity: 0.465
   - LLM Confidence: 0.800
   - Combined Score: 0.699 ← PRIMARY

2. 도시 계획 및 이용
   - Vector Similarity: 0.317
   - LLM Confidence: 0.800
   - Combined Score: 0.655

3. 토지 이용 및 보상절차
   - Vector Similarity: 0.307
   - LLM Confidence: 0.800
   - Combined Score: 0.652
```

### 3.5 시각화 (PPT용)

```
┌────────────────────────────────────────────────┐
│  Phase 0: Domain Routing                       │
├────────────────────────────────────────────────┤
│                                                 │
│  Input: "21조"                                 │
│                                                 │
│  Step 1: Vector Similarity                     │
│  ┌──────────────────────────────────┐          │
│  │ Query → KR-SBERT (768-dim)       │          │
│  │ ↓                                │          │
│  │ Cosine Similarity vs Centroids   │          │
│  │ ↓                                │          │
│  │ Top 5 Candidates                 │          │
│  └──────────────────────────────────┘          │
│                                                 │
│  Step 2: GPT-4o Self-Assessment (병렬)         │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐       │
│  │도메인1│  │도메인2│  │도메인3│  │도메인4│       │
│  │0.800 │  │0.800 │  │0.800 │  │0.750 │       │
│  └──────┘  └──────┘  └──────┘  └──────┘       │
│                                                 │
│  Step 3: Combined Score                        │
│  Score = (LLM × 0.7) + (Vector × 0.3)          │
│  ↓                                              │
│  Primary: "토지 이용 및 관리" (0.699)           │
└────────────────────────────────────────────────┘
```

---

## 4. Phase 1: Hybrid Search

### 4.1 목적

Primary Domain 내에서 쿼리와 가장 관련 있는 법률 조항을 찾습니다.

### 4.2 Hybrid Search = 3가지 검색 방법 병합

```
┌─────────────────────────────────────────────┐
│  Hybrid Search (3-in-1)                     │
├─────────────────────────────────────────────┤
│                                              │
│  [1] Exact Match (Sparse Retrieval)         │
│      - 정규식: 제?(\d+)조                   │
│      - "21조" → "제21조" 패턴 매칭          │
│      - Neo4j WHERE full_id CONTAINS         │
│                                              │
│  [2] Semantic Vector Search (Dense)         │
│      - KR-SBERT 768-dim embedding           │
│      - Neo4j Vector Index 검색              │
│      - Top-10 유사 조항                     │
│                                              │
│  [3] Relationship Search                    │
│      - OpenAI 3072-dim embedding            │
│      - CONTAINS 관계 임베딩 검색            │
│      - 관계 기반 연관 조항                  │
│                                              │
│  [4] RRF (Reciprocal Rank Fusion) 병합      │
│      - RRF Score = Σ 1/(k + rank)           │
│      - k = 60 (standard)                    │
│      - 중복 제거 및 통합                    │
└─────────────────────────────────────────────┘
```

### 4.3 세부 알고리즘

#### 4.3.1 Exact Match Search

**코드**: `domain_agent.py` (line 166-219)

```python
def _exact_match_search(query, limit=10):
    """
    정규식으로 조항 번호 추출 후 Neo4j 패턴 매칭

    쿼리: "21조" 또는 "제21조에 대해 알려주세요"

    [1] 정규식 추출
        - 패턴: r'제?(\d+)조'
        - 결과: "21"

    [2] 검색 패턴 생성
        - search_pattern = f'제{article_num}조'
        - 예: "제21조"

    [3] Neo4j 쿼리
        MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
        WHERE h.full_id CONTAINS $search_pattern
          AND NOT h.full_id CONTAINS '제4절'  -- 부칙 제외
        RETURN h.full_id, h.content, 1.0 as similarity
    """
```

**특징**:
- 정확도 100% (조항 번호가 있는 경우)
- "제17조", "17조", "17조의2" 등 변형 인식
- 부칙(제4절) 자동 필터링

#### 4.3.2 Semantic Vector Search

**코드**: `domain_agent.py` (line 317-360)

```python
def _vector_search(query_embedding, limit=5):
    """
    KR-SBERT 임베딩 기반 의미 유사도 검색

    [1] 쿼리 임베딩
        - Model: snunlp/KR-SBERT-V40K-klueNLI-augSTS
        - Dimension: 768
        - 예: "21조" → [0.023, -0.145, 0.332, ...]

    [2] Neo4j Vector Index 검색
        CALL db.index.vector.queryNodes(
            'hang_embedding_index',
            $limit_multiplier,
            $query_embedding
        )
        YIELD node, score
        WHERE score >= 0.5  -- 최소 유사도

    [3] 도메인 필터링
        - BELONGS_TO_DOMAIN 관계로 필터
        - Primary domain만 반환
    """
```

**특징**:
- 의미 기반 검색 ("도시계획 수립" ≈ "도시관리계획 입안")
- 한국어 특화 모델 (KR-SBERT)
- 최소 유사도 0.5 (threshold)

#### 4.3.3 Relationship Search

**코드**: `domain_agent.py` (line 362-408)

```python
def _search_relationships(query_embedding, limit=5):
    """
    CONTAINS 관계 임베딩 기반 검색

    [1] 쿼리 임베딩
        - Model: OpenAI text-embedding-3-large
        - Dimension: 3072
        - Context: "Source [관계] Target"

    [2] Neo4j Relationship Vector Index
        CALL db.index.vector.queryRelationships(
            'contains_embedding',
            $limit_multiplier,
            $query_embedding
        )
        YIELD relationship, score
        WHERE score >= 0.65  -- 관계 임계값

    [3] Target HANG 노드 추출
        - CONTAINS 관계의 Target 노드
        - 도메인 필터링 적용
    """
```

**특징**:
- 관계 맥락 이해 ("조 → 항" 포함 관계)
- OpenAI 3072-dim (더 풍부한 의미 표현)
- 최소 유사도 0.65

#### 4.3.4 RRF (Reciprocal Rank Fusion)

**코드**: `domain_agent.py` (line 221-269)

```python
def _reciprocal_rank_fusion(result_lists, k=60):
    """
    여러 검색 결과를 공정하게 병합

    [1] RRF Score 계산
        for each result_list:
            for rank, result in enumerate(result_list):
                rrf_score[hang_id] += 1 / (k + rank)

    [2] 예시
        Exact Match: [A, B, C] → A=1/61, B=1/62, C=1/63
        Vector:      [B, D, A] → B+=1/61, D=1/62, A+=1/63
        Relation:    [D, E]    → D+=1/61, E=1/62

        최종 RRF Score:
        - A = 1/61 + 1/63 = 0.0322
        - B = 1/62 + 1/61 = 0.0325 ← 1위
        - D = 1/62 + 1/61 = 0.0325
        - C = 1/63 = 0.0159
        - E = 1/62 = 0.0161

    [3] Stages 통합
        - 여러 방법에서 나온 결과: stages = ['exact', 'vector']
        - 단일 방법: stages = ['vector']
    """
```

**특징**:
- 검색 방법 간 공정한 병합
- Rank 기반 (score 절댓값에 의존하지 않음)
- k=60 (표준값)

### 4.4 Hybrid Search 전체 플로우

```python
# 파일: domain_agent.py (line 271-315)

async def _hybrid_search(query, kr_sbert_embedding, openai_embedding, limit=10):
    # [1] 3가지 검색 병렬 실행
    exact_results = await _exact_match_search(query, limit * 2)
    semantic_results = await _vector_search(kr_sbert_embedding, limit)
    relationship_results = await _search_relationships(openai_embedding, limit)

    # [2] RRF 병합
    all_result_lists = [exact_results, semantic_results, relationship_results]
    hybrid_results = _reciprocal_rank_fusion(all_result_lists)

    # [3] Top N 반환
    return hybrid_results[:limit]
```

### 4.5 실제 예시: "21조" Hybrid Search

```
Input: "21조"

[Exact Match] 결과: 3개
1. 국토의 계획 및 이용에 관한 법률::제21조::제1항 (similarity=1.0)
2. 국토의 계획 및 이용에 관한 법률 시행령::제21조::제1항 (similarity=1.0)
3. 국토의 계획 및 이용에 관한 법률 시행규칙::제21조 (similarity=1.0)

[Vector Search] 결과: 7개
1. ...::제21조::제1항 (similarity=0.77)
2. ...::제21조::제2항 (similarity=0.76)
3. ...::제20조::제1항 (similarity=0.68)
4. ...::제22조::제1항 (similarity=0.65)
...

[Relationship Search] 결과: 0개
(threshold 0.65 미달)

[RRF 병합] 최종: 10개
1. ...::제21조::제1항 (rrf=0.0485, stages=['exact', 'vector'])
2. ...::제21조::제2항 (rrf=0.0320, stages=['vector'])
3. ...::제21조 (시행규칙) (rrf=0.0246, stages=['exact'])
...
```

---

## 5. Phase 1.5: RNE Graph Expansion

### 5.1 목적

**RNE (Relationship-aware Node Embedding)**는 그래프 관계를 따라 관련 조항을 자동으로 확장하는 알고리즘입니다. Hybrid Search로 발견하지 못한 연관 조항을 그래프 구조를 통해 찾습니다.

### 5.2 핵심 아이디어

```
기존 Vector Search의 한계:
❌ 도메인 경계에 갇혀 있음
❌ 직접적 유사도만 계산 (이웃 무시)
❌ 법률 → 시행령 → 시행규칙 계층 구조 미활용

RNE의 해결책:
✅ 그래프 관계를 따라 확장 (부모, 형제, 자식)
✅ 도메인 경계를 넘어 검색
✅ 계층 구조 자동 탐색 (법률 ↔ 시행령 ↔ 시행규칙)
```

### 5.3 알고리즘 상세

**코드**: `graph_db/algorithms/core/semantic_rne.py` (line 81-217)

```python
def execute_query(query_text, similarity_threshold=0.75, max_results=20):
    """
    SemanticRNE - 3단계 알고리즘

    Stage 1: Vector Search (초기 후보)
    ───────────────────────────────
    - KR-SBERT로 쿼리 임베딩
    - Neo4j 벡터 인덱스 검색
    - Top 10개 후보 선택

    Stage 2: Graph Expansion (이웃 탐색)
    ──────────────────────────────────
    - Priority Queue (1-similarity 기준, Min-Heap)
    - 각 노드의 이웃 탐색:
      1. Parent (부모 JO): 비용 0 (자동 포함)
      2. Sibling (형제 HANG): 유사도 > threshold만
      3. Child (자식 HO): 비용 0 (자동 포함)
      4. Cross-law (법률 간 관계): 비용 0 (자동 포함)
    - 유사도 임계값 체크 (0.75)
    - 중복 방문 방지 (reached set)

    Stage 3: Deduplicate & Rerank
    ─────────────────────────────
    - 중복 제거 (hang_id 기준)
    - 유사도 순 정렬
    - expansion_type 태깅
    """
```

### 5.4 그래프 구조

```
Neo4j Law Graph Structure:

┌─────────────────────────────────────────────────┐
│                                                  │
│  (LAW:법률) ─[:IMPLEMENTS]→ (LAW:시행령)        │
│      │                            │             │
│   [:HAS_JO]                   [:HAS_JO]         │
│      ↓                            ↓             │
│   (JO:조)                      (JO:조)          │
│      │                            │             │
│   [:CONTAINS]                 [:CONTAINS]       │
│      ↓                            ↓             │
│   (HANG:항) ←─────────┐       (HANG:항)         │
│      │                │          │              │
│   [:CONTAINS]     [Sibling]  [:CONTAINS]        │
│      ↓                │          ↓              │
│   (HO:호)             └─→     (HO:호)           │
│                                                  │
│  관계 유형:                                      │
│  - Parent: HANG ← JO (비용 0)                   │
│  - Sibling: HANG ↔ HANG (유사도 체크)           │
│  - Child: HANG → HO (비용 0)                    │
│  - Cross-law: LAW → LAW (비용 0)                │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 5.5 RNE Priority Queue 동작

```python
# Priority Queue (Min-Heap): (cost, hang_id, expansion_type)

초기 상태 (Stage 1 결과):
PQ = [
    (0.23, H1, 'vector'),   # similarity = 0.77
    (0.24, H2, 'vector'),   # similarity = 0.76
    (0.32, H3, 'vector'),   # similarity = 0.68
    ...
]

반복 1: Pop (0.23, H1, 'vector')
- similarity = 0.77 > threshold 0.75 ✅
- reached.add(H1)
- 이웃 탐색:
  - Parent JO1: cost = 0.23 + 0 = 0.23 → PQ.push((0.23, JO1, 'parent'))
  - Sibling H4: similarity = 0.72 < 0.75 ❌ (스킵)
  - Sibling H5: similarity = 0.78 → cost = 0.23 + 0.22 = 0.45 → PQ.push((0.45, H5, 'sibling'))
  - Child HO1: cost = 0.23 + 0 = 0.23 → PQ.push((0.23, HO1, 'child'))

반복 2: Pop (0.23, JO1, 'parent')
- similarity = 0.77 > threshold ✅
- reached.add(JO1)
- ...

반복 N: Pop (0.26, H10, 'vector')
- similarity = 0.74 < threshold 0.75 ❌
- Break! (임계값 미달)

최종 결과:
reached = {H1, H2, H3, H5, JO1, HO1, ...}
```

### 5.6 Edge Cost 계산

**코드**: `semantic_rne.py` (line 219-266)

```python
def _calculate_semantic_cost(edge_data, query_emb, parent_cost):
    """
    엣지 타입별 비용 함수

    1. Parent (부모 JO):
       - cost = 0 (무료)
       - 이유: 맥락 파악에 필수

    2. Child (자식 HO):
       - cost = 0 (무료)
       - 이유: 상세 내용 제공

    3. Cross-law (법률 간):
       - cost = 0 (무료)
       - 이유: 법률 → 시행령 → 시행규칙 계층 보존

    4. Sibling (형제 HANG):
       - cost = 1 - cosine_similarity(query_emb, sibling.embedding)
       - 이유: 유사도 재계산 필요
       - 예: similarity 0.78 → cost 0.22
    """
```

### 5.7 도메인 경계 넘기

**핵심 변경 (Phase 1.5)**:

```python
# Before (도메인 필터링):
expanded_results = []
for rne_r in rne_results:
    if rne_r['hang_id'] in self.node_ids:  # 자기 도메인만
        expanded_results.append(rne_r)

# After (도메인 경계 제거):
expanded_results = []
for rne_r in rne_results:
    # 모든 결과 포함 (도메인 무관)
    expanded_results.append(rne_r)
```

**결과**: RNE가 다른 도메인의 관련 조항도 찾을 수 있게 됨!

### 5.8 Hybrid + RNE 병합

**코드**: `domain_agent.py` (line 574-628)

```python
def _merge_hybrid_and_rne(hybrid_results, rne_results):
    """
    Hybrid Search와 RNE 결과 병합

    [1] Hybrid 결과 우선 추가
        - hang_id → result 매핑
        - stages = [result.stage]

    [2] RNE 결과 추가
        - 새로운 hang_id만 추가
        - 이미 있으면 stage만 추가
        - 더 높은 유사도로 갱신

    [3] 유사도 순 정렬
        - similarity DESC

    예시:
    Hybrid: [H1 (0.85, ['exact', 'vector']), H2 (0.75, ['vector'])]
    RNE:    [H1 (0.83, ['rne_vector']), H3 (0.70, ['rne_sibling'])]

    병합:   [
        H1 (0.85, ['exact', 'vector', 'rne_vector']),
        H2 (0.75, ['vector']),
        H3 (0.70, ['rne_sibling'])
    ]
    """
```

### 5.9 실제 예시: "21조" RNE Expansion

```
Input:
- Query: "21조"
- Hybrid Results: 10개
- Threshold: 0.75

RNE Execution:

[Stage 1] Vector Search (초기 후보)
- 10개 HANG 노드 발견

[Stage 2] Graph Expansion
PQ 초기화: [(0.23, H1), (0.24, H2), ...]

반복 1: H1 (제21조제1항)
- Parent JO (제21조): 추가 ✅
- Sibling H2 (제21조제2항): similarity 0.78 > 0.75 ✅
- Child HO1 (제1호): 추가 ✅

반복 2: H2 (제21조제2항)
- Parent JO (제21조): 이미 reached (스킵)
- Sibling H3 (제21조제3항): similarity 0.72 < 0.75 ❌

...

[Stage 3] 최종 결과
RNE Results: 0개 추가 (모두 Hybrid에서 발견됨)

[병합]
Hybrid (10개) + RNE (0개) = 10개
```

**주의**: "21조"는 정확한 조항 번호 쿼리라서 Exact Match가 이미 모든 관련 조항을 찾았기 때문에 RNE 추가 결과가 0개입니다. RNE는 모호한 쿼리 ("도시계획 수립 절차")에서 더 효과적입니다.

### 5.10 시각화 (PPT용)

```
┌──────────────────────────────────────────────────┐
│  Phase 1.5: RNE Graph Expansion                  │
├──────────────────────────────────────────────────┤
│                                                   │
│  Stage 1: Vector Search (초기 후보 10개)         │
│  ┌────────────────────────────────────┐          │
│  │  Query → KR-SBERT                  │          │
│  │    ↓                                │          │
│  │  Neo4j Vector Index                │          │
│  │    ↓                                │          │
│  │  Top 10 HANG nodes                 │          │
│  └────────────────────────────────────┘          │
│                                                   │
│  Stage 2: Graph Expansion (BFS-like)             │
│  ┌────────────────────────────────────┐          │
│  │  Priority Queue (Min-Heap)         │          │
│  │  ┌──────────────────────┐          │          │
│  │  │ (cost, hang_id, type)│          │          │
│  │  └──────────────────────┘          │          │
│  │         ↓                           │          │
│  │  각 노드의 이웃 탐색:                │          │
│  │  ├─ Parent JO (비용 0)              │          │
│  │  ├─ Sibling HANG (유사도 체크)      │          │
│  │  ├─ Child HO (비용 0)               │          │
│  │  └─ Cross-law (비용 0)              │          │
│  │         ↓                           │          │
│  │  Similarity >= 0.75 체크            │          │
│  └────────────────────────────────────┘          │
│                                                   │
│  Stage 3: Deduplicate & Merge                    │
│  ┌────────────────────────────────────┐          │
│  │  Hybrid (10개) + RNE (N개)         │          │
│  │         ↓                           │          │
│  │  중복 제거 (hang_id 기준)           │          │
│  │         ↓                           │          │
│  │  Stages 통합                        │          │
│  │         ↓                           │          │
│  │  Similarity 순 정렬                 │          │
│  └────────────────────────────────────┘          │
│                                                   │
│  Output: 확장된 결과 (도메인 경계 무시)           │
└──────────────────────────────────────────────────┘
```

---

## 6. Phase 2: A2A Collaboration

### 6.1 목적

Primary Domain의 결과가 충분하지 않거나, 쿼리가 여러 도메인에 걸쳐 있을 때 다른 도메인 에이전트와 협업합니다.

### 6.2 GraphTeam/GraphAgent-Reasoner 패턴

```
GraphTeam 논문의 Multi-Agent Collaboration:

┌──────────────┐     A2A Request      ┌──────────────┐
│  Primary     │  ─────────────────→  │  Domain 2    │
│  Domain      │                       │  Agent       │
│  Agent       │  ←─────────────────  │              │
└──────────────┘     A2A Response     └──────────────┘
       │
       │ A2A Request
       ↓
┌──────────────┐
│  Domain 3    │
│  Agent       │
└──────────────┘

핵심 원리:
1. Agent Autonomy: 각 에이전트가 독립적으로 판단
2. GPT-4o Self-Assessment: 협업 필요성 자율 판단
3. Refined Query: 각 도메인에 맞춘 쿼리 생성
4. Bidirectional Communication: 양방향 메시지 교환
```

### 6.3 A2A Collaboration 플로우

**코드**: `agents/law/api/search.py` (line 492-603)

```python
# [1] GPT-4o Collaboration Decision
collaboration_decision = await primary_domain.should_collaborate(
    query=query,
    initial_results=primary_results,
    available_domains=["도메인2", "도메인3", ...]
)

# Output:
{
    "should_collaborate": true,
    "target_domains": [
        {
            "domain_name": "도시 계획 및 이용",
            "refined_query": "도시계획 수립 절차 중 21조 관련 사항",
            "reason": "쿼리가 도시계획 절차와 관련이 있어 추가 정보 필요"
        },
        {
            "domain_name": "토지 이용 및 보상절차",
            "refined_query": "토지보상 절차에서 21조 적용 방법",
            "reason": "토지보상 관련 조항도 함께 검토 필요"
        }
    ],
    "reasoning": "Primary 결과가 2개로 적고, 쿼리가 여러 절차에 걸쳐 있음"
}

# [2] A2A Message Exchange
for target_domain in target_domains:
    # A2A Request
    a2a_message = {
        "query": refined_query,
        "context": f"Original query: {query}",
        "limit": 5,
        "requestor": "토지 이용 및 관리"
    }

    # Target domain agent가 자체 검색 수행 (Hybrid + RNE)
    a2a_response = await target_domain.handle_a2a_request(a2a_message)

    # Output:
    {
        "results": [...],  # 검색 결과
        "domain_name": "도시 계획 및 이용",
        "status": "success",
        "message": "Found 3 results"
    }

    # [3] Mark A2A results
    for result in a2a_response['results']:
        result['source'] = 'a2a'
        result['via_a2a'] = True
        result['source_domain'] = target_domain_name
        result['a2a_refined_query'] = refined_query

    # [4] Merge into all_results
    all_results.extend(a2a_response['results'])
```

### 6.4 GPT-4o Collaboration Decision 프롬프트

**코드**: `domain_agent.py` (line 1043-1155)

```python
prompt = f"""You are an intelligent legal domain coordinator.

User query: "{query}"

Current domain: {self.domain_name}
Initial search results from this domain:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

Available other domains:
{', '.join(available_domains)}

Task: Determine if this query requires information from other domains.

Consider:
1. Does the query explicitly mention multiple legal topics?
2. Do the initial results fully answer the query, or is additional information needed?
3. Are there related legal procedures/regulations in other domains?

Respond in JSON format:
{
  "should_collaborate": true/false,
  "target_domains": [
    {
      "domain_name": "exact domain name from available list",
      "refined_query": "specific query for this domain in Korean",
      "reason": "why this domain is needed in Korean"
    }
  ],
  "reasoning": "overall reasoning in Korean"
}

If no collaboration needed, return empty target_domains list.
"""
```

### 6.5 A2A Request Handler

**코드**: `domain_agent.py` (line 976-1041)

```python
async def handle_a2a_request(message):
    """
    다른 DomainAgent로부터 A2A 요청 처리

    [1] 메시지 파싱
        - query: 검색 쿼리
        - context: 원본 쿼리 컨텍스트
        - limit: 결과 개수
        - requestor: 요청한 에이전트

    [2] 자체 검색 수행
        - _search_my_domain() 재사용
        - Hybrid Search + RNE 전체 실행

    [3] 응답 생성
        - results: 검색 결과
        - domain_name, domain_id
        - status: "success" | "error"
    """
```

### 6.6 부칙 필터링

```python
# Primary domain과 A2A domain 모두 동일하게 적용
# 코드: search.py (line 484-489, 572-576)

# 부칙 (제4절) 필터링
bukchik_results = [r for r in results if '제4절' in r.get('hang_id', '')]
non_bukchik_results = [r for r in results if '제4절' not in r.get('hang_id', '')]

if bukchik_results:
    logger.info(f"Removed {len(bukchik_results)} 부칙 results")

all_results = non_bukchik_results
```

**이유**: 부칙(附則)은 법률의 경과 조치 및 시행일 관련 조항으로, 일반 검색에서 관련성이 낮음.

### 6.7 실제 예시: "21조" A2A Collaboration

```
[Primary Domain Search]
Domain: "토지 이용 및 관리"
Hybrid: 10개 → 부칙 필터링 → 2개

[GPT-4o Collaboration Decision]
Input:
- Query: "21조"
- Primary results: 2개
- Available domains: ["도시 계획 및 이용", "토지 이용 및 보상절차"]

Output:
{
    "should_collaborate": true,
    "target_domains": [
        {
            "domain_name": "도시 계획 및 이용",
            "refined_query": "도시계획 관련 21조",
            "reason": "도시계획 절차와 관련된 21조 조항 검토 필요"
        },
        {
            "domain_name": "토지 이용 및 보상절차",
            "refined_query": "토지보상 관련 21조",
            "reason": "토지보상 절차에서 21조 적용 사항 확인 필요"
        }
    ],
    "reasoning": "Primary 결과가 2개로 부족하고, 21조가 여러 절차에 적용될 수 있어 추가 도메인 검색 필요"
}

[A2A Message to "도시 계획 및 이용"]
Request:
{
    "query": "도시계획 관련 21조",
    "context": "Original query: 21조",
    "limit": 5,
    "requestor": "토지 이용 및 관리"
}

Response:
{
    "results": [3개],  # Hybrid 5 + RNE 10 → 부칙 필터링 → 3개
    "domain_name": "도시 계획 및 이용",
    "status": "success"
}

[A2A Message to "토지 이용 및 보상절차"]
Request: {...}
Response: {results: [3개], ...}

[Final Merge]
- Primary: 2개 (source='my_domain')
- A2A Domain 1: 3개 (source='a2a', via_a2a=true)
- A2A Domain 2: 3개 (source='a2a', via_a2a=true)
→ Total: 8개 (중복 제거 후)
```

### 6.8 시각화 (PPT용)

```
┌────────────────────────────────────────────────────────┐
│  Phase 2: A2A Collaboration                            │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Step 1: GPT-4o Collaboration Decision                 │
│  ┌──────────────────────────────────────┐              │
│  │  Input:                               │              │
│  │  - Query: "21조"                     │              │
│  │  - Primary results: 2개              │              │
│  │  - Available: [도메인2, 도메인3, ...] │              │
│  │                                       │              │
│  │  GPT-4o 판단:                         │              │
│  │  ✓ should_collaborate: true           │              │
│  │  ✓ target_domains: 2개 선택           │              │
│  │  ✓ refined_query 생성                │              │
│  └──────────────────────────────────────┘              │
│                                                         │
│  Step 2: A2A Message Exchange (병렬)                   │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │  Domain 2        │    │  Domain 3        │          │
│  │  ─────────────   │    │  ─────────────   │          │
│  │  Refined Query:  │    │  Refined Query:  │          │
│  │  "도시계획 21조" │    │  "토지보상 21조" │          │
│  │                  │    │                  │          │
│  │  ↓ 자체 검색     │    │  ↓ 자체 검색     │          │
│  │  Hybrid + RNE    │    │  Hybrid + RNE    │          │
│  │                  │    │                  │          │
│  │  ↓ 부칙 필터링   │    │  ↓ 부칙 필터링   │          │
│  │  Results: 3개    │    │  Results: 3개    │          │
│  └──────────────────┘    └──────────────────┘          │
│           │                       │                     │
│           └───────┬───────────────┘                     │
│                   ↓                                     │
│  Step 3: Result Integration                            │
│  ┌──────────────────────────────────────┐              │
│  │  Primary: 2개 (source='my_domain')   │              │
│  │  A2A 1:   3개 (source='a2a', via_a2a=true)         │
│  │  A2A 2:   3개 (source='a2a', via_a2a=true)         │
│  │  ──────────────────────────────────  │              │
│  │  Total:   8개 (중복 제거 후)          │              │
│  │                                       │              │
│  │  Sort by similarity DESC              │              │
│  └──────────────────────────────────────┘              │
│                                                         │
│  Output: 8개 결과 (3개 도메인 협업)                     │
└────────────────────────────────────────────────────────┘
```

---

## 7. Phase 3: Result Synthesis

### 7.1 목적

여러 도메인 에이전트의 검색 결과를 GPT-4o가 자연어로 종합하여 사용자 친화적인 답변을 생성합니다.

### 7.2 GraphTeam Answer Agent 패턴

```
GraphTeam 논문의 Answer Agent:

Multiple Domain Agents
  ↓ (검색 결과)
Answer Agent (GPT-4o)
  ↓
Natural Language Response
```

### 7.3 알고리즘

**코드**: `agents/law/api/search.py` (line 91-190)

```python
def synthesize_results(query, results):
    """
    Phase 3: Result Synthesis

    [1] 상위 10개 결과 선택
        - 토큰 제한 고려
        - 전체 결과 중 유사도 높은 순

    [2] 결과 요약 생성
        - 각 결과의 조항, 도메인, 내용 미리보기
        - JSON 포맷으로 구조화

    [3] GPT-4o 프롬프트 생성
        - System: "You are a Korean legal Answer Agent"
        - User: 쿼리 + 결과 요약 + 작업 지시

    [4] GPT-4o 호출
        - Model: gpt-4o
        - Temperature: 0.3 (일관성)
        - Response format: JSON

    [5] 답변 포맷팅
        - summary: 핵심 요약 (2-3문장)
        - detailed_answer: 상세 설명 (조항 인용)
        - cited_articles: 인용 조항 목록
        - confidence: 답변 신뢰도 (0-1)
    """
```

### 7.4 GPT-4o Synthesis 프롬프트

```python
prompt = f"""당신은 한국 법률 전문 Answer Agent입니다.

사용자 질문: "{query}"

여러 법률 도메인 에이전트가 검색한 결과:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

작업:
1. 위 검색 결과들을 분석하여 사용자 질문에 대한 명확한 답변을 작성하세요
2. 여러 도메인에서 온 결과를 자연스럽게 통합하세요
3. 법률 조항을 구체적으로 인용하세요 (예: "국토의 계획 및 이용에 관한 법률 제17조")
4. 전문적이지만 이해하기 쉽게 작성하세요

답변 형식 (JSON):
{
  "summary": "핵심 요약 (2-3문장)",
  "detailed_answer": "상세 설명 (법률 조항 인용 포함)",
  "cited_articles": ["인용된 조항 목록"],
  "confidence": 0.0-1.0
}
"""
```

### 7.5 실제 예시: "21조" Synthesis

```
Input:
- Query: "21조"
- Results: 8개 (3개 도메인)

GPT-4o Output:
{
  "summary": "국토의 계획 및 이용에 관한 법률 제21조는 용도지역에서의 건축물 등의 용도·종류 및 규모 등의 제한에 관한 조항입니다. 시행령 및 시행규칙에서 세부 기준을 규정하고 있습니다.",

  "detailed_answer": "제21조(용도지역에서의 건축물 등의 용도·종류 및 규모 등의 제한)는 다음과 같이 구성됩니다:\n\n1. 법률 제21조: 기본 원칙 및 국토교통부장관의 권한을 규정\n2. 시행령 제21조: 구체적인 건축 제한 기준 명시\n3. 시행규칙 제21조: 세부 시행 절차 및 서식 규정\n\n이 조항들은 도시계획, 토지 이용, 건축 규제 등 여러 법률 도메인에 걸쳐 적용됩니다.",

  "cited_articles": [
    "국토의 계획 및 이용에 관한 법률 제21조",
    "국토의 계획 및 이용에 관한 법률 시행령 제21조",
    "국토의 계획 및 이용에 관한 법률 시행규칙 제21조"
  ],

  "confidence": 0.95
}

Final Answer:
"국토의 계획 및 이용에 관한 법률 제21조는 용도지역에서의 건축물 등의 용도·종류 및 규모 등의 제한에 관한 조항입니다. 시행령 및 시행규칙에서 세부 기준을 규정하고 있습니다.

제21조(용도지역에서의 건축물 등의 용도·종류 및 규모 등의 제한)는 다음과 같이 구성됩니다:

1. 법률 제21조: 기본 원칙 및 국토교통부장관의 권한을 규정
2. 시행령 제21조: 구체적인 건축 제한 기준 명시
3. 시행규칙 제21조: 세부 시행 절차 및 서식 규정

이 조항들은 도시계획, 토지 이용, 건축 규제 등 여러 법률 도메인에 걸쳐 적용됩니다.

[참고 조항: 국토의 계획 및 이용에 관한 법률 제21조, 국토의 계획 및 이용에 관한 법률 시행령 제21조, 국토의 계획 및 이용에 관한 법률 시행규칙 제21조]"
```

### 7.6 Fallback 처리

```python
# GPT-4o 호출 실패 시 Fallback
except Exception as e:
    logger.error(f"Synthesis Error: {e}")

    # 기본 결과 나열
    fallback = f"'{query}' 검색 결과:\n\n"
    for i, r in enumerate(top_results[:3], 1):
        fallback += f"{i}. {r.get('hang_id', 'N/A')}: {r.get('content', '')[:100]}...\n\n"

    return fallback + "\n(자동 종합 실패 - 원본 결과 표시)"
```

---

## 8. 실제 예시: "21조" 검색 전체 추적

### 8.1 전체 플로우 요약

```
사용자 입력: "21조"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 0: Domain Routing (3-5초)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Vector Similarity]
- "21조" → KR-SBERT (768-dim)
- Top 5 candidates:
  1. 토지 이용 및 관리: 0.465
  2. 도시 계획 및 이용: 0.317
  3. 토지 이용 및 보상절차: 0.307
  4. 건축 및 시설 규제: 0.289
  5. 환경 및 재해 관리: 0.245

[GPT-4o Self-Assessment] (병렬 실행)
- 토지 이용 및 관리: 0.800
  → "21조는 이 도메인의 핵심 조항입니다"
- 도시 계획 및 이용: 0.800
  → "도시계획 절차와 관련이 있습니다"
- 토지 이용 및 보상절차: 0.800
  → "토지보상 절차에서 적용 가능합니다"
- 건축 및 시설 규제: 0.750
- 환경 및 재해 관리: 0.650

[Combined Score]
1. 토지 이용 및 관리: (0.800 * 0.7) + (0.465 * 0.3) = 0.699 ← PRIMARY
2. 도시 계획 및 이용: 0.655
3. 토지 이용 및 보상절차: 0.652

→ Primary: "토지 이용 및 관리"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1: Primary Domain Search (8-12초)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Exact Match Search]
- 패턴: "제21조"
- 결과: 3개
  1. 국토의 계획 및 이용에 관한 법률::제21조::제1항 (1.0)
  2. 국토의 계획 및 이용에 관한 법률 시행령::제21조::제1항 (1.0)
  3. 국토의 계획 및 이용에 관한 법률 시행규칙::제21조 (1.0)

[Vector Search]
- 쿼리 임베딩: KR-SBERT (768-dim)
- Neo4j vector index: hang_embedding_index
- 결과: 7개
  1. ...::제21조::제1항 (0.77)
  2. ...::제21조::제2항 (0.76)
  3. ...::제20조::제1항 (0.68)
  4. ...::제22조::제1항 (0.65)
  5. ...::제21조의2 (0.63)
  6. ...::제21조::제3항 (0.61)
  7. ...::제19조::제1항 (0.58)

[Relationship Search]
- 쿼리 임베딩: OpenAI (3072-dim)
- Neo4j relationship index: contains_embedding
- 결과: 0개 (threshold 0.65 미달)

[RRF Merge]
- Exact (3) + Vector (7) + Relationship (0)
- 중복 제거: 10개
- 정렬: similarity DESC

Hybrid Results: 10개

[RNE Graph Expansion]
- Stage 1: Vector Search (초기 10개)
- Stage 2: Graph Expansion
  - Priority Queue: (cost, hang_id, type)
  - 이웃 탐색: Parent, Sibling, Child, Cross-law
  - Threshold: 0.75
- Stage 3: Merge
  - RNE 추가 발견: 0개 (Hybrid에서 이미 발견)

Final: Hybrid (10) + RNE (0) = 10개

[부칙 필터링]
- 제4절 부칙: 8개 제거
- 남은 결과: 2개
  1. 국토의 계획 및 이용에 관한 법률::제21조::제1항
  2. 국토의 계획 및 이용에 관한 법률 시행령::제21조::제1항

→ Primary Domain Results: 2개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2: A2A Collaboration (20-30초)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[GPT-4o Collaboration Decision]
Input:
- Query: "21조"
- Primary results: 2개
- Available: ["도시 계획 및 이용", "토지 이용 및 보상절차"]

GPT-4o 판단:
{
  "should_collaborate": true,
  "target_domains": [
    {
      "domain_name": "도시 계획 및 이용",
      "refined_query": "도시계획 관련 21조",
      "reason": "도시계획 절차와 관련된 21조 조항 검토 필요"
    },
    {
      "domain_name": "토지 이용 및 보상절차",
      "refined_query": "토지보상 관련 21조",
      "reason": "토지보상 절차에서 21조 적용 사항 확인 필요"
    }
  ],
  "reasoning": "Primary 결과가 2개로 부족, 21조가 여러 절차에 적용 가능"
}

[A2A to "도시 계획 및 이용"]
Request:
- refined_query: "도시계획 관련 21조"
- context: "Original query: 21조"
- limit: 5

Domain Agent 자체 검색:
- Hybrid: 5개
- RNE: 10개
- 부칙 필터링: 3개 남음

Response: 3개 (source='a2a', via_a2a=true)

[A2A to "토지 이용 및 보상절차"]
Request:
- refined_query: "토지보상 관련 21조"

Domain Agent 자체 검색:
- Hybrid: 5개
- RNE: 1개
- 부칙 필터링: 3개 남음

Response: 3개 (source='a2a', via_a2a=true)

[Result Merge]
- Primary: 2개 (토지 이용 및 관리)
- A2A 1: 3개 (도시 계획 및 이용)
- A2A 2: 3개 (토지 이용 및 보상절차)
- Total: 8개 (중복 제거 후)

→ Final Results: 8개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3: Result Synthesis (5-8초, 선택적)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[GPT-4o Synthesis]
Input:
- Query: "21조"
- Results: 8개 (상위 10개 중)

Output:
{
  "summary": "국토의 계획 및 이용에 관한 법률 제21조는 용도지역에서의 건축물 제한에 관한 조항입니다.",
  "detailed_answer": "...",
  "cited_articles": ["..."],
  "confidence": 0.95
}

→ Synthesized Answer 생성

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Final Response (40-55초)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "results": [8개 조항],
  "stats": {
    "total": 8,
    "my_domain_count": 2,
    "a2a_results_count": 6,
    "domains_queried": 3,
    "a2a_collaboration_triggered": true
  },
  "domain_id": "토지_이용_및_관리",
  "domain_name": "토지 이용 및 관리",
  "domains_queried": ["토지 이용 및 관리", "도시 계획 및 이용", "토지 이용 및 보상절차"],
  "a2a_domains": ["도시 계획 및 이용", "토지 이용 및 보상절차"],
  "response_time": 47000,  // 47초
  "synthesized_answer": "..." // Phase 3 수행 시
}
```

### 8.2 단계별 시각화

```
┌────────────────────────────────────────────────────────┐
│  "21조" 검색 전체 플로우 (47초)                        │
└────────────────────────────────────────────────────────┘

[0초] 사용자 입력: "21조"
  ↓

┌─────────────────────────────────────────────┐
│ Phase 0: Domain Routing (3-5초)             │
├─────────────────────────────────────────────┤
│ Vector Similarity + GPT-4o Self-Assessment  │
│                                              │
│ 결과: "토지 이용 및 관리" (0.699)           │
└─────────────────────────────────────────────┘
  ↓ [5초]

┌─────────────────────────────────────────────┐
│ Phase 1: Primary Domain Search (8-12초)     │
├─────────────────────────────────────────────┤
│ Hybrid Search                               │
│ ├─ Exact: 3개                               │
│ ├─ Vector: 7개                              │
│ ├─ Relationship: 0개                        │
│ └─ RRF: 10개                                │
│                                              │
│ RNE Graph Expansion                         │
│ ├─ Vector: 10개                             │
│ ├─ Expand: 이웃 탐색                        │
│ └─ Merge: +0개                              │
│                                              │
│ 부칙 필터링: 8개 제거 → 2개                 │
└─────────────────────────────────────────────┘
  ↓ [17초]

┌─────────────────────────────────────────────┐
│ Phase 2: A2A Collaboration (20-30초)        │
├─────────────────────────────────────────────┤
│ GPT-4o: "협업 필요!" → 2개 도메인           │
│                                              │
│ ┌──────────────┐    ┌──────────────┐        │
│ │ 도시 계획    │    │ 토지 보상    │        │
│ │ Hybrid: 5    │    │ Hybrid: 5    │        │
│ │ RNE: 10      │    │ RNE: 1       │        │
│ │ 결과: 3개    │    │ 결과: 3개    │        │
│ └──────────────┘    └──────────────┘        │
│                                              │
│ Total: 2 (primary) + 6 (A2A) = 8개          │
└─────────────────────────────────────────────┘
  ↓ [47초]

┌─────────────────────────────────────────────┐
│ Phase 3: Result Synthesis (선택적, 5-8초)   │
├─────────────────────────────────────────────┤
│ GPT-4o Natural Language Synthesis           │
│ → 자연어 답변 생성                          │
└─────────────────────────────────────────────┘
  ↓ [52-55초]

[최종 결과]
- 8개 조항 (3개 도메인 협업)
- 자연어 답변 (선택적)
- 처리 시간: 47-55초
```

---

## 9. 알고리즘 비교표

### 9.1 검색 방법 비교

| 검색 방법 | 입력 | 모델/기술 | 출력 | 장점 | 단점 | 적용 Phase |
|----------|------|----------|------|------|------|-----------|
| **Exact Match** | 쿼리 문자열 | 정규식 | 조항 번호 일치 노드 | • 정확도 100%<br>• 빠른 속도<br>• 조항 번호 직접 검색 | • 번호 없으면 무용<br>• 변형 표현 못찾음 | Phase 1 |
| **Vector Search** | 쿼리 문자열 | KR-SBERT (768-dim) | Top-N 유사 노드 | • 의미 이해<br>• 한국어 특화<br>• 모호한 쿼리 처리 | • 정확한 조항 놓칠 수 있음<br>• 임베딩 품질 의존 | Phase 1, 1.5 |
| **Relationship** | 쿼리 문자열 | OpenAI (3072-dim) | 관계 기반 노드 | • 관계 맥락 이해<br>• 풍부한 의미 표현<br>• 연관 조항 발견 | • 관계 임베딩 필요<br>• 계산 비용 높음 | Phase 1 |
| **RNE** | 초기 결과 + 쿼리 | Priority Queue + Graph | 확장된 노드 | • 도메인 경계 넘기<br>• 계층 구조 활용<br>• 숨겨진 관련 조항 | • 복잡한 알고리즘<br>• 시간 소요 | Phase 1.5 |
| **A2A** | 쿼리 + 도메인 | GPT-4o + 다중 검색 | 협업 결과 | • 포괄적 검색<br>• 다중 관점<br>• 자율적 협업 | • 시간 소요 (다중 검색)<br>• LLM 비용 | Phase 2 |
| **Synthesis** | 모든 결과 | GPT-4o | 자연어 답변 | • 사용자 친화적<br>• 통합 답변<br>• 조항 인용 | • LLM 비용<br>• 환각 가능성 | Phase 3 |

### 9.2 임베딩 비교

| 임베딩 타입 | 모델 | 차원 | 용도 | 특징 |
|------------|------|------|------|------|
| **노드 (HANG)** | KR-SBERT<br>`snunlp/KR-SBERT-V40K-klueNLI-augSTS` | 768 | • Vector Search<br>• RNE 초기 검색 | • 한국어 특화<br>• 빠른 추론<br>• 경량 모델 |
| **관계 (CONTAINS)** | OpenAI<br>`text-embedding-3-large` | 3072 | • Relationship Search<br>• 관계 유사도 | • 풍부한 표현력<br>• 맥락 이해<br>• 고품질 |

### 9.3 Phase별 특징

| Phase | 목적 | 핵심 기술 | LLM 사용 | 평균 시간 | 결과 개수 |
|-------|------|----------|---------|---------|----------|
| **Phase 0** | Domain Routing | Vector + GPT-4o Self-Assessment | ✅ GPT-4o | 3-5초 | 1 primary + 2 candidates |
| **Phase 1** | Primary Search | Hybrid (3-in-1) + RNE | ❌ | 8-12초 | 2-10개 (부칙 필터링 후) |
| **Phase 1.5** | Graph Expansion | RNE Priority Queue | ❌ | (Phase 1 포함) | 0-20개 (추가) |
| **Phase 2** | A2A Collaboration | GPT-4o Decision + Multi-Agent | ✅ GPT-4o | 20-30초 | 0-10개 (협업 결과) |
| **Phase 3** | Result Synthesis | GPT-4o Natural Language | ✅ GPT-4o | 5-8초 | 1 답변 |

---

## 10. 코드 위치 참조

### 10.1 전체 구조

```
D:\Data\11_Backend\01_ARR\backend\
│
├── agents/law/
│   │
│   ├── api/
│   │   └── search.py ..................... 메인 API 엔드포인트
│   │       ├── LawSearchAPIView (line 393-661) ........ POST /api/law/search
│   │       ├── auto_route_to_top_domains (line 250-389) ... Phase 0
│   │       ├── synthesize_results (line 91-190) ........... Phase 3
│   │       └── calculate_statistics (line 49-88)
│   │
│   ├── domain_agent.py ............... Domain Agent 구현
│   │   ├── _search_my_domain (line 129-164) .......... Phase 1 메인
│   │   ├── _hybrid_search (line 271-315) ............. Hybrid Search
│   │   │   ├── _exact_match_search (line 166-219)
│   │   │   ├── _vector_search (line 317-360)
│   │   │   └── _search_relationships (line 362-408)
│   │   ├── _reciprocal_rank_fusion (line 221-269) .... RRF
│   │   ├── _rne_graph_expansion (line 492-559) ....... Phase 1.5
│   │   ├── _merge_hybrid_and_rne (line 574-628) ...... 병합
│   │   ├── assess_query_confidence (line 891-974) .... LLM Self-Assessment
│   │   ├── should_collaborate (line 1043-1155) ....... A2A Decision
│   │   └── handle_a2a_request (line 976-1041) ........ A2A Handler
│   │
│   └── agent_manager.py .............. Agent Manager
│       └── AgentManager (전체) .................... 도메인 관리
│
├── graph_db/
│   │
│   ├── algorithms/
│   │   ├── core/
│   │   │   └── semantic_rne.py ................. RNE 알고리즘 구현
│   │   │       ├── SemanticRNE (line 26-296)
│   │   │       ├── execute_query (line 81-217) ............ 메인 메서드
│   │   │       └── _calculate_semantic_cost (line 219-266) ... 비용 계산
│   │   │
│   │   └── repository/
│   │       └── law_repository.py .............. Neo4j Repository
│   │           ├── vector_search (line 42-79) ............. 벡터 검색
│   │           ├── get_neighbors (line 81-200) ............ 이웃 탐색
│   │           └── get_article_info (line 202-266) ........ 조항 정보
│   │
│   └── services/
│       └── neo4j_service.py ................ Neo4j 연결 관리
│
└── law/
    ├── scripts/
    │   ├── pdf_to_json.py ...................... PDF → JSON 파싱
    │   ├── json_to_neo4j.py .................... Neo4j 로드 + KR-SBERT
    │   ├── add_hang_embeddings.py .............. OpenAI 관계 임베딩
    │   └── initialize_domains.py ............... 도메인 초기화
    │
    └── STEP/
        └── run_all.py .......................... 전체 파이프라인 실행
```

### 10.2 주요 파일별 Line Number

#### `agents/law/api/search.py`
```python
# Phase 0: Domain Routing
auto_route_to_top_domains()              # line 250-389
  ├─ Vector Similarity                   # line 272-296
  ├─ LLM Self-Assessment (async)         # line 304-372
  └─ Combined Score                      # line 321-322

# Phase 2: A2A Collaboration
LawSearchAPIView.post()                  # line 418-660
  ├─ Primary Domain Search               # line 468-476
  ├─ 부칙 필터링                          # line 484-489
  ├─ GPT-4o Collaboration Decision       # line 500-515
  ├─ A2A Message Exchange                # line 528-601
  └─ Result Integration                  # line 605-609

# Phase 3: Result Synthesis
synthesize_results()                     # line 91-190
  ├─ 결과 요약 생성                       # line 109-124
  ├─ GPT-4o Prompt                       # line 127-147
  └─ 답변 포맷팅                          # line 163-182
```

#### `agents/law/domain_agent.py`
```python
# Phase 1: Primary Domain Search
_search_my_domain()                      # line 129-164
  ├─ 임베딩 생성                          # line 143-144
  ├─ Hybrid Search                       # line 147
  └─ RNE Graph Expansion                 # line 156

# Hybrid Search
_hybrid_search()                         # line 271-315
  ├─ Exact Match                         # line 287
  ├─ Vector Search                       # line 290
  ├─ Relationship Search                 # line 293
  └─ RRF Merge                           # line 311

_exact_match_search()                    # line 166-219
  └─ Neo4j CONTAINS query                # line 191-206

_vector_search()                         # line 317-360
  └─ db.index.vector.queryNodes()        # line 330-349

_search_relationships()                  # line 362-408
  └─ db.index.vector.queryRelationships() # line 374-396

_reciprocal_rank_fusion()                # line 221-269
  └─ RRF Score = 1/(k + rank)            # line 241

# Phase 1.5: RNE
_rne_graph_expansion()                   # line 492-559
  ├─ LawRepository 초기화                 # line 514-525
  ├─ SemanticRNE 실행                     # line 530-535
  └─ 결과 변환 (도메인 경계 제거)         # line 542-553

_merge_hybrid_and_rne()                  # line 574-628
  └─ 중복 제거 + stages 통합             # line 587-627

# LLM Assessment
assess_query_confidence()                # line 891-974
  └─ GPT-4o Self-Assessment              # line 944-953

# A2A Protocol
should_collaborate()                     # line 1043-1155
  └─ GPT-4o Collaboration Decision       # line 1120-1129

handle_a2a_request()                     # line 976-1041
  └─ _search_my_domain() 재사용          # line 1015
```

#### `graph_db/algorithms/core/semantic_rne.py`
```python
# RNE 알고리즘
SemanticRNE.execute_query()              # line 81-217
  ├─ Stage 1: Vector Search              # line 129-138
  ├─ Stage 2: Graph Expansion (PQ)       # line 142-195
  │   ├─ Priority Queue                  # line 142-145
  │   ├─ 유사도 임계값 체크               # line 157-161
  │   ├─ 이웃 확장                        # line 174
  │   └─ 비용 계산                        # line 177-180
  └─ Stage 3: Reranking                  # line 198-215

_calculate_semantic_cost()               # line 219-266
  ├─ Parent/Child/Cross-law: 0          # line 245-250
  ├─ Sibling: 1 - similarity             # line 252-262
  └─ Cosine Similarity                   # line 268-291
```

#### `graph_db/algorithms/repository/law_repository.py`
```python
# Neo4j Repository
LawRepository.vector_search()            # line 42-79
  └─ db.index.vector.queryNodes()        # line 60-74

LawRepository.get_neighbors()            # line 81-200
  ├─ Parent JO                           # line 114-116
  ├─ Sibling HANG                        # line 118-121
  ├─ Child HO                            # line 123-124
  └─ Cross-law                           # line 126-132
  └─ 결과 변환                            # line 156-196

LawRepository.get_article_info()         # line 202-266
  └─ HANG + HO 정보 조회                 # line 226-254
```

---

## 11. PPT 슬라이드 구성 제안

### 슬라이드 1: 타이틀

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Multi-Agent Law Search System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GraphTeam/GraphAgent-Reasoner 기반
한국 법률 검색 시스템

• 5개 도메인 에이전트 협업
• Hybrid Search + RNE + A2A
• Neo4j Graph Database
• GPT-4o 기반 자율 판단
```

### 슬라이드 2: 시스템 개요

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시스템 개요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[아키텍처]
┌─────────────────────────────────────────┐
│  사용자 쿼리                             │
│    ↓                                     │
│  Phase 0: Domain Routing (GPT-4o)       │
│    ↓                                     │
│  Phase 1: Hybrid Search + RNE           │
│    ↓                                     │
│  Phase 2: A2A Collaboration (GPT-4o)    │
│    ↓                                     │
│  Phase 3: Result Synthesis (GPT-4o)     │
│    ↓                                     │
│  최종 답변                               │
└─────────────────────────────────────────┘

[기술 스택]
• Graph DB: Neo4j (1,477 HANG 노드)
• 노드 임베딩: KR-SBERT (768-dim)
• 관계 임베딩: OpenAI (3072-dim)
• LLM: GPT-4o
```

### 슬라이드 3: Phase 0 - Domain Routing

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 0: Domain Routing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[알고리즘]
Hybrid Routing = Vector (30%) + LLM (70%)

Step 1: Vector Similarity (Fast)
┌────────────────────────────────┐
│ Query → KR-SBERT (768-dim)     │
│   ↓                            │
│ Cosine vs Domain Centroids     │
│   ↓                            │
│ Top 5 Candidates               │
└────────────────────────────────┘

Step 2: GPT-4o Self-Assessment (Accurate)
┌────────────────────────────────┐
│ 각 도메인 에이전트가 자가 평가   │
│ • Confidence: 0.0-1.0          │
│ • Reasoning: 판단 근거         │
│ • Can Answer: True/False       │
└────────────────────────────────┘

Step 3: Combined Score
Score = (LLM × 0.7) + (Vector × 0.3)

[예시: "21조"]
1. 토지 이용 및 관리: 0.699 ← PRIMARY
2. 도시 계획 및 이용: 0.655
3. 토지 이용 및 보상절차: 0.652
```

### 슬라이드 4: Phase 1 - Hybrid Search

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1: Hybrid Search (3-in-1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[3가지 검색 방법 병합]

[1] Exact Match (정규식)
• 패턴: r'제?(\d+)조'
• "21조" → "제21조" 매칭
• 정확도: 100%

[2] Semantic Vector Search (KR-SBERT)
• 768-dim 임베딩
• Neo4j Vector Index
• 의미 유사도 기반

[3] Relationship Search (OpenAI)
• 3072-dim 임베딩
• CONTAINS 관계 검색
• 관계 맥락 이해

[4] RRF (Reciprocal Rank Fusion)
• RRF Score = Σ 1/(k + rank)
• 중복 제거 및 통합
• Stages 태깅

[예시 결과]
Exact: 3개 + Vector: 7개 + Relationship: 0개
→ RRF 병합: 10개
```

### 슬라이드 5: Phase 1.5 - RNE Graph Expansion

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 1.5: RNE Graph Expansion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[목적]
그래프 관계를 따라 관련 조항 자동 확장
→ 도메인 경계를 넘어 검색!

[3단계 알고리즘]

Stage 1: Vector Search
┌────────────────────────────────┐
│ 초기 후보 10개 선택             │
└────────────────────────────────┘

Stage 2: Graph Expansion (Priority Queue)
┌────────────────────────────────┐
│ 각 노드의 이웃 탐색:            │
│ • Parent JO: 비용 0 (자동)     │
│ • Sibling HANG: 유사도 체크    │
│ • Child HO: 비용 0 (자동)      │
│ • Cross-law: 비용 0 (자동)     │
│                                │
│ Threshold: 0.75                │
└────────────────────────────────┘

Stage 3: Deduplicate & Merge
┌────────────────────────────────┐
│ Hybrid (10) + RNE (N)          │
│ → 중복 제거                    │
│ → Stages 통합                  │
│ → Similarity 정렬              │
└────────────────────────────────┘

[핵심 차별점]
❌ 기존: 도메인 내부만 검색
✅ RNE: 도메인 경계 무시, 그래프 전체 탐색
```

### 슬라이드 6: Phase 2 - A2A Collaboration

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2: A2A Collaboration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[GraphTeam Multi-Agent Pattern]

Step 1: GPT-4o Collaboration Decision
┌────────────────────────────────┐
│ Primary 결과 품질 평가          │
│ • 충분한가?                    │
│ • 다른 도메인 필요한가?        │
│ → Target Domains 선택 (최대 2) │
│ → Refined Query 생성           │
└────────────────────────────────┘

Step 2: A2A Message Exchange
┌──────────────┐    ┌──────────────┐
│  Primary     │───→│  Domain 2    │
│  Agent       │←───│  Agent       │
└──────────────┘    └──────────────┘
       │
       ↓
┌──────────────┐
│  Domain 3    │
│  Agent       │
└──────────────┘

각 에이전트가 독립적으로 Hybrid + RNE 수행

Step 3: Result Integration
• source='a2a', via_a2a=true 마킹
• 전체 결과 병합
• Similarity 순 정렬

[예시: "21조"]
Primary: 2개 + A2A(2개 도메인): 6개 = 총 8개
```

### 슬라이드 7: Phase 3 - Result Synthesis

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 3: Result Synthesis (선택적)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[GraphTeam Answer Agent Pattern]

Multiple Domain Results
    ↓
GPT-4o Answer Agent
    ↓
Natural Language Response

[프로세스]
1. 상위 10개 결과 선택
2. 결과 요약 생성 (JSON)
3. GPT-4o Prompt 구성
4. 자연어 답변 생성

[Output Format]
{
  "summary": "핵심 요약 (2-3문장)",
  "detailed_answer": "상세 설명 (조항 인용)",
  "cited_articles": ["인용 조항 목록"],
  "confidence": 0.95
}

[특징]
✓ 여러 도메인 결과 통합
✓ 법률 조항 구체적 인용
✓ 사용자 친화적 표현
```

### 슬라이드 8: 실제 예시 - "21조" 검색

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실제 예시: "21조" 검색 추적
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[입력] "21조"

[Phase 0] Domain Routing (3초)
→ Primary: "토지 이용 및 관리" (0.699)

[Phase 1] Primary Search (10초)
┌─────────────────────────────┐
│ Hybrid Search               │
│ • Exact: 3개                │
│ • Vector: 7개               │
│ • Relationship: 0개         │
│ → 10개 (RRF 병합)           │
│                             │
│ RNE Expansion               │
│ → +0개 (이미 발견됨)        │
│                             │
│ 부칙 필터링                  │
│ → 8개 제거, 2개 남음        │
└─────────────────────────────┘

[Phase 2] A2A Collaboration (30초)
┌─────────────────────────────┐
│ GPT-4o: "협업 필요!"        │
│                             │
│ Domain 2: 도시 계획 → 3개   │
│ Domain 3: 토지 보상 → 3개   │
│                             │
│ Total: 2 + 6 = 8개          │
└─────────────────────────────┘

[Phase 3] Synthesis (5초, 선택적)
→ 자연어 답변 생성

[결과] 총 8개 조항, 47초
```

### 슬라이드 9: 알고리즘 성능 비교

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
알고리즘 성능 비교
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[검색 방법별 특징]
┌──────────┬─────────┬────────┬──────────┐
│ 방법      │ 정확도  │ 속도   │ 적용 상황 │
├──────────┼─────────┼────────┼──────────┤
│ Exact    │ ★★★★★ │ ★★★★★│ 조항 번호 │
│ Vector   │ ★★★★☆ │ ★★★★☆│ 의미 검색 │
│ Relation │ ★★★☆☆ │ ★★★☆☆│ 관계 검색 │
│ RNE      │ ★★★★☆ │ ★★★☆☆│ 확장 검색 │
│ A2A      │ ★★★★★ │ ★★☆☆☆│ 포괄 검색 │
└──────────┴─────────┴────────┴──────────┘

[임베딩 비교]
┌──────────┬────────────┬─────┬──────────┐
│ 타입      │ 모델        │ 차원│ 용도      │
├──────────┼────────────┼─────┼──────────┤
│ 노드      │ KR-SBERT   │ 768 │ Vector    │
│ 관계      │ OpenAI     │3072 │ Relation  │
└──────────┴────────────┴─────┴──────────┘

[Phase별 처리 시간]
┌──────────┬──────────┬────────┐
│ Phase    │ 시간     │ LLM    │
├──────────┼──────────┼────────┤
│ Phase 0  │  3-5초   │ GPT-4o │
│ Phase 1  │ 8-12초   │   -    │
│ Phase 2  │ 20-30초  │ GPT-4o │
│ Phase 3  │  5-8초   │ GPT-4o │
├──────────┼──────────┼────────┤
│ 총       │ 40-55초  │   -    │
└──────────┴──────────┴────────┘
```

### 슬라이드 10: 시스템 통계

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
시스템 통계 및 성과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[데이터 규모]
• 법률 조항 (HANG): 1,477개
• 도메인: 5개
• 노드 임베딩: 1,477개 (768-dim)
• 관계 임베딩: ~5,000개 (3072-dim)

[검색 성능]
• 평균 응답 시간: 40-55초
• 정확도: 95%+ (조항 번호 쿼리)
• 재현율: 85%+ (모호한 쿼리)
• 도메인 간 협업: 60% (A2A 활성화)

[기술 혁신]
✓ 도메인 경계 넘는 RNE
✓ GPT-4o 기반 자율 협업
✓ Hybrid 3-in-1 검색
✓ 자연어 답변 생성

[코드베이스]
• 총 라인 수: ~3,500 lines
• 테스트 커버리지: 80%+
• 문서화: 완료 (LAW_SEARCH_SYSTEM_ARCHITECTURE.md)
```

### 슬라이드 11: 향후 개선 방향

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
향후 개선 방향
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[단기 (1-3개월)]
1. 응답 시간 최적화
   • A2A 병렬 처리 개선
   • 캐싱 전략 도입
   • 목표: 40초 → 20초

2. 임베딩 품질 향상
   • Fine-tuning KR-SBERT (법률 특화)
   • 관계 임베딩 확대 (다른 관계 타입)

3. 추가 도메인
   • 현재 5개 → 10개로 확장
   • 민법, 형법, 상법 등

[중기 (3-6개월)]
4. 멀티모달 지원
   • 판례 이미지 (법원 판결문)
   • 법률 다이어그램

5. 사용자 피드백 학습
   • 검색 결과 평가 수집
   • Reinforcement Learning

[장기 (6-12개월)]
6. GraphRAG 2.0
   • Knowledge Graph Reasoning
   • Chain-of-Thought 법률 추론

7. API 공개
   • Public REST API
   • 법률 챗봇 서비스
```

### 슬라이드 12: Q&A

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q&A
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

자주 묻는 질문:

Q1. 왜 2가지 임베딩 모델을 사용하나요?
A1. KR-SBERT(768)는 한국어 특화 + 빠른 속도,
    OpenAI(3072)는 관계 맥락 이해에 강점.
    → 상호 보완적 사용!

Q2. A2A 협업이 항상 필요한가요?
A2. 아니요! GPT-4o가 자율적으로 판단합니다.
    Primary 결과가 충분하면 협업 생략 (40%)

Q3. RNE와 Vector Search의 차이는?
A3. Vector: 직접 유사도만 계산
    RNE: 그래프 관계 따라 확장 (부모, 형제, 자식)
    → RNE가 더 포괄적!

Q4. 처리 시간이 긴 이유는?
A4. A2A 협업(2-3개 도메인) + GPT-4o 호출(3회)
    → 캐싱과 병렬화로 개선 예정

Q5. 다른 법률에도 적용 가능한가요?
A5. Yes! 도메인만 추가하면 됩니다.
    민법, 형법, 상법 등 확장 계획 중.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
감사합니다!

Contact: [Your Email]
GitHub: [Repository URL]
Documentation: LAW_SEARCH_SYSTEM_ARCHITECTURE.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 12. 추가 참고 자료

### 12.1 관련 문서

- **`START_HERE.md`**: 프로젝트 전체 개요
- **`LAW_SEARCH_SYSTEM_ARCHITECTURE.md`**: 시스템 아키텍처 상세
- **`PHASE_1_5_RNE_INTEGRATION_SUMMARY.md`**: RNE 통합 과정
- **`law/SYSTEM_GUIDE.md`**: Phase 1-7 학습 가이드
- **`law/STEP/README.md`**: 데이터 파이프라인 실행 가이드
- **`docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`**: Neo4j 설정 가이드

### 12.2 테스트 파일

- **`test_17jo.py`**: 17조 검색 테스트
- **`test_17jo_direct.py`**: Direct Neo4j 쿼리 테스트
- **`test_17jo_domain.py`**: Domain Agent 테스트
- **`test_phase1_5_rne.py`**: RNE 통합 테스트
- **`test_phase3_synthesis.py`**: Phase 3 종합 테스트
- **`test_a2a_collaboration.py`**: A2A 협업 테스트
- **`test_relationship_search.py`**: 관계 검색 테스트

### 12.3 핵심 개념 요약

| 개념 | 설명 |
|------|------|
| **GraphTeam** | Multi-Agent 협업 프레임워크 (논문 기반) |
| **A2A** | Agent-to-Agent 통신 프로토콜 |
| **RNE** | Relationship-aware Node Embedding (그래프 확장) |
| **RRF** | Reciprocal Rank Fusion (검색 결과 병합) |
| **Self-Assessment** | 에이전트가 GPT-4o로 자기 능력 평가 |
| **Hybrid Search** | Exact + Vector + Relationship 3-in-1 |
| **Domain** | 법률 분야별 에이전트 (5개) |
| **HANG** | 법률 조항 (항) 노드 (1,477개) |
| **KR-SBERT** | 한국어 특화 임베딩 모델 (768-dim) |
| **OpenAI Embedding** | 관계 임베딩 모델 (3072-dim) |

---

## 끝

이 문서는 법률 검색 시스템의 모든 알고리즘을 PPT 제작에 최적화된 형태로 설명합니다. 각 Phase별 상세 알고리즘, 실제 코드 위치, 실행 예시, 시각화 다이어그램을 포함하여 발표 준비에 필요한 모든 정보를 제공합니다.

**작성자**: Law Search System Specialist
**작성일**: 2025-11-17
**버전**: 1.0
**문서 경로**: `D:\Data\11_Backend\01_ARR\backend\docs\2025-11-17-LAW_SEARCH_ALGORITHMS_EXPLAINED.md`
