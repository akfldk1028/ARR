# A6 — Repair Operator (Hard Constraint 강제)

**기간**: 1주 | **학습**: ❌ | **ROI 5.0** ⭐ (Flexity 격차 메우는 핵심)

## 목적
현재 GA는 *penalty* 로 처리 — 위반 매스도 Pareto에 들어갈 수 있음. **Repair Operator** 는 위반 매스를 *자동 수정*해 무조건 feasible 매스만 평가. = *Hard constraint 강제*.

플렉시티 광고처럼 매스가 *반드시* envelope 안에 fit 되도록.

## 작업

### 코드 위치
- `ARR/backend/design/services/repair_operator.py` (신규)
- `ARR/backend/design/engine/objects.py` 의 `Design.set_outputs()` 후 repair 호출

### 처리할 제약
1. **정북일조 사선** — `envelopes/sunlight.py` 사용. 위반 vertex를 envelope 면으로 *projection*
2. **도로 사선** — 도로 후퇴선 envelope 안으로 매스 clip
3. **인접대지 이격** — 이격선 위반 vertex projection
4. **BCR 한도 초과** — 매스 *수평 축소* (centroid 기준)
5. **FAR 한도 초과** — 층수 *감소* 또는 상층부 축소
6. **높이 제한** — 매스 *수직 클립*

### 알고리즘
```python
def repair(design: Design, envelopes: dict, regs: RegulationLimits) -> Design:
    polygon = decode_to_polygon(design)
    # 1. Envelope projection (정북일조 + 도로사선 + 이격)
    polygon = project_into_envelope(polygon, envelopes['sunlight'])
    polygon = project_into_envelope(polygon, envelopes['road_setback'])
    polygon = project_into_envelope(polygon, envelopes['adjacent_setback'])
    # 2. BCR/FAR/Height clamp
    polygon = scale_to_bcr(polygon, regs.bcr_limit)
    polygon = clamp_floors_to_far(polygon, regs.far_limit)
    polygon = clip_height(polygon, regs.height_limit)
    # 3. Re-encode to genes
    design.set_inputs(encode_polygon(polygon))
    return design
```

## 핵심 포인트
- *Penalty 대체* — penalty=0 으로 강제. 모든 매스가 feasible
- Pareto front에 *위반 매스가 절대 들어갈 수 없음*
- Generate-then-Verify 루프 (`regulation_validator.py`) 보강

## 검증
- 1k 매스 무작위 생성 → repair 적용 → BCR/FAR/envelope 100% 통과
- 회귀 테스트: 기존 통합 테스트 통과 (4대 자산 보존)

## 학계 위치
- Salcedo-Sanz 2009 (Repair survey) — GA repair 방법론 표준
- Yang & Deb 2020 — NSGA-II + repair 비교
- 우리 *envelopes/sunlight.py* 와 결합 → 한국 매스에서 학계 첫 사례 수준

## 참고 (related work)
- `06_LITERATURE/constraint_aware_survey.md` — Cat 2 (Repair Operator)
