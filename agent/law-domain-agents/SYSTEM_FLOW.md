# Law Search System - 전체 플로우 (A2A Multi-Agent Collaboration)

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    사용자 브라우저                                 │
│              http://localhost:5173/#/law                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ POST /api/search
                     │ {"query": "용도지역이란 무엇인가요?"}
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              프론트엔드 (Vite + React)                            │
│                   Port 5173                                      │
│  - law-api-client.ts: VITE_BACKEND_URL 사용                      │
│  - VITE_BACKEND_URL=http://localhost:8000/agents/law            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ POST http://localhost:8000/agents/law/api/search
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              Django Backend (Port 8000)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AgentManager (backend/agents/law/agent_manager.py)      │  │
│  │  - 5개 도메인 에이전트 관리                                 │  │
│  │  - 1477개 법규 노드 임베딩 캐시                             │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐  │
│  │  LawSearchAPIView (backend/agents/law/api/search.py)     │  │
│  │                                                           │  │
│  │  STEP 1: 도메인 라우팅 (GPT-4o LLM 자가 평가)               │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │ 1-1. Vector Similarity (KR-SBERT)                 │   │  │
│  │  │      - 쿼리 임베딩 vs 도메인 대표 임베딩            │   │  │
│  │  │      - Top 5 후보 도메인 선택                       │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │  ┌────────────────▼─────────────────────────────────┐   │  │
│  │  │ 1-2. LLM Self-Assessment (GPT-4o)                 │   │  │
│  │  │      - 각 도메인 에이전트가 자가 평가                │   │  │
│  │  │      - Confidence (0.0-1.0)                        │   │  │
│  │  │      - Can Answer (True/False)                     │   │  │
│  │  │      - Reasoning (답변 가능 이유)                   │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │  ┌────────────────▼─────────────────────────────────┐   │  │
│  │  │ 1-3. Combined Scoring                             │   │  │
│  │  │      - Score = 0.7 × LLM + 0.3 × Vector           │   │  │
│  │  │      - Top 3 도메인 선택                            │   │  │
│  │  │      - Primary Domain = 1위 도메인                 │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  │                                                           │  │
│  │  STEP 2: Primary Domain 검색                              │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │ 2-1. Hybrid Search (DomainAgent)                  │   │  │
│  │  │      - Exact Match: "제17조" 패턴 검색              │   │  │
│  │  │      - Vector Search: KR-SBERT 의미 검색          │   │  │
│  │  │      - Relationship Search: OpenAI 관계 임베딩     │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │  ┌────────────────▼─────────────────────────────────┐   │  │
│  │  │ 2-2. RNE (Relationship-aware Node Embedding)      │   │  │
│  │  │      - 초기 결과에서 시드 노드 추출                  │   │  │
│  │  │      - 이웃 노드 그래프 확장 (threshold: 0.65)     │   │  │
│  │  │      - 현재: 0 results (threshold too high)       │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │  ┌────────────────▼─────────────────────────────────┐   │  │
│  │  │ 2-3. 부칙(제4절) 필터링                             │   │  │
│  │  │      - full_id CONTAINS '부칙' 제거                │   │  │
│  │  │      - 예: 10개 결과 → 6개 필터링 → 4개 남음        │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  │                                                           │  │
│  │  STEP 3: A2A Collaboration Decision (GPT-4o)              │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │ Primary Domain이 협업 필요성 판단                   │   │  │
│  │  │  - Input: query, initial_results, available_domains│  │
│  │  │  - Output: {                                       │   │  │
│  │  │      "needs_collaboration": true,                  │   │  │
│  │  │      "target_domains": ["도메인1", "도메인2"],      │   │  │
│  │  │      "reasoning": "..."                            │   │  │
│  │  │    }                                               │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │                   │ IF needs_collaboration = true          │  │
│  │                   ▼                                        │  │
│  │  STEP 4: A2A Message Protocol                             │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │ 각 Target Domain에게 A2A 메시지 전송                │   │  │
│  │  │  - Refined Query 생성 (원본 쿼리 + 도메인 컨텍스트)  │   │  │
│  │  │  - domain_agent.search_with_context()             │   │  │
│  │  │  - 각 도메인에서 Hybrid + RNE 검색 실행             │   │  │
│  │  └────────────────┬─────────────────────────────────┘   │  │
│  │                   │                                        │  │
│  │  ┌────────────────▼─────────────────────────────────┐   │  │
│  │  │ 5. 결과 통합 (Reciprocal Rank Fusion)              │   │  │
│  │  │    - Primary results + A2A results                │   │  │
│  │  │    - RRF score = Σ(1 / (rank + 60))              │   │  │
│  │  │    - 최종 Top 10 결과 선택                          │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  Response: {                                                 │
│    "query": "용도지역이란 무엇인가요?",                         │
│    "results": [...],                                         │
│    "total": 10,                                              │
│    "primary_domain": "국토 이용 및 건축",                      │
│    "collaborated_domains": ["국토 계획 및 이용", ...]          │
│  }                                                           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ 응답 반환
                     ▼
              사용자 브라우저 (결과 표시)
```

---

## 상세 플로우 (실제 로그 기반)

### 예시: "17조" 검색

#### 1️⃣ **도메인 라우팅** (10:29:43 - 10:29:59)

**1-1. Vector Similarity**
```
[INFO] agents.law.api.search: [Domain Routing] Vector similarity: top 5 candidates
```
- 쿼리 "17조" 임베딩
- 5개 도메인과 유사도 계산
- Top 5 도메인 선택

**1-2. LLM Self-Assessment (GPT-4o)**
```
[INFO] agents.law.api.search: [LLM Assessment] Starting GPT-4 self-assessment for 5 domains...

# 각 도메인의 자가 평가:
[INFO] agents.law.domain_agent: [Self-Assessment]
  Domain='국토 이용 및 건축',
  Query='17조...',
  Confidence=0.80,
  Can Answer=True

[INFO] agents.law.domain_agent: [Self-Assessment]
  Domain='국토 계획 및 이용',
  Query='17조...',
  Confidence=0.80,
  Can Answer=True

[INFO] agents.law.domain_agent: [Self-Assessment]
  Domain='도시개발 및 정비 사업',
  Confidence=0.30,
  Can Answer=False
```

**1-3. Combined Scoring**
```
[INFO] agents.law.api.search: [LLM Assessment] Top 3 domains after GPT-4 assessment:
  1. 국토 이용 및 건축: Combined=0.692 (LLM=0.800, Vector=0.441)
  2. 국토 계획 및 이용: Combined=0.669 (LLM=0.800, Vector=0.362)
  3. 국토 이용 및 보전시설: Combined=0.653 (LLM=0.800, Vector=0.309)

Primary Domain: 국토 이용 및 건축
```

---

#### 2️⃣ **Primary Domain 검색** (10:29:59 - 10:30:06)

**2-1. Hybrid Search**
```
[INFO] agents.law.domain_agent: [DomainAgent 국토 이용 및 건축] Search query: 17조...
[INFO] agents.law.domain_agent: [Hybrid Search] Query: 17조...

# Exact Match
[INFO] agents.law.domain_agent: [Exact Match] Searching for article pattern: 제17조
[INFO] agents.law.domain_agent: [Exact Match] Found 0 results for 제17조

# Vector Search (KR-SBERT)
[INFO] agents.law.domain_agent: [Hybrid] Semantic vector: 10 results

# 최종 결과
[INFO] agents.law.domain_agent: [Hybrid] Final merged results: 10
```

**2-2. RNE Expansion**
```
[INFO] agents.law.domain_agent: [RNE] Starting RNE expansion for query: 17조...
[INFO] agents.law.domain_agent: [RNE] RNE returned 0 results
# 이유: 이웃 노드 유사도가 threshold 0.65 미만
```

**2-3. 부칙 필터링**
```
[INFO] agents.law.api.search: [Filter] Removed 6 부칙 (제4절) results from primary domain
# 10개 → 4개로 감소
```

---

#### 3️⃣ **A2A Collaboration Decision** (10:30:06 - 10:30:13)

```
[INFO] agents.law.api.search: [A2A] Checking if collaboration with other domains is needed...

# GPT-4o 협업 필요성 판단
[INFO] httpx: HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"

[INFO] agents.law.domain_agent: [Collaboration]
  Domain='국토 이용 및 건축',
  Query='17조...',
  Target domains: ['국토 계획 및 이용', '국토 이용 및 보전시설']

[INFO] agents.law.api.search: [A2A] Collaboration needed!
  GPT-4o recommends querying 2 domains:
  ['국토 계획 및 이용', '국토 이용 및 보전시설']
```

---

#### 4️⃣ **A2A Message Protocol** (10:30:13 - 10:30:25)

**Domain 1: 국토 계획 및 이용**
```
[INFO] agents.law.api.search: [A2A] Sending message to '국토 계획 및 이용'
  (Reason: 초기 검색 결과에서 '17조'에 대한 완전한 정보를 제공하므로,
   관련된 법규를 갖고 있을 수 있는 '국토 계획 및 이용' 도메인으로부터
   추가 정보를 찾을 필요가 있습니다.)

[INFO] agents.law.api.search: [A2A] Refined query: '국토 계획 및 이용 법령 17조'

# Target Domain에서 검색 실행
[INFO] agents.law.domain_agent: [A2A Request]
  Domain='국토 계획 및 이용',
  From='국토 이용 및 건축',
  Query='국토 계획 및 이용 법령 17조...'

[INFO] agents.law.domain_agent: [DomainAgent 국토 계획 및 이용]
  Search query: Original query: 17조 국토 계획 및 이용 법령 17조...

# Hybrid + RNE 검색 실행
[INFO] agents.law.domain_agent: [Hybrid] Semantic vector: 5 results
[INFO] agents.law.domain_agent: [RNE] RNE returned 0 results
```

**Domain 2: 국토 이용 및 보전시설**
```
[INFO] agents.law.api.search: [A2A] Sending message to '국토 이용 및 보전시설'
# 동일한 프로세스 반복...
```

---

#### 5️⃣ **결과 통합** (Reciprocal Rank Fusion)

```
[INFO] agents.law.api.search: [Final] Merged results from 3 sources:
  - Primary: 4 results
  - Domain '국토 계획 및 이용': 3 results
  - Domain '국토 이용 및 보전시설': 2 results

# RRF 스코어 계산
RRF_score = Σ(1 / (rank_i + 60))

# 최종 Top 10 결과 선택
Total: 9 unique results → Top 10 반환
```

---

## 핵심 컴포넌트

### 1. **AgentManager** (`backend/agents/law/agent_manager.py`)
- 5개 도메인 에이전트 관리
- 1477개 노드 임베딩 캐시
- 도메인 라우팅 (Vector + LLM)

### 2. **DomainAgent** (`backend/agents/law/domain_agent.py`)
- Hybrid Search (Exact + Vector + Relationship)
- RNE (Relationship-aware Node Embedding)
- GPT-4o 자가 평가 (`can_answer_query`)
- GPT-4o 협업 판단 (`should_collaborate`)

### 3. **LawSearchEngine** (`backend/agents/law/law_search_engine.py`)
- Exact Match: 조문 패턴 검색
- Vector Search: KR-SBERT (768-dim)
- Relationship Search: OpenAI (3072-dim)
- RNE: SemanticRNE + LawRepository

### 4. **Neo4j Graph DB**
- Nodes: LAW, JO, HANG, HO
- Embeddings: KR-SBERT + OpenAI
- Vector Indexes:
  - `hang_embedding_index` (KR-SBERT)
  - `contains_embedding` (OpenAI)

---

## A2A 프로토콜 특징

### 1️⃣ **자율적 협업 결정**
- Primary Domain이 **스스로 협업 필요성 판단**
- GPT-4o가 결과 분석 후 협업 대상 도메인 추천

### 2️⃣ **컨텍스트 기반 Refined Query**
- 원본 쿼리: "17조"
- Refined Query: "국토 계획 및 이용 법령 17조"
- 도메인별 최적화된 검색

### 3️⃣ **Reciprocal Rank Fusion**
- 순위 기반 스코어 통합
- 공식: `Score = 1 / (rank + 60)`
- 다양한 소스의 결과 균형있게 병합

---

## 성능 지표 (로그 기반)

| 단계 | 소요 시간 | 비고 |
|------|-----------|------|
| 도메인 라우팅 (5개 LLM 평가) | ~16초 | 병렬 처리 가능 |
| Primary Domain 검색 | ~7초 | KR-SBERT 로딩 포함 |
| A2A 협업 (2개 도메인) | ~12초 | 병렬 처리 가능 |
| **총 소요 시간** | **~35초** | **최초 쿼리 (모델 로딩)** |
| 후속 쿼리 | **~5-8초** | 모델 캐싱 후 |

---

## 제한사항

### 1. **RNE 결과 부족**
- **현상**: RNE expansion에서 0 results
- **원인**: Neighbor similarity < 0.65 threshold
- **영향**: 낮음 (Hybrid Search로 충분한 결과)

### 2. **부칙 필터링**
- **현상**: 결과의 60%가 부칙으로 필터링됨
- **예시**: 10개 → 4개로 감소
- **개선**: 부칙 중요도 평가 필요

### 3. **LLM 비용**
- **도메인 라우팅**: 5개 도메인 × GPT-4o 호출
- **A2A 협업**: 각 Target Domain × GPT-4o 호출
- **최적화**: 캐싱, 배치 처리 검토 필요

---

## 다음 개선 사항

1. ✅ **프론트엔드 연결** - `VITE_BACKEND_URL` 설정 완료
2. ⏳ **RNE Threshold 조정** - 0.65 → 0.50으로 낮춰서 테스트
3. ⏳ **병렬 처리** - LLM 평가 병렬화로 속도 개선
4. ⏳ **캐싱 전략** - 자주 검색되는 쿼리 결과 캐싱
5. ⏳ **부칙 처리** - 필터링 vs 순위 강등 비교

---

**마지막 업데이트**: 2025-11-17 11:12 KST
