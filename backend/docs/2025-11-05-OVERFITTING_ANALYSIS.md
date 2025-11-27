# 관계 임베딩 과적합 분석

**Date**: 2025-11-05
**Status**: ⚠️ **CRITICAL ISSUE FOUND**

---

## Executive Summary

패턴 없는 자연어 테스트 결과, **심각한 과적합**이 확인되었습니다.

| 측정 지표 | 패턴 없는 쿼리 | 패턴 있는 쿼리 | 차이 |
|----------|---------------|---------------|------|
| **정확도** | 33.3% (3/9) | 100.0% (3/3) | **+66.7%** |
| **평균 유사도** | 0.7217 | 0.7765 | +0.0548 |

→ **패턴 기반 과적합 확인** ⚠️

---

## 테스트 결과 상세

### EXCEPTION 타입 (예외 조항)

| 쿼리 | 패턴 | 예측 | 정확 | 유사도 |
|------|------|------|------|--------|
| "의무를 면제받을 수 있는 상황" | ❌ | REFERENCE | ❌ | 0.7064 |
| "규정이 적용되지 않는 때" | ❌ | REFERENCE | ❌ | 0.7201 |
| "특별히 허용되는 조건" | ❌ | EXCEPTION | ✅ | 0.7231 |
| "다만 제외되는 경우" | ✅ | EXCEPTION | ✅ | 0.7471 |

**패턴 없는 정확도**: 1/3 (33.3%)
**패턴 있는 정확도**: 1/1 (100%)

### REFERENCE 타입 (법 조항 참조)

| 쿼리 | 패턴 | 예측 | 정확 | 유사도 |
|------|------|------|------|--------|
| "다른 조항과의 연결 관계" | ❌ | GENERAL | ❌ | 0.7096 |
| "상위 규정과의 관련성" | ❌ | REFERENCE | ✅ | 0.7322 |
| "유사한 법률 내용" | ❌ | REFERENCE | ✅ | 0.7456 |
| "제5조를 준용한다" | ✅ | REFERENCE | ✅ | 0.8227 |

**패턴 없는 정확도**: 2/3 (66.7%)
**패턴 있는 정확도**: 1/1 (100%)

### DETAIL 타입 (상세 설명)

| 쿼리 | 패턴 | 예측 | 정확 | 유사도 |
|------|------|------|------|--------|
| "구체적인 하위 내용" | ❌ | REFERENCE | ❌ | 0.7197 |
| "세부 구분 사항" | ❌ | GENERAL | ❌ | 0.7211 |
| "항목별 설명" | ❌ | GENERAL | ❌ | 0.7174 |
| "다음 각 호와 같다" | ✅ | DETAIL | ✅ | 0.7598 |

**패턴 없는 정확도**: 0/3 (0%)
**패턴 있는 정확도**: 1/1 (100%)

---

## 문제 원인 분석

### 1. REFERENCE 타입 과다 분류

**현재 분포**:
```
REFERENCE    : 1,771개 (49.7%) ← 너무 많음!
DETAIL       :   620개 (17.4%)
EXCEPTION    :   580개 (16.3%)
GENERAL      :   399개 (11.2%)
ADDITION     :   194개 (5.4%)
CONDITION    :     1개 (0.0%)
```

**문제**:
- REFERENCE가 거의 절반 (49.7%)
- "제\d+조" 패턴이 너무 광범위
- 조항 번호가 들어가면 무조건 REFERENCE로 분류됨

**예시**:
```
From: LAW (제12조)
To: JANG (제1장)
관계: CONTAINS (구조적 포함)
Context: "제12조 원칙 → 제1장"
분류: REFERENCE (오분류!)
```

### 2. 규칙 기반 분류의 한계

**현재 분류 규칙**:
```python
SEMANTIC_PATTERNS = {
    'EXCEPTION': [r'다만', r'제외', r'생략', ...],
    'REFERENCE': [r'제\d+조', r'준용', r'참조', ...],  # ← 문제!
    'DETAIL': [r'다음 각', r'각 호', ...],
}
```

**한계**:
1. **단순 패턴 매칭**: 맥락 무시
2. **우선순위 없음**: 여러 패턴 겹치면 첫 번째만
3. **패턴 누락**: 새로운 표현 처리 불가

### 3. 애매한 쿼리의 다수 타입 쏠림

**관찰**:
- 패턴 없는 쿼리 → REFERENCE나 GENERAL로 쏠림
- REFERENCE가 가장 많아서 (49.7%)
- 벡터 검색 시 REFERENCE 결과 많음

**예시**:
```
쿼리: "구체적인 하위 내용" (DETAIL 의미)
검색 결과 Top 5:
  1. REFERENCE (유사도 0.72)
  2. REFERENCE (유사도 0.71)
  3. REFERENCE (유사도 0.71)
  4. REFERENCE (유사도 0.70)
  5. REFERENCE (유사도 0.70)

예측: REFERENCE (5/5) ← 오답!
```

---

## 긍정적 발견

### 1. 임베딩 자체는 작동함

**유사도 범위**:
- 패턴 없는 쿼리: 0.7064 ~ 0.7456
- 패턴 있는 쿼리: 0.7471 ~ 0.8227

→ **임베딩이 관계 맥락을 잘 표현함** ✅

### 2. 의미적으로 관련된 결과

패턴 없는 쿼리도 완전히 무관한 결과는 아님:
- "의무를 면제받을 수 있는 상황" → REFERENCE (오답이지만 관련성 있음)
- "구체적인 하위 내용" → REFERENCE (오답이지만 하위 구조 언급)

### 3. 일부 쿼리는 성공

```
"특별히 허용되는 조건" → EXCEPTION ✅
"상위 규정과의 관련성" → REFERENCE ✅
"유사한 법률 내용" → REFERENCE ✅
```

---

## 해결 방안

### Option 1: 타입 분류 개선 (권장)

#### 1.1 REFERENCE 타입 세분화
```python
# 현재
REFERENCE: 제\d+조, 준용, 참조

# 개선
REFERENCE_STRUCTURAL: 제\d+조 (구조적 포함)
REFERENCE_SEMANTIC: 준용, 참조 (의미적 참조)
```

#### 1.2 LLM 기반 분류
```python
def classify_semantic_type_llm(context):
    prompt = f"""
    다음 법률 관계를 분류하세요:
    - EXCEPTION: 예외 조항
    - REFERENCE: 다른 법 참조
    - DETAIL: 상세 설명

    관계: {context}
    분류:
    """
    return llm.generate(prompt)
```

**장점**:
- 맥락 이해
- 유연한 분류
- 새로운 패턴 처리

**단점**:
- 비용 (3,565개 × $0.01 = ~$36)
- 시간 (~10분)

#### 1.3 임베딩 기반 분류
```python
# 타입별 대표 임베딩 생성
type_embeddings = {
    'EXCEPTION': embed("예외 조항, 다만, 제외, 생략할 수 있다"),
    'REFERENCE': embed("다른 조항 참조, 준용한다, 따른다"),
    'DETAIL': embed("상세 설명, 다음 각 호, 구체적 사항"),
}

# 가장 유사한 타입 선택
def classify_by_similarity(context):
    context_emb = embed(context)
    similarities = {
        type_name: cosine_similarity(context_emb, type_emb)
        for type_name, type_emb in type_embeddings.items()
    }
    return max(similarities, key=similarities.get)
```

**장점**:
- 의미 기반
- 추가 비용 없음
- 빠름

**단점**:
- 대표 문장 선택 어려움

### Option 2: 타입 분류 제거 (대안)

#### 2.1 순수 벡터 검색만 사용
```python
# 타입 무시하고 유사도만 보기
results = vector_search_relationships(query)
# 유사도 순으로 정렬만
return sorted(results, key=lambda r: r.score, reverse=True)
```

**장점**:
- 과적합 문제 해결
- 단순함
- 유연성

**단점**:
- 타입 정보 손실
- 필터링 불가

#### 2.2 사후 타입 추론
```python
# 검색 후 타입 추론
results = vector_search_relationships(query)
for r in results:
    r.inferred_type = infer_type_from_content(r.context)
```

### Option 3: 하이브리드 (추천)

```python
# 1. 순수 벡터 검색
raw_results = vector_search_relationships(query)

# 2. LLM으로 쿼리 의도 분석
query_intent = llm.analyze_intent(query)
# → "EXCEPTION을 찾고 있음"

# 3. 타입 필터링 (선택적)
if query_intent.confidence > 0.8:
    filtered_results = [
        r for r in raw_results
        if r.semantic_type == query_intent.type
    ]
else:
    filtered_results = raw_results

# 4. 유사도 순 정렬
return sorted(filtered_results, key=lambda r: r.score)
```

**장점**:
- 타입 정보 활용 (높은 신뢰도일 때)
- 타입 무시 (낮은 신뢰도일 때)
- 유연성

---

## 즉시 조치 사항

### 1. REFERENCE 타입 재분류 (긴급)

**스크립트**: `step8_reclassify_reference.py`

```python
# REFERENCE를 STRUCTURAL과 SEMANTIC으로 분리
for rel in relationships:
    if rel.semantic_type == 'REFERENCE':
        if is_structural(rel.context):
            rel.semantic_type = 'STRUCTURAL'
        # else: REFERENCE 유지
```

### 2. 임베딩 기반 분류 재시도

**스크립트**: `step8_embedding_based_classification.py`

```python
# 타입별 대표 임베딩으로 재분류
type_prototypes = {
    'EXCEPTION': [
        "다만 다음의 경우에는 제외한다",
        "생략할 수 있다",
        "적용하지 아니한다"
    ],
    'REFERENCE': [
        "제12조를 준용한다",
        "제5조에 따른다"
    ],
    'DETAIL': [
        "다음 각 호와 같다",
        "구체적인 사항은 다음과 같다"
    ]
}
```

### 3. DomainAgent 통합 (타입 무시 버전)

**우선**: 타입 분류 개선 전에 순수 벡터 검색으로 통합

---

## 권장 로드맵

### Phase 1: 긴급 (오늘)
1. ✅ 과적합 확인 (완료)
2. ⏭ REFERENCE 타입 재분류
3. ⏭ 임베딩 기반 분류 재시도
4. ⏭ 재테스트

### Phase 2: 통합 (이번 주)
5. ⏭ DomainAgent POC (타입 무시 버전)
6. ⏭ 노드 + 관계 통합 검색
7. ⏭ 사용자 테스트

### Phase 3: 고도화 (다음 주)
8. ⏭ LLM 기반 타입 분류 (예산 확보 시)
9. ⏭ 하이브리드 검색 전략
10. ⏭ 실무 배포

---

## 결론

### 현재 상태
- ✅ 관계 임베딩 자체는 **유효함**
- ✅ 벡터 검색 **작동함**
- ⚠️ 타입 분류 **과적합**

### 핵심 문제
- **REFERENCE 타입 과다** (49.7%)
- **규칙 기반 분류 한계**
- **패턴 의존도 높음**

### 해결 방향
1. **즉시**: REFERENCE 재분류
2. **단기**: 임베딩 기반 분류
3. **중기**: DomainAgent 통합
4. **장기**: LLM 기반 분류

### 교수님께 보고
"관계 임베딩은 작동하지만, 타입 분류에 과적합이 발견되었습니다. REFERENCE 타입을 재분류하고 임베딩 기반 분류로 개선 중입니다."

---

**Next Steps**: Step 8 - REFERENCE 타입 재분류 및 임베딩 기반 분류
