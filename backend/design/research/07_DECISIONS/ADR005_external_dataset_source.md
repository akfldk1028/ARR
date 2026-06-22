# ADR-005 — 외부 데이터셋 출처

**Date**: 2026-05-06
**Status**: 🟡 Pending (ds02 검증 후 결정)

## Context
Phase 3 C1 SDF / C2 Diffusion 학습용 *한국 건축 매스 1k+ 데이터셋* 필요.

## Options

### Option A: Vworld 3D
- **장점**: 한국 데이터, 공공
- **단점**: LOD 수준 미확인 (LOD1 박스만 vs LOD2/3 매스)
- **다음 행동**: 샘플 10건 다운로드, LOD 확인

### Option B: 도시건축통합지도 (국토교통부)
- **장점**: 한국 데이터, 정부 공공
- **단점**: 학습 라이선스 검토 필요
- **다음 행동**: 공공데이터포털 라이선스 문의

### Option C: 건축 잡지 (공간, 건축계 등)
- **단점**: 저작권 위험 높음
- **결정**: ❌ 배제

### Option D: BuildingNet (Plan B)
- **장점**: 학습 라이선스 OK (CC BY-NC), 2k+ 매스
- **단점**: 해외 데이터, 한국 특화 약화
- **사용 시점**: A/B 모두 실패 시

## Decision Path
1. A/B 검증 (1주) → 가능하면 우선
2. 둘 다 실패 → D로 fallback + transfer learning
3. 결정 시점: Phase 3 진입 전 (예상 5-6개월 차)

## Open Questions
- Vworld 3D LOD 수준
- 도시건축통합지도 라이선스
- BuildingNet에 한국 사례 부재 시 transfer learning 효용
