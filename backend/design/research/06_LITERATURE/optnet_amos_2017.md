# Amos & Kolter 2017 — *OptNet: Differentiable Optimization as a Layer in Neural Networks* (ICML 2017)

**저자**: Brandon Amos, J. Zico Kolter (CMU)
**학회**: ICML 2017
**arXiv**: [1703.00443](https://arxiv.org/abs/1703.00443) (v5)
**PDF**: <https://arxiv.org/pdf/1703.00443>
**코드**: <https://github.com/locuslab/optnet>
**저자 슬라이드**: <http://bamos.github.io/data/slides/2017.optnet.pdf>

---

## 한 줄 요약

> 신경망에 *quadratic program(QP)을 한 layer로* 끼워 넣음. KKT 조건의 implicit differentiation으로 backprop 통과 → *hard constraint를 학습 시점에 강제*. 매스 도메인 응용은 0편이지만, 우리 *이격 거리 / BCR linear constraint*에 부분 적용 가능.

---

## 핵심 idea

```
OptNet layer:
  input:  z (이전 layer 출력)
  forward:  y* = argmin_y (1/2) y^T Q(z) y + p(z)^T y
                  s.t. A(z) y = b(z), G(z) y ≤ h(z)
  backward:  ∂y*/∂z = implicit diff of KKT conditions
```

- Q, p, A, b, G, h는 z의 함수 (학습 가능 파라미터 포함)
- backward = primal-dual interior point + sensitivity analysis
- GPU batch solver 자체 구현 → 실시간 학습 가능

**핵심 강점**: 기존 conv/FC layer가 표현 *못하는* hard constraint를 *학습 가능 layer*로. 미니 4×4 Sudoku 룰을 input/output 페어만 보고 학습 — 기존 NN은 실패.

---

## 우리 시스템 적용 가능성

### 적용 *가능*

#### Linear constraint만 있는 경우 (BCR, FAR, 부지 외곽)

```python
# Phase 3 매스 생성 last layer (가설)
mass_params = network(site_features)  # raw 매스 6 floors footprint
mass_proj = OptNet(
    Q = identity,                     # min ||mass_params - mass_proj||^2
    A_eq = volume_aggregator,         # sum(area_i * height_i) ≤ FAR * lot
    G_ineq = bcr_constraint,          # max footprint ≤ BCR * lot
    G_ineq2 = boundary_constraint,    # mass ⊂ buildable area
)
loss = task_loss(mass_proj)            # backprop 통과
```

→ **BCR/FAR/이격 = QP로 표현 가능 → hard 보장**.

### 적용 *불가*

- **정북일조 4단계 사선** = 비볼록, 비선형 (envelope = shapely buffer 4단계)
- **도로 사선** = piecewise linear ≠ QP (해석적으로 풀어도 OptNet 직접 적용 어려움)
- **시간대별 일조 시뮬레이션** = differentiable rendering 별도 (`dr_mitsuba3.md` 참조)

---

## 우리 적용 비용

| 항목 | 추정 |
|------|------|
| 구현 (cvxpylayers wrapper) | 2주 |
| BCR/FAR layer만 | 1주 |
| 이격 거리 layer (linear approx) | 1주 |
| **합계** | **4주** (Phase 3 부분 채택 가능) |

---

## 인용 위치

- `constraint_aware_survey.md` **Cat 3 (Constraint Layer)** 원전
- C7 Phase 3 전략 노트의 *부분 hard layer* 옵션
- `pgdm_christopher_2024.md`와 결합 가능 (PGDM projection이 OptNet QP solver 위에서 동작)

---

## 후속작

- Agrawal et al. 2019 *cvxpylayers* (NeurIPS) — OptNet의 cvxpy 자동화 wrapper
- Donti, Rolnick, Kolter 2021 *DC3* — hard constraint NN, KKT 외 보완

---

## 메모

- 2017 ICML 논문이지만 2026 현재 **constraint NN 분야 표준 인용**.
- 우리가 OptNet *전체*를 안 써도 *cvxpylayers* 라이브러리 차용으로 충분.
- *비볼록 사선*은 OptNet 영역 밖 → PGDM의 sub-gradient projection으로 보완.
