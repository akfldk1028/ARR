# Phase 1 — Quick Wins

**기간**: 1-2주
**학습**: ❌ 불필요
**목표**: 학계 표준 평가 인프라 확보. 코드 변경만으로 SOTA 격차 줄이기.

## 작업 순서

1. **A5** Baseline 측정 (반나절) — 정량 비교 기준
2. **A6** Repair Operator 신규 (1주) — ⭐ Hard constraint 강제, Flexity 격차 해소 핵심
3. **A3** Constraint penalty 정교화 (3일) — `objects.py:189-205`
4. **A1** NSGA-III pymoo 통합 (1주) — `objects.py` 에 NSGA3Job 추가
5. **A4** Evaluator 통일 (2일) — `mass_evaluator.py` 입출력 표준화
6. **A7** Constraint Visualizer 신규 (3-5일) — Cesium envelope + 매스 fit
7. **A2** Radiance lite (1주) — pyradiance/honeybee-radiance, ~30s/매스

## 완료 조건

- NSGA-II vs NSGA-III 동일 부지 비교 실험 1회 완료
- Radiance UDI 평가 1매스 회귀 테스트 통과
- A5 baseline → 최종 결과 정량 차이 측정 (hypervolume)

## Phase 2 트리거

Radiance가 GA 비실용화(50 gen × 30 indiv × 30s ≈ 12.5h) → 즉시 Phase 2 B1 surrogate 시작.

## 필요 도구

- pymoo>=0.6 (requirements.txt 추가 필요)
- pyradiance 또는 honeybee-radiance + Radiance 바이너리 별도 설치
