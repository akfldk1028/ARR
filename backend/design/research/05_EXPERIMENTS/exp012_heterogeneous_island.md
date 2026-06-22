# exp012 — B4 Heterogeneous Island (BLX/DE) vs Homogeneous (BLX)

**Date**: 2026-05-06 21:37 KST (실측 완료)
**Phase**: 2
**작업 ID**: B4 Heterogeneous Island
**부지**: 3 fixture × 2 mode × 3 reps = 18 SSIEA runs
**Engine**: SSIEAJob + A6 repair on + A3 normalized

## 가설

5 island 가 모두 BLX-α crossover (homogeneous) 를 쓰는 대신, 절반은 Differential Evolution (DE) 사용 → 다양성 ↑ → HV 향상.

**DE rand/1**: x_new = x1 + F · (x2 - x1), F ~ Uniform(0.4, 0.9)
**BLX-α**: x_new ~ Uniform(min - d/3, max + d/3), d=|x1-x2|

## 결과 (실측)

| 부지 | Homo HV (BLX×5) | Hetero HV (BLX/DE alternate) | Δ |
|------|------|------|------|
| 강남 | 270,803 | 276,290 | **+2.0%** |
| **분당** | **49,618** | **27,778** | **-44.0%** ⚠️ |
| 춘천 | 161,764 | 164,540 | +1.7% |

**평균 Δ HV: -13.4%** — *honest negative*.

## 분석

### 분당 -44% — DE의 약점 노출
- 분당은 BCR 60% / FAR 250% / **height 25m** 빡빡한 제약
- DE crossover x_new = x1 + F·(x2-x1) → range 끝까지 *외삽*
- A6 repair 가 매스를 cap 하지만, 외삽 매스는 처음부터 *대부분 height 한도 초과*
- BLX-α는 범위 *내부* 에서 sampling → 더 안정

### 강남 / 춘천 +2% — 미미한 향상
- 한도 여유 있음 → 외삽도 합리적 범위
- 하지만 +2% 는 *random noise 수준* (3 reps 으로 95% CI 넓음)

### 결론

❌ **Heterogeneous (BLX/DE alternate) 가 항상 좋진 않음**.
- 빡빡한 제약 환경: BLX 단독이 안정
- 여유 있는 제약 환경: 차이 미미

NSGA-III (exp006 +189~375%) 같은 *명확한 강점* 없음. *implementation 단순화* 필요.

## Improvement Ideas (Follow-up)

1. **Migration 의존도 ↑** — 현재 5 round 마다만. DE island가 BLX migrant 받아야 가치 발휘 가능.
2. **DE F factor adaptive** — 빡빡한 제약 시 F=0.3 (보수적), 여유 시 F=0.9 (적극)
3. **추가 operator** — CMA-ES, PSO 통합. 현재 BLX/DE 둘만 비교는 narrow.
4. **island별 mutation rate 다르게** — exploration island vs exploitation island 분리

## Production 권장

- **default = homogeneous BLX** (exp012 분당 결과 기반)
- heterogeneous 모드는 *연구 옵션* 으로 유지 (`island_mode='heterogeneous'`)
- 운영에선 NSGA-III (4+ obj) + SSIEA (2 obj) 선택이 더 큰 가치

## 변경 파일
- `design/engine/objects.py` — `Design.crossover(strategy='blx'|'de')` 옵션 + SSIEAJob `island_strategies`
- `05_EXPERIMENTS/exp012_data.json` — raw HV per site/mode/rep

## 회귀
**171/171 design 테스트 통과** (3 신규 HeterogeneousIslandTest).
