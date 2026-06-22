# C1 — SDF (Signed Distance Function) 매스 표현

**기간**: 4주 | **학습**: ✅ 본격 (GPU 24GB+, 1-2주)

## 목적
박스 적층(29 genes 제약)에서 *공간의 모든 점에 대한 함수* 로 매스 표현. 곡면, 비정형, 캔틸레버 자유 표현.

## 모델 후보
- **DeepSDF** (Park 2019) — auto-decoder + latent code
- **Occupancy Networks** (Mescheder 2019)
- **NeRF-based** (간소화)

## 학습 데이터
- ds02 한국 건축 매스 1k+ (`04_DATASETS/ds02_korean_buildings.md`)
- 또는 ds03 해외 공개 (BuildingNet)

## 검증
- Reconstruction 정확도 (Chamfer distance, IoU)
- 박스 적층 매스 5종 모두 SDF 표현 가능한지 sanity

## 의존성
- PyTorch, CUDA 11+/12, GPU 24GB+ (RTX 4090 / A100)

## Open Questions
- SDF 매스에서 *법규 hard constraint* (정북일조선, BCR, FAR) 강제 방법
- 박스 적층 → SDF 마이그레이션 자동화 가능성
