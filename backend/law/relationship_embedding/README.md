# 관계 임베딩 구현

**목적**: Neo4j CONTAINS 관계에 임베딩을 추가하여 의미 기반 법률 관계 검색 구현

---

## 빠른 실행

### 전체 프로세스 (순차 실행)

```bash
# Step 1: 관계 분석
python law/relationship_embedding/step1_analyze_relationships.py

# Step 2: 컨텍스트 추출 및 타입 분류
python law/relationship_embedding/step2_extract_contexts.py

# Step 3: 임베딩 생성
python law/relationship_embedding/step3_generate_embeddings.py

# Step 4: Neo4j 업데이트
python law/relationship_embedding/step4_update_neo4j.py

# Step 5-6: 벡터 인덱스 생성 및 테스트
python law/relationship_embedding/step5_create_index_and_test.py

# Step 7: 고급 검증 (패턴 없는 자연어)
python law/relationship_embedding/step7_advanced_tests.py

# Step 8: REFERENCE 타입 분석
python law/relationship_embedding/step8_analyze_reference_type.py

# Step 9: REFERENCE → STRUCTURAL 재분류
python law/relationship_embedding/step9_reclassify_reference.py

# Step 10: 타입 무시 순수 벡터 검색 (최종 권장)
python law/relationship_embedding/step10_type_agnostic_search.py
```

### 최종 검증만 실행

```bash
# 타입 무시 벡터 검색 테스트 (권장)
python law/relationship_embedding/step10_type_agnostic_search.py
```

---

## 파일 구조

```
law/relationship_embedding/
├── README.md                              # 이 파일
├── step1_analyze_relationships.py         # 관계 분석
├── step2_extract_contexts.py              # 컨텍스트 추출
├── step3_generate_embeddings.py           # 임베딩 생성
├── step4_update_neo4j.py                  # Neo4j 업데이트
├── step5_create_index_and_test.py         # 인덱스 생성 및 테스트
├── step7_advanced_tests.py                # 고급 검증
├── step8_analyze_reference_type.py        # REFERENCE 타입 분석
├── step9_reclassify_reference.py          # 재분류
├── step10_type_agnostic_search.py         # 타입 무시 검색 (최종)
├── relationship_contexts.json             # 컨텍스트 데이터 (4.4 MB)
└── relationship_contexts_with_embeddings.json  # 임베딩 포함 (311.8 MB)
```

---

## 주요 결과

### 최종 성능 (Step 10)
- **평균 유사도**: 0.7479
- **평균 관련성**: 54.3% (Top 5 중 관련 결과 비율)
- **특정 패턴 쿼리**: 80-100% 관련성

### Neo4j 상태
- **CONTAINS 관계**: 3,565개
- **임베딩**: 3,072차원 (OpenAI text-embedding-3-large)
- **벡터 인덱스**: `contains_embedding` (HNSW, cosine)

### 타입 분포 (참고용, 검색 시 무시)
- STRUCTURAL: 1,475개 (41.4%)
- DETAIL: 620개 (17.4%)
- EXCEPTION: 580개 (16.3%)
- GENERAL: 399개 (11.2%)
- REFERENCE: 296개 (8.3%)
- ADDITION: 194개 (5.4%)

---

## 핵심 발견

### 1. 타입 분류 과적합
- **문제**: 규칙 기반 타입 분류가 정확도 저해
- **원인**: 패턴 의존, 타입 불균형
- **해결**: 타입 무시, 순수 벡터 검색

### 2. 임베딩 유효성
- **증거**: 유사도 0.7~0.85 안정적
- **의미**: 관계의 의미를 잘 포착

### 3. 검색 전략
- **타입 기반**: 22.2% 정확도
- **타입 무시**: 54.3% 관련성 (2.5배 향상)

---

## DomainAgent 통합 가이드

### 관계 검색 함수

```python
def search_relationships(self, query: str, top_k: int = 10):
    """관계 임베딩 검색 (타입 무시)"""
    query_emb = self.embedding_model.embed_query(query)

    cypher = """
    CALL db.index.vector.queryRelationships(
        'contains_embedding',
        $top_k,
        $query_embedding
    ) YIELD relationship, score
    MATCH (from)-[relationship]->(to)
    WHERE score >= 0.70
    RETURN
        from.full_id, to.full_id,
        relationship.context, score
    ORDER BY score DESC
    """

    return neo4j.execute_query(cypher, {
        'query_embedding': query_emb,
        'top_k': top_k
    })
```

### 통합 검색 (노드 + 관계)

```python
def integrated_search(self, query: str):
    """노드 검색 + 관계 검색 통합"""
    hang_nodes = self.search_hang_nodes(query, top_k=5)  # 가중치 0.6
    relationships = self.search_relationships(query, top_k=5)  # 가중치 0.4

    # 유사도 순 정렬 후 Top 10 반환
    ...
```

---

## 문서

- **구현 완료 보고**: `docs/2025-11-05-RELATIONSHIP_EMBEDDING_IMPLEMENTATION_COMPLETE.md`
- **과적합 분석**: `docs/2025-11-05-OVERFITTING_ANALYSIS.md`
- **최종 보고서**: `docs/2025-11-05-RELATIONSHIP_EMBEDDING_FINAL.md`

---

## 다음 단계

1. ⏭ DomainAgent에 관계 검색 통합
2. ⏭ 노드 + 관계 통합 검색 구현
3. ⏭ 실제 법률 질의 테스트
4. ⏭ RNE/INE 알고리즘에 관계 경로 추가

---

## 참고

**학술적 배경:**
- Knowledge Graph Embedding (KGE) 연구
- TransE/TransR 모델 (관계를 벡터로 표현)
- 관계가 "의미의 운반체" 역할

**구현 기술:**
- Neo4j: `db.create.setRelationshipVectorProperty()`
- OpenAI: `text-embedding-3-large` (3072-dim)
- HNSW: 고속 유사도 검색 알고리즘
