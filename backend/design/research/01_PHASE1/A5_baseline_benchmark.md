# A5 — Baseline benchmark

**기간**: 반나절 | **학습**: ❌ | **ROI 2.0** (선행 필수)

## 목적
Phase 1/2/3 모든 변경 전후 *정량 비교 기준* 측정. 없으면 효과 입증 불가.

## 측정 항목
- **Hypervolume** (Pareto front 면적) — pymoo `pymoo.indicators.hv.HV`
- **Generational Distance (GD)** — 알려진 true Pareto 대비 거리
- **Spread** — Pareto front 분포 균등성
- **Time-to-converge** — 첫 feasible 매스 발견까지 sec
- **Total runtime** — 50 generations 완료 시간

## 작업
- 측정 스크립트: `ARR/backend/design/research/05_EXPERIMENTS/scripts/benchmark.py` 신규
- 표준 부지 3종 (강남구 역삼동 677 + 분당 + 춘천) 으로 5회 반복
- 결과: `05_EXPERIMENTS/exp001_baseline.md` 표 기록

## 출력 형식
```yaml
exp_id: exp001
date: 2026-05-XX
algorithm: NSGA-II (current)
test_sites: [강남역삼677, 분당XX, 춘천XX]
runs: 5
hypervolume_mean: 0.XX
hypervolume_std: 0.XX
runtime_min: XX
```
