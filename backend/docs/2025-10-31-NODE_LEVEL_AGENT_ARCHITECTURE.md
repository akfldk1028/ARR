# 노드 레벨 에이전트 아키텍처 (Node-Level MAS)

## 💡 핵심 아이디어

**기존 계획**: 중앙화된 LawSpecialist 에이전트 1개
**새로운 비전**: 각 법률 노드마다 에이전트 배치, 에이전트 간 A2A 통신

```
기존 (중앙화):
사용자 → LawSpecialist → Neo4j → 결과

새로운 비전 (분산):
사용자 → QueryCoordinator
            ↓ A2A
         [법률::제13조 Agent]
            ↓ A2A
         [시행령::제5조 Agent] ←→ [시행령::제6조 Agent]
            ↓ A2A
         [시행규칙::제3조 Agent]
            ↓
         통합 결과
```

---

## 🤔 순차적 사고 과정

### 1단계: 개념 명확화

#### 질문 1: "노드별 에이전트"의 의미는?

**Option A**: 각 HANG 노드마다 에이전트 (2,987개 에이전트)
```
Neo4j: 2,987개 HANG 노드
  ↓
2,987개 MicroAgent (각각 독립 실행)
```

**Option B**: 노드 타입별 에이전트 (LAW, JO, HANG 등)
```
Neo4j:
  - 3개 LAW → 3개 LawAgent
  - N개 JO → N개 JoAgent
  - 2,987개 HANG → 2,987개 HangAgent
```

**Option C**: 계층별 에이전트 클러스터
```
LawLevelAgents (3개):
  - 법률Agent
  - 시행령Agent
  - 시행규칙Agent

ArticleLevelAgents (수백 개):
  - 각 조(JO)마다 1개

ParagraphLevelAgents (2,987개):
  - 각 항(HANG)마다 1개
```

**Option D**: 도메인별 에이전트 (의미적 클러스터링)
```
ThematicAgents:
  - 도시계획Agent (관련 노드 100개 담당)
  - 건축규제Agent (관련 노드 150개 담당)
  - 토지이용Agent (관련 노드 200개 담당)
  ...
```

---

### 2단계: 장단점 분석

#### Option A: 각 HANG마다 에이전트

**장점**:
- ✅ 완전 분산 (진정한 MAS)
- ✅ 각 조항의 맥락을 에이전트가 완전히 이해
- ✅ 확장성 극대화

**단점**:
- ❌ 2,987개 에이전트 관리 복잡도
- ❌ 메모리/리소스 오버헤드 엄청남
- ❌ 에이전트 간 조정 복잡
- ❌ 5,000 PDF 처리 시 500,000개 에이전트!

**평가**: 🔴 비현실적

---

#### Option B: 노드 타입별 에이전트

**장점**:
- ✅ 구조가 명확 (LAW, JO, HANG 타입별)
- ✅ 계층 구조 반영

**단점**:
- ❌ 여전히 수천 개 에이전트
- ❌ 타입별 역할이 불명확 (모든 HANG이 같은 역할?)

**평가**: 🟡 구현 가능하지만 비효율적

---

#### Option C: 계층별 에이전트 클러스터 ⭐

**장점**:
- ✅ 관리 가능한 에이전트 수 (3~수백 개)
- ✅ 계층 구조 자연스럽게 반영
- ✅ 에이전트 역할 명확
- ✅ 확장 가능

**단점**:
- ⚠️ 조(JO) 레벨 에이전트 여전히 많음 (수백 개)

**평가**: 🟢 유망! 하지만 조정 필요

---

#### Option D: 도메인별 에이전트 (의미적 클러스터링) ⭐⭐

**장점**:
- ✅ **관리 가능한 에이전트 수** (10~50개)
- ✅ **의미적으로 관련된 노드를 하나의 에이전트가 관리**
- ✅ 에이전트 전문화 (도시계획 전문가, 건축 전문가 등)
- ✅ 확장성 뛰어남
- ✅ 사용자 쿼리와 자연스럽게 매핑

**단점**:
- ⚠️ 클러스터링 알고리즘 필요
- ⚠️ 에이전트 경계 모호할 수 있음

**평가**: 🟢🟢 최적!

---

### 3단계: 추천 아키텍처 (Option D 기반)

#### 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────┐
│                      사용자 쿼리                             │
│                  "도시계획 수립 절차는?"                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              QueryCoordinator Agent                         │
│  - 쿼리 분석 & 관련 도메인 식별                                │
│  - "도시계획" 키워드 → UrbanPlanningAgent 선택                 │
└─────────────────────┬───────────────────────────────────────┘
                      │ A2A
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │  Urban  │ │Building │ │  Land   │
    │Planning │ │  Code   │ │  Use    │
    │ Agent   │ │ Agent   │ │ Agent   │
    │         │ │         │ │         │
    │담당 노드:│ │담당 노드:│ │담당 노드:│
    │100개    │ │150개    │ │200개    │
    └────┬────┘ └────┬────┘ └────┬────┘
         │ A2A       │ A2A       │ A2A
         └───────────┼───────────┘
                     ▼
         ┌───────────────────────┐
         │   통합 & 순위화         │
         └───────────────────────┘
```

#### 에이전트 분류 (클러스터링)

**Step 1: 임베딩 기반 클러스터링**

```python
from sklearn.cluster import KMeans
import numpy as np

# 모든 HANG 노드의 임베딩 수집
embeddings = []
hang_ids = []

with neo4j.driver.session() as session:
    result = session.run("""
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN id(h) as hang_id, h.embedding as embedding, h.content as content
    """)

    for record in result:
        hang_ids.append(record['hang_id'])
        embeddings.append(record['embedding'])

embeddings = np.array(embeddings)

# KMeans 클러스터링 (20개 클러스터)
n_clusters = 20
kmeans = KMeans(n_clusters=n_clusters, random_state=42)
clusters = kmeans.fit_predict(embeddings)

# 각 클러스터에 에이전트 할당
for cluster_id in range(n_clusters):
    # 클러스터에 속한 노드들
    cluster_nodes = [hang_ids[i] for i in range(len(hang_ids)) if clusters[i] == cluster_id]

    # 클러스터 대표 텍스트 (centroid 가장 가까운 노드)
    centroid = kmeans.cluster_centers_[cluster_id]
    # ... 에이전트 생성
```

**Step 2: 도메인 레이블링 (LLM 활용)**

```python
# 각 클러스터의 대표 텍스트로 도메인 이름 생성
def label_cluster(cluster_texts):
    prompt = f"""다음 법률 조항들의 공통 주제를 한 단어로 요약하세요:

{cluster_texts}

주제:"""

    response = llm.complete(prompt)
    return response  # 예: "도시계획", "건축규제", "토지이용"

# 각 클러스터에 도메인 이름 할당
cluster_domains = {}
for cluster_id, nodes in cluster_map.items():
    # 대표 텍스트 추출
    sample_texts = [get_hang_content(node) for node in nodes[:5]]
    domain_name = label_cluster(sample_texts)
    cluster_domains[cluster_id] = domain_name
```

**예상 결과**:
```python
cluster_domains = {
    0: "도시계획",      # 120개 노드
    1: "건축규제",      # 180개 노드
    2: "토지이용",      # 150개 노드
    3: "개발행위허가",   # 90개 노드
    4: "용도지역",      # 200개 노드
    ...
    19: "기타규정"      # 80개 노드
}
```

---

### 4단계: 도메인 에이전트 구현

#### DomainAgent 클래스

```python
# agents/worker_agents/implementations/domain_agent.py

from ..base.base_worker import BaseWorkerAgent
from graph_db.algorithms.core.semantic_rne import SemanticRNE

class DomainAgent(BaseWorkerAgent):
    """
    특정 법률 도메인 담당 에이전트

    속성:
    - domain_name: 도메인 이름 (예: "도시계획")
    - node_ids: 담당하는 HANG 노드 ID 리스트
    - neighbors: 이웃 도메인 에이전트 리스트
    """

    def __init__(self, agent_card, domain_name, node_ids):
        super().__init__(agent_card)
        self.domain_name = domain_name
        self.node_ids = set(node_ids)
        self.neighbors = []  # 나중에 설정

        # 검색 알고리즘 (자기 도메인만)
        self.rne = SemanticRNE(None, self._get_scoped_repository(), model)

    def _get_scoped_repository(self):
        """자기 도메인 노드만 검색하는 Repository"""
        class ScopedLawRepository(LawRepository):
            def __init__(self, neo4j, allowed_nodes):
                super().__init__(neo4j)
                self.allowed_nodes = allowed_nodes

            def vector_search(self, query_emb, top_k):
                # 일반 검색
                results = super().vector_search(query_emb, top_k * 3)

                # 자기 도메인 노드만 필터링
                filtered = [(hid, sim) for hid, sim in results
                           if hid in self.allowed_nodes]

                return filtered[:top_k]

        return ScopedLawRepository(self.neo4j, self.node_ids)

    async def process_message(self, message, context_id, session_id):
        """
        쿼리 처리

        1. 자기 도메인에서 검색
        2. 관련성 있으면 이웃 에이전트에게 A2A 요청
        3. 결과 통합
        """

        # [1] 자기 도메인 검색
        my_results, _ = self.rne.execute_query(
            query_text=message,
            similarity_threshold=0.75,
            max_results=5
        )

        # [2] 이웃에게 문의 (관련성 높을 경우)
        neighbor_results = []
        if self._should_ask_neighbors(message, my_results):
            for neighbor_agent in self.neighbors:
                # A2A 프로토콜로 이웃에게 요청
                response = await self._call_neighbor(
                    neighbor_agent,
                    message,
                    context_id
                )
                neighbor_results.extend(response['results'])

        # [3] 결과 통합
        all_results = self._merge_results(my_results, neighbor_results)

        # [4] LLM 해석
        interpretation = await self._generate_interpretation(message, all_results)

        return {
            'domain': self.domain_name,
            'results': all_results,
            'interpretation': interpretation
        }

    def _should_ask_neighbors(self, message, my_results):
        """이웃 에이전트에게 물어볼지 판단"""
        # 내 도메인 결과가 부족하면 이웃에게 문의
        if len(my_results) < 3:
            return True

        # 평균 유사도가 낮으면 이웃에게 문의
        avg_similarity = sum(r['relevance_score'] for r in my_results) / len(my_results)
        if avg_similarity < 0.80:
            return True

        return False

    async def _call_neighbor(self, neighbor_agent, message, context_id):
        """A2A 프로토콜로 이웃 에이전트 호출"""
        from agents.a2a_client import A2AClient

        client = A2AClient(base_url="http://localhost:8000")
        response = await client.send_message(
            agent_slug=neighbor_agent.slug,
            message=message,
            context_id=context_id
        )

        return response
```

---

### 5단계: 에이전트 네트워크 구성

#### 이웃 관계 설정

**기준**: 에이전트가 담당하는 노드들 간 cross_law 관계

```python
def build_agent_network(domain_agents):
    """
    에이전트 간 이웃 관계 설정

    A 에이전트와 B 에이전트가 이웃인 조건:
    - A의 노드와 B의 노드 사이에 cross_law 관계가 N개 이상 존재
    """

    # 각 에이전트 쌍마다
    for agent_a in domain_agents:
        for agent_b in domain_agents:
            if agent_a == agent_b:
                continue

            # cross_law 관계 개수 세기
            cross_law_count = count_cross_law_edges(
                agent_a.node_ids,
                agent_b.node_ids
            )

            # 임계값 이상이면 이웃 등록
            if cross_law_count >= 10:
                agent_a.neighbors.append(agent_b)

def count_cross_law_edges(nodes_a, nodes_b):
    """두 노드 집합 간 cross_law 관계 개수"""
    with neo4j.driver.session() as session:
        result = session.run("""
            MATCH (ha:HANG)<-[:CONTAINS*]-(law_a:LAW)
                  -[:IMPLEMENTS*]->(law_b:LAW)
                  -[:CONTAINS*]->(hb:HANG)
            WHERE id(ha) IN $nodes_a
              AND id(hb) IN $nodes_b
            RETURN COUNT(*) as count
        """, nodes_a=list(nodes_a), nodes_b=list(nodes_b))

        return result.single()['count']
```

**예시 네트워크**:
```
[도시계획 Agent] ←→ [건축규제 Agent]  (cross_law: 45개)
       ↓                    ↓
[토지이용 Agent] ←→ [개발행위허가 Agent]  (cross_law: 30개)
       ↓
[용도지역 Agent]
```

---

### 6단계: QueryCoordinator (진입점)

```python
# agents/worker_agents/implementations/query_coordinator.py

class QueryCoordinator(BaseWorkerAgent):
    """
    쿼리 조정자

    역할:
    1. 사용자 쿼리 분석
    2. 관련 도메인 에이전트 선택
    3. 에이전트 호출 & 결과 통합
    """

    def __init__(self, agent_card, domain_agents):
        super().__init__(agent_card)
        self.domain_agents = domain_agents  # {domain_name: DomainAgent}

    async def process_message(self, message, context_id, session_id):
        # [1] 쿼리 임베딩
        query_emb = self.model.encode(message)

        # [2] 관련 도메인 선택 (여러 개 가능)
        relevant_domains = self._select_domains(query_emb, top_k=3)

        # [3] 선택된 도메인 에이전트들에게 병렬 요청
        tasks = []
        for domain_name in relevant_domains:
            agent = self.domain_agents[domain_name]
            task = agent.process_message(message, context_id, session_id)
            tasks.append(task)

        # 병렬 실행
        responses = await asyncio.gather(*tasks)

        # [4] 결과 통합 & 순위화
        all_results = []
        for response in responses:
            all_results.extend(response['results'])

        # 중복 제거 & 순위화
        all_results = self._deduplicate_and_rank(all_results)

        # [5] 최종 해석
        final_interpretation = await self._generate_final_interpretation(
            message,
            all_results,
            responses  # 각 도메인의 해석 포함
        )

        return final_interpretation

    def _select_domains(self, query_emb, top_k):
        """쿼리와 가장 관련된 도메인 선택"""

        # 각 도메인의 대표 임베딩 계산 (centroid)
        domain_embeddings = {}
        for domain_name, agent in self.domain_agents.items():
            # 도메인 노드들의 평균 임베딩
            embeddings = [get_hang_embedding(nid) for nid in agent.node_ids]
            centroid = np.mean(embeddings, axis=0)
            domain_embeddings[domain_name] = centroid

        # 쿼리와 유사도 계산
        similarities = {}
        for domain_name, domain_emb in domain_embeddings.items():
            sim = cosine_similarity(query_emb, domain_emb)
            similarities[domain_name] = sim

        # Top-k 선택
        top_domains = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [domain for domain, sim in top_domains]
```

---

### 7단계: 실제 동작 시뮬레이션

#### 시나리오: "도시계획 수립 절차는?"

```
[사용자]
"도시계획 수립 절차는?"
  ↓
[QueryCoordinator]
  - 쿼리 임베딩 생성
  - 도메인 유사도 계산:
    * 도시계획: 0.92
    * 건축규제: 0.76
    * 개발행위허가: 0.71
  - Top-3 선택: [도시계획, 건축규제, 개발행위허가]
  ↓ A2A (병렬)
  ├─→ [도시계획 Agent]
  │     - 자기 도메인 검색 (120개 노드)
  │     - 결과: 5개 (평균 유사도 0.88)
  │     - 이웃 문의 필요 없음
  │     - 해석: "도시계획은 국토부가 수립하며..."
  │
  ├─→ [건축규제 Agent]
  │     - 자기 도메인 검색 (180개 노드)
  │     - 결과: 2개 (평균 유사도 0.79)
  │     - 이웃 문의: [토지이용 Agent]
  │     ↓ A2A
  │     [토지이용 Agent]
  │       - 검색: 1개 (유사도 0.77)
  │     ↑ 응답
  │     - 통합 결과: 3개
  │     - 해석: "건축과 관련된 절차는..."
  │
  └─→ [개발행위허가 Agent]
        - 자기 도메인 검색 (90개 노드)
        - 결과: 3개 (평균 유사도 0.82)
        - 해석: "개발행위 허가는..."
  ↓ 응답
[QueryCoordinator]
  - 통합: 11개 결과 (5+3+3)
  - 중복 제거: 9개
  - 순위화: 유사도 기준
  - 최종 해석 생성:
    """
    도시계획 수립 절차는 다음과 같습니다:

    [도시계획 Agent의 해석]
    ...

    관련하여 건축규제와 개발행위허가도 함께 고려해야 합니다:
    [건축규제 Agent의 해석]
    [개발행위허가 Agent의 해석]
    """
  ↓
[사용자]
(통합 답변 수신)
```

---

### 8단계: 장점 분석

#### 기존 계획 (중앙화) vs 노드 레벨 MAS (분산)

| 항목 | 중앙화 (LawSpecialist 1개) | 분산 (DomainAgent 20개) |
|------|---------------------------|------------------------|
| **에이전트 수** | 1개 | 20개 |
| **관리 복잡도** | ⭐ (낮음) | ⭐⭐⭐ (중간) |
| **확장성** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **병렬 처리** | ❌ | ✅ (3개 동시) |
| **전문성** | ⭐⭐ | ⭐⭐⭐⭐⭐ (도메인별) |
| **에이전트 간 협업** | ❌ | ✅ (A2A) |
| **응답 시간** | 2초 | 0.8초 (병렬) |
| **정확도** | 88% | 92% (예상) |

#### 구체적 장점

**1. 병렬 처리**:
```
중앙화: 순차 검색 (2초)
  쿼리 → 벡터 검색 (0.5초) → RNE 확장 (1.0초) → 해석 (0.5초)

분산: 병렬 검색 (0.8초)
  쿼리 → 3개 도메인 병렬 (각 0.6초) → 통합 (0.2초)
```

**2. 전문성**:
```
중앙화: 모든 법률을 하나의 에이전트가 처리
  - 도메인 전문성 낮음
  - 맥락 이해 제한적

분산: 각 도메인 에이전트가 전문화
  - 도시계획Agent는 도시계획만 깊이 이해
  - 시스템 프롬프트도 도메인별 최적화
```

**3. 확장성**:
```
중앙화: 5,000 PDF 추가 시
  - LawSpecialist 1개가 500,000 노드 처리
  - 검색 시간 증가

분산: 5,000 PDF 추가 시
  - 새 도메인 에이전트 10개 추가 (총 30개)
  - 각 에이전트당 노드 수는 비슷 (10,000~20,000개)
  - 검색 시간 유지
```

**4. 에이전트 간 협업** (핵심!):
```
예시: "도시계획과 건축규제의 관계는?"

중앙화:
  LawSpecialist → 두 도메인 검색 → 통합 (단순)

분산:
  QueryCoordinator
    ↓ A2A
  [도시계획 Agent] ←→ [건축규제 Agent]
    ↓ 대화             ↓ 대화
  "내 도메인에서는..." "내 도메인에서는..."
    ↓ 협상
  "우리 도메인 간 cross_law 관계가 45개 있어요"
    ↓ 통합
  더 풍부한 답변
```

---

### 9단계: 단점 & 과제

#### 단점

**1. 복잡도 증가**:
- 20개 에이전트 관리
- 에이전트 간 통신 오버헤드
- 디버깅 어려움

**2. 일관성 유지**:
- 각 에이전트가 다른 해석 제공 가능
- 통합 시 모순 발생 가능

**3. 클러스터링 품질**:
- 잘못된 클러스터링 시 에이전트 효율 저하
- 도메인 경계 모호

#### 해결 방안

**1. 모니터링 대시보드**:
```python
# 에이전트 상태 모니터링
class AgentMonitor:
    def get_agent_stats(self):
        return {
            agent.domain_name: {
                'queries_handled': agent.query_count,
                'avg_response_time': agent.avg_time,
                'neighbor_calls': agent.neighbor_call_count
            }
            for agent in domain_agents
        }
```

**2. 에이전트 재조정**:
```python
# 주기적으로 클러스터링 재실행 (월 1회)
def recalibrate_agents():
    # 새로운 데이터 기반으로 클러스터링
    new_clusters = kmeans.fit_predict(new_embeddings)

    # 에이전트 재배치
    for agent in domain_agents:
        agent.node_ids = new_cluster_map[agent.cluster_id]
```

---

### 10단계: 구현 로드맵

#### Phase 1: 프로토타입 (2주)

**목표**: 3개 도메인 에이전트로 POC

```
1. 클러스터링 (3개):
   - 도시계획Agent (1,000개 노드)
   - 건축규제Agent (1,000개 노드)
   - 토지이용Agent (987개 노드)

2. DomainAgent 구현

3. QueryCoordinator 구현

4. 테스트:
   - "도시계획 수립 절차는?"
   - "건축과 토지이용의 관계는?"
```

#### Phase 2: 확장 (2주)

**목표**: 20개 도메인 에이전트

```
1. 전체 클러스터링 (20개)

2. 이웃 관계 설정

3. A2A 통신 최적화

4. 모니터링 대시보드
```

#### Phase 3: 대량 데이터 (2주)

**목표**: 5,000 PDF 처리

```
1. 배치 클러스터링

2. 동적 에이전트 생성

3. 성능 튜닝
```

---

## 🎯 결론

### 중앙화 vs 분산 비교

| 측면 | 중앙화 (기존 계획) | 분산 (노드 레벨 MAS) |
|------|-------------------|---------------------|
| **구현 난이도** | ⭐⭐ (낮음) | ⭐⭐⭐⭐ (높음) |
| **확장성** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **성능** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **혁신성** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **MAS 철학 부합** | ⭐ | ⭐⭐⭐⭐⭐ |

### 추천: 하이브리드 접근

**Phase 1**: 중앙화 (빠른 구현)
- LawSpecialist 1개로 시작
- 기능 검증

**Phase 2**: 분산 (점진적 전환)
- 3개 도메인 에이전트로 확장
- 성능 비교

**Phase 3**: 완전 분산 (최종)
- 20개 도메인 에이전트
- 진정한 MAS 구현

---

**작성일**: 2025-10-31
**작성자**: Claude Code
**다음 논의**: Phase 1 프로토타입 구현 계획
