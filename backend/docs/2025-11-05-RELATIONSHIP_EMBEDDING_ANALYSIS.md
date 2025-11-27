# Relationship Embedding Analysis
**Date**: 2025-11-05
**Context**: 교수님 피드백 - "노드뿐만 아니라 관계에도 임베딩이 필요하지 않나?"

## Executive Summary

**결론: 교수님이 맞습니다!** 관계(Relationship)에 임베딩을 추가하는 것이 법률 검색 시스템의 정확도와 의미 이해를 크게 향상시킬 수 있습니다.

## 학술적 근거

### 1. Knowledge Graph Embedding (KGE) 최신 연구 (2024-2025)

**핵심 논문**:
- "Knowledge Graph Embeddings: A Comprehensive Survey on Capturing Relation Properties" (2024년 10월, 2025년 3월 업데이트)
- ACM Computing Surveys - "Knowledge Graph Embedding from Representation Spaces" (2024년 2월)

**주요 발견**:
- 관계는 **"의미의 운반자(carriers of semantic meaning)"**
- 관계의 정확한 모델링이 KGE 성능에 결정적
- 복잡한 매핑 속성 처리: 1-to-1, 1-to-many, many-to-one, many-to-many
- Composition patterns (대칭, 역, 조합)이 거의 모든 관계에 중요

### 2. TransE/TransR 모델

**TransE (Translating Embeddings)**:
```
h + r ≈ t
(head entity + relation ≈ tail entity)
```
- 관계를 벡터 공간의 변환(translation)으로 모델링
- **한계**: 대칭 관계, 1-to-N 관계 모델링 불가

**TransR (Translation in Relation-Specific Spaces)**:
- 엔티티와 관계를 **별도의 임베딩 공간**에 유지
- 각 관계마다 고유한 투영 매트릭스
- **장점**: 대칭, 역, 조합, 1-to-N 관계 모두 표현 가능

## 기술적 지원: Neo4j

### Neo4j의 관계 임베딩 기능

**1. 관계에 벡터 저장**:
```python
db.create.setRelationshipVectorProperty(
    relationship_id,
    property_name,
    embedding_vector
)
```

**2. 관계 벡터 인덱스**:
```cypher
CREATE VECTOR INDEX relationship_vector
FOR ()-[r:CONTAINS]-()
ON (r.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 3072,
        `vector.similarity_function`: 'cosine'
    }
}
```

**3. 관계 유사도 검색**:
```cypher
CALL db.index.vector.queryRelationships(
    'relationship_vector',
    5,  // top-k
    $query_embedding
)
YIELD relationship, score
```

**4. LangChain 통합**:
```python
Neo4jVector.from_existing_relationship_index(
    embedding=embeddings,
    index_name="relationship_vector"
)
```

## 우리 법률 시스템 적용

### 현재 시스템의 한계

**구조**:
```
JO (조) --[CONTAINS]-> HANG (항) --[CONTAINS]-> HO (호)
HANG1 --[CITES]-> HANG2
```

**문제점**:

1. **CONTAINS 관계의 다양한 의미**:
   - "제1항에서 다음과 같이 규정한다" → **원칙 제시**
   - "다만, 다음의 경우는 제외한다" → **예외 규정**
   - "제1항의 세부사항은 다음과 같다" → **상세 설명**
   - "제1항을 적용함에 있어서는..." → **적용 조건**
   - **→ 같은 CONTAINS지만 의미가 완전히 다름!**

2. **CITES 관계의 모순된 의미**:
   - "제12조를 **준용**한다" → 동일 적용
   - "제12조를 **참조**한다" → 참고만
   - "제12조의 규정에도 **불구하고**" → 예외
   - "제12조를 **적용하지 아니**한다" → 배제
   - **→ 같은 CITES지만 정반대 의미도 가능!**

3. **검색 시나리오 실패 예시**:
```
사용자: "주민의견 청취를 생략할 수 있는 경우는?"

현재 시스템:
- "생략" 키워드로 HANG 노드만 검색
- 해당 노드 내용 반환
- ❌ "왜 예외인지" 맥락 부족
- ❌ 관계의 의미(예외 조항임) 활용 못함

관계 임베딩 추가 시:
- "생략 가능" 의미와 유사한 **관계 임베딩** 검색
- CONTAINS(원칙→예외) 관계 발견
- ✅ 예외 조항과 그 근거 함께 반환
- ✅ 관계의 의미(예외 조항) 명확히 전달
```

### 실제 법률 예시

**국토계획법 제12조**:
```
제12조(주민의견 청취)
① 관계 행정기관의 장은 주민 의견을 들어야 한다.
② 다만, 다음 각 호의 어느 하나에 해당하는 경우에는 청취를 생략할 수 있다.
  1. 국가안보상 긴급한 경우
  2. 재해 복구를 위한 긴급한 경우
```

**그래프 구조**:
```
JO(제12조) --[CONTAINS]-> HANG(①항)
            --[CONTAINS]-> HANG(②항) --[CONTAINS]-> HO(1호)
                                       --[CONTAINS]-> HO(2호)
```

**관계 임베딩 적용**:
```python
# CONTAINS(①→②) 관계
{
    'type': 'CONTAINS',
    'from': 'JO:제12조:①항',
    'to': 'JO:제12조:②항',
    'properties': {
        'order': 2,
        'semantic_type': 'EXCEPTION',  # 예외 조항
        'context': '주민 의견을 들어야 한다. → 다만, 다음 각 호의 어느 하나에 해당하는 경우에는',
        'embedding': [0.023, -0.145, ...],  # 3072-dim
        'keywords': ['다만', '생략할 수 있다', '예외']
    }
}

# CONTAINS(②→1호) 관계
{
    'type': 'CONTAINS',
    'from': 'JO:제12조:②항',
    'to': 'JO:제12조:②항:1호',
    'properties': {
        'order': 1,
        'semantic_type': 'DETAIL',  # 구체적 상세
        'context': '청취를 생략할 수 있다. → 국가안보상 긴급한 경우',
        'embedding': [0.156, 0.023, ...],
        'keywords': ['긴급', '국가안보']
    }
}
```

**검색 개선 효과**:
```python
# 사용자 질의: "주민의견을 생략할 수 있는 경우"
query_embedding = embed("생략 가능 조건 예외")

# 관계 유사도 검색
similar_relations = search_relationship_embeddings(query_embedding)
# → CONTAINS(①→②) 발견 (semantic_type='EXCEPTION')

# 결과:
# 1. 원칙 조항: ①항
# 2. 예외 조항: ②항 (생략 가능)
# 3. 구체적 경우: 1호, 2호
# 4. 관계 맥락: "다만... 생략할 수 있다"
```

## 구현 방안

### 방법 1: 관계 텍스트 기반 임베딩 (권장)

**프로세스**:
1. 부모 노드 내용 (끝부분 100자)
2. 연결 키워드 추출 ("다만", "준용", "불구하고" 등)
3. 자식 노드 내용 (시작부분 100자)
4. → 결합하여 임베딩 생성

**코드 예시**:
```python
def create_relationship_embedding(parent_node, child_node):
    """관계 맥락 기반 임베딩 생성"""
    # 관계 맥락 텍스트
    parent_tail = parent_node['content'][-100:]
    child_head = child_node['content'][:100]
    relation_context = f"{parent_tail} → {child_head}"

    # 연결 키워드 추출
    keywords = extract_keywords(relation_context)

    # 의미 타입 분류 (LLM 또는 규칙 기반)
    semantic_type = classify_relation(relation_context)
    # → 'PRINCIPLE', 'EXCEPTION', 'DETAIL', 'CONDITION', etc.

    # 임베딩 생성
    embedding = openai.embed(relation_context)

    return {
        'context': relation_context,
        'semantic_type': semantic_type,
        'keywords': keywords,
        'embedding': embedding
    }
```

### 방법 2: 관계 타입 세분화 + 대표 임베딩

**세분화된 관계 타입**:
```cypher
# CONTAINS의 세부 타입
CONTAINS_PRINCIPLE  (원칙 제시)
CONTAINS_EXCEPTION  (예외 규정)
CONTAINS_DETAIL     (상세 설명)
CONTAINS_CONDITION  (적용 조건)
CONTAINS_EXAMPLE    (예시)

# CITES의 세부 타입
CITES_APPLY         (준용)
CITES_REFER         (참조)
CITES_EXCLUDE       (배제)
CITES_OVERRIDE      (우선 적용)
```

**각 타입마다 대표 임베딩**:
```python
representative_embeddings = {
    'CONTAINS_PRINCIPLE': embed("원칙을 제시한다 규정한다"),
    'CONTAINS_EXCEPTION': embed("다만 예외 제외 생략할 수 있다"),
    'CITES_APPLY': embed("준용한다 동일하게 적용한다"),
    'CITES_EXCLUDE': embed("적용하지 아니한다 제외한다"),
    # ...
}
```

### 방법 3: 하이브리드 (방법 1 + 2 조합) - 최종 권장

```python
{
    'type': 'CONTAINS',
    'semantic_subtype': 'EXCEPTION',  # 방법 2
    'from_id': parent_id,
    'to_id': child_id,
    'properties': {
        'order': 2,
        'context': relation_context,  # 방법 1
        'embedding': instance_embedding,  # 방법 1: 인스턴스별 고유 임베딩
        'type_embedding': type_embedding,  # 방법 2: 타입 대표 임베딩
        'keywords': ['다만', '생략', '예외'],
        'confidence': 0.85  # 분류 신뢰도
    }
}
```

## 구현 우선순위

### High Priority: CONTAINS, CITES

**이유**:
- 의미가 매우 다양함
- 법률 해석에 결정적 영향
- 검색 정확도 향상 효과 큼

**예상 개수**:
- CONTAINS: ~2000개
- CITES: ~500개
- **총 ~2500개 관계**

### Low Priority: NEXT

**이유**:
- 단순 순서 관계
- 의미적 다양성 낮음
- 구조적 탐색에만 사용

## 성능 영향 분석

### 저장 공간

**현재**:
- HANG 노드 1477개 × 3072-dim × 4 bytes = **18.1 MB**

**추가**:
- 관계 2500개 × 3072-dim × 4 bytes = **30.7 MB**

**총합**: 48.8 MB (매우 적음, 무시 가능)

### 검색 성능

**임베딩 검색 속도**:
- Neo4j 벡터 인덱스: O(log n) HNSW 알고리즘
- 2500개 관계 검색: ~10-20ms

**정확도 향상**:
- 노드만 검색: 키워드 매칭 의존
- 노드 + 관계 검색: **의미적 맥락 이해**
- **예상 정확도 향상: 20-30%**

### 쿼리 예시

```cypher
// 1. 관계 벡터 인덱스 생성
CREATE VECTOR INDEX contains_embedding
FOR ()-[r:CONTAINS]-()
ON (r.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 3072,
        `vector.similarity_function`: 'cosine'
    }
}

// 2. 관계 유사도 검색
CALL db.index.vector.queryRelationships(
    'contains_embedding',
    10,
    $query_embedding
) YIELD relationship, score
MATCH (parent)-[relationship]->(child)
RETURN parent, relationship, child, score
ORDER BY score DESC

// 3. 특정 semantic_type 필터링
CALL db.index.vector.queryRelationships(
    'contains_embedding',
    20,
    $query_embedding
) YIELD relationship, score
WHERE relationship.semantic_type = 'EXCEPTION'
MATCH (parent)-[relationship]->(child)
RETURN parent, relationship, child, score
```

## 다음 단계 (Implementation Roadmap)

### Phase 1: 관계 데이터 수집 및 분석
- [ ] 현재 CONTAINS, CITES 관계 분석
- [ ] 관계 맥락 텍스트 추출 로직 구현
- [ ] 의미 타입 분류 규칙/모델 개발

### Phase 2: 임베딩 생성
- [ ] 관계 텍스트 추출 스크립트 (`add_relationship_embeddings.py`)
- [ ] OpenAI API로 임베딩 생성
- [ ] Neo4j 관계 속성 업데이트

### Phase 3: 벡터 인덱스 구축
- [ ] Neo4j 관계 벡터 인덱스 생성
- [ ] 인덱스 성능 테스트
- [ ] 검색 쿼리 최적화

### Phase 4: 검색 알고리즘 통합
- [ ] DomainAgent에 관계 검색 추가
- [ ] AgentManager의 검색 로직 개선
- [ ] RNE/INE 알고리즘에 관계 경로 포함

### Phase 5: 평가 및 개선
- [ ] 검색 정확도 평가 (관계 임베딩 전/후 비교)
- [ ] 사용자 피드백 수집
- [ ] 세부 튜닝

## 예상 결과

### 정량적 개선
- **검색 정확도**: +20-30%
- **관련 조항 발견율**: +40%
- **응답 시간**: +5-10ms (무시 가능)

### 정성적 개선
- ✅ "예외 조항" 질의 정확도 대폭 향상
- ✅ 법률 간 참조 관계 의미 이해
- ✅ 조항 간 논리적 연결 파악
- ✅ "왜 이 조항이 연결되는가?" 맥락 제공

## 결론

교수님의 지적은 매우 타당하며, 다음 이유로 관계 임베딩 구현을 **강력히 권장**합니다:

1. **학술적 타당성**: KGE 최신 연구에서 관계는 핵심 의미 요소
2. **기술적 실현 가능성**: Neo4j가 관계 벡터 인덱스 완전 지원
3. **실용적 필요성**: 법률 관계의 의미적 다양성 (원칙/예외/참조/배제 등)
4. **성능 영향 최소**: 저장 공간 +30MB, 검색 시간 +10ms 미만
5. **정확도 향상 기대**: 20-30% 검색 정확도 향상 예상

**다음 작업**: Phase 1 시작 - 관계 데이터 분석 및 텍스트 추출 로직 구현

## References

1. "Knowledge Graph Embeddings: A Comprehensive Survey on Capturing Relation Properties" (arXiv:2410.14733, 2024-2025)
2. "Knowledge Graph Embedding: A Survey from the Perspective of Representation Spaces" (ACM Computing Surveys, 2024)
3. Neo4j Documentation - Vector Indexes for Relationships
4. TransE: "Translating Embeddings for Modeling Multi-relational Data" (NeurIPS 2013)
5. TransR: "Learning Entity and Relation Embeddings for Knowledge Graph Completion" (AAAI 2015)
