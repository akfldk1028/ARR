# ROI 우선순위표

**질문**: "어디부터 시작해야 가장 효율적인가?"

---

## ROI 매트릭스

ROI = 효과 / 비용 (둘 다 1-5 스케일, 비용은 낮을수록 쌈)

| 작업 | 효과 | 비용 | ROI | 학습 | Phase | 우선순위 |
|---|---|---|---|---|---|---|
| **A1** NSGA-III (pymoo) | 4 | 1 | **4.0** | ❌ | 1 | ⭐ 즉시 |
| **A4** Evaluator 통일 | 3 | 1 | 3.0 | ❌ | 1 | ⭐ 즉시 |
| **A2** Radiance lite | 5 | 2 | 2.5 | ❌ | 1 | 다음 |
| **A3** Constraint penalty | 2 | 1 | 2.0 | ❌ | 1 | ⭐ 즉시 |
| **B2** BO | 4 | 2 | 2.0 | ❌ | 2 | 1개월 후 |
| **B3** LLM RAG | 4 | 2 | 2.0 | 인덱싱 | 2 | 1개월 후 |
| **A5** Baseline | 2 | 1 | 2.0 | ❌ | 1 | ⭐ 선행 |
| **B1** Surrogate | 5 | 3 | 1.67 | 경량 | 2 | 1개월 후 |
| **B4** Hetero Island | 3 | 3 | 1.0 | ❌ | 2 | 1.5개월 후 |
| **B5** Typology 추천 | 2 | 2 | 1.0 | 경량 | 2 | 2개월 후 |
| **C2** Diffusion | 5 | 5 | 1.0 | ✅ | 3 | 3-6개월 |
| **C4** DRL Bootstrap | 5 | 5 | 1.0 | ✅ | 3 | 3-6개월 |
| **C1** SDF | 4 | 5 | 0.8 | ✅ | 3 | 6개월+ |
| **C3** Differentiable Rendering | 4 | 5 | 0.8 | ❌ (Mitsuba 3) | 3 | 6개월+ |

---

## 해석

### 이번 주 (즉시 시작)
- **A5 Baseline** (선행) — 정량 비교 기준 확보
- **A1 NSGA-III** — pymoo 한 줄 추가, 효과 큼
- **A3 Constraint penalty** — 작은 수정, 정확도 향상
- **A4 Evaluator 통일** — 후속 작업의 토대

### 2-3주 차
- **A2 Radiance lite** — 평가 함수가 *기하 검증*에서 *진짜 채광*으로 도약

### 1-2개월 차 (학습 시작)
- **B1 Surrogate** — Radiance 비실용화 해결의 정답
- **B2 BO** — Surrogate 위에서 GA 대체
- **B3 LLM RAG** — 사례 기반 가이드

### 3-6개월 차 (재설계)
- **C2 Diffusion** 또는 **C4 DRL** 중 *하나만* 우선 (둘 다 시작은 비현실적)

---

## Open Questions

- 효과 점수는 *체감 추정*. 정확한 정량화는 A5 baseline + Phase 1 결과 후 재평가 필요
- C2 vs C4 어느 쪽이 발표/논문 가치 큰지 (ADR 결정 필요)
