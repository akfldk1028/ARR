# 07_DECISIONS — Architecture Decision Records (ADR)

각 ADR은 *큰 결정* 1개를 기록. 변경 시 새 ADR 추가 (기존 supersede).

## ADR 인덱스

| ADR | 제목 | 결정 | 날짜 |
|---|---|---|---|
| [ADR001](ADR001_research_folder_location.md) | research/ 폴더 위치 | `ARR/backend/design/research/` (design 앱 내부) | 2026-05-06 |
| [ADR002](ADR002_phase_gates.md) | Phase 진입/종료 조건 | Phase 1 → 2 (Radiance 비실용화 시), Phase 2 → 3 (surrogate 한계 도달 시) | 2026-05-06 |
| [ADR003](ADR003_box_stack_deprecation.md) | 박스 적층 GA 언제 deprecate? | Phase 3 SDF/Diffusion 검증 + 4 조건 충족 시 | 2026-05-06 |
| [ADR004](ADR004_gpu_buy_vs_rent.md) | GPU 인프라 — 구매 vs 임대 | vast.ai A100 임대 우선 (필요 시 구매) | 2026-05-06 |
| [ADR005](ADR005_external_dataset_source.md) | 외부 데이터셋 출처 | Vworld 3D LOD + 도시건축통합지도 1순위, BuildingNet 2순위 | 2026-05-06 |
| [ADR006](ADR006_code_review_fixes.md) | Phase 1+2 Code Review Fixes | 4 CRITICAL + 6 IMPORTANT applied, 2 deferred (north setback rotation, road max). 171/171 통과 | 2026-05-06 |

## ADR 작성 규칙
- 제목: `ADRXXX_<short_topic>.md`
- 본문: Context → Decision → Consequences → Alternatives Considered
- supersede 시 신규 ADR 추가 + 본문에서 명시적 참조
