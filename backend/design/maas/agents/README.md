# MAAS Agent Contracts

Updated: 2026-05-28

This folder defines the multi-agent contract for interactive massing.

Current agents are deterministic local reviewers:

- `geometry_agent`: records how the user's edit was converted into a MAAS seed.
- `law_agent`: checks returned FAR/BCR/height against the legal summary.
- `optimization_agent`: reports utilization and MAAS score.
- `review_agent`: summarizes audit state and selected mass shape.

The contract is intentionally JSON-first so later LLM agents or MCP workers can
replace individual reviewers without changing the frontend response shape.

## A2UI

`a2ui_surface.py` emits v0.9-style A2UI messages using the ARR catalog id
`arr.maas.agent_review.v0`. The official reference repo is cloned at
`/mnt/d/Data/25_ACE/clone/A2UI`.
