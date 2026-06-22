# Tsai & Hariharan 2025 — *3D Synthesis for Architectural Design* (WACV 2025)

**저자**: I-Ting Tsai, Bharath Hariharan (Cornell University)
**학회**: IEEE/CVF Winter Conference on Applications of Computer Vision (WACV) 2025
**페이지**: 4799-4809
**PDF**: <https://openaccess.thecvf.com/content/WACV2025/papers/Tsai_3D_Synthesis_for_Architectural_Design_WACV_2025_paper.pdf>
**프로그램 가이드**: <https://wacv2025.thecvf.com/wp-content/uploads/2025/02/WACV-2025-Program.pdf>

---

## 한 줄 요약

> 사용자가 3D 매스 형태(massing)를 input으로 주면, *facade-by-facade* 방식으로 inpainting diffusion을 적용해 *외관 텍스처/재료가 일관된* 3D 건물을 생성. **법규 hard constraint는 다루지 않음** — 매스 형태는 *사용자가 이미 제공*한다는 가정.

---

## 핵심 contribution

1. **Facade-by-facade inpainting** — 매스의 각 면을 순차적으로 텍스처 inpainting. 인접 facade 간 *cross-face continuity* 유지.
2. **3D-aware textures** — 기존 NeRF 기반 architectural generation의 *반복적/단조로운* 결과 문제 해결. 다양한 디자인 (concrete + mechanistic features, photorealistic wooden industrial style 등) 가능.
3. **Diffusion 모델 재사용** — Stable Diffusion 같은 사전학습 모델을 inpainting 변형으로 활용 → 별도 매스 학습 데이터셋 불요.

---

## 우리 시스템 적용 가능성

### 적용 *불가* 영역 (명시)
- **법규 hard constraint** — 본 논문은 매스 형태가 input. BCR/FAR/사선은 사용자 책임.
- **매스 자동 생성** — 시각화/외관만, 형태 결정은 architect.

### 적용 *가능* 영역
- **Phase 5+ Visualization 단계**: Cesium 3D viewer에서 우리가 GA로 결정한 매스에 facade 텍스처 입힐 때.
- **데이터 증강 (Phase 3 ds02)**: 한국 매스 데이터셋 부족 시 매스만 합성하고 텍스처는 본 방식으로 → 수천 개 합성 매스 visualization 보강.

---

## 인용 위치

- 발표 자료에서 *학계 SOTA*로 이미 언급됨 (사용자 제공)
- **본 프로젝트 명시적 한계**: 우리는 *매스 형태 자체를 자동 생성*하므로, 본 논문은 *상보적*. 우리가 풀려는 문제 ⊃ Tsai 문제.
- `constraint_aware_survey.md` Cat 7 (Generate-then-Verify) 도 아니고, 그냥 *외관 합성*. 카테고리 외.

---

## 주의

- 본 논문 PDF는 검색 결과로만 확인. 직접 BCR/FAR 언급 없음 (web search 결과).
- 한국 사선 처리는 명시적으로 *out of scope*.
- 발표 시 인용 톤: "외관 합성은 Tsai 2025가 풀었지만, *매스 결정과 법규 강제*는 학계 미해결 → 우리 contribution".
