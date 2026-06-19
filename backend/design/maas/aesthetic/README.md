# MAAS Aesthetic Image Generation

This package prepares MAAS candidates for facade/material image generation.

Core rule:

- MAAS legal geometry is the source of truth.
- Image models may add facade language, materials, atmosphere, and presentation
  quality.
- Image models must not change the approved mass silhouette, height, floor
  count, setbacks, or legal envelope.

Pipeline:

```text
MAAS evidence bundle
-> deterministic multi-view reference render specification
-> facade/material prompt
-> image model job
-> silhouette/geometry validation
-> evidence assets + agent review
```

Use code for:

- deterministic camera/reference render specs
- deterministic multi-view reference PNG generation from locked `mass_geojson`,
  `floor_plates`, and `mass_volumes`
- prompt construction from evidence
- image job records
- provider adapters for GPT Image / Nano Banana contract
- asset/provenance links
- silhouette and consistency validation

Use skills/manual prompting for:

- style vocabulary research
- prompt template refinement
- one-off visual experiments
- critic/reviewer instructions

Do not allow image generation to mark legal checks as pass.

## Implemented Provider Behavior

- `placeholder`
  - Local dry-run adapter.
  - Generates no image provider asset.
  - Used to verify the pipeline contract without API keys.
- `gpt-image`
  - Uses OpenAI Image API edit when `OPENAI_API_KEY` is set.
  - Default model: `gpt-image-2`.
  - Env overrides: `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_SIZE`.
- `nano-banana`
  - Uses Google Gemini API when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set.
  - Default model: `gemini-2.5-flash-image-preview`.
  - Env override: `NANO_BANANA_MODEL`.
  - Also supports generic HTTP fallback with `NANO_BANANA_ENDPOINT` and
    `NANO_BANANA_API_KEY`.
- `unitex`
  - Researched and checked out under `clone/maas-aesthetic-texturing/UniTEX`.
  - Must run as a separate CUDA worker; do not install into ARR backend venv.

## Current Live Dry-Run

Live evidence can now produce a locked multi-view reference PNG:

```text
evidence -> aesthetic job -> multi-view reference PNG -> provider adapter -> evidence asset attachment
```

If no provider key/endpoint is configured, the pipeline returns `needs_provider`
instead of pretending an image was generated.

## Live API / Frontend Integration

The pipeline is exposed through:

```text
POST /design/jobs/<job_id>/results/<design_id>/aesthetic/
GET  /design/maas/aesthetic-assets/<asset_path>
```

Request body:

```json
{
  "provider": "placeholder",
  "style": "warm brick residential facade",
  "attach_to_evidence": true
}
```

Valid providers are `placeholder`, `gpt-image`, and `nano-banana`.

The `/design` candidate panel calls this endpoint from the `외관 이미지 생성`
section. The frontend displays the deterministic multi-view reference PNG first,
then the provider image if a real image adapter returns an asset.

Important boundary:

- The generated image is only a visualization/evidence asset.
- The locked `mass_geojson` remains the geometry source of truth.
- Provider output must not modify silhouette, floor count, height, setbacks, or
  legal envelope.

Verified browser dry-run:

```text
docs/playwright/design-route-live-verify/windows-cdp-aesthetic-check.cjs
docs/playwright/design-route-live-verify/windows_chrome_aesthetic_check.png
docs/playwright/design-route-live-verify/windows-chrome-aesthetic-check.json
```

Expected dry-run result without provider keys:

- `placeholder · needs_provider / needs_provider`
- multi-view reference image loaded from `/design/maas/aesthetic-assets/references/*.multi-view.png`
- `legal_status_effect: none`

## Research Direction

The correct next step is not a single beauty render. Current architecture and
3D-texturing papers point to a geometry-conditioned flow:

```text
MAAS 3D mass
-> multi-view orthographic/axon references
-> depth/normal/silhouette/floor-line guides
-> scene graph
-> image/facade synthesis
-> projection or texture asset on the same mass
```

Relevant direction:

- WACV 2025, `3D Synthesis for Architectural Design`: architectural mass first,
  facade synthesis second.
- CAADRIA 2025, `Multi-View Depth Consistent Image Generation`: predefined
  architectural views plus depth consistency.
- CVPR 2026, `UniTEX`: lift multi-view visual outputs into consistent 3D
  texture representation.

Current implementation covers the first production step: `MultiViewReferencePackRenderer`
with front/right/back/left/axon/top panels and a lightweight
`arr.maas.scene_graph.v0` metadata graph.
