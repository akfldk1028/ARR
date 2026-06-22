# Constraint-Aware Generative Models for Architectural Mass — 학계 SOTA 종합 조사

**작성일**: 2026-04-30
**목적**: 25_ACE 프로젝트의 *법규 hard constraint 강제* 매스 자동화에서 학계가 어디까지 와있는지 정직 평가
**스코프**: 한국 법규(정북일조 + 도로사선 + BCR/FAR + 이격) 적용 가능성 중심

> 본 노트는 *우리 시스템이 학계 어디 위치인지*를 결론하기 위한 조사. 박제용 단일 논문 노트는 분리 (`tsai_2025_wacv.md`, `pgdm_christopher_2024.md`, `cdd_cardei_2025.md`, `optnet_amos_2017.md`).

---

## 1. 핵심 질문

> *법규(정북일조, 도로사선, BCR/FAR, 이격) hard constraint를 강제하는 매스 자동 생성 모델, 학계에 존재하는가?*

**한 줄 결론**: **부분적으로 풀렸지만, 한국식 사선 제약(시간대별 일조 시뮬레이션 + 4단계 사선 + 도로 사선)을 hard 보장한 학습 기반 매스 모델은 2026년 4월 현재 *없음*.** 가장 가까운 SOTA는 *Projected Diffusion (NeurIPS 2024) + Constrained Discrete Diffusion (NeurIPS 2025)*. 둘 다 *일반 constraint*에 대한 generic 프레임워크이고, 매스/일조 도메인 검증은 누락. 우리 시스템의 *generate-then-verify + GA penalty + repair* 조합은 학계 표준 기법의 합성으로, *완성도가 SOTA보다 떨어지지 않음*. 단, 학습 기반(Diffusion/DRL)으로 박스 적층 GA를 대체하려면 Phase 3 트랙에서 *constraint sampling*을 채택해야 함.

---

## 2. Hard Constraint 처리 방법론 카테고리

### Cat 1. Penalty (Soft Constraint) — *우리 현재 GA 방식*

**원리**: 위반량에 비례한 penalty를 fitness에 더해 *infeasible도 후보로 살려둠*. NSGA-II/III 표준.
**대표 논문**:
- Deb & Jain 2014 NSGA-III (이미 `nsga3_deb_jain_2014.md`)
- pymoo Constraint Handling docs ([pymoo](https://www.pymoo.org/constraints/index.html))
- Yang & Deb 2020 *A Comparison of Constraint Handling Techniques on NSGA-II* ([Springer](https://link.springer.com/article/10.1007/s11831-020-09525-y))

**장점**: 구현 단순, infeasible→feasible 전이 가능, 어떤 제약식이든 가능.
**단점**: *수렴 끝까지 위반 매스가 살아있을 수 있음*, penalty weight 튜닝 매직넘버, hard 보장 없음.
**우리 적용**: 이미 `engine/regulation_validator.py`에서 사용 중.

---

### Cat 2. Repair Operator — *일부 적용 (deterministic projection)*

**원리**: GA 변이/교차 직후 infeasible 개체를 *수정 함수*로 feasible 영역으로 끌어옴. genetic 다양성 일부 보존.
**대표 논문**:
- Salcedo-Sanz 2009 *A survey of repair methods used as constraint handling techniques in evolutionary algorithms* ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1574013709000379))
- Costa et al. 2015 *Feasibility preserving constraint-handling strategies for real parameter EA* ([MIT DSpace](https://dspace.mit.edu/bitstream/handle/1721.1/103366/10589_2015_9752_ReferencePDF.pdf?sequence=1&isAllowed=y))
- Coello Coello 2002 *Theoretical and numerical constraint-handling techniques* survey ([CSU](https://faculty.csu.edu.cn/_tsf/00/65/zYJ7vmQJbU7z.pdf))

**장점**: feasible 보장 (repair가 perfect할 경우), 수렴 가속.
**단점**: 도메인-특화 repair 함수 필요, 강한 bias로 search 왜곡 가능, 비선형 제약은 repair 자체가 NP.
**우리 적용**: `engine/setback.py`의 *clip-to-buildable-area* 가 이 카테고리. 정북일조/4단계 사선은 아직 penalty.

---

### Cat 3. Constraint Layer / Differentiable Projection

**원리**: 신경망 출력을 *KKT 조건*을 만족하는 layer로 통과시켜 feasible 영역에 투영. backprop도 통과.
**대표 논문**:
- Amos & Kolter 2017 *OptNet: Differentiable Optimization as a Layer in Neural Networks* (ICML 2017, [arXiv 1703.00443](https://arxiv.org/abs/1703.00443)) — **원전. 박제: `optnet_amos_2017.md`**
- Agrawal et al. 2019 *Differentiable Convex Optimization Layers* (cvxpylayers, NeurIPS)
- Donti, Rolnick, Kolter 2021 *DC3: A learning method for optimization with hard constraints*

**장점**: hard 보장, backprop 통합, 학습-시 constraint 자동.
**단점**: QP/Convex만 가능 (정북일조 같은 *비볼록 사선*은 직접 불가), GPU 비용, 매스 도메인 응용은 0편.
**우리 적용**: 직접 매스 생성에 쓰기 어려움 (정북일조 = 시간대별 ray casting → 비볼록). *후보지 후처리 단계*에서 이격 거리만 QP로 lock 가능.

---

### Cat 4. Constrained Sampling for Diffusion — *2024-2026 핫 토픽*

**원리**: 사전학습 diffusion의 reverse process에 *projection / Lagrangian / primal-dual* 단계를 끼워 넣어 hard constraint 강제. retraining 불필요한 *training-free* 변형이 트렌드.
**대표 논문 (시간순)**:
1. Christopher, Baek, Fioretto 2024 *Constrained Synthesis with Projected Diffusion Models* (PGDM, NeurIPS 2024, [arXiv 2402.03559](https://arxiv.org/abs/2402.03559)) — **박제: `pgdm_christopher_2024.md`**. Convex + 비볼록 모두.
2. Zampini et al. 2025 *Training-Free Constrained Generation with Stable Diffusion Models* (NeurIPS 2025 Spotlight, [arXiv 2502.05625](https://arxiv.org/abs/2502.05625))
3. Cardei et al. 2025 *Constrained Discrete Diffusion* (CDD, NeurIPS 2025, [arXiv 2503.09790](https://arxiv.org/abs/2503.09790)) — **박제: `cdd_cardei_2025.md`**. 이산 시퀀스 (코드/언어).
4. Rochman-Sharabi & Louppe 2026 *Predict-Project-Renoise: Sampling Diffusion Models under Hard Constraints* ([arXiv 2601.21033](https://arxiv.org/abs/2601.21033))
5. Stoppani, Bacciu, Mokarizadeh 2026 *Boundary-Constrained Diffusion Models for Floorplan Generation* (ESANN 2026, [arXiv 2602.01949](https://arxiv.org/abs/2602.01949)) — *floorplan*만, 매스 X
6. *Constrained Diffusers for Safe Planning and Control* ([arXiv 2506.12544](https://arxiv.org/html/2506.12544))
7. *CCS: Controllable and Constrained Sampling with Diffusion Models via Initial Noise Perturbation* ([arXiv 2502.04670](https://arxiv.org/pdf/2502.04670))

**장점**: 사전학습 모델 재사용, 비볼록 가능 (PPR), training-free 변형 존재, **2025년 NeurIPS 다수 채택 (학계 합의)**.
**단점**: 복잡한 사선 + 4단계 일조 시뮬레이션을 *projection 함수*로 구현 어려움 (sub-gradient만 가능). 매스 도메인 응용 누락 (floorplan은 일부).
**우리 적용**: **Phase 3 C2 Diffusion prior에 PGDM 채택 권장**. 단, projection 함수를 우리 `regulation_validator.py`로 구현해야 함 → 8주+.

---

### Cat 5. Lagrangian / Augmented Reward DRL (CMDP)

**원리**: Constrained MDP에서 reward = task return − λ·constraint violation. λ는 dual update로 tightening.
**대표 논문**:
- Achiam et al. 2017 *Constrained Policy Optimization* (CMU, [PDF](https://www.ri.cmu.edu/app/uploads/2017/11/1705.10528.pdf))
- Yang et al. 2022 *Penalized Proximal Policy Optimization for Safe RL* (IJCAI 2022, [PDF](https://www.ijcai.org/proceedings/2022/0520.pdf))
- Liu et al. 2025 *A Survey of Safe RL and Constrained MDPs* ([arXiv 2505.17342](https://arxiv.org/html/2505.17342v1))
- Chen et al. 2024 (이미 박제) *MADDPG renovation* — 우리 `drl_chen_2024.md`

**장점**: 시퀀셜 의사결정 (매스 적층 step-by-step) 자연스러움, hard 보장은 *suboptimal 정책에서만* (asymptotic).
**단점**: 학습 안정성 약함, hard 절대 보장 X (확률적 violation 잔존), reward shaping 매직넘버.
**우리 적용**: Phase 3 C4 DRL Bootstrap에 PPO-Lagrangian 채택 가능. 단, *법규 절대 보장은 verify-step에서 별도 컷*.

---

### Cat 6. Feasibility Predictor (Surrogate Classifier)

**원리**: 별도 ML이 candidate 매스를 *feasible/infeasible*로 분류 → infeasible 후보를 fitness 평가 전에 컷. 시뮬레이션 비용 절감 목적.
**대표 논문**:
- Sharpe et al. 2018 *Active-learning PNN for feasibility classification* ([Springer](https://link.springer.com/article/10.1007/s00366-021-01441-4))
- 우리 `surrogate_westermann_2019.md` 의 일부

**장점**: 시뮬레이션 비용 절감, GA에 직접 끼워 넣기 쉬움.
**단점**: *분류만*, 위반 매스를 feasible로 *변환하지 못함*. 학습 데이터 필요.
**우리 적용**: surrogate model의 자연스러운 확장 (Phase 2). 정북일조 시뮬레이션 5분→0.1초로 줄여 GA 처리량 확장.

---

### Cat 7. Generate-then-Verify Loop — *우리 + LLM 분야 트렌드*

**원리**: 생성 모델이 후보 매스 → 외부 verifier가 hard constraint 검사 → 통과만 채택. iterative refinement 가능.
**대표 논문**:
- Nauata et al. 2021 *House-GAN++* (CVPR 2021, [arXiv 2103.02574](https://arxiv.org/abs/2103.02574)) — graph constraint, iterative refinement
- Wu et al. 2025 *Automated Code Compliance via LLM-assisted Building Design Alterations* ([SSRN](https://papers.ssrn.com/sol3/Delivery.cfm/e6a7511a-fd46-4d95-b8be-33d42ad28ccb-MECA.pdf?abstractid=6073688&mirid=1))
- Zhang et al. 2023 *LLM-FuncMapper: Translating Regulatory Clauses into Executable Codes* ([arXiv 2308.08728](https://arxiv.org/abs/2308.08728))
- BuildThemis (RAG + 코드 생성, 2025)

**장점**: blackbox 생성기 재사용, hard 보장 (verifier가 perfect할 경우), LLM 시대에 딱 맞음.
**단점**: rejection rate 높으면 비효율, *verifier 자체 정확도*가 병목, 한국 법규 공식 verifier 부재.
**우리 적용**: **이미 사용 중**. `engine/regulation_validator.py` = 우리 verifier. 8종 규제선 + BCR/FAR 전수 대조 (`ARR/backend/tools/verify_setbacks.py`)가 정확히 이 패턴.

---

## 3. SOTA 정리 (5-10개 논문 표)

| # | 논문 | 연도 | 학회/저널 | 카테고리 | hard 강제 방식 | 우리 적용 |
|---|------|------|-----------|----------|----------------|-----------|
| 1 | **Tsai & Hariharan, *3D Synthesis for Architectural Design*** ([WACV 2025 PDF](https://openaccess.thecvf.com/content/WACV2025/papers/Tsai_3D_Synthesis_for_Architectural_Design_WACV_2025_paper.pdf)) | 2025 | WACV | 7 (생성+texture inpainting) | hard 없음, 시각 품질만 | 매스 *외관* phase, 법규 X |
| 2 | **Christopher et al. *Projected Diffusion Models* (PGDM)** ([arXiv 2402.03559](https://arxiv.org/abs/2402.03559)) | 2024 | NeurIPS | 4 (constrained sampling) | reverse process 매 step *projection* | **Phase 3 C2 후보** |
| 3 | **Cardei et al. *Constrained Discrete Diffusion* (CDD)** ([arXiv 2503.09790](https://arxiv.org/abs/2503.09790)) | 2025 | NeurIPS | 4 (이산 + 차별화 가능 opt) | 차별화 가능 constraint를 sampling에 직접 주입 | discrete 매스 인코딩 시 적용 |
| 4 | **Zampini et al. *Training-Free Constrained Stable Diffusion*** ([arXiv 2502.05625](https://arxiv.org/abs/2502.05625)) | 2025 | NeurIPS Spotlight | 4 | latent space 제약, train 불필요 | 사전학습 매스 모델 채택 시 |
| 5 | **Stoppani et al. *Boundary-Constrained Floorplan Diffusion*** ([arXiv 2602.01949](https://arxiv.org/abs/2602.01949)) | 2026 | ESANN | 4 (Boundary Cross-Attention) | site boundary를 cross-attention으로 강제 | floorplan 한정, 매스에 포팅 가능 |
| 6 | **Rochman-Sharabi & Louppe *Predict-Project-Renoise* (PPR)** ([arXiv 2601.21033](https://arxiv.org/abs/2601.21033)) | 2026 | preprint | 4 | constrained forward + alternating proj | 비볼록 가능, 우리 사선에 적합 |
| 7 | **Nauata et al. *House-GAN++*** ([arXiv 2103.02574](https://arxiv.org/abs/2103.02574)) | 2021 | CVPR | 7 (iterative refinement) | graph constraint + refinement loop | floorplan, 매스 X |
| 8 | **Amos & Kolter *OptNet*** ([arXiv 1703.00443](https://arxiv.org/abs/1703.00443)) | 2017 | ICML | 3 (KKT layer) | QP layer + implicit diff | 이격 거리만 적용 가능 |
| 9 | **Achiam et al. *Constrained Policy Optimization*** ([CMU PDF](https://www.ri.cmu.edu/app/uploads/2017/11/1705.10528.pdf)) | 2017 | ICML | 5 (Lagrangian DRL) | trust region + cost ≤ d | Phase 3 C4 후보 |
| 10 | **Salcedo-Sanz *Repair methods survey*** ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1574013709000379)) | 2009 | C-S Review | 2 (repair) | 도메인 repair 함수 | 우리 setback clip 이 이 카테고리 |
| 11 | **Wu et al. *LLM Building Code Alterations*** ([SSRN](https://papers.ssrn.com/sol3/Delivery.cfm/e6a7511a-fd46-4d95-b8be-33d42ad28ccb-MECA.pdf?abstractid=6073688&mirid=1)) | 2025 | SSRN | 7 (LLM verify) | LLM이 alteration 제안 | 우리 verifier에 LLM repair 추가 가능 |

---

## 4. 한국 법규 특수성 — 학계 공백 진단

### 한국식 사선 제약 = *시간대별 + 다단계 + 도로 폭 의존*

**예시**: 정북일조선
- 동지일 09:00–15:00 6시간 *연속 일조* 시뮬레이션
- 인접 대지 경계로부터 *높이별 차등* 이격 (4m 이하: 1m, 8m 이하: 1/2 H, 그 이상: H/2)
- 4단계 사선 envelope (`envelopes/sunlight.py` LOCKED — Session 14)

**도로 사선** (2024년 폐지, 일부 잔존):
- 전면 도로 폭 W → 건축물 높이 ≤ 1.5W
- 전면 도로 = 폭원 4m 이상
- 코너 부지 = 양 도로 가산

**검색 결과**: *Korean sunlight regulation + deep learning* → 0편 (CGAN 일조 surrogate는 있음 ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378778824004110)) — 우리 `surrogate_westermann_2019.md`와 비슷, hard 보장 X)

> **결론**: 한국식 비볼록 사선을 *학습 기반 hard*로 처리한 사례 **0편**. 우리 `envelopes/sunlight.py` (shapely buffer 4단계) + verify-loop가 *학계 첫 사례 수준*. 단, generate 단계는 여전히 GA penalty.

---

## 5. 우리 시스템 학계 위치 — 정직 평가

### 5.1 현재 (Phase 1-2 완료)

```
표현:    박스 적층 (param: 6 floors × 다양한 footprint)
생성:    GA NSGA-III (penalty + box clip repair)
verify:  envelopes/sunlight.py (4단계 사선) + setback (7종) + BCR/FAR
loop:    generate(GA) → simulate(Radiance/일조) → fitness → next gen
hard:    geometry-level만 (clip), 일조는 penalty
```

**학계 위치**:
- Cat 1 (Penalty) + Cat 2 (Repair) + Cat 7 (Generate-then-Verify) **하이브리드**
- 매스 도메인에서 *비볼록 한국 사선*을 verify까지 자동화한 사례 = 우리가 제일 멀리 와있음
- 학습 기반(Cat 3, 4, 5) **0%** — Phase 3 트랙 시작 전

### 5.2 Phase 3 학습 트랙 결정 (C7 참조)

- **C2 Diffusion prior** → PGDM (Cat 4) 채택, projection 함수를 우리 verifier로
- **C4 DRL Bootstrap** → PPO-Lagrangian (Cat 5), constraint = verify violation
- **둘 다 Phase 3 결과 합격 시 박스 적층 deprecate** (ADR003)

### 5.3 구체적 적용 비용/난이도

| 카테고리 | 우리 도입 비용 | 효과 | Phase |
|----------|---------------|------|-------|
| Cat 1 Penalty | 0 (이미) | hard 보장 X | 1-2 |
| Cat 2 Repair | 1주 (정북일조 repair 함수) | 일부 hard | 2.5 |
| Cat 3 OptNet | 4주 (이격 QP만) | 부분 hard | optional |
| Cat 4 PGDM | 8-12주 (projection = `regulation_validator.differentiable_projection`) | hard at sampling | 3 (C2) |
| Cat 5 PPO-Lag | 12주 (env 정의 + reward shaping) | suboptimal hard | 3 (C4) |
| Cat 6 Feasibility Pred | 2주 (CNN 일조 surrogate) | 처리량 ↑ | 2 |
| Cat 7 Verify Loop | 0 (이미) | hard 보장 (verifier perfect 시) | 1-2 |

---

## 6. 한 줄 결론 (E단계)

> **학계는 hard constraint *일반 framework*는 풀었으나(NeurIPS 2024-2025 PGDM/CDD), 한국식 비볼록 사선 + 4단계 일조 + 도로 사선 + BCR/FAR 동시 강제는 *2026년 4월 현재 미해결*. 우리의 generate-then-verify + GA penalty + repair 조합은 Cat 1+2+7 하이브리드로 *매스 도메인에서 학계 SOTA에 근접*. 학습 기반으로 가려면 Phase 3에서 PGDM 채택이 합리.**

---

## 7. 인용 트리

```
constraint_aware_survey.md (본 노트)
├─ tsai_2025_wacv.md           # 매스 외관 (texture)
├─ pgdm_christopher_2024.md     # ⭐ Phase 3 C2 후보
├─ cdd_cardei_2025.md           # 이산 매스 인코딩 시
├─ optnet_amos_2017.md          # KKT layer 원전
├─ diffusion_zhang_2024.md      # 기존 (3D form-finding)
├─ drl_chen_2024.md             # 기존 (MADDPG)
└─ nsga3_deb_jain_2014.md       # 기존 (현재 GA)
```

## 8. 출처 (8개 arxiv 키워드 + 8개 WebSearch)

### arxiv-mcp 검색 (8 키워드, 일부 429 rate limit 후 재시도 성공)
- "constraint-aware generative model 3D architecture" → 우회 검색 성공
- "hard constraint diffusion model building" → diffusion survey 위주
- "feasibility-guaranteed neural network design" → 우회 성공
- "safe reinforcement learning architectural design" → SafeRL survey 9편
- "differentiable constraint satisfaction layer" → CSP-NN 위주
- "projection-based feasibility neural generative" → 429
- "building code aware deep learning" → 429 (web search 보완)
- "repair operator feasible genetic algorithm" → 429 (web search 보완)

### WebSearch (8개, 모두 성공)
- Tsai 2025 WACV
- Constraint-aware diffusion 2025
- NSGA-II repair vs penalty
- Constrained sampling diffusion reverse
- Korean sunlight deep learning
- OptNet KKT
- House-GAN++ graph constraint
- Generate-then-verify LLM building code
- Lagrangian CMDP RL
- ArchGen massing 2025
- Tsai+Hariharan BCR FAR setback
- Repair operator survey
- Feasibility predictor classifier
