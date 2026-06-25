# MAAS Design Agents

Updated: 2026-06-25

This folder defines the deterministic ARR-side agent layer for MAAS legal
massing. The structure follows the Google ADK/A2A pattern at a local scale:
each agent has its own package, card builder, and contract, while
`orchestrator/flow.py` owns the canonical handoff sequence.

## Flow

`design_orchestrator -> law_graph_agent -> parking_agent -> maas_geometry_agent -> review_agent`

- `design_orchestrator`: routes a PNU/design candidate into the law-to-design flow.
- `law_graph_agent`: checks FAR/BCR/height against structured legal constraints.
- `parking_agent`: summarizes parking count and layout precheck evidence.
- `maas_geometry_agent`: explains the selected MAAS repair/shape operation.
- `review_agent`: summarizes rejected candidates and final audit state.

`contracts.py` is a compatibility wrapper used by the existing interactive
operation endpoint. It now delegates to `shared/registry.py`, so future agent
implementations can replace one folder without changing the endpoint response
shape.

## A2UI

`a2ui_surface.py` emits v0.9-style A2UI messages using the ARR catalog id
`arr.maas.agent_review.v0`. The frontend React Flow surface maps the same agent
ids, and the AG-light CLI imports `orchestrator.flow.FLOW_STEPS` so CLI and UI
stay aligned.
