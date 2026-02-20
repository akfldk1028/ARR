# Neo4j 법령 그래프 스키마 (2025-10-26 업데이트)

> **실제 구현된 스키마**를 정확히 반영합니다. 국토계획법 시스템 기준 (3,976개 노드, 7,023개 관계)

---

## 📊 데이터 현황

### 전체 통계
- **총 노드**: 3,976개
- **총 관계**: 7,023개
- **법률 문서**: 3개 (법률, 시행령, 시행규칙)
- **총 조문**: 1,053개 조, 1,586개 항, 1,025개 호, 263개 목

### 파싱 현황
- **법률**: 1,554 units (201,519자) ✓ 전체 내용 파싱됨
- **시행령**: 2,078 units (294,414자) ✓ 전체 내용 파싱됨
- **시행규칙**: 341 units (54,267자) ✓ 전체 내용 파싱됨

---

## 🔷 노드 타입 (Node Types)

### 1. LAW (법률 문서) - 3개

```cypher
(:LAW {
  name: String,              // 법률명 (예: "국토의 계획 및 이용에 관한 법률")
  full_id: String,           // 고유 ID (법률명)
  law_category: String,      // "법률", "시행령", "시행규칙"
  law_type: String,          // 법률 유형
  base_law_name: String,     // 기본 법률명 (약칭)
  total_units: Integer,      // 총 하위 단위 개수
  agent_id: String,          // 에이전트 ID (예: "agent_국토계획법")
  created_at: DateTime
})
```

**예시:**
```
name: "국토의 계획 및 이용에 관한 법률 시행령"
law_category: "시행령"
total_units: 2078
```

### 2. JANG (장) - 24개

```cypher
(:JANG {
  title: String,             // 장 제목 (예: "도시ㆍ군관리계획")
  unit_number: String,       // 장 번호 (예: "2")
  full_id: String,           // 고유 ID (법률명::제2장)
  law_name: String,          // 소속 법률명
  law_category: String,      // "법률", "시행령", "시행규칙"
  order: Integer,            // 순서
  created_at: DateTime
})
```

### 3. JEOL (절) - 22개

```cypher
(:JEOL {
  title: String,             // 절 제목 (예: "지구단위계획")
  unit_number: String,       // 절 번호 (예: "4")
  full_id: String,           // 고유 ID (법률명::제12장::제4절)
  content: String,           // 절 제목 전체
  law_name: String,
  law_category: String,
  order: Integer,
  created_at: DateTime
})
```

### 4. JO (조) - 1,053개 ⚠️ 제목만 저장!

```cypher
(:JO {
  title: String,             // 조 제목 (예: "도시ㆍ군기본계획 수립을 위한 기초조사 및 공청회")
  content: String,           // ⚠️ 제목만! (32자 정도, 실제 내용은 HANG에)
  unit_number: String,       // 조 번호 (예: "20조")
  full_id: String,           // 고유 ID (법률명::제3장::제20조)
  law_name: String,
  law_category: String,
  base_law_name: String,
  agent_id: String,
  order: Integer,
  line_number: Integer,
  unit_path: String,         // 경로 (예: "제3장_제20조")
  created_at: DateTime
})
```

**중요:** JO 노드는 **제목만** 저장! 실제 조문 내용은 하위 HANG 노드에 있음!

### 5. HANG (항) - 1,586개 ✓ 실제 조문 내용!

```cypher
(:HANG {
  content: String,           // ✓ 실제 조문 내용! (수백 자)
  unit_number: String,       // 항 번호 (예: "①", "②")
  full_id: String,           // 고유 ID
  law_name: String,
  law_category: String,
  base_law_name: String,
  agent_id: String,
  order: Integer,
  created_at: DateTime
})
```

**예시:**
```
unit_number: "①"
content: "도시ㆍ군기본계획을 수립하거나 변경하는 경우에는 제 치시장ㆍ특별자치도지사ㆍ시장 또는 군수로, 광역도시계획은 도시ㆍ군기본계획으로 본다. <개정 2011. 4. 14.>..." (수백 자)
```

### 6. HO (호) - 1,025개

```cypher
(:HO {
  content: String,           // 호 내용
  unit_number: String,       // 호 번호 (예: "1", "2", "17")
  full_id: String,
  law_name: String,
  law_category: String,
  order: Integer,
  created_at: DateTime
})
```

### 7. MOK (목) - 263개

```cypher
(:MOK {
  content: String,           // 목 내용
  unit_number: String,       // 목 문자 (예: "가", "나")
  full_id: String,
  law_name: String,
  law_category: String,
  order: Integer,
  created_at: DateTime
})
```

---

## 🔗 관계 타입 (Relationship Types)

### 계층 관계 (모두 CONTAINS 사용)

```cypher
// 전체 계층 구조
(:LAW)-[:CONTAINS {order: Integer}]->(:JANG)
(:JANG)-[:CONTAINS {order: Integer}]->(:JEOL)
(:JEOL)-[:CONTAINS {order: Integer}]->(:JO)

// 장/절 없는 경우 직접 연결
(:LAW)-[:CONTAINS {order: Integer}]->(:JO)  // 94개 직접 연결

// 조문 계층
(:JO)-[:CONTAINS {order: Integer}]->(:HANG)
(:HANG)-[:CONTAINS {order: Integer}]->(:HO)
(:HO)-[:CONTAINS {order: Integer}]->(:MOK)
```

**실제 경로 예시:**
```
LAW (국토계획법 시행령)
 └── JANG (제12장 벌칙)
      └── JEOL (제4절 지구단위계획)
           └── JO (213개 조)
                └── HANG (547개 항) ← 실제 내용!
                     └── HO
                          └── MOK
```

---

## 📑 실제 데이터 분포

### 노드별 개수
| 노드 타입 | 개수 | 설명 |
|----------|------|------|
| LAW | 3 | 법률, 시행령, 시행규칙 |
| JANG | 24 | 장 |
| JEOL | 22 | 절 |
| JO | 1,053 | 조 (제목만) |
| **HANG** | **1,586** | **항 (실제 내용!)** |
| HO | 1,025 | 호 |
| MOK | 263 | 목 |

### LAW → JO 경로 길이 분포
| 경로 길이 | 개수 | 설명 |
|----------|------|------|
| 1 | 94 | LAW → JO 직접 연결 |
| 2 | 281 | LAW → JANG → JO |
| 3 | 678 | LAW → JANG → JEOL → JO |

### JEOL 노드 하위 구조 통계
- **최소 하위 노드**: 3개
- **평균 하위 노드**: 30.82개
- **최대 하위 노드**: 213개 (제12장 제4절 "지구단위계획")

---

## 🔍 인덱스 (Indexes)

### UNIQUE 제약조건

```cypher
CREATE CONSTRAINT law_fullid_unique FOR (n:LAW) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT jang_fullid_unique FOR (n:JANG) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT jeol_fullid_unique FOR (n:JEOL) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT jo_fullid_unique FOR (n:JO) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT hang_fullid_unique FOR (n:HANG) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT ho_fullid_unique FOR (n:HO) REQUIRE n.full_id IS UNIQUE;
CREATE CONSTRAINT mok_fullid_unique FOR (n:MOK) REQUIRE n.full_id IS UNIQUE;
```

### NOT NULL 제약조건

```cypher
CREATE CONSTRAINT jo_law_name_not_null FOR (n:JO) REQUIRE n.law_name IS NOT NULL;
CREATE CONSTRAINT hang_law_name_not_null FOR (n:HANG) REQUIRE n.law_name IS NOT NULL;
CREATE CONSTRAINT ho_law_name_not_null FOR (n:HO) REQUIRE n.law_name IS NOT NULL;
CREATE CONSTRAINT mok_law_name_not_null FOR (n:MOK) REQUIRE n.law_name IS NOT NULL;
```

### 검색 인덱스

```cypher
// 법률명 검색
CREATE INDEX law_name_idx FOR (n:LAW) ON (n.name);
CREATE INDEX law_category_idx FOR (n:LAW) ON (n.law_category);

// 조 번호 검색
CREATE INDEX jo_number_idx FOR (n:JO) ON (n.unit_number);
CREATE INDEX jo_title_idx FOR (n:JO) ON (n.title);

// 복합 인덱스
CREATE INDEX jo_law_unit_idx FOR (n:JO) ON (n.law_name, n.unit_number);

// 전문 검색
CREATE FULLTEXT INDEX jo_content_fulltext FOR (n:JO) ON EACH [n.title, n.content];
```

---

## 📝 쿼리 예시

### 1. 특정 법률의 모든 조 조회

```cypher
MATCH (law:LAW {law_category: "법률"})-[:CONTAINS*]->(jo:JO)
RETURN jo.unit_number, jo.title, jo.content
ORDER BY jo.order
LIMIT 10
```

### 2. 제20조의 실제 내용 조회 (HANG 포함!)

```cypher
MATCH (jo:JO {unit_number: "20조", law_category: "법률"})
MATCH (jo)-[:CONTAINS]->(hang:HANG)
RETURN jo.title as 조_제목,
       hang.unit_number as 항_번호,
       hang.content as 실제_내용
ORDER BY hang.order
```

**결과:**
```
조_제목: "도시ㆍ군기본계획 수립을 위한 기초조사 및 공청회"
항_번호: "①"
실제_내용: "도시ㆍ군기본계획을 수립하거나 변경하는 경우에는..."
```

### 3. 특정 JEOL의 모든 하위 조 조회

```cypher
MATCH (jeol:JEOL)-[:CONTAINS]->(jo:JO)
WHERE id(jeol) = 798  // 제4절 지구단위계획
RETURN count(jo) as 조_개수
// 결과: 213개
```

### 4. LAW → JANG → JEOL → JO 전체 경로 확인

```cypher
MATCH path = (law:LAW)-[:CONTAINS]->(jang:JANG)-[:CONTAINS]->(jeol:JEOL)-[:CONTAINS]->(jo:JO)
RETURN law.name, jang.title, jeol.title, jo.title
LIMIT 5
```

### 5. 특정 조의 모든 하위 항목 트리 (조 → 항 → 호 → 목)

```cypher
MATCH (jo:JO {unit_number: "20조", law_category: "법률"})
OPTIONAL MATCH (jo)-[:CONTAINS]->(hang:HANG)
OPTIONAL MATCH (hang)-[:CONTAINS]->(ho:HO)
OPTIONAL MATCH (ho)-[:CONTAINS]->(mok:MOK)
RETURN jo.title,
       collect(DISTINCT hang.unit_number) as 항_목록,
       count(DISTINCT hang) as 항_개수,
       count(DISTINCT ho) as 호_개수,
       count(DISTINCT mok) as 목_개수
```

### 6. 전체 노드 개수 통계

```cypher
MATCH (n)
RETURN labels(n)[0] as 노드타입, count(*) as 개수
ORDER BY 개수 DESC
```

---

## ⚠️ 중요 사항

### 1. JO vs HANG 내용 저장 위치

```
JO 노드:
  └── content: "제20조(도시ㆍ군기본계획 수립을 위한 기초조사 및 공청회)"  ← 32자 (제목만!)

HANG 노드:
  └── content: "도시ㆍ군기본계획을 수립하거나 변경하는 경우에는 제 치시장ㆍ특별자치도지사ㆍ시장 또는 군수로..."  ← 수백 자 (실제 내용!)
```

**검색 시 주의:**
- JO 검색: 조 제목 검색
- HANG 검색: 실제 조문 내용 검색 ✓

### 2. 계층 구조가 유연함

모든 법률이 동일한 구조를 가지지 않음:
```
법률 A: LAW → JANG → JEOL → JO → HANG
법률 B: LAW → JO → HANG  (장/절 없음)
```

### 3. JEOL 노드 크기 차이

- 작은 JEOL: 3개 하위 노드
- 큰 JEOL: 213개 하위 노드 (40배 차이!)

---

## 🎯 RAG 시스템 통합

### Neo4j + 벡터 검색 (향후)

현재는 구조화된 그래프만 저장. 벡터 검색 추가 시:

```cypher
// HANG 노드에 벡터 임베딩 추가
(:HANG {
  content: String,
  embedding: [Float]  // 768차원 벡터
})

// 벡터 인덱스 생성
CREATE VECTOR INDEX hang_vector_idx
FOR (n:HANG) ON (n.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}
```

### 하이브리드 검색

1. **벡터 검색** → 의미적으로 유사한 HANG 찾기
2. **그래프 탐색** → 해당 HANG의 상위 JO, JANG 찾기
3. **컨텍스트 확장** → 전후 HANG도 함께 반환

---

**작성일**: 2025-10-26
**기준 데이터**: 국토의 계획 및 이용에 관한 법률 시스템
**검증**: ✓ 실제 Neo4j 데이터베이스 구조 확인 완료
