# Research Notes

Current implementation direction should follow the newest geometry-aware texture
and facade synthesis work, while keeping older SIGGRAPH procedural modeling as
the structural precedent.

## Most Relevant Recent Work

- Tsai & Hariharan, WACV 2025, *3D Synthesis for Architectural Design*.
  - Directly relevant because it starts from a user-provided 3D architectural
    mass and applies facade-by-facade diffusion/inpainting.
  - Fit for ARR/MAAS: use our legal mass as the input geometry, then generate
    exterior treatment.
  - Limitation: it does not solve legal mass generation or hard constraints.
- UniTEX, CVPR 2026 / arXiv 2025, *Universal High Fidelity Generative
  Texturing for 3D Shapes*.
  - Relevant as the newest high-fidelity 3D texturing direction: operate with
    explicit geometry conditioning and preserve texture consistency on 3D
    assets.
- MD-ProjTex, arXiv 2025, *Texturing 3D Shapes with Multi-Diffusion
  Projection*.
  - Relevant for consistent text-guided texture generation across rendered
    views of a 3D shape.
- ProcTex, arXiv 2025, *Consistent and Interactive Text-to-texture Synthesis
  for Procedural Models*.
  - Relevant if MAAS later stores facade grammar/procedural material parameters
    instead of only raster images.
- TextureDreamer, CVPR 2024, *Image-guided Texture Synthesis through
  Geometry-aware Diffusion*.
  - Relevant when a style/reference image is available.
- TEXTure, SIGGRAPH 2023, *Text-Guided Texturing of 3D Shapes*.
  - Important SIGGRAPH reference for texturing an existing mesh using
    depth-to-image diffusion and multi-view painting.
- Text2Tex, ICCV 2023, *Text-driven Texture Synthesis via Diffusion Models*.
  - Useful baseline for progressive view-based mesh texturing.

## Source Links

- 3D Synthesis for Architectural Design: https://openaccess.thecvf.com/content/WACV2025/papers/Tsai_3D_Synthesis_for_Architectural_Design_WACV_2025_paper.pdf
- UniTEX: https://arxiv.org/abs/2505.23253
- MD-ProjTex: https://arxiv.org/abs/2504.02762
- ProcTex: https://arxiv.org/abs/2501.17895
- TextureDreamer: https://openaccess.thecvf.com/content/CVPR2024/html/Yeh_TextureDreamer_Image-Guided_Texture_Synthesis_Through_Geometry-Aware_Diffusion_CVPR_2024_paper.html
- TEXTure: https://texturepaper.github.io/TEXTurePaper/
- Text2Tex: https://arxiv.org/abs/2303.11396
- Procedural Modeling of Buildings: https://paperswelove.org/papers/procedural-modeling-of-buildings-d7ac8760/
- Inverse Procedural Modeling of Facade Layouts: https://arxiv.org/abs/1308.0419

## Structural / Procedural Precedent

- Mueller et al., SIGGRAPH 2006, *Procedural Modeling of Buildings*.
  - Shape grammar precedent for generating detailed architecture from rules.
- Wu et al., SIGGRAPH 2014, *Inverse Procedural Modeling of Facade Layouts*.
  - Useful precedent for facade grammar/layout recovery.

## Local Takeaway

For ARR/MAAS, the best architecture is not text-to-building from scratch. The
newest papers reinforce the same pattern: the geometry must be explicit and
conditioned before the image model is allowed to paint facade/material detail.

Use:

```text
legal MAAS mass -> reference views -> image/facade generation -> validation
```

Avoid:

```text
prompt -> arbitrary beautiful building -> backfit legal mass
```

The latter destroys evidence/provenance and makes legal validation unreliable.
