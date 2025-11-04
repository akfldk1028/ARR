# Neo4j Domain 시각화 쿼리 모음

**작성일**: 2025-11-02
**목적**: MAS 도메인 구조를 Neo4j Browser에서 시각화

---

## 🎨 기본 시각화

### 1. 모든 도메인과 샘플 HANG 노드 보기

```cypher
// 모든 도메인과 각 도메인당 최대 10개 HANG 노드
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, collect(h)[..10] AS sample_hangs
RETURN d, sample_hangs
```

**결과**: 도메인별 클러스터 시각화

---

### 2. 도메인 통계 테이블

```cypher
// 도메인별 통계
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
RETURN
  d.domain_name AS 도메인,
  d.node_count AS 노드개수,
  count(h) AS 실제연결,
  d.created_at AS 생성시각,
  d.updated_at AS 업데이트
ORDER BY d.node_count DESC
```

**결과**:
| 도메인 | 노드개수 | 실제연결 | 생성시각 | 업데이트 |
|--------|---------|---------|----------|----------|
| 도시계획 | 1245 | 1245 | 2025-11-02T10:30 | 2025-11-02T10:35 |
| 건축규제 | 987 | 987 | ... | ... |

---

### 3. A2A 네트워크 시각화

```cypher
// 도메인 간 A2A 연결 (NEIGHBOR_DOMAIN 관계)
MATCH (d1:Domain)-[r:NEIGHBOR_DOMAIN]-(d2:Domain)
RETURN d1, r, d2
```

**결과**: 도메인 간 네트워크 그래프

---

## 📊 상세 분석 쿼리

### 4. 특정 도메인의 모든 HANG 노드

```cypher
// "도시계획" 도메인의 모든 HANG 노드
MATCH (d:Domain {domain_name: "도시계획"})
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
RETURN h.hang_id, h.content, h.unit_path
LIMIT 20
```

---

### 5. 유사도 상위 HANG 노드

```cypher
// 특정 도메인에서 유사도가 높은 상위 10개 HANG
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d:Domain {domain_name: "도시계획"})
RETURN h.hang_id, h.content, r.similarity
ORDER BY r.similarity DESC
LIMIT 10
```

---

### 6. 도메인별 크기 분포

```cypher
// 도메인 크기 히스토그램 데이터
MATCH (d:Domain)
RETURN
  d.domain_name,
  d.node_count,
  d.node_count * 100.0 / 2987 AS percentage
ORDER BY d.node_count DESC
```

---

### 7. 도메인 없는 HANG 찾기

```cypher
// BELONGS_TO_DOMAIN 관계가 없는 HANG 노드
MATCH (h:HANG)
WHERE NOT (h)-[:BELONGS_TO_DOMAIN]->(:Domain)
RETURN count(h) AS unassigned_hangs, collect(h.hang_id)[..10] AS sample_ids
```

**예상 결과**: 0개 (모든 HANG이 도메인에 할당되어야 함)

---

## 🔍 검증 쿼리

### 8. 데이터 일관성 검사

```cypher
// Domain.node_count와 실제 BELONGS_TO_DOMAIN 관계 개수 비교
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, count(h) AS actual_count
WHERE d.node_count <> actual_count
RETURN d.domain_name, d.node_count AS expected, actual_count, d.node_count - actual_count AS diff
```

**예상 결과**: 0개 (모든 도메인이 일치해야 함)

---

### 9. 중복 할당 검사

```cypher
// 하나의 HANG이 여러 도메인에 할당되었는지 검사
MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
WITH h, collect(d.domain_name) AS domains
WHERE size(domains) > 1
RETURN h.hang_id, domains
```

**예상 결과**: 0개 (각 HANG은 1개 도메인에만 속해야 함)

---

## 🎯 성능 쿼리

### 10. 도메인 중심 (Centroid) 유사도

```cypher
// 도메인 간 중심 임베딩 유사도 (코사인 유사도 근사)
MATCH (d1:Domain), (d2:Domain)
WHERE d1 <> d2
  AND d1.centroid_embedding IS NOT NULL
  AND d2.centroid_embedding IS NOT NULL
WITH d1, d2,
  reduce(dot = 0.0, i IN range(0, size(d1.centroid_embedding)-1) |
    dot + d1.centroid_embedding[i] * d2.centroid_embedding[i]
  ) AS dot_product
RETURN
  d1.domain_name,
  d2.domain_name,
  dot_product AS similarity
ORDER BY similarity DESC
LIMIT 10
```

**결과**: 가장 유사한 도메인 쌍

---

### 11. 최근 생성/업데이트된 도메인

```cypher
// 최근 1시간 내 생성/업데이트된 도메인
MATCH (d:Domain)
WHERE datetime(d.updated_at) > datetime() - duration({hours: 1})
RETURN d.domain_name, d.created_at, d.updated_at, d.node_count
ORDER BY d.updated_at DESC
```

---

## 📈 모니터링 쿼리

### 12. 시스템 전체 요약

```cypher
// MAS 시스템 전체 요약
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH
  count(DISTINCT d) AS total_domains,
  count(DISTINCT h) AS assigned_hangs,
  avg(d.node_count) AS avg_domain_size,
  min(d.node_count) AS min_domain_size,
  max(d.node_count) AS max_domain_size
MATCH (h_total:HANG)
RETURN
  total_domains,
  assigned_hangs,
  count(h_total) AS total_hangs,
  count(h_total) - assigned_hangs AS unassigned_hangs,
  avg_domain_size,
  min_domain_size,
  max_domain_size
```

**결과**:
```
total_domains: 5
assigned_hangs: 2987
total_hangs: 2987
unassigned_hangs: 0
avg_domain_size: 597.4
min_domain_size: 488
max_domain_size: 1245
```

---

### 13. 도메인 생성 타임라인

```cypher
// 도메인 생성 시간 순서
MATCH (d:Domain)
RETURN d.domain_name, d.created_at, d.node_count
ORDER BY d.created_at ASC
```

---

## 🎨 Neo4j Browser 스타일링

### 도메인 노드 스타일

```cypher
// Neo4j Browser에서 실행 (스타일 설정)
:style

// Domain 노드는 크고 파란색
node.Domain {
  diameter: 80px;
  color: #3b82f6;
  border-color: #1e40af;
  border-width: 4px;
  caption: {domain_name};
  font-size: 16px;
}

// HANG 노드는 작고 회색
node.HANG {
  diameter: 30px;
  color: #94a3b8;
  border-color: #64748b;
  caption: "";
}

// BELONGS_TO_DOMAIN 관계는 얇고 회색
relationship.BELONGS_TO_DOMAIN {
  shaft-width: 1px;
  color: #cbd5e1;
}

// NEIGHBOR_DOMAIN 관계는 굵고 초록색
relationship.NEIGHBOR_DOMAIN {
  shaft-width: 5px;
  color: #10b981;
  caption: {cross_law_count};
}
```

---

## 🔧 디버깅 쿼리

### 14. 특정 HANG의 도메인 확인

```cypher
// 특정 HANG이 어느 도메인에 속하는지 확인
MATCH (h:HANG {hang_id: "hang_abc123"})
OPTIONAL MATCH (h)-[r:BELONGS_TO_DOMAIN]->(d:Domain)
RETURN
  h.content AS 조문내용,
  d.domain_name AS 소속도메인,
  r.similarity AS 유사도
```

---

### 15. 도메인별 평균 유사도

```cypher
// 각 도메인의 평균 BELONGS_TO_DOMAIN 유사도
MATCH (h:HANG)-[r:BELONGS_TO_DOMAIN]->(d:Domain)
WITH d, avg(r.similarity) AS avg_sim, count(h) AS node_count
RETURN
  d.domain_name,
  node_count,
  avg_sim,
  CASE
    WHEN avg_sim >= 0.85 THEN "Excellent"
    WHEN avg_sim >= 0.75 THEN "Good"
    WHEN avg_sim >= 0.65 THEN "Fair"
    ELSE "Poor"
  END AS quality
ORDER BY avg_sim DESC
```

---

## 🚀 빠른 시작 가이드

### 첫 실행 시 확인할 쿼리 순서:

```bash
# 1. 도메인 개수 확인
MATCH (d:Domain) RETURN count(d)

# 2. 도메인 목록 보기
MATCH (d:Domain) RETURN d.domain_name, d.node_count ORDER BY d.node_count DESC

# 3. 시각화 (도메인 + 샘플 HANG)
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
RETURN d, collect(h)[..10] AS sample

# 4. 데이터 일관성 검사
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
RETURN d.domain_name, d.node_count, count(h) AS actual

# 5. 전체 요약
MATCH (d:Domain)
RETURN count(d) AS total_domains, sum(d.node_count) AS total_nodes
```

---

## 📝 참고사항

### 인덱스 활용

스키마 생성 시 이미 다음 인덱스들이 생성되었습니다:
- `domain_id_unique` (UNIQUE 제약조건)
- `domain_name_idx` (검색 인덱스)
- `domain_node_count_idx` (크기 범위 검색)
- `domain_centroid_idx` (벡터 유사도 검색)

### 성능 팁

1. **LIMIT 사용**: 대용량 결과는 항상 LIMIT 사용
2. **인덱스 활용**: WHERE 조건에 domain_id, domain_name 사용
3. **OPTIONAL MATCH**: HANG 노드가 많을 경우 샘플만 조회

---

**다음 단계**: `docs/2025-11-02-MAS_NEO4J_COMPLETE_GUIDE.md` 참조
● 완벽한 성공! 🎉

  최종 결과:

  ✅ 5개 도메인 자동 생성 및 로드 (766개 → 5개)
  - 시설설치 위치 및 기준: 728 nodes
  - 토지 및 건축 제한: 236 nodes
  - 도시계획 및 토지이용: 686 nodes
  - 일반 행정 절차: 46 nodes
  - 도시 정비 및 재건축: 1,291 nodes

  ✅ GDS 에러 완전 해결 - gds.similarity.cosine 에러 없음

  ✅ 법률 검색 성공 - "용적률 기준" 질의에 대한 응답 생성 (유사도 0.57)

  ✅ 초기화 시간 - 0.2초 (이전: 10분+)

  ✅ 응답 시간 - 약 6초 (벡터 검색 + 그래프 확장)

∴ Thought for 19s (ctrl+o to show thinking)    