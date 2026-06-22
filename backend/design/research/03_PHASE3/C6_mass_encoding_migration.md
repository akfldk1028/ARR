# C6 — 박스 적층 → SDF 마이그레이션 / Deprecation

**기간**: 4-8주 | **학습**: ❌ (전환 작업)

## 핵심 원칙
- 박스 적층은 **즉시 deprecate 하지 않음**.
- Phase 3 SDF/Diffusion이 *학계 SOTA 검증* 완료 후 사용자 모드 분리.

## 마이그레이션 단계
1. Phase 3 C1 SDF + C2 Diffusion 검증 완료
2. 한국 부지 100건 회귀 테스트 통과 (4대 자산 보존)
3. 사용자 모드 분리:
   - `algorithm=box-stack` → 박스 적층 GA (MVP/legacy)
   - `algorithm=sdf-diffusion` → SDF 매스 (research)
4. 6개월 운영 후 사용자 사용 빈도 측정 → 박스 적층 deprecate 결정 (ADR003)

## ADR003 트리거
- C2 Diffusion init GA가 박스 적층 GA 대비 모든 지표(품질, 속도, 다양성)에서 우월
- 한국 부지 100건 회귀 테스트 통과
- 사용자 박스 적층 사용 빈도 < 5% / 월

## Risk
- 영원히 deprecate 못 할 가능성 (R4)
- 대응: 사용자 모드 분리 유지, *둘 다 운영*
