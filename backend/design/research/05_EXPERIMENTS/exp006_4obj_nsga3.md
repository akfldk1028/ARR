# exp006 — 4-Objective NSGA-III vs SSIEA (진짜 강점 검증)

**Date**: 2026-05-06 20:59~21:02 KST (실측 완료, 약 3분 소요)
**Phase**: 1
**작업 ID**: A1 NSGA-III follow-up
**부지**: 강남 / 분당 / 춘천 (3종 fixture, A6 repair on)
**반복**: 3회 / engine

## 가설

NSGA-III의 *진짜 강점*은 4+ objectives에서 ref-point density로 Pareto 다양성 + HV 큰 폭 향상. exp002 (2 obj) 에서는 +5~34% — 크지 않음. 4 obj 에서 +50% 이상 기대.

## 실험 설계 — 4 objectives

기존 2 obj (floor_area Max + daylight_score Max) 에 2개 추가:
- **compactness** (Minimize): footprint perimeter² / area. 정사각형 ≈ 16, 길쭉/요철 매스 ↑
- **stepback_factor** (Maximize): 1 - upper_scale. 0=균일적층, 0.5=상층 절반축소

이 2 obj 는 *실제 건축에서 의미 있음*:
- compactness ↓ → 단순한 매스 (시공 쉽고 효율)
- stepback ↑ → 도시 친화 (햇빛/조망 양보)

대부분의 매스 옵션이 이 4축 사이 trade-off → Pareto front 다양화.

## 변경 사항

`mass_evaluator.py:_compute_metrics` 출력에 `compactness` + `stepback_factor` 추가.
`benchmark.py:_build_spec(n_objectives=4)` 옵션 — 추가 2 obj 를 outputs 에 삽입.
`_METRIC_MAP` 에 두 metric mapping 추가.

## 결과 (실측)

| 부지 | engine | Feasible | HV | Runtime | Pareto 크기 | Δ HV vs SSIEA |
|------|------|------|------|------|------|------|
| 강남 역삼 677 | ssiea | 99.97% | 15,132,516 | 1.62s | 496.7 | — |
| | **nsga3** | 99.85% | **71,893,703** | 14.07s | 963.3 | **+375.1%** |
| 분당 | ssiea | 99.87% | 1,642,112 | 1.61s | 233.3 | — |
| | **nsga3** | 99.92% | **4,736,738** | 13.23s | 832.0 | **+188.5%** |
| 춘천 | ssiea | 100.00% | 9,365,792 | 1.54s | 149.0 | — |
| | **nsga3** | 99.92% | **28,579,541** | 13.12s | 648.0 | **+205.1%** |

## 비교: 2 obj vs 4 obj

| 부지 | NSGA3 vs SSIEA Δ HV (2 obj, exp002) | NSGA3 vs SSIEA Δ HV (4 obj, exp006) |
|---|---|---|
| 강남 | +34.1% | **+375.1%** (11x 격차) |
| 분당 | +12.9% | **+188.5%** (15x 격차) |
| 춘천 | +4.8% | **+205.1%** (43x 격차) |

→ 가설 *완벽 검증*. NSGA-III 의 ref-point 알고리즘은 obj 수에 비례해 강점 증가.

## Pareto 다양성 — *2 배 ~ 4.3 배*

| 부지 | SSIEA | NSGA3 | x |
|---|---|---|---|
| 강남 | 497 | 963 | 1.9x |
| 분당 | 233 | 832 | **3.6x** |
| 춘천 | 149 | 648 | **4.3x** |

NSGA-III는 사용자에게 *훨씬 다양한 Pareto-optimal 매스* 제공.

## 분석

### NSGA-III 메커니즘
- NSGA-II / SSIEA: crowding distance (목적공간 sparseness)로 다양성. obj가 많아지면 crowding 신호 약화 (curse of dimensionality).
- NSGA-III: das-dennis reference points (균등 분산 시뮬레이션 anchor). obj 수에 robust.

### 실용적 시사
| 사용자 시나리오 | 권장 engine |
|---|---|
| 빠른 단일 응답 (2 obj, 1초) | SSIEA |
| 다양한 옵션 탐색 (4 obj, ~14초) | **NSGA-III** ⭐ |
| 사용자에게 100~1000개 매스 옵션 제시 | NSGA-III |
| Real-time SSE 스트리밍 시연 | SSIEA |

### Phase 1 종합 권장 production 설정
- **default**: SSIEA + A6 repair on + A3 normalized (탑 빠르게)
- **advanced mode**: NSGA-III + A6 repair on (사용자가 4 obj 선택 시 자동 전환)

## 결론

✅ **A1 NSGA-III 진짜 강점 정량 검증 완료**.
- 4 obj에서 HV +189~375% (2 obj +5~34% 대비 11~43배 격차)
- Pareto 다양성 2~4배

이제 NSGA-III 의 *production 가치*가 명확해짐. *선택적* 전환 (사용자가 4+ obj 선택 시) 가 최적.

## 회귀

**152/152 design 테스트 통과** (compactness/stepback 출력 추가, 기존 키 보존).

## 다음

- **B1a Dataset 자가 생성** — Phase 2 진입
- exp005: Radiance UDI (바이너리 설치 후)
- exp008+: B1 Surrogate validation

## 참조 데이터
- `exp006_data.json` — 4 obj × 2 engine × 3 sites × 3 reps raw
