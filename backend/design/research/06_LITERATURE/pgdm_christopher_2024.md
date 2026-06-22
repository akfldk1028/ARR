# Christopher, Baek, Fioretto 2024 — *Constrained Synthesis with Projected Diffusion Models* (PGDM, NeurIPS 2024)

**저자**: Jacob K. Christopher, Stephen Baek, Ferdinando Fioretto
**학회**: 38th Conference on Neural Information Processing Systems (NeurIPS 2024)
**arXiv**: [2402.03559](https://arxiv.org/abs/2402.03559) (v3, 2024-02-05)
**PDF**: <https://arxiv.org/pdf/2402.03559v3>

---

## 한 줄 요약

> Diffusion 모델의 reverse process(샘플링)를 *constrained optimization*으로 재정의. 매 step에서 noise prediction → *feasible 영역 projection*을 alternating. **Convex constraint는 hard 보장**, 비볼록 constraint도 sub-gradient로 strongly improved feasibility. **Phase 3 C2 Diffusion prior 1순위 후보.**

---

## 핵심 idea

```
표준 reverse:           x_{t-1} = denoise(x_t, ε_θ(x_t, t))
PGDM reverse (convex):  x_{t-1} = Proj_C(denoise(x_t, ε_θ(x_t, t)))
PGDM reverse (nonconvex): x_{t-1} = denoise(x_t, ε_θ) − η·∇violation(·)
```

여기서 `Proj_C` = constraint set C로의 Euclidean projection. C는 *학습-시점*에는 등장하지 않아도 되고, *sampling 시점*에만 강제. **재학습 불필요**.

---

## 검증 도메인 (논문 Table)

- **Convex**: 분자 생성 (valence + bond constraint)
- **비볼록 challenging**: 물리 시뮬레이션 (Navier-Stokes inverse problem), traffic optimization
- **양자 화학**: HOMO-LUMO gap 강제

→ 매스/건축 도메인 검증은 **누락**. 우리가 first-mover 가능.

---

## 우리 시스템 적용 시나리오 (Phase 3 C2)

### 가능
- **BCR/FAR**: linear constraint → Convex projection. ${\sum A_i \leq BCR \cdot A_{lot}}$.
- **이격 거리**: signed distance function (SDF)으로 표현, distance ≥ d_min → projection 정의 가능.
- **건축물 외곽선 ⊂ 부지**: convex polytope → exact projection.

### 어려움
- **정북일조 4단계 사선**: 시간대별 일조 시뮬레이션은 *non-differentiable*. PGDM 비볼록 변형도 sub-gradient만, hard 보장 X.
- **도로 사선**: 도로 폭 W → 높이 ≤ 1.5W. 부지 외 도로 정보 필요 → conditional input.

### 통합 전략 (제안)
```
Phase 3 매스 생성:
  1. Diffusion sampling (PGDM):
     - Convex projection: BCR/FAR/이격 → hard 보장
     - Sub-gradient: 정북일조 → soft 강화
  2. 후처리 verify (우리 envelopes/sunlight.py):
     - 정북일조 사선 final clip
     - 통과 후보만 GA fitness 진행
  3. Hybrid:
     - PGDM = init solution → GA refine (수렴 30→10 gen 가능, Phase 3 목표)
```

---

## 비용 추정

- **데이터셋**: ds02 한국 매스 1k+ (Phase 3 dependency)
- **GPU**: 24GB+ (Stable Diffusion variant 학습), vast.ai a100 ~$1.5/h × 100h ≈ $150
- **구현**: 8-12주 (`engine/diffusion_prior.py` + `engine/projection.py`)
- **projection 함수**: `regulation_validator.py`의 *differentiable variant* 만들어야 → BCR/FAR는 trivial, 일조는 sub-gradient

---

## 인용 위치

- `constraint_aware_survey.md` **Cat 4 (Constrained Sampling)** 대표 SOTA
- `03_PHASE3/C2_diffusion_prior.md` 와 **연결 필수**
- `03_PHASE3/C7_hard_constraint_strategy.md` Phase 3 진입 시 채택 결정

---

## 다음 단계

- [ ] PDF 풀텍스트 다운로드 후 projection lemma 검토
- [ ] author Fioretto의 후속작 (`Training-Free Constrained Stable Diffusion` 2025) 확인 — 이미 `constraint_aware_survey.md`에 인덱싱됨
- [ ] 우리 verify 함수의 differentiable variant 가능성 평가 (정북일조는 *sub-gradient만 가능*인지 확인)
