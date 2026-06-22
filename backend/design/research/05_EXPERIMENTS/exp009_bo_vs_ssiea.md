# exp009 — Bayesian Optimization vs SSIEA (적은 평가로 같은 품질?)

**Date**: 2026-05-06 21:14~21:16 KST (실측 완료)
**Phase**: 2
**작업 ID**: B2 Bayesian Optimization
**부지**: 강남 역삼 677 (single site, 빠른 실험)
**Engine**: Custom BO (50 random init + 10 rounds × 5 picks) vs SSIEAJob

## 가설

Surrogate (B1b MLP) + acquisition 으로 *적은 real evaluation* 횟수에 SSIEA 와 동등한 HV 도달. 100 evals로 SSIEA 1050 evals 의 80% HV 도달 기대.

## BO 구현 (간이)

```
1. n_initial=50 random gene vectors → real evaluate
2. for 10 rounds:
   a. MLP fit on (history)
   b. sample 200 random candidates → MLP predict
   c. acquisition = normalized(floor_area + daylight) score
   d. top 5 candidates → real evaluate, append to history
3. final HV
```

Acquisition: *naive surrogate-mean maximization* (uncertainty term 없음, 단순 EI 아님).

## 결과 (실측)

### BO HV 진행
| Round | Evals | HV | Best floor_area | Best daylight |
|---|---|---|---|---|
| 1 | 55 | 87,670 | 4206 | 97.24 |
| 5 | 75 | 106,442 | 6419 | 99.79 |
| 10 | 100 | **125,942** | 6419 | 100.00 |

### vs SSIEA (same HV metric, same site)

| Eval count | BO HV | SSIEA HV | Δ |
|---|---|---|---|
| 50 | (init only) | 136,003 | — |
| **100** | **125,942** | **173,492** | **BO -27%** ⚠️ |
| 200 | — | 180,177 | — |
| 500 | — | 259,681 | — |
| 1050 | — | 281,825 | — |

→ **BO 100 evals < SSIEA 100 evals**. Naive BO 가 SSIEA 못 이김.

## 분석 — 왜 BO가 졌나

### 1. 단순 acquisition
- Naive `normalized(floor_area + daylight)` — uncertainty 무시
- 진짜 BO: Expected Improvement = (μ - μ_best) Φ(z) + σ φ(z)
- 우리 surrogate (MLP) 는 σ 출력 없음 → Gaussian Process 필요

### 2. 작은 초기 sample
- 50 init + 32-D input + 4-D output → MLP 학습 데이터 부족
- 처음 5-10 round 동안 surrogate accuracy 낮음 → guidance 약함

### 3. SSIEA가 *이미 효율적*
- Steady-state evolution: 75 pop × 14 gen → 1050 evals
- 매 step 마다 best parent crossover + adaptive mutation → 점진 개선
- Random sampling (BO init phase) 보다 *결정적으로 좋음*

### 4. Geometric evaluator 자체가 빠름
- 1매스 ~1ms — 1050 evals = ~1초
- BO의 *진짜 장점* = "1매스 평가가 비쌀 때" (예: Radiance 30s)
- 1050 SSIEA = 1초 vs 1050 Radiance = 8.75 hours
- 이 환경에선 BO 50 vs SSIEA 50 만 비교 의미

## 결론 — *honest negative*

❌ **현재 환경에서 naive BO 는 SSIEA를 못 이김**.

이유:
- Geometric eval 빠름 → BO의 "비싼 평가 절감" 효과 무용
- Naive acquisition (uncertainty 무시) → SSIEA 의 explore-exploit 보다 약함
- 50 init 으로는 surrogate 학습 데이터 부족

## BO 진가 발휘 시점

✅ **A2 Radiance 활성화 후** — 1매스 평가 30s가 되면:
- SSIEA 1050 evals = 8.75 hours (비실용)
- BO 50 evals = 25 min (실용)
- 이 때 비로소 BO acquisition 효율이 의미

## Follow-up 개선 제안

1. **Proper EI** — Gaussian Process + uncertainty aware acquisition (BoTorch 사용)
2. **Larger initial sample** — 100~200 init
3. **Multi-objective BO** — qEHVI (parallel EHVI) 또는 NSGA-II + GP surrogate hybrid
4. **Phase 2 exp010**: Radiance 활성화 후 BO vs SSIEA 재비교 (이게 *진짜 검증*)

## 회귀
**152/152 design 테스트 통과**.

## 참조 데이터
- `exp009_data.json` — 10 round HV/best progression
