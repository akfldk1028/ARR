# MAS Neo4j 스키마 설계

**작성일**: 2025-11-02
**목적**: MAS 도메인 정보를 Neo4j에 저장하여 시각화

---

## 🎯 목표

**문제**: 현재 MAS는 메모리에만 존재 → Neo4j에서 확인 불가
**해결**: Domain 노드 추가 → 시각적 클러스터 확인 가능

---

## 📊 추가할 스키마

### 1. Domain 노드

```cypher
(:Domain {
  domain_id: String,              // 고유 ID (예: "domain_001")
  domain_name: String,            // AI 생성 이름 (예: "도시계획")
  agent_slug: String,             // Worker slug (예: "domain-agent-001")
  node_count: Integer,            // 속한 HANG 노드 개수
  centroid_embedding: [Float],    // 도메인 중심 임베딩 (768-dim)
  created_at: DateTime,           // 생성 시각
  updated_at: DateTime            // 업데이트 시각
})
```

**예시**:
```json
{
  "domain_id": "domain_001",
  "domain_name": "도시계획",
  "agent_slug": "domain-agent-001",
  "node_count": 1245,
  "centroid_embedding": [0.123, -0.456, ...],
  "created_at": "2025-11-02T10:30:00",
  "updated_at": "2025-11-02T10:35:00"
}
```

---

### 2. BELONGS_TO_DOMAIN 관계

```cypher
(:HANG)-[:BELONGS_TO_DOMAIN {
  similarity: Float,              // 중심과의 유사도 (0.0~1.0)
  assigned_at: DateTime           // 할당 시각
}]->(:Domain)
```

**예시**:
```cypher
(:HANG {full_id: "국토계획법::제2장::제12조::①"})
  -[:BELONGS_TO_DOMAIN {similarity: 0.89, assigned_at: "2025-11-02T10:30:15"}]->
(:Domain {domain_id: "domain_001", domain_name: "도시계획"})
```

---

### 3. NEIGHBOR_DOMAIN 관계 (A2A 네트워크)

```cypher
(:Domain)-[:NEIGHBOR_DOMAIN {
  cross_law_count: Integer,      // Cross-law 참조 개수
  created_at: DateTime
}]->(:Domain)
```

**예시**:
```cypher
(:Domain {domain_name: "도시계획"})
  -[:NEIGHBOR_DOMAIN {cross_law_count: 15}]->
(:Domain {domain_name: "건축규제"})
```

---

## 🔍 전체 그래프 구조

```
┌─────────────────────────────────────────────────────────────┐
│ 기존 구조 (법률 계층)                                         │
├─────────────────────────────────────────────────────────────┤
│ LAW → JANG → JEOL → JO → HANG → HO → MOK                   │
│                                                             │
│ HANG ← 실제 조문 내용 + embedding (768-dim)                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 추가 구조 (MAS 도메인) ✨                                     │
├─────────────────────────────────────────────────────────────┤
│ HANG -[BELONGS_TO_DOMAIN]-> Domain                          │
│                                                             │
│ Domain -[NEIGHBOR_DOMAIN]-> Domain (A2A)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 Neo4j Browser 시각화 예시

### 도메인별 클러스터 보기

```cypher
// 모든 도메인과 속한 HANG 노드 (최대 10개씩)
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, collect(h)[..10] as sample_hangs
RETURN d, sample_hangs
```

**결과 (시각화)**:
```
      [도시계획]
     /    |    \
  HANG  HANG  HANG ...

      [건축규제]
     /    |    \
  HANG  HANG  HANG ...

      [토지이용]
     /    |    \
  HANG  HANG  HANG ...
```

---

### 도메인 통계 확인

```cypher
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
RETURN
  d.domain_name as 도메인,
  d.node_count as 노드개수,
  count(h) as 실제연결,
  d.created_at as 생성시각
ORDER BY d.node_count DESC
```

**결과**:
| 도메인 | 노드개수 | 실제연결 | 생성시각 |
|--------|---------|---------|---------|
| 도시계획 | 1245 | 1245 | 2025-11-02T10:30 |
| 건축규제 | 987 | 987 | 2025-11-02T10:32 |
| 토지이용 | 755 | 755 | 2025-11-02T10:34 |

---

### A2A 네트워크 시각화

```cypher
MATCH (d1:Domain)-[r:NEIGHBOR_DOMAIN]->(d2:Domain)
RETURN d1, r, d2
```

**결과 (그래프)**:
```
[도시계획] <--15--> [건축규제]
     |                  |
     8                  12
     |                  |
  [토지이용] <--6--> [용적률관리]
```

---

### 특정 HANG의 도메인 확인

```cypher
MATCH (h:HANG {full_id: "국토계획법::제2장::제12조::①"})
MATCH (h)-[r:BELONGS_TO_DOMAIN]->(d:Domain)
RETURN
  h.content as 조문내용,
  d.domain_name as 소속도메인,
  r.similarity as 유사도
```

---

## 🔧 인덱스 및 제약조건

### UNIQUE 제약조건

```cypher
CREATE CONSTRAINT domain_id_unique
FOR (n:Domain)
REQUIRE n.domain_id IS UNIQUE;
```

### 검색 인덱스

```cypher
// 도메인 이름 검색
CREATE INDEX domain_name_idx
FOR (n:Domain) ON (n.domain_name);

// 노드 개수 범위 검색
CREATE INDEX domain_node_count_idx
FOR (n:Domain) ON (n.node_count);
```

### 벡터 인덱스 (centroid_embedding)

```cypher
CREATE VECTOR INDEX domain_centroid_idx
FOR (n:Domain) ON (n.centroid_embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}
```

---

## 📝 AgentManager 동기화 로직

### 도메인 생성 시

```python
def _create_new_domain(self, hang_ids, embeddings):
    # [1] 메모리에 DomainInfo 생성
    domain_info = DomainInfo(domain_id, domain_name, agent_slug)

    # [2] Neo4j에 Domain 노드 생성 ✨
    self._sync_domain_to_neo4j(domain_info, embeddings)

    # [3] HANG 노드에 관계 추가 ✨
    self._assign_hangs_to_domain_neo4j(hang_ids, domain_id, embeddings)
```

### 도메인 분할 시

```python
def _split_agent(self, domain_info):
    # [1] K-means로 2개 클러스터 생성
    clusters = KMeans(n_clusters=2).fit(embeddings)

    # [2] 메모리에 새 도메인 생성
    new_domain = DomainInfo(...)

    # [3] Neo4j에 반영 ✨
    self._sync_domain_to_neo4j(new_domain, embeddings)
    self._update_domain_assignments_neo4j(...)
```

### 도메인 병합 시

```python
def _merge_agents(self, domain1, domain2):
    # [1] 메모리에서 병합
    merged_domain = self._merge_domain_info(domain1, domain2)

    # [2] Neo4j에 반영 ✨
    self._delete_domain_from_neo4j(domain2.domain_id)
    self._sync_domain_to_neo4j(merged_domain, embeddings)
    self._update_domain_assignments_neo4j(...)
```

---

## 🧪 테스트 쿼리

### 1. 도메인 개수 확인

```cypher
MATCH (d:Domain)
RETURN count(d) as total_domains
```

### 2. 각 도메인의 크기 분포

```cypher
MATCH (d:Domain)
RETURN
  d.domain_name,
  d.node_count,
  d.node_count * 100.0 / 2987 as percentage
ORDER BY d.node_count DESC
```

### 3. 도메인 없는 HANG 찾기

```cypher
MATCH (h:HANG)
WHERE NOT (h)-[:BELONGS_TO_DOMAIN]->(:Domain)
RETURN count(h) as unassigned_hangs
```

### 4. 도메인 간 거리 (중심 임베딩 유사도)

```cypher
MATCH (d1:Domain), (d2:Domain)
WHERE d1 <> d2
WITH d1, d2,
  reduce(dot = 0.0, i IN range(0, size(d1.centroid_embedding)-1) |
    dot + d1.centroid_embedding[i] * d2.centroid_embedding[i]
  ) as dot_product
RETURN
  d1.domain_name,
  d2.domain_name,
  dot_product as similarity
ORDER BY similarity DESC
LIMIT 10
```

---

## 🎨 시각화 활용

### Neo4j Browser 스타일

```cypher
// 도메인은 크고 파란색
node.Domain {
  diameter: 80px;
  color: #3b82f6;
  caption: {domain_name};
}

// HANG은 작고 회색
node.HANG {
  diameter: 30px;
  color: #94a3b8;
  caption: "";
}

// 도메인 관계는 굵게
relationship.NEIGHBOR_DOMAIN {
  shaft-width: 5px;
  color: #10b981;
}
```

### Bloom 시각화 (향후)

- 도메인별 색상 구분
- 노드 크기로 node_count 표시
- 관계 굵기로 cross_law_count 표시

---

## ✅ 장점

### 1. 시각적 확인
- ✅ Neo4j Browser에서 도메인 클러스터 직관적 확인
- ✅ A2A 네트워크 구조 그래프로 보기
- ✅ 도메인 크기 분포 한눈에 파악

### 2. 디버깅
- ✅ 어떤 HANG이 어떤 도메인에 속하는지 즉시 확인
- ✅ 도메인 할당 오류 쉽게 발견
- ✅ 도메인 분할/병합 결과 검증

### 3. 분석
- ✅ 도메인 크기 통계
- ✅ 도메인 간 유사도 분석
- ✅ Cross-law 참조 패턴 분석

### 4. 운영
- ✅ 실시간 모니터링 가능
- ✅ 도메인 재구성 이력 추적
- ✅ 성능 병목 지점 파악

---

## 🚀 구현 계획

### Phase 1: 스키마 추가 (30분)
- [ ] Domain 노드 타입 정의
- [ ] BELONGS_TO_DOMAIN 관계 정의
- [ ] 인덱스 및 제약조건 생성

### Phase 2: AgentManager 동기화 (1시간)
- [ ] `_sync_domain_to_neo4j()` 메서드 추가
- [ ] `_assign_hangs_to_domain_neo4j()` 메서드 추가
- [ ] `_update_domain_assignments_neo4j()` 메서드 추가
- [ ] `_delete_domain_from_neo4j()` 메서드 추가

### Phase 3: 초기 데이터 동기화 (10분)
- [ ] 기존 메모리 도메인 → Neo4j 동기화
- [ ] 기존 HANG → Domain 관계 생성

### Phase 4: 시각화 쿼리 작성 (20분)
- [ ] 도메인 클러스터 쿼리
- [ ] A2A 네트워크 쿼리
- [ ] 통계 쿼리

### Phase 5: 테스트 (30분)
- [ ] 도메인 생성 테스트
- [ ] 도메인 분할 테스트
- [ ] 도메인 병합 테스트
- [ ] 시각화 확인

---

## 📊 예상 결과

### 초기 상태 (2,987 HANG 노드)

```
도메인 5개 생성:
- 도시계획: 1,245 nodes
- 건축규제: 987 nodes
- 토지이용: 755 nodes
- 용적률관리: 512 nodes
- 개발행위: 488 nodes

A2A 네트워크: 10개 연결
```

### Neo4j Browser에서 확인

```cypher
MATCH (d:Domain)
RETURN d.domain_name, d.node_count
ORDER BY d.node_count DESC
```

**결과 그래프**:
- 5개의 큰 Domain 노드 (파란색)
- 각 Domain에 연결된 HANG 노드들
- Domain 간 NEIGHBOR_DOMAIN 관계

---

**다음 단계**: AgentManager에 Neo4j 동기화 로직 추가
