# MAAS Aesthetic Image Generation Plan - 2026-06-09

## Decision

Use code as the source of truth and skills/prompts as support.

Image generation must be downstream of MAAS evidence:

```text
MAAS mass/evidence
-> deterministic reference render
-> prompt/image model
-> silhouette validation
-> evidence assets
-> agent review
```

## Latest Research Direction

Use recent geometry-aware texture and architectural synthesis work as the main
guide:

- Tsai & Hariharan 2025, WACV, *3D Synthesis for Architectural Design*
  - Closest fit. Starts from a 3D architectural massing model and applies
    facade-by-facade inpainting diffusion.
  - Important limitation: legal massing is assumed, not solved.
- MD-ProjTex 2025
  - Fast text-guided texture generation using multi-diffusion projection.
- UniTEX 2025
  - High-fidelity generative texturing for 3D shapes.
  - Code is now available and locally checked out under
    `design/maas/aesthetic/external/UniTEX` for inspection.
  - It should run in a separate CUDA environment; do not merge its dependencies
    into the ARR backend venv.
- TextureDreamer 2024
  - Geometry-aware diffusion for image-guided texture transfer.
- TEXTure, SIGGRAPH 2023
  - Text-guided texturing of existing 3D shapes.
- Text2Tex 2023
  - Progressive multi-view texture synthesis for meshes.

Older SIGGRAPH papers are still useful, but as foundations:

- Mueller et al., SIGGRAPH 2006, procedural modeling of buildings.
- Wu et al., SIGGRAPH 2014, inverse procedural facade layouts.

## Local Implementation Started

Added:

- `design.maas.aesthetic`
- `prompts.py`
- `reference_render.py`
- `image_job.py`
- `validators.py`
- `research_notes.md`
- `external/README.md`
- local ignored checkout of UniTEX at revision `affa1e2`

The current implementation builds a job record only. It does not call an image
model yet.

## External Code Triage

- UniTEX: usable candidate. Input contract is reference image plus input mesh
  path, with OBJ/GLB examples. License is Apache-2.0. Dependencies include
  PyTorch/CUDA, kaolin, nvdiffrast, cupy, xatlas, and Blender-related packages,
  so it belongs in an isolated GPU worker.
- MD-ProjTex: repository exists, MIT license, but currently says `Code coming
  soon...`.
- 3D Synthesis for Architectural Design: paper/project page exists; no public
  code link was visible in the latest check.

## Non-Negotiable

The image model may change:

- facade material
- window rhythm
- surface detail
- lighting and presentation style

The image model must not change:

- mass geometry
- footprint
- height
- number of floors
- setbacks
- roofline
- legal envelope

Generated images are aesthetic assets, not legal evidence of compliance.
