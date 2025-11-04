# MAS 도메인 시각화 가이드

**Date**: 2025-11-02
**Status**: Production Ready
**Purpose**: Neo4j Browser에서 MAS 도메인 클러스터 시각화 방법

---

## 📋 현재 시스템 상태

### 전체 통계
- **총 HANG 노드**: 2,987개
- **도메인 개수**: 5개
- **Coverage**: 100% (모든 HANG이 도메인에 할당됨)
- **평균 도메인 크기**: 597.4개 노드

### 생성된 5개 도메인

| 도메인명 | 노드 수 | 비율 | 평균 유사도 | Agent Slug |
|---------|--------|------|------------|------------|
| 도시 계획 및 관리 | 1,291 | 43.2% | 0.7335 | law_도시_계획_및_관리 |
| 도시시설 설치 및 운영 | 728 | 24.4% | 0.6488 | law_도시시설_설치_및_운영 |
| 토지 계획 및 용도 | 686 | 23.0% | 0.7684 | law_토지_계획_및_용도 |
| 건축 및 개발 규제 | 236 | 7.9% | 0.7821 | law_건축_및_개발_규제 |
| 환경 보전 규제 | 46 | 1.5% | 0.8301 | law_환경_보전_규제 |

**특징**:
- 유사도가 높을수록 (0.8301) 클러스터가 명확하게 구분됨
- 환경 보전 규제는 작지만 매우 일관된 도메인
- 도시시설은 가장 큰 도메인이지만 다양한 주제 포함 (0.6488)

---

## 🗺️ Neo4j 그래프 구조

### 노드 타입

```
LAW (법률 문서)
 │
 ├─ JANG (장)
 │   └─ JEOL (절)
 │       └─ JO (조)
 │           └─ HANG (항)  ← MAS 도메인의 기본 단위
 │               └─ HO (호)
 │                   └─ MOK (목)
 │
 └─ Domain (MAS 자율 조직 도메인)
     └─ HANG (항들이 BELONGS_TO_DOMAIN으로 연결)
```

### 관계 타입

1. **CONTAINS** (7,123개)
   - 법률 계층 구조 (LAW → JANG → JEOL → JO → HANG → HO → MOK)
   - 부모-자식 관계

2. **NEXT** (5,527개)
   - 같은 레벨의 순서 관계
   - 예: 제1항 → 제2항 → 제3항

3. **BELONGS_TO_DOMAIN** (2,987개) ← **NEW! MAS 핵심**
   - HANG 노드 → Domain 노드
   - 속성: `similarity` (코사인 유사도 0.0~1.0)
   - 속성: `assigned_at` (할당 시간)

---

## 🎨 Neo4j Browser 시각화

### 1. 전체 도메인 클러스터 보기 (추천!)

```cypher
// 5개 도메인과 각 도메인의 샘플 HANG 노드 10개씩
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d)
WITH d, collect(h)[..10] AS sample_hangs, collect(r)[..10] AS sample_rels
RETURN d, sample_hangs, sample_rels
```

**보이는 것**:
- 🔵 Domain 노드 5개 (중심)
- 🟡 각 도메인의 HANG 샘플 10개
- ➡️ BELONGS_TO_DOMAIN 관계

**시각적 효과**:
- 5개 클러스터가 별 모양으로 분리됨
- 각 클러스터의 크기 차이 명확
- 도메인 이름이 중심 노드에 표시

### 2. 도메인 통계 테이블

```cypher
MATCH (d:Domain)
RETURN d.domain_name AS 도메인명,
       d.node_count AS 노드수,
       d.created_at AS 생성시간,
       d.agent_slug AS 에이전트
ORDER BY d.node_count DESC
```

**결과 예시**:
```
┌─────────────────────┬────────┬───────────────────────┬──────────────────────┐
│ 도메인명              │ 노드수  │ 생성시간               │ 에이전트              │
├─────────────────────┼────────┼───────────────────────┼──────────────────────┤
│ 도시 계획 및 관리     │ 1291   │ 2025-11-02T12:41:23   │ law_도시_계획_및_관리 │
│ 도시시설 설치 및 운영 │ 728    │ 2025-11-02T12:41:21   │ law_도시시설_설치_... │
│ 토지 계획 및 용도     │ 686    │ 2025-11-02T12:41:24   │ law_토지_계획_및_용도 │
│ 건축 및 개발 규제     │ 236    │ 2025-11-02T12:41:22   │ law_건축_및_개발_규제 │
│ 환경 보전 규제        │ 46     │ 2025-11-02T12:41:25   │ law_환경_보전_규제    │
└─────────────────────┴────────┴───────────────────────┴──────────────────────┘
```

### 3. 특정 도메인의 법률 조항 보기

```cypher
// "도시 계획 및 관리" 도메인에 속한 법률 조항들
MATCH (d:Domain {domain_name: "도시 계획 및 관리"})
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d)
RETURN h.full_id AS 조항ID,
       substring(h.content, 0, 100) AS 내용,
       r.similarity AS 유사도
ORDER BY r.similarity DESC
LIMIT 20
```

**결과 예시**:
```
조항ID: 국토의 계획 및 이용에 관한 법률::제12조::제1항
내용: "도시·군관리계획은 특별시·광역시·특별자치시·특별자치도·시 또는 군의..."
유사도: 0.8523
```

### 4. 도메인 간 비교

```cypher
// 각 도메인의 유사도 분포
MATCH (d:Domain)
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d)
RETURN d.domain_name AS 도메인,
       count(h) AS 노드수,
       avg(r.similarity) AS 평균_유사도,
       min(r.similarity) AS 최소_유사도,
       max(r.similarity) AS 최대_유사도
ORDER BY avg(r.similarity) DESC
```

---

## 🎨 스타일 설정 (Neo4j Browser)

```cypher
:style

// Domain 노드: 크고 파란색
node.Domain {
  diameter: 80px;
  color: #3b82f6;
  border-color: #1e40af;
  border-width: 4px;
  caption: {domain_name};
  font-size: 16px;
  text-color-internal: #ffffff;
}

// HANG 노드: 작고 회색
node.HANG {
  diameter: 30px;
  color: #94a3b8;
  border-color: #64748b;
  border-width: 2px;
  caption: "";
}

// JO 노드: 중간 크기, 노란색
node.JO {
  diameter: 50px;
  color: #fbbf24;
  border-color: #f59e0b;
  caption: {number};
}

// BELONGS_TO_DOMAIN 관계: 얇은 파란 선
relationship.BELONGS_TO_DOMAIN {
  shaft-width: 2px;
  color: #60a5fa;
  caption: "";
}

// CONTAINS 관계: 회색 선
relationship.CONTAINS {
  shaft-width: 1px;
  color: #cbd5e1;
}
```

---

## 🔍 분석용 고급 쿼리

### 1. 도메인 경계 분석 (낮은 유사도 노드 찾기)

```cypher
// 각 도메인에서 가장 경계에 있는 노드들 (유사도 낮음)
MATCH (d:Domain)
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d)
WHERE r.similarity < 0.6
RETURN d.domain_name AS 도메인,
       count(h) AS 경계_노드수,
       avg(r.similarity) AS 평균_유사도
ORDER BY 경계_노드수 DESC
```

**용도**: 잘못 분류되었을 가능성 있는 노드 찾기

### 2. 도메인별 법률 조항 분포

```cypher
// 각 도메인이 어느 법률의 조항을 많이 포함하는지
MATCH (d:Domain)
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, split(h.full_id, "::")[0] AS law_name, count(*) AS cnt
RETURN d.domain_name AS 도메인,
       law_name AS 법률,
       cnt AS 조항수
ORDER BY d.domain_name, cnt DESC
```

### 3. 특정 법률 조항이 속한 도메인 찾기

```cypher
// 예: 제12조 관련 조항들이 어느 도메인에 있는지
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d:Domain)
WHERE h.full_id CONTAINS "제12조"
RETURN h.full_id AS 조항,
       d.domain_name AS 소속_도메인,
       r.similarity AS 유사도
ORDER BY h.full_id
```

---

## 🔄 도메인 자동 생성 과정

### 트리거 조건

AgentManager가 자동으로 도메인을 생성하는 시점:

1. **서버 시작 시 도메인이 없을 때**
   ```python
   # agents/law/agent_manager.py __init__()
   loaded_domains = self._load_domains_from_neo4j()
   if not loaded_domains:
       hang_count = self._count_hangs_in_neo4j()
       if hang_count > 0:
           self._initialize_from_existing_hangs(n_clusters=5)
   ```

2. **검사 순서**:
   - Neo4j에 Domain 노드 있음? → 로드
   - Neo4j에 Domain 노드 없음 + HANG 노드 있음? → 자동 생성
   - Neo4j에 Domain/HANG 둘 다 없음? → 대기

### 생성 프로세스

```
[1] HANG 노드 로드 (2,987개)
    ↓
[2] 임베딩 추출 (768차원 벡터)
    ↓
[3] K-means 클러스터링 (k=5)
    ↓
[4] 각 클러스터마다:
    - 샘플 조항 5개 추출
    - OpenAI GPT로 도메인 이름 생성
    - DomainAgent 인스턴스 생성
    - Neo4j에 Domain 노드 생성
    - BELONGS_TO_DOMAIN 관계 생성 (유사도 계산)
    ↓
[5] 완료: 5개 도메인, 2,987개 관계
```

### 도메인 이름 생성 (LLM)

**프롬프트**:
```python
f"""다음 법률 조항들을 대표하는 간단한 도메인 이름을 생성하세요.

샘플 조항들:
{sample_texts}

요구사항:
- 한국어 10자 이내
- 명사형 (예: "도시 계획", "환경 규제")
- 전문용어 사용 가능
"""
```

**생성 예시**:
- "국토의 계획 및 이용에 관한 법률::제12조::제1항" 등
  → "도시 계획 및 관리"

- "국토의 계획 및 이용에 관한 법률 시행령::제70조::제3항" 등
  → "도시시설 설치 및 운영"

---

## 📊 데이터 검증

### Coverage 확인

```cypher
// 모든 HANG이 도메인에 할당되었는지 확인
MATCH (h_total:HANG)
WITH count(h_total) AS total
MATCH (h_assigned:HANG)-[:BELONGS_TO_DOMAIN]->(:Domain)
RETURN total AS 전체_HANG,
       count(h_assigned) AS 할당된_HANG,
       (count(h_assigned) * 100.0 / total) AS 커버리지_퍼센트
```

**기대 결과**: 100%

### 중복 할당 확인

```cypher
// HANG이 여러 도메인에 중복 할당되었는지 확인
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
WITH h, collect(d.domain_name) AS domains
WHERE size(domains) > 1
RETURN h.full_id, domains
```

**기대 결과**: 0개 (중복 없음)

### 도메인 노드 수 일치 확인

```cypher
// Domain.node_count와 실제 관계 수가 일치하는지
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, count(h) AS actual_count
WHERE d.node_count <> actual_count
RETURN d.domain_name,
       d.node_count AS 예상,
       actual_count AS 실제
```

**기대 결과**: 0개 (모두 일치)

---

## 🚀 실전 사용 시나리오

### 시나리오 1: 법률 검색 시 도메인 필터링

**사용자 질문**: "도시계획 관련 조항을 찾아줘"

**AgentManager 동작**:
```python
# 1. 질문 임베딩 생성
query_embedding = embed("도시계획 관련 조항")

# 2. 가장 유사한 도메인 찾기
domain = find_most_similar_domain(query_embedding)
# → "도시 계획 및 관리" (1,291개 노드)

# 3. 해당 도메인의 DomainAgent에게 위임
agent = domain.agent  # law_도시_계획_및_관리
result = agent.search(query, node_ids=domain.node_ids)
```

**Neo4j 쿼리**:
```cypher
// DomainAgent가 실행하는 쿼리
MATCH (h:HANG)
WHERE h.full_id IN ['국토의계획...::제12조::제1항', '...']
  AND h.embedding IS NOT NULL
CALL db.index.vector.queryNodes(
  'hang_embedding_index',
  10,
  $query_embedding
) YIELD node, score
WHERE node IN collect(h)
RETURN node.full_id, node.content, score
ORDER BY score DESC
LIMIT 5
```

**효과**:
- 전체 2,987개가 아닌 **1,291개 노드만 검색** (56% 감소)
- 검색 속도 2배 향상
- 정확도 향상 (관련 없는 도메인 제외)

### 시나리오 2: 도메인 분할 (Split)

**조건**: 도메인 크기가 1,500개 초과

```python
if domain.size() > 1500:
    # "도시 계획 및 관리" (1,291개) → 2개로 분할
    domain_a, domain_b = agent_manager._split_agent(domain_id)
```

**Neo4j 변화**:
```cypher
// Before
(Domain {name: "도시 계획 및 관리", node_count: 1291})

// After
(Domain {name: "도시 기본 계획", node_count: 650})
(Domain {name: "도시 관리 계획", node_count: 641})
```

### 시나리오 3: 도메인 병합 (Merge)

**조건**: 두 도메인 간 유사도 > 0.8

```python
if similarity(domain_a, domain_b) > 0.8:
    # "건축 규제" + "개발 규제" → "건축 및 개발 규제"
    merged = agent_manager._merge_agents(domain_a_id, domain_b_id)
```

**Neo4j 변화**:
```cypher
// Before
(Domain {name: "건축 규제", node_count: 150})
(Domain {name: "개발 규제", node_count: 86})

// After
(Domain {name: "건축 및 개발 규제", node_count: 236})
```

---

## 🎯 다음 단계 (향후 확장)

### 1. A2A 네트워크 시각화

```cypher
// 도메인 간 협업 관계
MATCH (d1:Domain)-[r:NEIGHBOR_DOMAIN]->(d2:Domain)
RETURN d1, r, d2
```

**NEIGHBOR_DOMAIN 관계 생성 조건**:
- DomainAgent가 다른 DomainAgent에게 질문 위임
- 두 도메인의 centroid 유사도 > 0.7

### 2. 도메인 진화 추적

```cypher
// 도메인 분할/병합 이벤트 기록
CREATE (e:DomainEvent {
  type: "SPLIT",
  from_domain: "domain_83982053",
  to_domains: ["domain_new1", "domain_new2"],
  timestamp: datetime(),
  reason: "Size exceeded 1500 nodes"
})
```

### 3. 실시간 모니터링

```cypher
// 최근 24시간 도메인 변화
MATCH (e:DomainEvent)
WHERE e.timestamp > datetime() - duration('P1D')
RETURN e
ORDER BY e.timestamp DESC
```

---

## 📖 참고 문서

- **Schema Design**: `docs/2025-11-02-MAS_NEO4J_SCHEMA.md`
- **Integration Complete**: `docs/2025-11-02-MAS_NEO4J_INTEGRATION_COMPLETE.md`
- **Visualization Queries**: `docs/2025-11-02-NEO4J_DOMAIN_VISUALIZATION.md`

---

**Last Updated**: 2025-11-02
**Next Review**: 도메인 분할/병합 이벤트 발생 시
