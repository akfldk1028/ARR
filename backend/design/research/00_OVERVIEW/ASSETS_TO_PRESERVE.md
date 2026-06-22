# 보호해야 할 핵심 자산

**원칙**: Phase 1/2/3 어떤 단계에서도 *반드시 유지*. 이게 우리 시스템의 진짜 가치.

---

## 4대 자산

### 1. 한국 법규 31,126 노드 Neo4j 그래프 ⭐
- **무엇**: 20개 법률 × 58개 법령 × 31,126개 조항 노드 + 31,063개 관계 (CONTAINS/NEXT/CITES)
- **왜 중요**: 학계 어느 논문도 못 한 *한국 건축 법규 완전 그래프화*
- **코드 경로**:
  - 적재: `ARR/backend/law/STEP/`, `ARR/backend/law/scripts/`
  - 조회: `ARR/backend/law/views.py` (proxy → law-domain-agents :8011)
  - 직접 쿼리: `ARR/backend/law/views.py` (Neo4j 직접 조회)
- **DB**: `bolt://localhost:7687`, pw=11111111
- **vector index**: `hang_embedding_index` (3072d cosine), `contains_embedding`
- **fulltext**: `hang_content_fulltext` (CJK Bigram)

### 2. PNU + Vworld 자동 연동 ⭐
- **무엇**: 주소/PNU 입력 → 부지 polygon + 면적 + 용도지역 + 공시지가 자동 조회
- **왜 중요**: *한국 행정 API와의 직접 연결*. 다른 나라에서는 같은 작업이 수동
- **코드 경로**:
  - PNU resolver: `ARR/backend/land/services/pnu_resolver.py`
  - Vworld geocoding: `level4LC` 직접 추출
  - 토지 정보 API: `ARR/backend/land/services/land_api.py`
- **API key**: `VWORLD_API_KEY` in `.env` (만료: 2026-08-24)

### 3. 실시간 SSE 스트리밍 UI ⭐
- **무엇**: GA 진행 상황을 *실시간 브라우저로 스트리밍*. 사용자가 generation별 진행 시각적으로 확인
- **왜 중요**: 실무 사용성. 30초 안에 첫 결과 보여줘야 사용자가 떠나지 않음
- **코드 경로**:
  - Backend SSE: `ARR/backend/design/views.py` (`GET /design/jobs/<id>/stream/`)
  - Frontend hook: `ARR/frontend/src/design/hooks/use-optimization-stream.ts`
  - Pareto 시각화: `ARR/frontend/src/design/ParetoChart.tsx`

### 4. land/ 41 규제 자동 도출 ⭐
- **무엇**: PNU 입력 → BCR/FAR/높이/이격/조경 등 41개 건축 규제 자동 도출 (10 core + 31 extended)
- **왜 중요**: *법규 도메인 전문성 자체가 가치*. 시스템에 의해 자동화됨
- **코드 경로**:
  - 메인: `ARR/backend/land/views.py` (`POST /land/analyze/`)
  - 용도지역 매핑: `ARR/backend/land/services/zoning_mapper.py`
  - 법조항 검색: `ARR/backend/land/services/law_enricher.py` (병렬, ThreadPoolExecutor 5 workers)
  - LLM 추출: gpt-4o-mini (LLM_EXTRACTION_ENABLED 기본 true)

---

## 회귀 테스트 (Phase 변경 시 필수)

각 Phase 작업 전후로 다음 4개 시나리오가 *동일 결과* 인지 검증:

```python
# 1. 법규 그래프 검색
GET /law/article/?full_id=건축법(법률)::제86조
→ HANG/HO 노드 정확히 반환 (3072d 임베딩 매칭)

# 2. PNU 자동 추출
POST /land/resolve/ {"input": "강남구 역삼동 677"}
→ PNU 19자리 정확히 반환

# 3. SSE 진행 스트리밍
GET /design/jobs/<id>/stream/
→ generation별 ScatterPoint 실시간 수신

# 4. 41 규제 자동 도출
POST /land/analyze/ {"pnu": "..."}
→ BCR=80, FAR=1300 + 41 규제 + 170 법조항
```

**위 4개 중 하나라도 실패 → 변경 rollback. 절대 deploy 금지.**

---

## 어떤 변화에도 *유지*

| Phase | 매스 알고리즘 | 평가 함수 | 자산 |
|---|---|---|---|
| 현재 | 박스 적층 GA | BCR/FAR/일조선 기하 | ✅ 4개 자산 그대로 |
| Phase 1 | + NSGA-III | + Radiance UDI/sDA | ✅ 4개 자산 그대로 |
| Phase 2 | + Heterogeneous | + Surrogate | ✅ 4개 자산 그대로 |
| Phase 3 | SDF/Diffusion | Differentiable Rendering | ✅ 4개 자산 *반드시* 유지 |

**박스 적층 GA가 Phase 3에서 deprecate 되더라도** 4개 자산은 새 매스 시스템과 *반드시 통합*되어야 함.
