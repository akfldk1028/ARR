# Cardei, Christopher, Hartvigsen et al. 2025 — *Constrained Discrete Diffusion* (CDD, NeurIPS 2025)

**저자**: Michael Cardei, Jacob K Christopher, Thomas Hartvigsen 외 (5인)
**학회**: 39th Conference on Neural Information Processing Systems (NeurIPS 2025)
**arXiv**: [2503.09790](https://arxiv.org/abs/2503.09790) (v3, 2025-03-12)
**PDF**: <https://arxiv.org/pdf/2503.09790v3>

---

## 한 줄 요약

> *이산* sequence 생성에서 sequence-level hard constraint를 강제. PGDM(Christopher 2024 NeurIPS)의 이산 확장. **Diffusion sampling 중에 *차별화 가능 constraint optimization*을 직접 통합 → training-free, post-hoc filter 불필요.** 자연어/코드/논리 규칙 도메인. **매스를 grid token으로 인코딩 시 적용 가능**.

---

## 핵심 idea

- 이산 diffusion: $p(x_t | x_{t-1})$가 categorical noise (state token).
- 표준 모델은 sampling 후 *post-hoc 검증/필터*만 가능 → CDD는 sampling 시점에 differentiable constraint를 reverse step에 *directly* 주입.
- Christopher 2024 PGDM이 *연속* domain projection을 제시했다면, CDD는 *이산* domain의 Lagrangian-style 통합.

---

## 적용 도메인 (논문)

- 자연어 생성: 키워드 강제, 길이 제약, 안전성 룰
- 코드 생성: 문법 (CFG)
- 논리 추론 시퀀스

→ **건축/매스 직접 응용 X**. 단, *시퀀셜 매스 적층 (floor 1 → 2 → ...)*을 token sequence로 인코딩하면 가능.

---

## 우리 시스템 적용 가능성

### 시나리오: Discrete 매스 인코딩

```
매스 = sequence of (footprint_idx, height_idx) tokens
       e.g., [(F1, H1), (F2, H1), (F2, H2), ...]
constraint: 누적 면적 ≤ FAR · A_lot, 누적 높이 ≤ 일조 envelope, ...
```

CDD를 사용하면 sampling 시점에:
- BCR token-by-token (footprint 누적) hard 강제
- FAR sequence-level hard 강제
- 일조: token 추가 시 *envelope 위반 차별화 가능 cost* 주입

### 한계
- 매스를 정말로 token sequence로 환원할 수 있나? *연속 footprint*는 PGDM이 더 자연스러움.
- 학습 데이터: 시퀀셜 매스 적층 trajectory 1k+ 필요 → 데이터셋 부재 (ds02 진행 후 가능).

---

## 인용 위치

- `constraint_aware_survey.md` **Cat 4 (Constrained Sampling) — 이산 변형**
- C2 Diffusion prior의 *대안 인코딩* 옵션
- AUA reference의 *room subdivision* 패턴과 결합 가능 (subdivision = discrete tree)

---

## 다음 단계

- [ ] PGDM (이미 박제) vs CDD 인코딩 비교 노트 작성 시점에 본 노트 갱신
- [ ] 시퀀셜 매스 dataset 가능성 검증 (ds02)
