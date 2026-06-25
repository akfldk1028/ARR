# MAAS Legal Envelope Handoff

Updated: 2026-06-25

## 2026-06-25 MAAS Agent Modularization / AG-light Flow State

- User goal: the right-side "AI 설계 협업" must show a real law-to-design
  collaboration, not a decorative graph. The backend agent structure should be
  modular like official ADK/A2A examples: each agent owns a folder, card, and
  contract; the orchestrator owns the canonical flow.
- Current backend structure:
  - `agents/orchestrator/flow.py`: canonical handoff sequence
    `user -> design_orchestrator -> law_graph_agent -> parking_agent -> maas_geometry_agent -> review_agent -> design_orchestrator`.
  - `agents/orchestrator/agent.py`: top-level routing card/result.
  - `agents/law_graph_agent/agent.py`: FAR/BCR/height constraint review.
  - `agents/parking_agent/agent.py`: parking count/layout precheck review.
  - `agents/maas_geometry_agent/agent.py`: MAAS operation/shape explanation.
  - `agents/review_agent/agent.py`: rejected-candidate/final audit summary.
  - `agents/shared/types.py`: `AgentContext`, `AgentResult`, `AgentCard`, `MaasAgent`.
  - `agents/shared/registry.py`: registry/card builder and review runner.
  - `agents/shared/evidence.py`: shared feature/parking evidence helpers.
  - `agents/contracts.py`: compatibility wrapper for existing interactive endpoint; it delegates to the registry now.
- Current agent ids are intentionally aligned with
  `JSON_MODULES/teams/041_MAAS_Legal_Design_Team.json` and frontend
  `ARR/frontend/src/design/components/ag-light-flow/agents/*`:
  `law_graph_agent`, `parking_agent`, `maas_geometry_agent`, `review_agent`.
  Do not reintroduce old ids `law_agent`, `geometry_agent`, or
  `optimization_agent` in API output.
- `ARR/backend/design/scripts/ag_light_agent_flow_cli.py` imports
  `orchestrator.flow.FLOW_STEPS` instead of duplicating flow text. This keeps
  CLI, backend, and React Flow semantics aligned.
- Verified this session:
  - Python compile for modified agent/CLI files passed with `.venv/bin/python`.
  - Direct registry smoke check returned cards:
    `design_orchestrator, law_graph_agent, parking_agent, maas_geometry_agent, review_agent`.
  - Django targeted tests passed:
    `test_interactive_operation_endpoint_returns_synced_metrics`,
    `test_interactive_offset_edge_returns_agent_reviewed_legal_mass`,
    `test_maas_agent_registry_exposes_flow_cards`.
  - AG-light CLI live bus smoke passed:
    `.venv/bin/python design/scripts/ag_light_agent_flow_cli.py --runs 1 --delay 0 --base-url http://127.0.0.1:8200`
    returned `success_rate: 100.0%`.
- Next frontend work, if requested:
  - React Flow should display per-agent reasoning/evidence from `agent_reviews`
    and A2UI updates: cited legal limits/rule ids, parking count/layout evidence,
    MAAS operation/shape reason, and final review status.
  - Keep the graph visually simple and vertical. Lines must be readable; avoid
    dense crossed edges. The user expects the flow to show real-time progress
    when PNU lookup/optimization runs.

## 2026-06-15 Parking Layout / VWorld Resume State

- User issue: parking looked like odd diagonal/floating lines, stalls were visually unclear, adjacent small stalls were separated, and the sidebar did not explain why the legal count was what it was.
- Current implementation state:
  - Live Neo4j parking graph is available from WSL at
    `bolt://172.27.80.1:7687` with `NEO4J_PASSWORD=11111111`.
    The backend must be started with these env vars to avoid JSON fallback:
    `NEO4J_URI=bolt://172.27.80.1:7687 NEO4J_PASSWORD=11111111 .venv/bin/python manage.py runserver 127.0.0.1:18000`.
    Latest graph checks: `verify_parking_law_graph.py` `49/49 passed`,
    `check_parking_counts.py` `23/23 passed`.
  - `ARR/backend/design/maas/parking_layout.py`
    - Grid solver still operates at mass-stage feasibility, not final BIM.
    - Candidate selection now tries same-row contiguous stalls first.
    - Expected small-row result: `adjacency.status=row_contiguous`, `gap_pairs=0`, `max_gap_m=0`.
    - Layout result now includes `layout_formula`, `adjacency`, `column_clearance`, `drive_aisle_clearance`, and `turning_clearance`.
    - Grid result now includes `entrance_connection_type`, `entrance_verified`,
      and connector dimensions; `site_connector_v1` means a 3m-wide straight
      connector corridor from drive cell to road frontage stays inside the drive
      area and real `road_frontage_geometry` is present.
    - Piloti columns/cores are not read from structural drawings. Current status `column_clearance.status=deferred_structural_review` means record the assumed clear bay but do not display it as OK.
    - Turning is not a vehicle swept-path simulation. Current method `stall_frontage_and_entrance_connector_v1` checks whether stalls have enough frontage on the generated 6m drive aisle and whether that aisle connects to the entrance connector. For `grid_connected_90` row-contiguous stalls, `contiguous_row_frontage_relief` accepts a row with one generated 6m drive cell per stall to avoid false line-intersection failures.
    - For `공동주택`, `parking_requirements.py` now computes a mass-stage housing parking estimate from `주택건설기준 등에 관한 규정 제27조` and Seoul ordinance row 5. `legal_mesh_optimizer.py` supplies a `mass_stage_estimate` household/exclusive-area schedule from floor plates, or `num_floors * footprint_area` when floor plates are absent. This is a planning estimate until real household/exclusive-area schedules are supplied.
  - `ARR/frontend/src/design/lib/cesium/mass-entities.ts`
    - Exact stall polygons render as clean solid pink lines (`#ff2f92`) with dark shadow/raised visible line.
    - Raised stall lines are drawn higher/thicker (`groundH + 1.15m`) so they remain visible through translucent mass volumes.
    - Parking envelope/hatch/guide clutter is suppressed when exact stalls exist.
    - `grid_solver.entrance_connector_polygon_wgs84` renders as a low-alpha cyan corridor/outline plus thin centerline for the 3m road-to-drive connector.
    - Piloti support columns and `PILOTI VOID` labels are intentionally not rendered until explicit structural column/core polygons exist.
  - `ARR/frontend/src/design/components/DesignInspector.tsx`
    - Shows legal parking formula, rule id, layout mode, 11m/16m module formula, adjacency, aisle, entrance connector, and turning.
    - Column/core status is intentionally hidden for now; backend evidence may still record `deferred_structural_review`.
  - Playwright batch script:
    - `docs/playwright/design-route-live-verify/windows-cdp-vworld-pnu-batch.cjs`
    - Uses Windows Chrome CDP/VWorld and saves zoom PNGs.
- Latest verified command:
  ```bash
  powershell.exe -NoProfile -Command "node D:\\Data\\25_ACE\\docs\\playwright\\design-route-live-verify\\windows-cdp-vworld-pnu-batch.cjs --cases=D:\\Data\\25_ACE\\docs\\playwright\\design-route-live-verify\\parking-stall-cases.json"
  ```
- Latest live local URL: `http://127.0.0.1:5174/design`
- Latest JSON/PNG result paths:
  - `docs/playwright/design-route-live-verify/pnu-batch/01_gangnam-small-neighborhood-stalls_1168011800104170004.json`
  - `docs/playwright/design-route-live-verify/pnu-batch/02_gangnam-dogok-neighborhood-stalls_1168011800104670003.json`
  - `docs/playwright/design-route-live-verify/pnu-batch/zoom_01_gangnam-small-neighborhood-stalls_1168011800104170004.png`
  - `docs/playwright/design-route-live-verify/pnu-batch/zoom_02_gangnam-dogok-neighborhood-stalls_1168011800104670003.png`
- Latest observed values:
  - PNU `1168011800104170004`: `piloti_ground`, required/provided `3/3`, `parkingStallEntities=3`, `parkingEntities=12`, `pilotiEntities=0`, `adjacency.status=row_contiguous`, `touching_pairs=2`, `gap_pairs=0`, `max_gap_m=0`, backend `column_clearance.status=deferred_structural_review` only, aisle `6m`, `turning_clearance.status=v1_pass`, `turning_clearance.frontage_connected_stalls=1/3`, `turning_clearance.contiguous_row_frontage_relief.available=true`, `grid_solver.entrance_verified=true`, `grid_solver.entrance_connection_type=site_connector_v1`, connector length `8m`, connector width `3m`, connector WGS84 polygon present/rendered, layout status `pass`.
  - PNU `1168011800104170004` with building type `공동주택`: default-apartment parking count/visual regression fixed. `required_count.status=computed_estimate`, `selected_rule_id=seoul_parking_appendix2_row_05`, `base_rule_id=parking_appendix1_row_05`, `source_ordinance=seoul_parking_ordinance`, `required_spaces=3`, `raw_spaces=2.4`, `unit_schedule.source=mass_stage_estimate`, `parkingStallEntities=3`, `parkingEntities=12`, `pilotiEntities=0`, selected strategy `ground_surface`, layout status `needs_swept_path_review`, and the PNG path is `docs/playwright/design-route-live-verify/pnu-batch/zoom_01_gangnam-small-apartment-visual-stalls_1168011800104170004.png`. Count estimate is graph-backed; final turning/swept-path remains unresolved.
  - PNU `1168011800104670003`: `ground_surface`, required/provided `1/1`, `parkingStallEntities=1`, `column_clearance.status=not_applicable`, `drive_aisle_clearance.status=needs_review`, `turning_clearance.status=needs_swept_path_review`, layout status `needs_aisle_review`.
- Verification completed this session:
  - Django targeted parking tests passed:
    `design.test_maas_export.MaasLegalVariantsTest.test_parking_layout_grid_solver_prefers_adjacent_small_stalls`,
    `test_parking_layout_grid_solver_places_connected_drive_cells`,
    `test_parking_layout_candidate_places_internal_double_loaded_stalls`,
    and connector entrance tests.
  - Frontend `npm run type-check` passed.
  - Windows Chrome CDP Playwright batch passed for both parking-stall cases.
  - Visual PNG for `1168011800104170004` now shows the 3 contiguous stall lines and no piloti column helper entities. The remaining large translucent pink diagonal in some views is the pre-existing sunlight/legal envelope overlay, not parking.
- Review notes for next session:
  - Do not call this "final parking approval". It is a v1 mass-stage solver.
  - Main remaining work is replacing `site_connector_v1` with real entrance throat geometry, swept-path validation, and explicit column/core polygons. The row-frontage pass is a mass-stage v1 assumption, not a vehicle swept-path simulation.
  - Real structural column/core polygons, basement ramp geometry, mechanical equipment, accessible route, and swept-path vehicle simulation are still not implemented.
  - If the user complains about columns again, explain that columns are intentionally deferred now; implement actual `column_polygons/core_polygons` input before claiming real conflict clearance.

## 2026-06-05 Resume Result

- Recovered the interrupted MAAS `/design` work from the dirty tree.
- Verified backend `design.test_maas_export design.test_interactive_patch`: 22 tests passed before edits.
- Verified backend full `design`: 196 tests passed.
- Verified frontend `npm run type-check` and `npx vite build --mode web`: passed.
- Verified live API flow on `PNU 1168011800104170004`:
  - `site-boundary` -> `auto-constraints` -> `jobs` -> `run` -> `results`.
  - `maas_legal_envelope` returned 18 Pareto candidates.
- Fixed the tiny FAR-remainder floor issue:
  - Before: first `legal_layered_max` candidate produced a 6th floor plate of `6.44m2`.
  - After: first candidate is 5 floors, `17.5m`, FAR `136.78%`, floor plate areas `[102.93, 102.93, 74.99, 51.47, 28.96]`.
  - Rule: do not create a standalone floor plate below `min(24m2, ground_plate_area * 0.25)`.
- Added regression checks in `design.test_maas_export` so legal floor plates do not include tiny architectural remainder floors.

## Direction

- MAAS generation is legal-envelope-first.
- The old 10 mass algorithms are no longer the capacity source; they are seed/operator diversity sources after the legal layered candidate.
- `legal_layered_max` should be the primary candidate: it clips each floor plate by the legal envelope, then fills FAR/BCR as much as the constraints allow.

## Key Files

- `legal_envelope.py`: builds the legal envelope and per-floor `floor_plates`.
- `legal_mesh_optimizer.py`: ranks `legal_layered_max` and seed variants by FAR/BCR utilization plus diversity.
- `seed_library.py`: wraps legacy mass logic as seeds/operators.
- `interactive/`: operation schema, geometry seed mutation, and legal-repair orchestration.
- `agents/`: deterministic multi-agent review contract for Geometry/Law/Optimization/Review plus ARR A2UI message emission.
- `../services/mass_operations.py`: compatibility wrapper for the interactive MAAS orchestrator.

## Verification Notes

- Important PNU: `1168011800104170004`.
- Also checked: `1168011800104670003`, `1129010100103300000`, `1168010100106770000`, `1165010800113170029`.
- Django `design` tests passed: 196 tests on 2026-06-05.
- `design.test_maas_export` passed: 15 tests on 2026-06-05.
- Playwright/API operation request passed against backend `18001`.
- Frontend `npx vite build --mode web` passed on 2026-06-05.
- Official A2UI reference repo cloned to `/mnt/d/Data/25_ACE/clone/A2UI` at `e05dd969`.

## Current Limits

- Do not describe this logic as complete or perfect. It is a verified prototype path for legal-envelope-first mass generation.
- The UI has coarse `층+`, `층-`, `폭+`, `폭-`, and edge-offset operation buttons. Cesium mass entities now carry interaction metadata, but true click-drag face editing is still the next UI controller step.
- `buildable_footprint_from_setback_geometries()` uses line half-plane clipping with the site representative point. This worked in tested PNUs, but concave parcels and complex multi-road parcels need stronger edge-normal metadata or direct trusted buildable polygons.
- The tiny FAR-remainder floor issue has a first pass threshold now. It still needs architectural review for program-specific minimum plates, especially by building type and core feasibility.
- Headless Playwright verifies the React/API flow, not final Cesium/WebGL pixels in this environment.
- A candidate should be treated as reviewable only after API metrics, floor plates, legal datum/envelope basis, and real-browser VWorld placement all agree.
