# ds01 — 자가 생성 (Phase 2 GA + Radiance)

**용도**: Phase 2 B1 surrogate 학습
**크기**: 1k-5k 매스
**비용**: GA 1회 = 1500 매스, 3회 반복 = 4500 매스. Radiance 평가 ~30s/매스 → 12.5h × 3 = 37.5h
**라이선스**: 자체 생성, 무관
**위치**: `04_DATASETS/data/ds01_self_generated_v1.parquet`

## 스키마
- 입력: 29 features (Additive 매스 gene)
- 출력: 5 targets (UDI, sDA, BCR, FAR, daylight_score)
- split: train/val/test = 70/15/15

## 생성 절차
B1a 참조 (`02_PHASE2/B1a_dataset_generation.md`)
