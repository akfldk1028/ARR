# MAAS Evidence Review - 2026-06-09

## Scope

Reviewed the current MAAS evidence/export path, AG-light MCP bridge, and
Neo4j verifier behavior after the WSL/Windows Neo4j restart.

## Verified

- `arr.maas.evidence.v0` bundle is emitted from:
  - `GET /design/jobs/<job_id>/results/<design_id>/evidence/`
- Missing PNU remains `null`; no fake parcel number is synthesized.
- Numeric values such as `0` and `0.0` are preserved when merging metrics.
- AG-light exposes:
  - `arr_maas_evidence`
  - `arr_maas_review`
- AG-light live MCP call returned `final_status = needs_evidence`.
- Neo4j graph is reachable from WSL through:
  - `NEO4J_URI=bolt://172.27.80.1:7687`
- `law/STEP/verify_system.py` passes `6/6` with the WSL host URI.
- `design.test_maas_export` passes 18 tests.
- After graph projection work, `design.test_maas_export` passes 19 tests.
- Live evidence endpoint resolves 6 Neo4j law article references.

## Fixed During Review

- `AG-light/server/main.py`
  - `create_app()` no longer returns an app missing `/health`, `/bus/*`, and
    `/memory/*` routes when called after module import.
- `AG-light/server/mcp_tools/tools.py`
  - Default `ARR_BACKEND_URL` changed to `http://127.0.0.1:18000`.
- `ARR/backend/law/STEP/verify_system.py`
  - Neo4j connection failure now stops with one clear message instead of
    cascading through every check.
- `ARR/backend/design/maas/law_provenance.py`
  - Added a non-authoritative Neo4j projection adapter for law article refs.
  - Projection is disabled during tests unless explicitly opted in, so CI does
    not depend on a live graph database.
- `ARR/backend/design/maas/evidence.py`
  - Merges graph law refs into `checks[].basis.law_articles`,
    `checks[].evidence_refs`, `legal.law_articles`, and `provenance`.

## Current MAAS Status

The MAAS pipeline is reviewable, but not complete.

The current sample candidate now has law references from Neo4j for:

- `bulk_and_density.bcr`
- `bulk_and_density.far`
- `bulk_and_density.height`
- `building_line_and_setbacks.adjacent_setback`
- `zoning_and_land_use.allowed_by_zone`
- `parking_loading_and_mobility.parking_required_count`

The current sample candidate still reports `needs_evidence` for:

- `bulk_and_density.height`
- `zoning_and_land_use.allowed_by_zone`
- `parking_loading_and_mobility.parking_required_count`
- `model_documents_and_artifacts.vworld_visual_check`

This is correct behavior. These must not be marked `pass` until backed by real
evidence.

## Next Implementation Gates

1. Add zoning/use allowance evidence:
   - requested use
   - normalized use class
   - allowed/prohibited/conditional result
   - source law/ordinance refs
2. Add parking evidence:
   - required count
   - provided count
   - formula/input assumptions
   - layout feasibility status
3. Add height/datum basis:
   - datum source
   - computed height limit
   - applied legal articles
4. Add real-browser VWorld/Cesium placement artifact:
   - screenshot or pixel-check asset
   - browser console/network result
   - `validators.runs[]` entry
5. Persist actual agent review outputs into `agent_reviews`.

## Non-Negotiable

MAAS candidates can be shown as generated alternatives, but final legal approval
must remain blocked while any hard `needs_evidence` check exists.
