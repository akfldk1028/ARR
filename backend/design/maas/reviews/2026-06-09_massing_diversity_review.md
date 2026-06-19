# MAAS Massing Diversity Review - 2026-06-09

## Scope

Reviewed whether the current legal-envelope-first MAAS generator produces
meaningfully diverse mass candidates:

```text
legal envelope
-> floor plate / mass volume generation
-> MAAS morphology
-> legal repair/check
-> evidence/validator review
```

## Code Paths Reviewed

- `legal_mesh_optimizer.py`
  - Builds the legal envelope.
  - Adds `legal_layered_max` as the capacity anchor.
  - Generates morphology/grammar seed variants.
  - Repairs every variant.
  - Rejects variants that fail BCR/FAR/height/sunlight metrics.
  - Selects candidates by concept family and score.
- `morphology_operators.py`
  - Generates inset, BCR-fill, notch, open court, slender bar, split, branch,
    pinch, interlock, overlap, courtyard, terrace/stepback, tower, taper, and
    grade variants.
- `diversity.py`
  - Uses footprint IoU against source/selected candidates.
- `test_maas_export.py`
  - Already asserts at least 6 candidates and at least 5 distinct shapes for
    the diversity scenario.

## Sample Scenario

Used the existing diversity-style scenario:

- BCR limit: 60%
- FAR limit: 250%
- height limit: 50m
- building type: 공동주택
- sunlight envelope: slanted 10m/14m/30m/24m corner cap
- max variants: 8

Result:

- Candidate count: 8
- Unique `mass_shape`: 8
- Unique concept labels: 8
- Rejected candidates: 0
- Pairwise footprint IoU range: 0.4141 to 1.0

Generated concepts:

| rank | mass_shape | concept | height | BCR | FAR | volumes | floor plates |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `legal_layered_max` | 법규엔벨로프 | 14.0 | 59.4 | 249.88 | 2 | 5 |
| 2 | `lift_overlap_slabs_layered` | 포디움/타워 | 14.0 | 58.81 | 249.85 | 4 | 5 |
| 3 | `grammar_sunlight_multi_step_layered` | 다단 일조스텝 | 14.0 | 58.81 | 249.85 | 4 | 5 |
| 4 | `grammar_podium_tower_offset_layered` | 포디움+타워오프셋 | 14.0 | 58.81 | 249.85 | 2 | 5 |
| 5 | `grammar_cave_inset_puncture` | 케이브+인셋+보이드 | 8.4 | 58.81 | 176.42 | 1 | 0 |
| 6 | `court_open_east` | 코너/오픈코트 | 8.4 | 58.81 | 176.42 | 1 | 0 |
| 7 | `courtyard_void` | 중정형 | 8.4 | 58.81 | 176.42 | 1 | 0 |
| 8 | `slender_bar_east` | 바형 | 8.4 | 45.73 | 137.2 | 1 | 0 |

## Assessment

The generator is producing diverse concepts, not just one legal box:

- Capacity anchor: `legal_layered_max`
- Sectional/tower strategies: `lift_overlap_slabs_layered`,
  `grammar_sunlight_multi_step_layered`, `grammar_podium_tower_offset_layered`
- Void/open-space strategies: `grammar_cave_inset_puncture`, `court_open_east`,
  `courtyard_void`
- Slender bar strategy: `slender_bar_east`

The legal-first contract is also preserved:

- All selected candidates stay under BCR/FAR/height constraints in the sample.
- Floor-plate candidates carry `floor_plates`, `floor_groups`, and
  `mass_volumes`.
- Non-floor-stack morphology candidates still pass repair/metric checks before
  being selected.

## Weak Spots

- Two or more vertical strategies can share the same ground footprint
  (`pairwise_iou = 1.0`) and differ only by section/volume grouping. This is
  acceptable for section design, but the UI/review must label them as sectional
  alternatives, not plan alternatives.
- `diversity_score` is footprint-based. It does not yet score true 3D mass
  difference from floor-plate/volume profiles.
- Some morphology variants have `floor_plate_count = 0` because they are
  single-volume repaired footprints, not floor-by-floor stacks. They are legal
  candidates but less reviewable than layered candidates.
- The current diversity tests check count and distinct shape labels, but they do
  not yet enforce a minimum 3D/section diversity metric.

## Recommended Next Gate

Implemented first-pass 3D diversity signature after this review:

- footprint IoU
- volume band count
- volume band area profile
- floor-plate area profile
- height/step profile

It is now exposed in generated candidates and evidence as:

- `geometry.geometry_metrics.shape_signature_3d`
- `candidate.diversity`
- `properties.shape_signature_3d`
- `properties.candidate_diversity`

High-footprint-IoU sectional candidates are not rejected automatically. They are
classified as:

- `plan_diverse`
- `section_diverse`
- `near_duplicate`

Remaining gate:

- Add a `validators.runs[]` entry for a future `maas_diversity_validator`.
- Use the 3D signature in frontend/agent review so users can see whether a
  candidate differs by plan, section, or both.
