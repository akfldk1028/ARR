# ADR-002 — Phase 진입/종료 조건

**Date**: 2026-05-06
**Status**: ✅ Accepted

## Phase 1 → Phase 2 트리거
- ✅ A1 NSGA-III 통합 완료
- ✅ A2 Radiance 통합 완료 (단일 매스 평가 ~30s)
- ✅ A5 baseline 측정 완료 (`exp001`)
- ⚡ **트리거**: Radiance가 GA를 비실용화 (50×30×30s ≈ 12.5h) → B1 surrogate *즉시* 시작

## Phase 2 → Phase 3 트리거
- ✅ B1 surrogate validation R² > 0.85
- ✅ B2 BO 50평가 = GA 1500평가 hypervolume 동등
- ✅ B3 RAG 사례 매칭 작동
- ⚡ **트리거 조건**:
  - Surrogate MSE plateau (더 이상 개선 안 됨)
  - 박스 적층 표현이 RAG 사례 매칭에 부족
  - ds02 한국 매스 1k+ 확보 가능성 검증 완료

## Phase 3 종료 조건
- ✅ C2 Diffusion init GA 수렴 30→10 gen 단축 검증
- ✅ C4 DRL policy 새 부지 zero-shot ms 추론
- ✅ 한국 부지 100건 회귀 테스트 통과 (4대 자산 유지)
- ⚡ **다음**: 박스 적층 deprecate 결정 (ADR003)
