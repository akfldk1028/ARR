# Interactive MAAS

Updated: 2026-05-28

This folder owns direct/conversational mass editing before it enters the legal
MAAS generator.

## Flow

1. UI gesture or chat intent becomes an operation object.
2. `schemas.py` normalizes that operation.
3. `geometry_ops.py` creates a temporary geometry seed.
4. `orchestrator.py` sends the seed through `generate_legal_mass_variants()`.
5. `design.maas.agents` returns deterministic multi-agent review objects.

Every positive geometry edit must return through legal MAAS repair before the
client can preview it.

## Supported Operation Types

- `push_pull_face`: top-face/floor push-pull. Legacy `push_pull_height` is
  normalized to this type.
- `offset_edge`: side/edge offset before legal repair.
- `scale_footprint`: whole-footprint scale before legal repair.
- `reshape_floor_plate`: reserved alias for floor-plate reshaping.

## Next Step

Cesium entities now carry `interactionKind` and `target` metadata. The next UI
step is a screen-space picking/drag controller that emits these operation
objects instead of using only buttons.
