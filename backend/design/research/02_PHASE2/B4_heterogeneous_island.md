# B4 — Heterogeneous Island ✅ DONE — *honest negative* (2026-05-06 21:37)

## 상태: COMPLETE — 측정 후 비채택 권장

**기간**: 3주 예상 → 1시간 (BLX/DE 두 operator)
**학습**: ❌
**구현**: `engine/objects.py:Design.crossover(strategy)` + `SSIEAJob.island_strategies`
**실험**: `05_EXPERIMENTS/exp012_*.md`

## 검증 결과

5 island × BLX vs 5 island × {BLX,DE,BLX,DE,BLX} 비교 (3 reps):

| 부지 | Homo HV | Hetero HV | Δ |
|---|---|---|---|
| 강남 | 270k | 276k | +2.0% |
| **분당** | 49k | **27k** | **-44%** ⚠️ |
| 춘천 | 161k | 164k | +1.7% |

**평균 -13%** — heterogeneous *항상 좋진 않음*. NSGA-III처럼 명확한 강점 부재.

## 분석
- DE crossover (x_new = x1 + F·(x2-x1), F=0.4~0.9) 가 *외삽* → 빡빡한 제약 환경 (분당 H 25m) 에서 대부분 매스가 한도 초과
- BLX-α 는 범위 내부 sampling → 안정

## Production
- **default = homogeneous BLX** 유지
- `island_mode='heterogeneous'` 옵션은 *연구용*

## 회귀
**171/171 design 테스트 통과** (3 신규 HeterogeneousIslandTest).

---

## (Original Plan)

## 목적
현재 SSIEA 5개 섬은 *모두 동일 알고리즘*. 섬마다 *다른 algorithm* (NSGA-II / NSGA-III / Differential Evolution / CMA-ES) 사용 → 다양성 +20%.

## 작업
- `ARR/backend/design/engine/objects.py` — `HeterogeneousSSIEAJob` 신규
- 섬 0=NSGA-II, 1=NSGA-III, 2=DE, 3=CMA-ES, 4=SSIEA 등
- Ring migration은 동일 (10세대마다 best 2명)

## 검증
- 단일 algorithm SSIEA 대비 hypervolume 비교
- 다양성 지표(spread) 측정
