# C2 — Diffusion Prior

**기간**: 8-12주 | **학습**: ✅ 본격 (GPU 24GB+, 1-2주)

## 목적
1,000건 우수 건축 사례 학습 → *부지 + 법규 입력 → 학습된 분포에서 매스 sampling*. GA 무작위 시작 → Diffusion init.

## 모델 후보
- **Stable Diffusion 3D** + LoRA fine-tune
- **PointE** (OpenAI 3D point cloud)
- **GET3D** (NVIDIA 3D textured shapes)

## 학습 데이터
- ds02 한국 건축 매스 1k+
- 또는 ds03 BuildingNet

## 통합
- Diffusion sample → 박스 적층 또는 SDF로 *전환* → GA refine
- *Hybrid pipeline*: Diffusion init + GA local search

## 검증
- Diffusion init GA vs random init GA — 수렴 30 gen → 10 gen 단축 검증
- 학계 사례: Tian+ 2025 *Energy & Buildings* GAN+DRL 유사 구조

## Open Questions
- Constraint-aware sampling (법규 위반 매스 샘플링 방지)
- 한국 사례 학습 시 *prompt vs LoRA fine-tune* 어느 쪽 효과?
