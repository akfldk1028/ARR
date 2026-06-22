# Phase 3 — Redesign Track (별도 트랙)

**기간**: 3-6개월 | **학습**: ✅ 본격 (외부 데이터셋 1k+ + GPU 24GB+)

## 핵심 원칙
- *기존 박스 적층 GA는 유지*. 신규 SDF/Diffusion 트랙을 *옆에* 만듦.
- Phase 3 결과가 검증된 후 (학계 SOTA 도달 시) 박스 적층 deprecate 결정 (ADR003).

## 작업 순서 (병렬 가능)
1. C5 GPU 인프라 결정 (1주) — vast.ai vs 자체 vs Colab Pro
2. ds02 한국 매스 데이터셋 (4-8주) — 04_DATASETS 참조
3. C1 SDF 매스 (4주) | C3 Differentiable Rendering (4-8주)
4. C2 Diffusion prior (8-12주)
5. C4 DRL Bootstrap (8-12주)
6. **C7 Hard Constraint Strategy** (2026-04-30 추가) — 3-layer hybrid (PGDM proj + verify cut + repair clip)

## 완료 조건
- Diffusion init GA 수렴 30→10 gen 단축
- DRL policy 새 부지 zero-shot ms 추론

## 트리거 (Phase 3 진입 조건)
1. Phase 2 완료 + Surrogate MSE plateau
2. 박스 적층 표현이 RAG 사례 매칭에 부족
3. ds02 한국 매스 데이터셋 1k+ 확보 가능성 검증

## Plan B
- 데이터셋 실패 → ds03 해외 공개(BuildingNet)
- GPU 비용 폭발 → C3 Differentiable Rendering(학습 불요)만
