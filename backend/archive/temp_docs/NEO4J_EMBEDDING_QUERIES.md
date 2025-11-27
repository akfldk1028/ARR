# Neo4j Browser에서 임베딩 확인하는 방법

## 접속 방법
1. 브라우저에서 **http://localhost:7474** 접속
2. Connect URL: `neo4j://127.0.0.1:7687`
3. Username: `neo4j`
4. Password: `11111111`

## 확인 쿼리들

### 1. 임베딩 개수 확인 (가장 기본)
```cypher
// 임베딩이 있는 노드 vs 없는 노드
MATCH (h:HANG)
RETURN
  count(CASE WHEN h.embedding IS NOT NULL THEN 1 END) as with_embedding,
  count(CASE WHEN h.embedding IS NULL THEN 1 END) as without_embedding,
  count(h) as total
```

**결과 예상**:
```
with_embedding: 1586
without_embedding: 0
total: 1586
```

---

### 2. 임베딩 차원 확인 (중요!)
```cypher
// 임베딩 차원 확인
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN
  size(h.embedding) as dimension,
  count(h) as node_count
```

**결과 예상**:
```
dimension: 3072
node_count: 1586
```

---

### 3. 샘플 노드 확인 (임베딩 내용 보기)
```cypher
// 임베딩이 있는 노드 5개 샘플
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN
  h.full_id as 조항ID,
  h.law_name as 법률명,
  h.number as 항번호,
  substring(h.content, 0, 50) as 내용샘플,
  size(h.embedding) as 임베딩차원,
  h.embedding[0..5] as 임베딩처음5개값
LIMIT 5
```

**결과 예상**:
| 조항ID | 법률명 | 항번호 | 내용샘플 | 임베딩차원 | 임베딩처음5개값 |
|--------|--------|--------|----------|-----------|----------------|
| 국토의 계획 및... | 국토의 계획... | 1 | "별표 제1호의... | 3072 | [0.0193, -0.0214, ...] |

---

### 4. 특정 법률의 임베딩 확인
```cypher
// 국토의 계획 및 이용에 관한 법률의 임베딩 확인
MATCH (h:HANG)
WHERE h.law_name CONTAINS '국토의 계획'
  AND h.embedding IS NOT NULL
RETURN
  h.full_id as 조항,
  size(h.embedding) as 차원,
  substring(h.content, 0, 30) as 내용
ORDER BY h.full_id
LIMIT 10
```

---

### 5. 임베딩 값 통계 (수치 분포 확인)
```cypher
// 임베딩 값의 통계
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
WITH h.embedding as emb
UNWIND emb as value
RETURN
  min(value) as 최소값,
  max(value) as 최대값,
  avg(value) as 평균값,
  stDev(value) as 표준편차
LIMIT 1
```

**결과 예상**:
```
최소값: -0.5 ~ -1.0
최대값: 0.5 ~ 1.0
평균값: 0에 가까운 값
표준편차: 0.1 ~ 0.3
```

---

### 6. 유사도 검색 테스트 (가장 중요!)
```cypher
// 특정 조항과 유사한 조항 찾기
MATCH (target:HANG {full_id: '국토의 계획 및 이용에 관한 법률::제1조::①'})
WHERE target.embedding IS NOT NULL

MATCH (h:HANG)
WHERE h.embedding IS NOT NULL

WITH target, h,
     reduce(dot = 0.0, i IN range(0, size(h.embedding)-1) |
            dot + h.embedding[i] * target.embedding[i]) as similarity
ORDER BY similarity DESC
LIMIT 5

RETURN
  h.full_id as 유사조항,
  substring(h.content, 0, 50) as 내용,
  round(similarity * 1000) / 1000 as 유사도
```

**결과 예상**:
| 유사조항 | 내용 | 유사도 |
|---------|------|--------|
| 국토의 계획...::제1조::① | (원본) | 1.000 |
| 국토의 계획...::제2조::① | "국토"란 대한민국의... | 0.65 |
| 국토의 계획...::제3조::① | 국가 및 지방자치단체는... | 0.58 |

---

### 7. 벡터 인덱스 확인
```cypher
// 벡터 인덱스 상태 확인
SHOW INDEXES
```

**찾아야 할 것**:
- `hang_embedding_index` - State: ONLINE, Type: VECTOR

---

### 8. 임베딩 없는 노드 찾기 (문제 확인용)
```cypher
// 혹시 임베딩이 없는 노드가 있는지 확인
MATCH (h:HANG)
WHERE h.embedding IS NULL
RETURN
  h.full_id as 조항,
  h.content as 내용
LIMIT 10
```

**결과 예상**: (0 rows) - 임베딩이 모두 있어야 정상

---

### 9. 법률별 임베딩 통계
```cypher
// 법률별 임베딩 개수
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN
  h.law_name as 법률,
  count(h) as 임베딩노드수,
  size(h.embedding) as 차원
ORDER BY count(h) DESC
```

---

### 10. 그래프 시각화 (구조 확인)
```cypher
// LAW -> JANG -> JO -> HANG 구조 시각화
MATCH path = (law:LAW)-[:CONTAINS*]->(hang:HANG)
WHERE hang.embedding IS NOT NULL
RETURN path
LIMIT 1
```

**시각적으로 확인**: 법률 계층 구조 + 임베딩이 HANG 노드에 있는지

---

## 문제 해결 쿼리

### 임베딩이 중복된 차원인지 확인
```cypher
// 3072가 진짜인지, 1536x2인지 확인
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
WITH h.embedding as emb
RETURN
  size(emb) as 전체크기,
  size(emb[0..1536]) as 앞절반,
  size(emb[1536..3072]) as 뒷절반
LIMIT 1
```

### 임베딩 무결성 확인
```cypher
// NULL이나 NaN 값이 있는지 확인
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
WITH h.embedding as emb
UNWIND emb as value
WITH value
WHERE value IS NULL OR NOT (value >= -1000 AND value <= 1000)
RETURN count(value) as 이상한값개수
```

**결과 예상**: 0 (이상한 값 없어야 정상)

---

## 빠른 확인 순서

1. **http://localhost:7474** 접속
2. **쿼리 1번 실행** → 1586/0/1586 확인
3. **쿼리 2번 실행** → 3072 차원 확인
4. **쿼리 6번 실행** → 유사도 검색 작동 확인

이 3개만 확인하면 임베딩이 제대로 되었는지 알 수 있습니다!

---

## 예상 결과 요약

| 항목 | 값 |
|------|-----|
| 전체 HANG 노드 | 1,586개 |
| 임베딩 있음 | 1,586개 (100%) |
| 임베딩 차원 | 3072 |
| 임베딩 모델 | OpenAI text-embedding-3-large |
| 벡터 인덱스 | hang_embedding_index (ONLINE) |
| 유사도 검색 | 작동함 |

---

## 추가 팁

### 성능 확인
```cypher
// 임베딩 쿼리 성능 테스트
PROFILE
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN count(h)
```

### 임베딩 샘플 다운로드 (JSON)
```cypher
// 임베딩 데이터 샘플 추출
MATCH (h:HANG)
WHERE h.embedding IS NOT NULL
RETURN {
  id: h.full_id,
  dimension: size(h.embedding),
  embedding: h.embedding
} as data
LIMIT 1
```

Neo4j Browser에서 결과를 JSON으로 다운로드 가능합니다.
