# C7 — Hard Constraint Strategy (Phase 3)

**작성일**: 2026-04-30
**선행 노트**: `06_LITERATURE/constraint_aware_survey.md` (학계 SOTA 종합)
**관련 결정**: C1 SDF, C2 Diffusion prior, C4 DRL Bootstrap

---

## 0. 결정 사항 (TL;DR)

> Phase 3에서 hard constraint 처리 전략 = **3-layer hybrid**:
> 1. **Sampling 시점**: PGDM (Christopher 2024 NeurIPS) projection — BCR/FAR/이격만 hard
> 2. **Verify 시점**: 우리 `regulation_validator.py` + `envelopes/sunlight.py` — 정북일조/도로사선 hard cut
> 3. **Repair 시점**: 위반 매스를 deterministic clip → next iteration init
>
> *모든 constraint를 sampling에서 hard 강제* 하려는 시도는 **포기**. 정북일조/도로사선의 비볼록성 + 시간대별 시뮬레이션 비차별성이 학계 미해결이기 때문 (`constraint_aware_survey.md` Cat 4 참조).

---

## 1. 배경

### 1.1 우리 현재 (Phase 1-2)

```
GA NSGA-III
├─ 변이/교차 → infeasible 가능
├─ Repair: setback box clip (hard 보장 일부)
├─ Penalty: 정북일조/사선 위반 = fitness penalty (soft)
└─ Verify: tools/verify_setbacks.py 8종 + BCR/FAR 전수 대조
```

**문제**:
- 일조 시뮬레이션 = GA 매 individual 마다 5-30초 → 1세대 100 ind × 100 gen = **30+시간**
- penalty weight 매직넘버 (현재 alpha=10, beta=5) — 부지 변경 시 재튜닝
- 학습 기반 매스 생성 (Phase 3 C1/C2/C4) 채택 시 *어떻게 hard 강제할지* 미정

### 1.2 학계 SOTA (요약, 자세한 건 survey 노트)

- **Cat 4 (Constrained Sampling)**: PGDM 2024 NeurIPS, CDD 2025 NeurIPS, PPR 2026, Training-Free Stable Diffusion 2025 NeurIPS Spotlight
- **Cat 3 (Constraint Layer)**: OptNet 2017 + cvxpylayers — convex만
- **Cat 5 (Lagrangian DRL)**: CPO 2017, PPO-Lagrangian 2022 — 확률적
- **Cat 7 (Generate-then-Verify)**: 우리가 이미 사용 중

---

## 2. 3-Layer 전략 상세

### Layer 1. Sampling 시점 — PGDM projection

```python
# 가설: engine/diffusion_prior.py (Phase 3 C2)
class PGDMSampler:
    def reverse_step(self, x_t, t):
        x_pred = self.denoise(x_t, t)              # 표준 reverse
        x_proj = self.project_convex(x_pred)        # ← 추가
        return x_proj

    def project_convex(self, x):
        # x = 매스 (n_floors x footprint_params)
        # constraint: BCR, FAR, lot_boundary, 이격
        # → cvxpylayers QP solve
        return solve_qp(x, A, b, G, h)
```

**커버**: BCR, FAR, 이격, 부지 외곽 — **hard 보장**
**불가**: 정북일조 4단계, 도로 사선 — sub-gradient만, soft

### Layer 2. Verify 시점 — Generate-then-Verify

```python
# 이미 존재: engine/regulation_validator.py
def verify(mass):
    if not envelopes.sunlight.contains(mass):     # 정북일조 hard
        return False
    if not envelopes.road_diagonal.contains(mass): # 도로사선 hard
        return False
    if mass.bcr > BCR_LIMIT: return False
    if mass.far > FAR_LIMIT: return False
    return True
```

**Phase 3 통합**:
- PGDM sampling → 후보 N개 생성
- verify pass 후보만 GA fitness로 진행
- pass rate < 30% 이면 PGDM weight λ 자동 증가

### Layer 3. Repair — Deterministic clip

```python
# engine/repair.py (확장 필요)
def repair(mass):
    mass = clip_to_buildable(mass, buildable)        # setback (이미)
    mass = clip_to_envelope(mass, sunlight_env)      # 정북일조 (신규)
    mass = clip_to_envelope(mass, road_diagonal_env) # 도로사선 (신규)
    mass = scale_to_bcr(mass, BCR_LIMIT)             # BCR (이미)
    mass = trim_to_far(mass, FAR_LIMIT)              # FAR (신규)
    return mass
```

**효과**: verify fail 후보를 *next iteration init*으로 재활용 → diversity 손실 최소.

---

## 3. 학계 위치 — 정직 평가

| 우리 layer | 학계 카테고리 | 학계 sota | 우리 진척 |
|-----------|--------------|----------|-----------|
| Layer 1 | Cat 4 (Constrained Sampling) | PGDM NeurIPS 2024 | Phase 3 시작 (미구현) |
| Layer 2 | Cat 7 (Generate-then-Verify) | House-GAN++ 2021, BuildThemis 2025 | **Phase 1-2 완성, 학계와 동급** |
| Layer 3 | Cat 2 (Repair) | Salcedo-Sanz 2009 survey | 부분 구현 (setback만) |

> **종합**: Layer 2/3은 학계 동급, Layer 1은 PGDM 도입으로 학계 수준 도달 가능. 한국식 비볼록 사선의 *sampling-hard 강제*는 학계 미해결이라 우리도 verify/repair로 우회.

---

## 4. Phase 3 구현 우선순위

### Phase 3a (필수, 8주)

1. `engine/repair.py` 확장 — 정북일조 clip + FAR trim (Layer 3) — **2주**
2. `engine/diffusion_prior.py` PGDM 구현 — Convex projection만 — **6주**
3. ds02 한국 매스 데이터셋 1k+ (의존) — **4-8주 (병렬)**

### Phase 3b (선택, 4주)

4. `engine/optnet_layer.py` cvxpylayers wrapper — BCR/FAR layer 이중화 — **2주**
5. Sub-gradient 일조 cost — PGDM 비볼록 변형 — **2주**

### Phase 3c (이연)

6. PPO-Lagrangian DRL (`drl_chen_2024.md`, C4) — *Phase 3a 결과 미흡 시*
7. CDD discrete 인코딩 — *PGDM 한계 봉착 시*

---

## 5. 트리거 / Plan B

### Trigger (Phase 3a 진입 조건)

- [x] Phase 1-2 완료 (DONE 2026-04-21 Session 14)
- [ ] Surrogate model (Phase 2) MSE plateau — *진행 중*
- [ ] ds02 한국 매스 1k+ 확보 — *Phase 3 dependency*
- [ ] GPU 24GB+ 확보 (vast.ai 또는 자체) — *C5 결정*

### Plan B

- **PGDM 학습 실패** → Layer 2 verify-loop만으로도 *hard 보장* (속도만 손해, 학계 동급 유지)
- **데이터셋 부족** → BuildingNet (해외) 또는 *룰 기반 데이터 합성*
- **GPU 비용 폭발** → OptNet QP만 (학습 불요, CPU 가능) — Layer 1 약화 버전

---

## 6. 성공 기준 (Phase 3 완료 조건)

1. **수렴 속도**: GA only 100 gen → PGDM init 30 gen (3.3x)
2. **법규 hard 보장**: verify pass rate ≥ 95% (현재 70-80%)
3. **새 부지 ms 추론**: PGDM 단독으로 zero-shot 매스 1초 이내
4. **ADR003 트리거**: 위 3개 모두 달성 시 박스 적층 deprecate 검토

---

## 7. 인용

- `06_LITERATURE/constraint_aware_survey.md` — 카테고리 7개 종합
- `06_LITERATURE/pgdm_christopher_2024.md` — Layer 1 원전
- `06_LITERATURE/optnet_amos_2017.md` — Layer 1 부분 대안
- `06_LITERATURE/cdd_cardei_2025.md` — Phase 3c 이산 변형
- `C2_diffusion_prior.md` — 기존 결정과 통합 필요
- `C4_drl_bootstrap.md` — Phase 3c PPO-Lagrangian 후보

## 8. 한 줄 결론

> *학계가 hard constraint를 sampling 시점에 완전히 푼 generic framework는 NeurIPS 2024-2025에 존재 (PGDM/CDD)지만, 한국식 비볼록 사선은 sampling-hard 미해결.* **3-layer hybrid (sampling proj + verify cut + repair clip)이 정직한 우리 답.**
