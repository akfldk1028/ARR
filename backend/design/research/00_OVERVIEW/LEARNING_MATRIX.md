# 학습 필요 매트릭스

**질문**: "어떤 작업이 *학습이 필요*하고, 어떤 작업이 *코드만으로 가능*한가?"

---

## 매트릭스

| 작업 ID | 작업명 | 학습 필요? | 데이터셋 | 모델 | 학습 비용 | 학습 시간 |
|---|---|---|---|---|---|---|
| **A1** | NSGA-III (pymoo) | ❌ | — | — | — | — |
| **A2** | Radiance lite | ❌ | — | — | — | — |
| **A3** | Constraint penalty | ❌ | — | — | — | — |
| **A4** | Evaluator 통일 | ❌ | — | — | — | — |
| **A5** | Baseline benchmark | ❌ | — | — | — | — |
| **B1** | Surrogate model | ⚠️ 경량 | 자가 생성 1k-5k | GP / MLP / GBM | CPU 충분 | 분~시간 |
| **B2** | Bayesian Opt | ❌ (B1 모델 사용) | — | — | — | — |
| **B3** | LLM RAG | ❌ (인덱싱만) | 건축 사례 100-1k | OpenAI embed-3-large | API 비용 | — |
| **B4** | Heterogeneous Island | ❌ | — | — | — | — |
| **B5** | Typology 추천 | ⚠️ 경량 | 자가 생성 + 라벨 1k | Logistic / 작은 MLP | CPU 충분 | 분 |
| **C1** | SDF 매스 | ✅ 본격 | 한국 건축 매스 1k+ | DeepSDF / NeRF류 | GPU 24GB+ | 1-2주 |
| **C2** | Diffusion prior | ✅ 본격 | 한국 건축 매스 1k+ (3D) | Stable Diffusion 3D + LoRA | GPU 24GB+ | 1-2주 |
| **C3** | Differentiable Rendering | ❌ (Mitsuba 3) | — | — | GPU 권장 | — |
| **C4** | DRL Bootstrap | ✅ 본격 | GA Pareto 1k+ 부지 | PPO / MADDPG + IL warm-start | GPU 16GB+ | 수일~1주 |

---

## 결론

- **Phase 1 (A1~A5)**: 학습 0%. *지금 바로* 시작 가능
- **Phase 2 (B1~B5)**: 학습 30% — 자가 생성 데이터, CPU만, 외부 데이터셋 불요
- **Phase 3 (C1~C4)**: 학습 70% — 외부 데이터셋 + GPU 인프라 + 1-2주 학습 시간

---

## Open Questions

1. B1a 자가 생성 1k-5k 데이터로 surrogate 정확도가 학계 표준(Westermann 2019)에 도달하는지
2. B3 건축 사례 RAG 데이터 출처 — 도시건축통합지도 / Vworld / 잡지 라이선스 검토
3. C2/C1 한국 건축 매스 1k+ 라이선스 + 데이터 품질 (Vworld 3D LOD 수준)
4. C5 GPU 정확 견적 (vast.ai A100 시간당 + 학습 1회 총 시간)
