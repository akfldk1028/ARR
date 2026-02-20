# Law DomainAgent GraphDB 통합 가이드

**작성일**: 2025-11-06
**목적**: 다음 AI가 법률 시스템 DomainAgent 구조를 이해하기 위한 가이드
**상태**: ✅ GraphDB 통합 완료

---

## 📌 핵심 요약

**DomainAgent가 GraphDB 장점을 완전히 활용하여 법률 질문에 답변합니다.**

- ✅ **이중 임베딩**: KR-SBERT (768-dim) + OpenAI (3072-dim)
- ✅ **관계 임베딩 검색**: 법률 조항 간 관계의 의미 이해
- ✅ **GraphDB 경로 탐색**: 상위 조항 정보 자동 표시
- ✅ **통합 검색 통계**: 노드/관계/확장 검색 결과 분리 표시

---

## 🏗️ 시스템 아키텍처

### 데이터 구조 (Neo4j)

```
LAW (법률)
  ↓ CONTAINS
JO (조) - Articles
  ↓ CONTAINS
HANG (항) - Paragraphs [768-dim embeddings]
  ↓ CONTAINS
HO (호) - Items
  ↓ CONTAINS
MOK (목) - Sub-items

CONTAINS 관계 [3072-dim embeddings]
  - context: "제XX조 → 제X항" 같은 관계 설명
  - semantic_type: STRUCTURAL, DETAIL, EXCEPTION 등
```

### 임베딩 모델

| 대상 | 모델 | 차원 | 용도 |
|------|------|------|------|
| HANG 노드 | KR-SBERT (snunlp/KR-SBERT-V40K-klueNLI-augSTS) | 768 | 직접적인 내용 검색 |
| CONTAINS 관계 | OpenAI text-embedding-3-large | 3072 | 관계의 의미 검색 |

**중요**: 차원이 다르기 때문에 **쿼리마다 2가지 임베딩을 생성**해야 함!

---

## 🔧 핵심 구현 (agents/law/domain_agent.py)

### 1. 이중 임베딩 생성 (lines 570-589)

```python
async def _generate_kr_sbert_embedding(self, query: str) -> List[float]:
    """쿼리 임베딩 생성 - KR-SBERT (768-dim, HANG 노드 검색용)"""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
    embedding = model.encode(query)
    return embedding.tolist()

async def _generate_openai_embedding(self, query: str) -> List[float]:
    """쿼리 임베딩 생성 - OpenAI (3072-dim, 관계 검색용)"""
    from openai import OpenAI
    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=query
    )
    return response.data[0].embedding
```

**왜 필요한가?**
- HANG 노드 벡터 인덱스: 768-dim 필요
- CONTAINS 관계 벡터 인덱스: 3072-dim 필요
- 동일한 쿼리로 둘 다 검색해야 하므로 2가지 임베딩 생성

---

### 2. 통합 검색 흐름 (_search_my_domain, lines 121-179)

```python
async def _search_my_domain(self, query: str) -> List[Dict]:
    # [1] 쿼리 임베딩 생성 (2가지)
    kr_sbert_embedding = await self._generate_kr_sbert_embedding(query)  # 768-dim
    openai_embedding = await self._generate_openai_embedding(query)      # 3072-dim

    # [2] Stage 1-A: Vector Search (노드 임베딩, 768-dim)
    vector_results = await self._vector_search(kr_sbert_embedding, limit=5)

    # [2] Stage 1-B: Relationship Search (관계 임베딩, 3072-dim)
    relationship_results = await self._search_relationships(openai_embedding, limit=5)

    # [2-1] 관계 검색 결과에서 to_id를 HANG 노드로 변환
    relationship_hang_results = []
    for rel in relationship_results:
        # Case 1: to_id가 HANG 노드인 경우
        if '항' in rel['to_id']:
            # 직접 HANG 조회

        # Case 2: to_id가 JO/HO 노드인 경우
        else:
            # 하위 HANG 노드 찾기
            # MATCH (parent {full_id: $parent_id})-[:CONTAINS*1..2]->(hang:HANG)

    # [3] 노드 + 관계 결과 통합
    combined_results = vector_results + relationship_hang_results

    # [4] Stage 2: Graph Expansion (RNE) - 최상위 결과 기준 (768-dim)
    expanded_results = await self._graph_expansion(combined_results[0]['hang_id'], kr_sbert_embedding)

    # [5] Stage 3: Reranking (768-dim)
    all_results = combined_results + expanded_results
    reranked = self._rerank_results(all_results, kr_sbert_embedding)

    return reranked[:10]
```

**검색 단계**:
1. **Stage 1-A**: HANG 노드 벡터 검색 (768-dim)
2. **Stage 1-B**: CONTAINS 관계 벡터 검색 (3072-dim) → HANG 노드로 변환
3. **Stage 2**: GraphDB 확장 (RNE 알고리즘)
4. **Stage 3**: 재정렬 (Reranking)

---

### 3. 관계 임베딩 검색 (_search_relationships, lines 225-269)

```python
async def _search_relationships(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
    """관계 임베딩 검색 (CONTAINS 관계)"""
    query = """
    CALL db.index.vector.queryRelationships(
        'contains_embedding',
        $limit,
        $query_embedding
    ) YIELD relationship, score
    MATCH (from)-[relationship]->(to)
    WHERE score >= 0.65
    RETURN
        from.full_id AS from_id,
        to.full_id AS to_id,
        relationship.context AS context,
        relationship.semantic_type AS semantic_type,
        score AS similarity
    ORDER BY similarity DESC
    LIMIT $limit
    """

    results = self.neo4j_service.execute_query(query, {
        'query_embedding': query_embedding,
        'limit': limit
    })

    return [
        {
            'from_id': r['from_id'],
            'to_id': r['to_id'],
            'context': r['context'],
            'semantic_type': r['semantic_type'],
            'similarity': r['similarity'],
            'stage': 'relationship'
        }
        for r in results
    ]
```

**핵심 포인트**:
- `db.index.vector.queryRelationships()`: Neo4j 관계 벡터 인덱스 검색
- `score >= 0.65`: 유사도 임계값
- `to_id`가 JO/HO 노드일 수 있음 → 이후 HANG 노드로 변환 필요

---

### 4. 관계 대상 노드 변환 (lines 141-184)

**문제**: 관계 검색 결과의 `to_id`가 JO/HO 노드인 경우가 많음
- 예: "국토의 계획 및 이용에 관한 법률::제12장::제1절::제24조" (JO 노드)
- 예: "국토의 계획 및 이용에 관한 법률::제12장::제1절::제48조" (JO 노드)

**해결**:
```python
for rel in relationship_results:
    hang_data_list = []

    # Case 1: to_id가 HANG 노드인 경우 (full_id에 "항" 포함)
    if '항' in rel['to_id']:
        hang_query = """
        MATCH (hang:HANG {full_id: $hang_id})
        WHERE hang.full_id IN $node_ids
        RETURN hang.full_id, hang.content, hang.unit_path
        """
        hang_data_list = neo4j.execute_query(hang_query, {...})

    # Case 2: to_id가 JO/HO 노드인 경우 - 하위 HANG 노드 찾기
    else:
        hang_query = """
        MATCH (parent {full_id: $parent_id})-[:CONTAINS*1..2]->(hang:HANG)
        WHERE hang.full_id IN $node_ids
        RETURN hang.full_id, hang.content, hang.unit_path
        LIMIT 3
        """
        hang_data_list = neo4j.execute_query(hang_query, {...})

    # 찾은 HANG 노드들을 결과에 추가
    for hang_data in hang_data_list:
        relationship_hang_results.append({
            'hang_id': hang_data['hang_id'],
            'content': hang_data['content'],
            'unit_path': hang_data['unit_path'],
            'similarity': rel['similarity'] * 0.9,  # 관계 검색은 약간 낮은 가중치
            'stage': 'relationship',
            'semantic_type': rel.get('semantic_type', 'UNKNOWN')
        })
```

**핵심**: `MATCH (parent)-[:CONTAINS*1..2]->(hang:HANG)` 패턴으로 JO/HO의 하위 HANG 노드 조회

---

### 5. GraphDB 경로 탐색 (_get_parent_jo_info, lines 374-403)

```python
def _get_parent_jo_info(self, hang_id: str) -> Optional[Dict]:
    """HANG 노드의 상위 JO 조항 정보 가져오기 (GraphDB 경로 탐색)"""
    query = """
    MATCH path = (hang:HANG {full_id: $hang_id})<-[:CONTAINS*]-(jo:JO)
    WHERE jo.title IS NOT NULL AND jo.title <> 'None'
    RETURN jo.number AS jo_number,
           jo.title AS jo_title,
           jo.full_id AS jo_id,
           length(path) as path_length
    ORDER BY path_length ASC
    LIMIT 1
    """

    results = self.neo4j_service.execute_query(query, {'hang_id': hang_id})

    if results:
        return {
            'jo_number': results[0]['jo_number'],
            'jo_title': results[0]['jo_title'],
            'jo_id': results[0]['jo_id']
        }

    return None
```

**핵심 포인트**:
- `<-[:CONTAINS*]`: 역방향으로 CONTAINS 관계 따라가기 (HANG → JO)
- `WHERE jo.title <> 'None'`: title='None'인 JO 노드 제외
- `ORDER BY path_length ASC`: 가장 가까운 부모 JO 우선
- **주의**: `length(jo.full_id)` (X) → `length(path)` (O)
  - Neo4j `length()`는 그래프 경로용, 문자열 길이는 `size()`

---

### 6. 응답 포맷 (_format_response, lines 516-566)

```python
# 핵심 조항 (Top 3) - GraphDB 경로 탐색으로 상위 JO 정보 표시
response_parts.append("\n[핵심 조항]")
for i, r in enumerate(results[:3], 1):
    # 상위 JO 조항 정보 가져오기 (GraphDB 경로 탐색)
    jo_info = self._get_parent_jo_info(r['hang_id'])

    if jo_info:
        jo_display = f"{jo_info['jo_number']} ({jo_info['jo_title']})"
    else:
        jo_display = "상위 조항 정보 없음"

    response_parts.append(
        f"\n{i}. {jo_display} → {r['unit_path']}\n"
        f"   유사도: {r['similarity']:.2f} | 검색: {r.get('stage', 'unknown')}\n"
        f"   {r['content'][:200]}..."
    )

# 검색 방식별 통계
vector_count = sum(1 for r in results if r.get('stage') == 'vector')
relationship_count = sum(1 for r in results if r.get('stage') == 'relationship')
graph_expansion_count = sum(1 for r in results if r.get('stage') == 'graph_expansion')

response_parts.append(
    f"\n\n[검색 통계]\n"
    f"총 {len(results)}개 조항 발견\n"
    f"- 노드 임베딩: {vector_count}개\n"
    f"- 관계 임베딩: {relationship_count}개\n"
    f"- GraphDB 확장: {graph_expansion_count}개\n"
)
```

**출력 예시**:
```
[핵심 조항]
1. 110조 (광역도시계획위원회의 설치) → 제12장_제4절_제110조_3
   유사도: 0.85 | 검색: vector
   제3호제2항 제5호 개발행위허가에 관한 사항

[검색 통계]
총 3개 조항 발견
- 노드 임베딩: 3개
- 관계 임베딩: 0개
- GraphDB 확장: 0개
```

---

## 🧪 테스트 방법

### 테스트 파일: `law/test_domain_agent_final.py`

```bash
python law/test_domain_agent_final.py
```

### 테스트 질문 수정 (lines 89-93)

```python
test_questions = [
    "도시계획 수립은 어떻게 해야 하나요?",      # 여기를 원하는 질문으로 바꾸기
    "개발행위 허가를 받아야 하는 경우는?",
    "생략할 수 있는 경우가 뭐야?",
]
```

### 기대 결과

1. **관계 임베딩 검색 작동 확인**:
   - `[검색 통계]`에서 "관계 임베딩: X개" (X > 0)

2. **GraphDB 경로 탐색 작동 확인**:
   - 결과에 "제XX조 (제목)" 형식으로 표시
   - "상위 조항 정보 없음"이 아닌 실제 조항 제목 표시

3. **통합 검색 작동 확인**:
   - 노드 임베딩 + 관계 임베딩 + GraphDB 확장 모두 표시
   - 각 결과마다 `검색: vector` 또는 `검색: relationship` 태그

---

## 📊 테스트 결과 (2025-11-05)

### 질문 #1: "도시계획 수립은 어떻게 해야 하나요?"

```
[검색 통계]
총 4개 조항 발견
- 노드 임베딩: 0개
- 관계 임베딩: 4개 ✅
- GraphDB 확장: 0개
```

**분석**: 복잡한 질문에 관계 임베딩이 효과적 (노드 검색은 0개, 관계 검색만 4개)

---

### 질문 #2: "개발행위 허가를 받아야 하는 경우는?"

```
[핵심 조항]
1. 110조 (광역도시계획위원회의 설치) → 제12장_제4절_제110조_3 ✅
   유사도: 0.85 | 검색: vector

[검색 통계]
총 3개 조항 발견
- 노드 임베딩: 3개 ✅
- 관계 임베딩: 0개
- GraphDB 확장: 0개
```

**분석**:
- ✅ 상위 JO 정보 표시 성공: "110조 (광역도시계획위원회의 설치)"
- ✅ 노드 임베딩 검색 작동 (0.85 유사도)

---

### 질문 #3: "생략할 수 있는 경우가 뭐야?"

```
[검색 통계]
총 1개 조항 발견
- 노드 임베딩: 1개 ✅
- 관계 임베딩: 0개
- GraphDB 확장: 0개
```

**분석**: 의미 기반 검색으로 "생략" 키워드 포함 조항 발견

---

## 🔍 주요 이슈 해결 기록

### 이슈 #1: 임베딩 차원 불일치
**증상**:
```
Failed to invoke procedure `db.index.vector.queryRelationships`:
Index query vector has 768 dimensions, but indexed vectors have 3072.
```

**원인**:
- HANG 노드: 768-dim (KR-SBERT)
- CONTAINS 관계: 3072-dim (OpenAI)
- 쿼리 임베딩: 768-dim (KR-SBERT만 사용)

**해결**:
쿼리마다 2가지 임베딩 생성
- `_generate_kr_sbert_embedding()`: 768-dim for HANG nodes
- `_generate_openai_embedding()`: 3072-dim for relationships

---

### 이슈 #2: 관계 대상 노드 타입 불일치
**증상**: 관계 검색 결과의 `to_id`가 JO/HO 노드 (예: "제24조", "제48조")

**원인**: CONTAINS 관계가 JO → HANG, JO → HO, HANG → HO 등 다양한 타입 연결

**해결**:
`to_id`가 JO/HO인 경우 하위 HANG 노드 자동 조회
```cypher
MATCH (parent {full_id: $parent_id})-[:CONTAINS*1..2]->(hang:HANG)
WHERE hang.full_id IN $node_ids
RETURN hang.full_id, hang.content, hang.unit_path
```

---

### 이슈 #3: Neo4j length() 함수 타입 에러
**증상**:
```
Type mismatch: expected Path but was Boolean, Float, Integer, Number, Point, String...
"ORDER BY length(jo.full_id) ASC"
```

**원인**: Neo4j `length()`는 그래프 경로 전용, 문자열 길이는 `size()` 사용

**해결**:
```cypher
# Before (X)
MATCH (hang)<-[:CONTAINS*]-(jo:JO)
ORDER BY length(jo.full_id) ASC

# After (O)
MATCH path = (hang)<-[:CONTAINS*]-(jo:JO)
ORDER BY length(path) ASC
```

---

### 이슈 #4: JO 노드 title='None' 문제
**증상**: 일부 결과에 "상위 조항 정보 없음" 대신 실제로는 있는데 표시 안 됨

**원인**: 일부 JO 노드가 `title` 속성에 문자열 "None" 저장 (null이 아님)

**해결**:
```cypher
WHERE jo.title IS NOT NULL AND jo.title <> 'None'
```

---

## 🚀 향후 작업

### 1. RNE (Range Network Expansion) 알고리즘 활성화
**현재 상태**: 구현되어 있으나 결과가 0개
**파일**: `graph_db/algorithms/core/semantic_rne.py`
**필요 작업**:
- `_graph_expansion()` 함수 디버깅
- RNE threshold 조정 (현재 0.75)

### 2. INE (Iterative Neighbor Expansion) 알고리즘 활성화
**현재 상태**: 구현되어 있으나 미사용
**파일**: `graph_db/algorithms/core/semantic_ine.py`
**필요 작업**:
- DomainAgent에 INE 통합
- `ine_k` 파라미터 활용

### 3. 도메인 간 협업 검색
**현재 상태**: 단일 도메인 내 검색만 가능
**필요 작업**:
- `neighbor_agents` 활용
- 도메인 간 메시지 전달
- 교차 도메인 검색 결과 통합

---

## 📝 중요 체크리스트

### 새로운 AI가 작업 시작 전 확인할 것

- [ ] Neo4j가 실행 중인가? (http://localhost:7474 접속 확인)
- [ ] HANG 노드에 임베딩이 있는가? (1477개 노드)
- [ ] CONTAINS 관계에 임베딩이 있는가? (3565개 관계)
- [ ] 벡터 인덱스가 존재하는가?
  - `hang_embedding_index` (768-dim)
  - `contains_embedding` (3072-dim)

### 코드 수정 시 주의 사항

- [ ] **절대 단일 임베딩으로 돌아가지 마세요**: 노드와 관계 임베딩 차원이 다릅니다!
- [ ] `length()` 함수는 경로용, 문자열은 `size()` 사용
- [ ] JO 노드 조회 시 `WHERE jo.title <> 'None'` 필수
- [ ] 관계 검색 결과는 HANG 노드로 변환 필요 (JO/HO일 수 있음)

---

## 🔗 관련 파일

| 파일 | 설명 |
|------|------|
| `agents/law/domain_agent.py` | DomainAgent 메인 구현 (이중 임베딩, 통합 검색) |
| `law/test_domain_agent_final.py` | GraphDB 통합 테스트 |
| `law/INTEGRATION_SUCCESS_SUMMARY.md` | 통합 완료 보고서 (상세) |
| `law/relationship_embedding/TEST_RESULTS_SUMMARY.md` | 관계 임베딩 테스트 결과 |
| `graph_db/algorithms/core/semantic_rne.py` | RNE 알고리즘 구현 |
| `graph_db/algorithms/core/semantic_ine.py` | INE 알고리즘 구현 |

---

## 💡 핵심 개념 정리

### 왜 이중 임베딩이 필요한가?

**노드 임베딩 (KR-SBERT 768-dim)**:
- 조항의 **내용**을 검색
- "개발행위 허가" → 허가 관련 조항 찾기

**관계 임베딩 (OpenAI 3072-dim)**:
- 조항 간 **관계**의 의미를 검색
- "도시계획 수립" → 수립 절차 관련 조항 연결 관계 찾기

둘 다 필요한 이유: 법률은 **내용**과 **구조(관계)** 모두가 중요하기 때문!

### GraphDB 장점이 뭔가?

1. **경로 탐색**: "제1항이 뭐야?" → 제12조 제목도 함께 표시
2. **관계 검색**: 조항 간 연결 관계의 의미를 이해
3. **확장 검색**: 관련 조항을 그래프로 따라가며 확장

---

**작성자**: Claude Code
**날짜**: 2025-11-06
**상태**: ✅ 완료 (RNE/INE 활성화 대기)
