# MILESTONES — 구현 단계

## M0 — Plan freeze

목표:
- 상호소통형 설계 루프의 source of truth 확정
- OpenSCAD를 보조 레이어로 제한

산출물:
- 본 폴더 문서 4개

## M1 — Natural language to patch

범위:
- 사용자 발화를 intent JSON으로 변환
- 실제 optimizer 수정은 하지 않고 dry-run patch만 생성

예:

```text
"북측 상부를 더 낮춰줘"
→ {"intent": "lower_north_upper_mass", "target_side": "north"}
```

수정 후보 파일:
- `ARR/backend/design/services/interactive_patch.py`
- `ARR/backend/design/views.py`
- `ARR/frontend/src/design/components/*`

성공 기준:
- 10개 대표 발화가 안정적인 patch schema로 변환됨

현재 상태:
- 1차 구현 완료. `POST /design/interactive/patch/`
- 대표 intent: 북측 상부 후퇴, 도로측 포디움, 코어 이동, 비례 조정, 용적률 보강
- `동선`을 `동측`으로 오해하지 않도록 방향 파서 보정

## M2 — Patch apply + validator gate

범위:
- patch를 기존 mass inputs에 적용
- evaluator/validator 재실행
- pass/fail과 지표 변화 반환

성공 기준:
- 원안/수정안 FAR/BCR/height/daylight 비교 가능
- fail 후보는 UI에 "법규상 불가"로 표시

현재 상태:
- 1차 구현 완료. `POST /design/interactive/preview/`
- 선택된 design inputs를 보수적으로 조정해 mass_geojson/metrics/feasible/penalty 반환
- 전체 optimizer 재실행 없이 미리보기 생성
- 정북일조 hard envelope 및 코어 평면 검증은 다음 단계에서 강화 필요

## M3 — Interactive compare UI

범위:
- 원안/수정안 비교
- 사용자가 후보를 채택하거나 다시 수정 요청
- Explanation Generator와 연결

성공 기준:
- 교수님 데모 시나리오 3개 통과

## M4 — Optional OpenSCAD export

범위:
- 선택된 최종안을 `.scad`로 export
- OpenSCAD CLI가 있으면 `.stl/.3mf/.png` 생성

수정 후보 파일:
- `ARR/backend/design/services/openscad_exporter.py`
- `ARR/backend/design/views.py`

성공 기준:
- single-tier mass export
- two-tier stepback mass export
- CLI 미설치 환경에서도 graceful fallback

## M5 — Multi-agent design review

범위:
- Design Chat Agent
- Constraint Agent
- Patch Agent
- Validator Agent
- Explanation/Export Agent

성공 기준:
- 사용자 요청 1개에 대해 후보 2-3개 생성
- pass 후보만 제시
- 설명과 export 산출물 동시 제공

## 우선순위

```text
M1 → M2 → M3 먼저.
M4 OpenSCAD는 뒤.
M5 멀티에이전트는 M1-M3 schema가 안정된 뒤.
```

이유:
- 사용자가 원하는 것은 상호소통이다.
- OpenSCAD는 그 자체로 상호소통을 만들지 않는다.
- 먼저 자연어 → 안전한 설계 변경 루프를 만들어야 한다.
