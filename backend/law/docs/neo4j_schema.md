# Neo4j 법령 그래프 스키마 설계

## 노드 타입 (Node Types)

### 1. 법률 계층 노드

```cypher
(:LAW {
  name: String,              // 법률명 (예: "건축법")
  law_id: String,            // 법률 고유 ID
  promulgation_date: Date,   // 공포일
  enforcement_date: Date,    // 시행일
  law_type: String,          // 법률 유형 (법률/시행령/시행규칙)
  ministry: String           // 소관 부처
})

(:PYEON {
  number: String,            // 편 번호 (예: "1")
  title: String,             // 편 제목
  full_id: String,           // 고유 ID (법률명::제1편)
  path: String               // 경로
})

(:JANG {
  number: String,            // 장 번호 (예: "1")
  title: String,             // 장 제목
  full_id: String,           // 고유 ID
  path: String
})

(:JEOL {
  number: String,            // 절 번호
  title: String,             // 절 제목
  full_id: String,
  path: String
})

(:GWAN {
  number: String,            // 관 번호
  title: String,             // 관 제목
  full_id: String,
  path: String
})

(:JO {
  number: String,            // 조 번호 (예: "3조", "44조의2")
  title: String,             // 조 제목 (예: "적용 제외")
  content: String,           // 전체 내용
  full_id: String,           // 고유 ID (법률명::제3조)
  path: String,              // 경로
  revision_dates: [Date],    // 개정일자 목록
  deleted: Boolean           // 삭제 여부
})

(:HANG {
  number: String,            // 항 번호 (예: "①", "②")
  content: String,           // 항 내용
  full_id: String,
  path: String,
  revision_dates: [Date]
})

(:HO {
  number: String,            // 호 번호 (예: "1", "2")
  content: String,           // 호 내용
  full_id: String,
  path: String,
  referenced_laws: [String]  // 인용 법률 목록
})

(:MOK {
  number: String,            // 목 문자 (예: "가", "나")
  content: String,           // 목 내용
  full_id: String,
  path: String
})
```

## 관계 타입 (Relationship Types)

### 1. 계층 관계 (Hierarchy)

```cypher
// 상위가 하위를 포함하는 관계
(:LAW)-[:CONTAINS {order: Integer}]->(:PYEON)
(:PYEON)-[:CONTAINS {order: Integer}]->(:JANG)
(:JANG)-[:CONTAINS {order: Integer}]->(:JEOL)
(:JEOL)-[:CONTAINS {order: Integer}]->(:GWAN)
(:GWAN)-[:CONTAINS {order: Integer}]->(:JO)

(:LAW)-[:CONTAINS {order: Integer}]->(:JO)  // 편/장/절 없는 경우 직접 연결
(:JANG)-[:CONTAINS {order: Integer}]->(:JO) // 절/관 없는 경우

(:JO)-[:CONTAINS {order: Integer}]->(:HANG)
(:HANG)-[:CONTAINS {order: Integer}]->(:HO)
(:HO)-[:CONTAINS {order: Integer}]->(:MOK)
```

### 2. 순서 관계 (Sequential)

```cypher
// 같은 레벨의 다음 요소
(:JO)-[:NEXT]->(:JO)
(:HANG)-[:NEXT]->(:HANG)
(:HO)-[:NEXT]->(:HO)
(:MOK)-[:NEXT]->(:MOK)
```

### 3. 참조 관계 (Reference)

```cypher
// 조항 간 참조 (예: "제3조에 따라...")
(:JO)-[:REFERENCES {
  context: String,           // 참조 문맥
  reference_type: String     // 참조 유형 (준용/적용/제외 등)
}]->(:JO)

(:HANG)-[:REFERENCES]->(:HANG)
```

### 4. 인용 관계 (Citation)

```cypher
// 타법 인용 (예: 「국토의 계획 및 이용에 관한 법률」)
(:JO)-[:CITES {
  citation_text: String,     // 인용 원문
  citation_type: String      // 인용 유형
}]->(:LAW)

(:HO)-[:CITES]->(:LAW)
```

### 5. 개정 관계 (Revision)

```cypher
// 개정 이력 추적
(:JO)-[:REVISED_BY {
  revision_date: Date,
  revision_type: String,     // 개정/신설/삭제
  law_number: String         // 개정 법률 번호
}]->(:JO)
```

## 인덱스 (Indexes)

```cypher
// 검색 성능 향상을 위한 인덱스
CREATE INDEX law_name_idx FOR (n:LAW) ON (n.name);
CREATE INDEX law_id_idx FOR (n:LAW) ON (n.law_id);
CREATE CONSTRAINT law_fullid_unique FOR (n:LAW) REQUIRE n.full_id IS UNIQUE;

CREATE INDEX jo_number_idx FOR (n:JO) ON (n.number);
CREATE INDEX jo_fullid_idx FOR (n:JO) ON (n.full_id);
CREATE CONSTRAINT jo_fullid_unique FOR (n:JO) REQUIRE n.full_id IS UNIQUE;

CREATE INDEX hang_fullid_idx FOR (n:HANG) ON (n.full_id);
CREATE INDEX ho_fullid_idx FOR (n:HO) ON (n.full_id);
CREATE INDEX mok_fullid_idx FOR (n:MOK) ON (n.full_id);

// 전문 검색을 위한 인덱스
CREATE FULLTEXT INDEX jo_content_fulltext FOR (n:JO) ON EACH [n.title, n.content];
CREATE FULLTEXT INDEX hang_content_fulltext FOR (n:HANG) ON EACH [n.content];
```

## 쿼리 예시

### 1. 특정 법률의 모든 조 조회

```cypher
MATCH (law:LAW {name: "건축법"})-[:CONTAINS*]->(jo:JO)
RETURN jo.number, jo.title, jo.content
ORDER BY jo.number
```

### 2. 특정 조의 전체 계층 구조 조회

```cypher
MATCH path = (law:LAW)-[:CONTAINS*]->(jo:JO {number: "3조"})-[:CONTAINS*]->(child)
RETURN path
```

### 3. 조항 간 참조 네트워크 조회

```cypher
MATCH (jo1:JO)-[r:REFERENCES]->(jo2:JO)
WHERE jo1.full_id STARTS WITH "건축법"
RETURN jo1.number, jo1.title, type(r), jo2.number, jo2.title
```

### 4. 타법 인용 관계 조회

```cypher
MATCH (jo:JO)-[c:CITES]->(law:LAW)
WHERE jo.full_id STARTS WITH "건축법"
RETURN jo.number, jo.title, law.name, c.citation_text
```

### 5. 특정 조의 모든 하위 항목 조회 (트리 구조)

```cypher
MATCH (jo:JO {full_id: "건축법::제3조"})
OPTIONAL MATCH (jo)-[:CONTAINS]->(hang:HANG)
OPTIONAL MATCH (hang)-[:CONTAINS]->(ho:HO)
OPTIONAL MATCH (ho)-[:CONTAINS]->(mok:MOK)
RETURN jo, hang, ho, mok
ORDER BY hang.number, ho.number, mok.number
```

### 6. 개정 이력이 있는 조 조회

```cypher
MATCH (jo:JO)
WHERE size(jo.revision_dates) > 0
RETURN jo.full_id, jo.title, jo.revision_dates
ORDER BY jo.revision_dates[-1] DESC
```

### 7. 키워드로 조문 검색 (전문 검색)

```cypher
CALL db.index.fulltext.queryNodes("jo_content_fulltext", "건축허가")
YIELD node, score
RETURN node.full_id, node.title, node.content, score
ORDER BY score DESC
LIMIT 10
```

## 데이터 모델 특징

### 1. 계층적 구조
- 법률 → 편 → 장 → 절 → 관 → 조 → 항 → 호 → 목
- 유연한 구조: 편/장/절/관은 선택적으로 존재

### 2. 다중 관계
- 계층 관계 (CONTAINS)
- 순서 관계 (NEXT)
- 참조 관계 (REFERENCES, CITES)
- 개정 관계 (REVISED_BY)

### 3. 검색 최적화
- 고유 ID 기반 인덱스
- 전문 검색 인덱스
- 경로 기반 쿼리 지원

### 4. 메타데이터 관리
- 개정일자 추적
- 인용 법률 목록
- 삭제 여부 플래그
