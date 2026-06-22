# ADR-003 — 박스 적층 GA Deprecation

**Date**: 2026-05-06
**Status**: 🟡 Proposed (Phase 3 결과 후 최종 결정)

## Context
박스 적층 GA(현재 메인)를 Phase 3 SDF/Diffusion 검증 후 *언제 deprecate* 할 것인가?

## Decision (잠정)
**즉시 deprecate 하지 않음**. 다음 조건 *모두* 충족 시 deprecate.

## Trigger 조건
1. ✅ C2 Diffusion init GA가 박스 적층 GA 대비 *모든 지표*(품질, 속도, 다양성) 우월
2. ✅ 한국 부지 100건 회귀 테스트 통과
3. ✅ 사용자 박스 적층 사용 빈도 < 5% / 월 (3개월 관찰)
4. ✅ 4대 자산(법규 31K, PNU, Vworld, SSE) 새 시스템과 *완전 통합* 확인

## 사용자 모드 분리 (전환 기간)
- `algorithm=box-stack` → 박스 적층 GA (MVP/legacy)
- `algorithm=sdf-diffusion` → SDF 매스 (research)
- 6개월 운영 후 사용량 측정 → 최종 결정

## Risk
- 영원히 deprecate 못 할 가능성 (R4)
- 대응: 사용자 모드 분리 유지, *둘 다 운영* 도 옵션
