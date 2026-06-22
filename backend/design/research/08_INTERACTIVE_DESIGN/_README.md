# 08_INTERACTIVE_DESIGN — 사용자 상호소통형 매스 설계

**Date**: 2026-05-25  
**Status**: PLAN MODE  
**Trigger**: 교수님 피드백 — "사용자와 상호소통되면 더 좋겠다"

## 목적

현재 시스템은 법규/PNU/VWorld 기반으로 매스를 자동 생성하고 Cesium에서 보여준다. 다음 단계는 사용자가 생성된 매스를 보면서 자연어로 수정 방향을 말하고, 시스템이 이를 안전한 설계 파라미터 변경으로 바꿔 재검증하는 것이다.

핵심은 OpenSCAD가 아니라 **상호소통형 design loop**다. OpenSCAD는 최종 산출물 export 또는 외부 검증용 보조 레이어로만 둔다.

```text
User
→ "북측 상층부를 더 부드럽게 후퇴시켜줘. 용적률은 5% 이상 잃지 말고."
→ Intent Parser
→ Mass Parameter Patch
→ Optimizer / Repair / Validator
→ Cesium 업데이트
→ Explanation Generator
→ optional OpenSCAD/STL/3MF export
```

## 문서 구성

| 파일 | 내용 |
|---|---|
| [PLAN.md](PLAN.md) | 전체 제품/기술 플랜 |
| [WORKFLOW.md](WORKFLOW.md) | 사용자 상호작용 시나리오 |
| [OPENSCAD_ROLE.md](OPENSCAD_ROLE.md) | OpenSCAD의 역할과 한계 |
| [MILESTONES.md](MILESTONES.md) | 단계별 구현 계획 |

## 결론

OpenSCAD를 붙이면 매스 품질이 자동으로 좋아지는 것이 아니다. 가치는 다음에 있다.

1. 사용자가 고른 매스를 재현 가능한 CAD 코드/파일로 내보낸다.
2. LLM/에이전트가 형상 코드를 읽고 수정안을 제안할 수 있다.
3. 최종 산출물을 STL/3MF/PNG로 검증하고 공유할 수 있다.

그러나 실시간 상호작용의 중심은 기존 `mass_geojson` + Cesium + validator가 되어야 한다.
