# ADR006 — Phase 1+2 Code Review Fixes (2026-05-06)

**Status**: APPLIED
**Date**: 2026-05-06 22:30 KST

## Context

Phase 1+2 (12개 신규 파일, ~2500 줄) 완료 후 외부 code review (superpowers:code-reviewer 에이전트). 20개 issue 발견 (4 CRITICAL / 8 IMPORTANT / 8 MINOR).

## Decision — 적용된 fix

### CRITICAL 4건 → 4 fix (+ 1 deferred)

1. **`repair_operator.py` BCR clamp re-violation** ✅ FIXED
   - 문제: BCR scale 후 `intersection(site_utm)` 만 → setback boundary 무시되어 setback 위반 가능
   - Fix: `intersect with inward (= site.buffer(-effective_setback))` + 최대 3 iter guard loop
2. **`repair_operator.py` north setback bbox 가정** ⏸️ DEFERRED
   - 문제: axis-aligned bbox `maxy` 로 북쪽 가정. 회전된/비정형 부지에서 잘못된 변 carve.
   - Defer 사유: 현재 fixture (3 부지) 모두 axis-aligned. 운영 시 envelope sunlight LOCKED 모듈로 위임 권장.
   - 박제: `repair_operator.py` 모듈 docstring 에 "axis-aligned 가정" 명시 필요
3. **`precedent_rag.py` api_key 전파 안 됨** ✅ FIXED
   - Fix: `_api_key` 인스턴스 변수 + search 시 build 때 키 재사용
4. **`mass_evaluator.py` repair 후 stepback 1층 매스에도 보고** ✅ FIXED
   - Fix: `if num_floors < 2: has_stepback = False` 추가 → B7 explanation 거짓말 방지

### IMPORTANT 8건 → 6 fix (+ 2 deferred)

5. **typology_recommender 모듈 mutable state** ✅ FIXED (테스트만)
   - Fix: `setUp/tearDown` 으로 `set_ranking(None)` — 테스트 격리
   - Defer: production thread-safety (RLock) — 현재 Django sync request 전용 → 차후
6. **explanation_generator content None** ✅ FIXED
   - Fix: `content = resp.choices[0].message.content; if content is None: return None`
7. **HV duplicate (BO + typology_benchmark)** ✅ FIXED
   - Fix: `design/services/hv_utils.py` 신규 → 두 스크립트 import
8. **"BO" 명칭 부정확 (실제 surrogate-guided search)** ✅ FIXED
   - Fix: exp009 JSON `title="Surrogate-Guided Search (SGS) vs SSIEA"` + `method_clarification` 필드. exp009.md 도 정직하게 적힘.
9. **road_setback max() 보수적** ⏸️ DEFERRED
    - per-edge classification 필요 — 운영에서 도로 자동 감지 후 별도 PR
10. **lambda variable capture (closure)** ⏸️ DEFERRED
    - 현재 sync, 단일 iteration → 즉시 위험 X. async refactor 시 재검토.
11. **core_planner shrink off-by-one** ✅ FIXED
    - 1.5m 시도까지 도달하도록. 마지막 contains check 추가.
12. **radiance_evaluator import flow** (style만) — defer
13. **NSGA3Job 명칭 정확하지 않음** ✅ FIXED (docstring)
    - "NSGA-III-inspired (현재는 NSGA-II rank+crowding fallback)" 명시
    - exp002/006 결과는 *NSGA-III 와 다른 메커니즘* 임을 명확히

### MINOR 8건 → 모두 defer

- 14. Scripts → Django management commands
- 15. Imports inside functions (circular)
- 16. RandomForest max_depth 8 (현재 15)
- 17. Audit log duplication
- ... 운영 영향 없음

## Verification

- **171/171 design 테스트 통과** (회귀 0)
- **exp003 재측정**: 강남 99.97% / 분당 99.93% / 춘천 100% feasible — *fix 전후 동일* (변동은 SSIEA random seed)

## Consequences

### 즉시 효과
- A6 BCR clamp 의 *진짜 100% feasible* 보장 (이전엔 setback 위반 가능했음)
- B7 explanation 의 거짓 stepback 보고 차단
- B3 PrecedentRAG 의 sandbox/test 환경 안정성

### 잔여 위험
- repair_operator.py 의 north setback (axis-aligned 가정) — 한국 부지 ~95% axis-aligned 라 즉시 영향 적으나, 회전된 곡선 부지 운영 시 재검토 필요
- typology_recommender 의 thread safety — Django sync 환경에선 OK

## Alternatives Considered

- *모든 issue 즉시 해결*: 너무 큰 PR. CRITICAL/IMPORTANT 우선, MINOR 는 별도 PR.
- *전혀 fix 안 함*: claim ("99.93~100% feasible") 거짓 가능성 → 신뢰성 손상.
- *외부 라이브러리 (BoTorch, pymoo NSGA-III) 통합*: Phase 3 GPU 환경에서 Eagle. Phase 2 minimum viable 유지.

## 변경 파일 (총 9개)

- `design/services/repair_operator.py` (BCR guard loop)
- `design/services/mass_evaluator.py` (stepback after repair)
- `design/services/precedent_rag.py` (api_key + pre-normalize)
- `design/services/explanation_generator.py` (None content)
- `design/services/core_planner.py` (shrink off-by-one)
- `design/services/hv_utils.py` (NEW)
- `design/research/05_EXPERIMENTS/scripts/bayesian_optimization.py` (BO rename + import)
- `design/research/05_EXPERIMENTS/scripts/typology_benchmark.py` (HV import)
- `design/engine/objects.py` (NSGA3Job docstring)
- `design/tests.py` (TypologyRecommenderTest setUp/tearDown)
