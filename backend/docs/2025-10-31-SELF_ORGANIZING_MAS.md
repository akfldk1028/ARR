# 자가 조직화 MAS (Self-Organizing Multi-Agent System)

## 🔥 문제점 지적

**제가 제안한 방식의 문제**:
```
1. 5,000개 PDF 들어옴
2. 수동으로 클러스터링 실행
3. "이건 도시계획, 이건 건축규제" 수동 분류
4. 도메인별로 에이전트 수동 생성
5. 새 PDF 들어오면? → 처음부터 다시!
```

**문제**:
- ❌ 완전히 수동적
- ❌ 확장 불가능
- ❌ 새 법규마다 재작업
- ❌ 진정한 MAS가 아님

---

## 💡 올바른 접근: 자가 조직화

### 핵심 아이디어

**에이전트가 스스로 생성되고, 진화하고, 소멸한다**

```
[새 PDF 들어옴]
  ↓ 자동 파싱
[임베딩 생성]
  ↓ 자동 분석
[AgentManager]
  ├─ 기존 도메인과 유사? → 기존 에이전트에 추가
  ├─ 새로운 도메인? → 새 에이전트 자동 생성
  ├─ 에이전트 너무 커짐? → 분할
  └─ 에이전트 너무 작음? → 병합
  ↓
[자가 조직화된 에이전트 네트워크]
```

---

## 🏗️ 아키텍처

### 1. AgentManager (메타 에이전트)

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentManager                            │
│  - 에이전트 라이프사이클 관리                                  │
│  - 자동 생성/삭제/병합/분할                                    │
│  - 네트워크 최적화                                            │
└─────────────────────┬───────────────────────────────────────┘
                      │ 관리
          ┌───────────┼───────────┬───────────┐
          ▼           ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Agent 1 │ │ Agent 2 │ │ Agent 3 │ │ Agent N │
    │120 nodes│ │180 nodes│ │150 nodes│ │... nodes│
    └─────────┘ └─────────┘ └─────────┘ └─────────┘
         ↑           ↑           ↑           ↑
         └───────────┴───────────┴───────────┘
              자동으로 생성/삭제됨
```

---

## 📝 구현: AgentManager

### 핵심 클래스

```python
# agents/agent_manager.py

import numpy as np
from sklearn.cluster import DBSCAN
from typing import Dict, List, Set
import logging

logger = logging.getLogger(__name__)

class AgentManager:
    """
    자가 조직화 에이전트 관리자

    역할:
    1. 새 데이터 → 자동 에이전트 할당
    2. 에이전트 생성/삭제/병합/분할
    3. 네트워크 최적화
    """

    def __init__(self, neo4j_service, model):
        self.neo4j = neo4j_service
        self.model = model  # SentenceTransformer

        # 활성 에이전트들
        self.agents: Dict[str, DomainAgent] = {}

        # 클러스터링 설정
        self.min_nodes_per_agent = 50      # 에이전트당 최소 노드
        self.max_nodes_per_agent = 300     # 에이전트당 최대 노드
        self.similarity_threshold = 0.85   # 도메인 할당 임계값

    def process_new_pdf(self, pdf_path):
        """
        새 PDF 자동 처리

        1. 파싱 → Neo4j
        2. 임베딩 생성
        3. 도메인 할당 (기존 or 새로 생성)
        4. 에이전트 업데이트
        """

        logger.info(f"새 PDF 처리: {pdf_path}")

        # [1] 파싱
        from law.core.pdf_extractor import PDFExtractor
        from law.core.law_parser_improved import LawParser

        extractor = PDFExtractor()
        text = extractor.extract(pdf_path)

        parser = LawParser()
        data = parser.parse(text)

        # [2] Neo4j 삽입
        hang_ids = self._insert_to_neo4j(data)
        logger.info(f"Neo4j 삽입: {len(hang_ids)}개 HANG 노드")

        # [3] 임베딩 생성
        embeddings = self._generate_embeddings(hang_ids)

        # [4] 도메인 할당 (핵심!)
        self._assign_to_agents(hang_ids, embeddings)

        # [5] 네트워크 최적화
        self._optimize_network()

        logger.info(f"처리 완료. 현재 에이전트 수: {len(self.agents)}")

    def _assign_to_agents(self, hang_ids: List[int], embeddings: np.ndarray):
        """
        HANG 노드들을 에이전트에 할당

        전략:
        1. 기존 에이전트와 유사도 계산
        2. 임계값 이상이면 기존 에이전트에 추가
        3. 없으면 새 에이전트 생성
        """

        for hang_id, embedding in zip(hang_ids, embeddings):
            # 기존 에이전트들과 유사도 계산
            best_agent, best_similarity = self._find_best_agent(embedding)

            if best_similarity >= self.similarity_threshold:
                # 기존 에이전트에 추가
                logger.info(f"HANG {hang_id} → {best_agent.domain_name} "
                           f"(유사도: {best_similarity:.2f})")
                best_agent.add_node(hang_id, embedding)

                # 에이전트가 너무 커지면 분할
                if len(best_agent.node_ids) > self.max_nodes_per_agent:
                    self._split_agent(best_agent)

            else:
                # 새 에이전트 생성
                logger.info(f"HANG {hang_id} → 새 에이전트 생성 "
                           f"(최고 유사도: {best_similarity:.2f})")
                self._create_new_agent([hang_id], [embedding])

    def _find_best_agent(self, embedding: np.ndarray):
        """
        주어진 임베딩과 가장 유사한 에이전트 찾기

        Returns:
            (best_agent, similarity)
        """

        if not self.agents:
            return None, 0.0

        best_agent = None
        best_similarity = 0.0

        for agent in self.agents.values():
            # 에이전트의 중심(centroid)과 비교
            centroid = agent.get_centroid()
            similarity = self._cosine_similarity(embedding, centroid)

            if similarity > best_similarity:
                best_similarity = similarity
                best_agent = agent

        return best_agent, best_similarity

    def _create_new_agent(self, hang_ids: List[int], embeddings: np.ndarray):
        """
        새 에이전트 자동 생성

        1. 도메인 이름 자동 생성 (LLM)
        2. DomainAgent 인스턴스 생성
        3. 등록
        """

        # 도메인 이름 자동 생성
        domain_name = self._generate_domain_name(hang_ids)

        # 에이전트 생성
        agent_id = f"agent_{len(self.agents) + 1}"
        agent = DomainAgent(
            agent_id=agent_id,
            domain_name=domain_name,
            node_ids=set(hang_ids),
            embeddings=embeddings,
            neo4j=self.neo4j,
            model=self.model
        )

        self.agents[agent_id] = agent
        logger.info(f"✨ 새 에이전트 생성: {domain_name} ({len(hang_ids)}개 노드)")

        return agent

    def _generate_domain_name(self, hang_ids: List[int]):
        """
        LLM으로 도메인 이름 자동 생성

        전략:
        1. HANG 노드들의 내용 샘플링
        2. LLM에게 공통 주제 요청
        3. 한 단어로 요약
        """

        # 샘플 텍스트 추출 (최대 5개)
        sample_texts = []
        for hang_id in hang_ids[:5]:
            content = self._get_hang_content(hang_id)
            sample_texts.append(content[:200])  # 첫 200자

        # LLM 프롬프트
        prompt = f"""다음 법률 조항들의 공통 주제를 짧은 이름(2-4단어)으로 요약하세요:

조항 1: {sample_texts[0]}
조항 2: {sample_texts[1] if len(sample_texts) > 1 else 'N/A'}
조항 3: {sample_texts[2] if len(sample_texts) > 2 else 'N/A'}

공통 주제 (예: "도시계획", "건축규제", "환경보호"):"""

        # LLM 호출
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3
        )

        domain_name = response.choices[0].message.content.strip()
        logger.info(f"LLM 생성 도메인 이름: {domain_name}")

        return domain_name

    def _split_agent(self, agent: 'DomainAgent'):
        """
        에이전트가 너무 커지면 2개로 분할

        전략:
        1. 에이전트 내부에서 KMeans(k=2) 클러스터링
        2. 2개의 새 에이전트 생성
        3. 기존 에이전트 삭제
        """

        logger.info(f"에이전트 분할: {agent.domain_name} "
                   f"({len(agent.node_ids)}개 노드 → 2개 에이전트)")

        # 에이전트 노드들의 임베딩
        embeddings = agent.get_all_embeddings()

        # KMeans(k=2)
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=2, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # 2개 그룹으로 분할
        node_list = list(agent.node_ids)
        group1_ids = [node_list[i] for i in range(len(node_list)) if labels[i] == 0]
        group2_ids = [node_list[i] for i in range(len(node_list)) if labels[i] == 1]

        group1_embs = embeddings[labels == 0]
        group2_embs = embeddings[labels == 1]

        # 새 에이전트 2개 생성
        new_agent1 = self._create_new_agent(group1_ids, group1_embs)
        new_agent2 = self._create_new_agent(group2_ids, group2_embs)

        # 기존 에이전트 삭제
        del self.agents[agent.agent_id]
        logger.info(f"기존 에이전트 삭제: {agent.domain_name}")

        logger.info(f"분할 완료: {new_agent1.domain_name} ({len(group1_ids)}개), "
                   f"{new_agent2.domain_name} ({len(group2_ids)}개)")

    def _merge_agents(self, agent1: 'DomainAgent', agent2: 'DomainAgent'):
        """
        에이전트가 너무 작거나 유사하면 병합

        전략:
        1. 두 에이전트의 노드 합치기
        2. 새 도메인 이름 생성
        3. 기존 에이전트 2개 삭제
        """

        logger.info(f"에이전트 병합: {agent1.domain_name} + {agent2.domain_name}")

        # 노드 합치기
        merged_ids = list(agent1.node_ids.union(agent2.node_ids))
        merged_embs = np.vstack([agent1.get_all_embeddings(),
                                 agent2.get_all_embeddings()])

        # 새 에이전트 생성
        merged_agent = self._create_new_agent(merged_ids, merged_embs)

        # 기존 에이전트 삭제
        del self.agents[agent1.agent_id]
        del self.agents[agent2.agent_id]

        logger.info(f"병합 완료: {merged_agent.domain_name} "
                   f"({len(merged_ids)}개 노드)")

    def _optimize_network(self):
        """
        에이전트 네트워크 최적화

        1. 너무 작은 에이전트 병합
        2. 이웃 관계 재설정
        3. 고아 에이전트 처리
        """

        logger.info("네트워크 최적화 시작")

        # [1] 너무 작은 에이전트들 찾기
        small_agents = [a for a in self.agents.values()
                       if len(a.node_ids) < self.min_nodes_per_agent]

        if small_agents:
            logger.info(f"작은 에이전트 {len(small_agents)}개 발견")

            # 가장 유사한 에이전트와 병합
            for small_agent in small_agents:
                # 가장 유사한 큰 에이전트 찾기
                best_partner = None
                best_similarity = 0.0

                for other_agent in self.agents.values():
                    if other_agent == small_agent:
                        continue
                    if len(other_agent.node_ids) < self.min_nodes_per_agent:
                        continue  # 둘 다 작으면 스킵

                    similarity = self._agent_similarity(small_agent, other_agent)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_partner = other_agent

                if best_partner:
                    self._merge_agents(small_agent, best_partner)

        # [2] 이웃 관계 재설정
        self._rebuild_neighbor_network()

        logger.info(f"네트워크 최적화 완료. 최종 에이전트 수: {len(self.agents)}")

    def _rebuild_neighbor_network(self):
        """
        에이전트 간 이웃 관계 재설정

        전략:
        - cross_law 관계가 N개 이상 있으면 이웃 등록
        """

        logger.info("이웃 관계 재설정")

        # 모든 에이전트의 이웃 초기화
        for agent in self.agents.values():
            agent.neighbors = []

        # 모든 에이전트 쌍 검사
        agent_list = list(self.agents.values())
        for i, agent_a in enumerate(agent_list):
            for agent_b in agent_list[i+1:]:
                # cross_law 관계 개수
                cross_law_count = self._count_cross_law(
                    agent_a.node_ids,
                    agent_b.node_ids
                )

                # 임계값 이상이면 이웃 등록
                if cross_law_count >= 10:
                    agent_a.neighbors.append(agent_b)
                    agent_b.neighbors.append(agent_a)
                    logger.info(f"이웃 등록: {agent_a.domain_name} ←→ "
                               f"{agent_b.domain_name} ({cross_law_count}개 연결)")

    def _count_cross_law(self, nodes_a: Set[int], nodes_b: Set[int]) -> int:
        """두 노드 집합 간 cross_law 관계 개수"""
        with self.neo4j.driver.session() as session:
            result = session.run("""
                MATCH (ha:HANG)<-[:CONTAINS*]-(law_a:LAW)
                      -[:IMPLEMENTS*]->(law_b:LAW)
                      -[:CONTAINS*]->(hb:HANG)
                WHERE id(ha) IN $nodes_a
                  AND id(hb) IN $nodes_b
                RETURN COUNT(*) as count
            """, nodes_a=list(nodes_a), nodes_b=list(nodes_b))

            return result.single()['count']

    def _cosine_similarity(self, emb1, emb2):
        """코사인 유사도"""
        return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

    def _agent_similarity(self, agent1, agent2):
        """두 에이전트 간 유사도 (centroid 기준)"""
        centroid1 = agent1.get_centroid()
        centroid2 = agent2.get_centroid()
        return self._cosine_similarity(centroid1, centroid2)

    # ... (기타 헬퍼 메서드)
```

---

## 🔄 DomainAgent 업데이트

```python
# agents/worker_agents/implementations/domain_agent.py

class DomainAgent(BaseWorkerAgent):
    """
    동적으로 생성/관리되는 도메인 에이전트
    """

    def __init__(self, agent_id, domain_name, node_ids, embeddings, neo4j, model):
        self.agent_id = agent_id
        self.domain_name = domain_name
        self.node_ids = set(node_ids)
        self.embeddings = embeddings  # numpy array
        self.neo4j = neo4j
        self.model = model
        self.neighbors = []

        # 통계
        self.query_count = 0
        self.avg_time = 0.0
        self.created_at = datetime.now()

    def add_node(self, hang_id: int, embedding: np.ndarray):
        """노드 추가 (동적)"""
        self.node_ids.add(hang_id)
        self.embeddings = np.vstack([self.embeddings, embedding])

    def get_centroid(self) -> np.ndarray:
        """에이전트의 중심(평균 임베딩)"""
        return np.mean(self.embeddings, axis=0)

    def get_all_embeddings(self) -> np.ndarray:
        """모든 노드의 임베딩"""
        return self.embeddings

    # ... (기존 process_message 등)
```

---

## 📊 실제 동작 시뮬레이션

### 시나리오 1: 최초 시작 (빈 시스템)

```
[시스템 시작]
AgentManager.agents = {}  # 빈 상태

[PDF 1 투입] "국토계획법.pdf"
  ↓ 파싱
  120개 HANG 노드
  ↓ 임베딩
  ↓ assign_to_agents()
  - 기존 에이전트 없음
  - 새 에이전트 생성!
  ↓ LLM
  도메인 이름: "도시계획"
  ↓
✨ Agent 1 생성: 도시계획 (120개 노드)

AgentManager.agents = {
  "agent_1": DomainAgent("도시계획", 120개 노드)
}
```

---

### 시나리오 2: 유사한 PDF 투입

```
[PDF 2 투입] "도시계획법_개정.pdf"
  ↓ 파싱
  80개 HANG 노드
  ↓ 임베딩
  ↓ assign_to_agents()
  - 기존 에이전트: agent_1 (도시계획)
  - 유사도 계산: 0.92 (>0.85)
  - agent_1에 추가!
  ↓
✅ Agent 1 업데이트: 도시계획 (200개 노드)

AgentManager.agents = {
  "agent_1": DomainAgent("도시계획", 200개 노드)  # 증가
}
```

---

### 시나리오 3: 다른 도메인 PDF 투입

```
[PDF 3 투입] "건축법.pdf"
  ↓ 파싱
  150개 HANG 노드
  ↓ 임베딩
  ↓ assign_to_agents()
  - 기존 에이전트: agent_1 (도시계획)
  - 유사도 계산: 0.68 (<0.85)
  - 새 에이전트 생성!
  ↓ LLM
  도메인 이름: "건축규제"
  ↓
✨ Agent 2 생성: 건축규제 (150개 노드)

AgentManager.agents = {
  "agent_1": DomainAgent("도시계획", 200개 노드),
  "agent_2": DomainAgent("건축규제", 150개 노드)
}

[네트워크 최적화]
  - cross_law 관계: 45개
  - agent_1 ←→ agent_2 이웃 등록
```

---

### 시나리오 4: 에이전트 분할

```
[PDF 4~10 투입] "도시계획 관련 PDF 7개"
  ↓ 모두 agent_1 (도시계획)에 추가
  ↓
Agent 1: 도시계획 (350개 노드)  # max_nodes_per_agent(300) 초과!

[자동 분할 트리거]
  ↓ KMeans(k=2)
  - 클러스터 1: "도시개발계획" (180개)
  - 클러스터 2: "도시관리계획" (170개)
  ↓
✨ Agent 3 생성: 도시개발계획 (180개 노드)
✨ Agent 4 생성: 도시관리계획 (170개 노드)
❌ Agent 1 삭제

AgentManager.agents = {
  "agent_2": DomainAgent("건축규제", 150개 노드),
  "agent_3": DomainAgent("도시개발계획", 180개 노드),
  "agent_4": DomainAgent("도시관리계획", 170개 노드)
}
```

---

### 시나리오 5: 에이전트 병합

```
[PDF 100 투입] "환경보호법.pdf" (소량)
  ↓ 파싱
  30개 HANG 노드  # 너무 적음!
  ↓
✨ Agent 5 생성: 환경보호 (30개 노드)

[최적화 트리거] min_nodes_per_agent(50) 미만
  - agent_5 너무 작음
  - 가장 유사한 에이전트 찾기: agent_3 (유사도 0.78)
  - 병합!
  ↓
✅ Agent 3 업데이트: 도시개발계획+환경 (210개 노드)
❌ Agent 5 삭제

AgentManager.agents = {
  "agent_2": DomainAgent("건축규제", 150개 노드),
  "agent_3": DomainAgent("도시개발계획+환경", 210개 노드),
  "agent_4": DomainAgent("도시관리계획", 170개 노드)
}
```

---

## 🎯 핵심 장점

### 1. 완전 자동화

```
수동 (기존):
  5,000 PDF → 수동 분류 → 수동 에이전트 생성 (불가능!)

자동 (자가 조직화):
  5,000 PDF → AgentManager.process_new_pdf() → 자동 처리!
```

### 2. 적응형 구조

```
시간에 따른 에이전트 진화:

T=0: 에이전트 0개
T=1: 에이전트 1개 (도시계획, 120 노드)
T=2: 에이전트 2개 (도시계획 200, 건축규제 150)
T=5: 에이전트 4개 (분할/병합 발생)
T=10: 에이전트 15개 (5,000 PDF 처리 완료)
```

### 3. 확장성

```
[시스템 부하]
기존 (수동): O(n) - 사람이 일일이 분류
자가 조직화: O(log n) - 자동으로 균형 유지
```

### 4. 진화

```
초기:
  Agent 1: "도시계획" (단일 도메인)

중기:
  Agent 3: "도시개발계획" (세분화)
  Agent 4: "도시관리계획" (세분화)

후기:
  Agent 3: "도시개발계획+환경" (병합으로 연관 도메인 발견)
```

---

## 🚀 구현 로드맵

### Phase 1: AgentManager 구현 (1주)

**목표**: 자동 에이전트 생성

```python
# 테스트
manager = AgentManager(neo4j, model)

# PDF 투입
manager.process_new_pdf("law1.pdf")
manager.process_new_pdf("law2.pdf")
manager.process_new_pdf("law3.pdf")

# 결과 확인
print(f"생성된 에이전트: {len(manager.agents)}개")
for agent in manager.agents.values():
    print(f"  - {agent.domain_name}: {len(agent.node_ids)}개 노드")
```

### Phase 2: 분할/병합 (1주)

**목표**: 에이전트 라이프사이클 관리

```python
# 대량 투입
for pdf in pdf_files:
    manager.process_new_pdf(pdf)

# 자동 최적화 발생
# - 큰 에이전트 자동 분할
# - 작은 에이전트 자동 병합
```

### Phase 3: 실시간 모니터링 (1주)

**목표**: 에이전트 상태 시각화

```python
# 대시보드
http://localhost:8000/agent-dashboard/

[Agent Network Graph]
  도시계획 (180) ←→ 건축규제 (150)
       ↓              ↓
  토지이용 (200) ←→ 개발허가 (120)

[Agent Stats]
  - 총 에이전트: 15개
  - 평균 노드 수: 165개
  - 최근 생성: 환경보호 (1시간 전)
  - 최근 분할: 도시계획 (2시간 전)
```

---

## 🎯 결론

### 제가 놓친 것

**수동 분류의 문제**:
- ❌ 5,000 PDF를 사람이 분류? 불가능
- ❌ 새 법규마다 재분류? 유지보수 불가
- ❌ 진정한 MAS가 아님

### 올바른 접근

**자가 조직화 MAS**:
- ✅ PDF 들어오면 자동 처리
- ✅ 에이전트가 스스로 생성/진화/소멸
- ✅ 네트워크가 데이터에 맞춰 최적화
- ✅ 진정한 분산 지능 시스템

### 다음 단계

1. AgentManager 구현
2. 자동 도메인 발견 (LLM)
3. 분할/병합 로직
4. 실시간 모니터링

이게 진짜 MAS입니다! 🔥

---

**작성일**: 2025-10-31
**작성자**: Claude Code
**다음 작업**: AgentManager 프로토타입 구현
