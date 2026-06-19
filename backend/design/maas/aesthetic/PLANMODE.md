# MAAS Aesthetic Pipeline PLANMODE

Updated: 2026-06-09

## Goal

Make legal MAAS masses visually presentable without letting an image model alter
legal geometry.

The pipeline must start from `/design` results or a canonical MAAS evidence
bundle and end with generated image assets plus validation records.

## Non-Negotiable Contract

Allowed changes:

- facade material
- window rhythm
- surface detail
- lighting
- presentation style

Forbidden changes:

- `mass_geojson`
- footprint
- height
- floor count
- setbacks
- roofline
- legal envelope
- legal check status

Image output is an aesthetic artifact. It is not proof of legal compliance.

## Target Pipeline

```text
/design MAAS result
-> evidence bundle
-> aesthetic image job
-> reference render asset
-> provider adapter
   - gpt-image / nano-banana image-to-image
   - UniTEX GPU worker for mesh texturing
-> generated image/mesh assets
-> silhouette + geometry validation
-> evidence asset/provenance attachment
-> agent review
```

## Current Implemented Files

- `image_job.py`
  - builds `arr.maas.aesthetic_image_job.v0`
- `prompts.py`
  - builds facade/material prompt with locked geometry constraints
- `reference_render.py`
  - builds deterministic render spec; does not render pixels yet
- `validators.py`
  - validates job contract and provider result contract
- `pipeline.py`
  - orchestrates job validation, reference renderer, provider adapter, and
    result validation
- `adapters/`
  - provider interfaces and placeholder adapters
- `renderers/`
  - reference renderer interfaces and deterministic PNG renderer
- `storage/`
  - evidence asset/provenance attachment helpers
- `external/`
  - ignored local checkouts of paper code

## Provider Plan

### `gpt-image`

Use for quick image-to-image facade/material studies.

Adapter needs:

- reference PNG path
- prompt/negative prompt
- output image path or remote asset URL
- model response metadata

### Nano Banana

Use as another image-to-image provider if API access is available.

Adapter needs the same provider contract as `gpt-image`. Do not add
provider-specific fields to core evidence; keep them under provider metadata.

### UniTEX

Use for geometry-aware textured mesh generation.

Current local checkout:

- `external/UniTEX`
- revision: `affa1e2`
- license: Apache-2.0

Do not install UniTEX dependencies into ARR backend venv. Run it in a separate
Python 3.10 CUDA worker. ARR should call it through a thin adapter or subprocess
boundary.

## Implementation Phases

1. Reference renderer
   - Convert `mass_geojson` to deterministic white-mass PNG.
   - Save asset path and hash.
   - Status: implemented by `ReferencePngRenderer`.
2. Provider adapters
   - Implement `gpt-image` adapter.
   - Implement Nano Banana adapter if API/env details are available.
   - Keep UniTEX as separate GPU worker.
   - Status: `gpt-image` and generic `nano-banana` adapters implemented;
     both are safe without keys and return `not_configured`.
   - `gpt-image` default model: `gpt-image-2`.
   - Nano Banana default model: `gemini-2.5-flash-image-preview`.
3. Validation
   - Compare generated image silhouette against reference render.
   - Record `pass/fail/needs_review`.
   - Status: provider contract validation implemented; pixel silhouette compare
     still pending.
4. Evidence attachment
   - Add reference image, generated image, prompt, provider metadata, and
     validation result as assets/provenance.
   - Status: implemented by `storage/evidence_assets.py`.
5. Frontend
   - Add candidate action in `/design`: `Generate Facade`.
   - Show reference render, generated image, validation badge, and provider
     metadata.
   - Status: pending.

## Next Session Checklist

1. Read this file first.
2. Run `/design` focused verification if services are already up.
3. Use `build_aesthetic_pipeline()` in `pipeline.py`.
4. Replace placeholder renderer with real render implementation.
5. Replace placeholder provider with real API adapter.
6. Keep evidence schema stable; attach outputs as assets/provenance instead of
   adding random top-level fields.
