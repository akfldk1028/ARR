# exp007 — A6 × A3 시너지 매트릭스 (2x2 cell)

**Date**: 2026-05-06 20:55~20:57 KST (실측 완료, 약 2분 소요)
**Phase**: 1
**작업 ID**: A6 + A3 cross
**부지**: 강남 / 분당 / 춘천 (3종 fixture)
**반복**: 3회 / cell
**Engine**: SSIEA only

## 가설

A6 (Repair Operator, hard constraint 강제) + A3 (Penalty 정규화, soft signal) 두 작업의 *합 효과* 정량 측정. 직관: A6=hard / A3=soft 이라 *시너지* 가 있을 것.

## 실험 설계 — 2x2 매트릭스

| cell | A6 repair | A3 penalty | 의미 |
|---|---|---|---|
| cell1 | OFF | binary | 원시 baseline (Phase 1 이전 상태) |
| cell2 | OFF | normalized | A3만 단독 (=exp001 재현) |
| cell3 | ON | binary | A6만 단독 |
| cell4 | ON | normalized | A6+A3 (=exp003 재현) |

## 결과 (실측)

| 부지 | cell1 (off/bin) | cell2 (off/norm) | cell3 (on/bin) | cell4 (on/norm) |
|------|------|------|------|------|
| 강남 | 10.44% / HV 36,637 | 14.16% / **63,550** | 99.97% / 268,677 | **99.97% / 270,460** |
| 분당 | 1.14% / HV 774 | 8.06% / **5,294** | 99.90% / **29,362** | 99.93% / 28,761 |
| 춘천 | 8.95% / HV 29,410 | 16.51% / **46,180** | 100% / **163,592** | 100% / 161,488 |

## 핵심 발견 — *시너지가 아닌 Redundant*

### 1. A6 단독 효과 = A6+A3 효과 (거의 동일)
- 강남 cell3 vs cell4: HV 268,677 → 270,460 (+0.66%) — *무의미한 차이*
- 분당 cell3 vs cell4: HV 29,362 → 28,761 (-2.04%) — *오히려 감소*
- 춘천 cell3 vs cell4: HV 163,592 → 161,488 (-1.29%) — *오히려 감소*

→ A6가 켜지면 A3 normalized 의 추가 효과 없음. *redundant*.

### 2. A3 단독 효과 (A6 OFF) — exp004 재현
- 강남 cell1 vs cell2: 36,637 → 63,550 (+73%)
- 분당 cell1 vs cell2: 774 → 5,294 (+584%)
- 춘천 cell1 vs cell2: 29,410 → 46,180 (+57%)

→ A6 없을 때 A3 normalized 가 유의미. exp004와 동일.

### 3. A6 단독 효과 (A3 binary) — *놀랍게도 충분*
- 강남 cell1 vs cell3: 36,637 → 268,677 (+633%)
- 분당 cell1 vs cell3: 774 → 29,362 (+3693%)
- 춘천 cell1 vs cell3: 29,410 → 163,592 (+456%)

→ A6 binary penalty만으로도 GA가 feasible 영역에 도달.

## 해석

A6 와 A3 는 *같은 문제를 다른 방식으로* 푸는 redundant solution:
- **A6 (Repair)**: feasibility를 *직접 강제* — 어떤 GA가 만들든 feasible로 변환
- **A3 (Normalized penalty)**: feasibility 방향 *gradient signal* — GA가 *스스로* feasible로 진화

A6 가 켜지면 모든 매스가 이미 feasible → A3 의 gradient signal은 *이미 feasible 영역 내부*에서만 작동 → 추가 가치 미미.

A6 가 꺼지면 GA가 feasibility를 *직접 해결*해야 함 → A3 gradient가 *결정적*.

## 결론

✅ **A6 가 production default로 적합** — 단독으로 99.9% feasible.
- A3 normalized 는 *A6 가 사용 불가한 상황에서의 backup*
- 둘 다 적용 시 추가 효과 미미 (A3 의 gradient는 A6 결과 내에서 microbenefit만)

이는 *예상과 다른* 발견. 시너지 가설 기각.

## 회귀

**152/152 design 테스트 통과**.

## 다음

- exp006: 4-objective NSGA-III vs SSIEA (NSGA-III 진짜 강점, exp002 follow-up)
- B1a: Phase 2 진입 — Surrogate 학습용 데이터셋 자가 생성 (1-5k)

## 참조 데이터
- `exp007_data.json` — 4 cells × 3 sites × 3 reps raw
