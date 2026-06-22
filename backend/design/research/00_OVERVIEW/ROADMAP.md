# 25_ACE 매스 자동 생성 — 연구 로드맵

**Date**: 2026-05-06
**Owner**: DongHyeon KIM
**위치**: `ARR/backend/design/research/`
**Plan 원본**: `D:\DevCache\claude-data\plans\sequential-roaming-mochi.md`

---

## Context

현재 25_ACE의 매스 최적화 시스템은 *NSGA-II + 박스 5개 적층(29 genes)* 의 GA 기반이며, AUA Discover 포팅 위에 한국 법규 31K 노드 + PNU + Vworld + SSE 통합이 더해진 형태다.

- **시스템 통합**: 학계 비교 대상 없음 — 진짜 강점
- **알고리즘/매스 표현**: 2010년대 SOTA 수준 — 한계 명확

본 로드맵은 *제대로 된 프로젝트* 로 발전시키기 위한 3단계 계획이다.

---

## 학습 필요 여부 — 한 줄 답

| Phase | 기간 | 학습 필요? | 비고 |
|---|---|---|---|
| **Phase 1** Quick Wins | 1-2주 | ❌ 불필요 | pymoo NSGA-III + Radiance + constraint penalty. 코드만 |
| **Phase 2** Light Learning | 1-2개월 | ⚠️ 경량 학습 | Surrogate(GP/MLP)는 *자가 생성* 1k-5k 데이터로 CPU 학습. RAG는 인덱싱만 |
| **Phase 3** Redesign Track | 3-6개월 | ✅ 본격 학습 | SDF/Diffusion/DRL — 외부 데이터셋 1k+ + GPU 24GB+ 1-2주 학습 |

**결론**: Phase 1은 *지금 바로* 학습 없이. Phase 2의 surrogate부터 학습 진입(외부 데이터셋 불필요). Phase 3는 별도 *연구 트랙* 으로 데이터셋 + GPU 인프라 확보 후 시작.

---

## 폴더 구조

```
research/
├── 00_OVERVIEW/        # 본 ROADMAP + 매트릭스 + 자산
├── 01_PHASE1/          # Quick Wins (1-2주, 학습 없음)
├── 02_PHASE2/          # Light Learning (1-2개월)
├── 03_PHASE3/          # Redesign Track (3-6개월, 본격 학습)
├── 04_DATASETS/        # 데이터셋 일관 관리
├── 05_EXPERIMENTS/     # 실험 결과 누적
├── 06_LITERATURE/      # 인용 논문
└── 07_DECISIONS/       # ADR 스타일 의사결정
```

상세는 `00_OVERVIEW/` 하위 4개 .md 참조:
- `LEARNING_MATRIX.md` — 작업×학습 필요성
- `ROI_PRIORITY.md` — 효과/비용 우선순위
- `RISKS_AND_PLAN_B.md` — 위험 + 폴백
- `ASSETS_TO_PRESERVE.md` — 모든 단계 유지

---

## ROI 우선순위 (즉시 시작 → 장기)

| 작업 | 효과 | 비용 | ROI | 학습 | 우선순위 |
|---|---|---|---|---|---|
| A1 NSGA-III | 4 | 1 | 4.0 | 불필요 | **즉시** |
| A4 Evaluator 통일 | 3 | 1 | 3.0 | 불필요 | 즉시 |
| A2 Radiance lite | 5 | 2 | 2.5 | 불필요 | 다음 |
| A3 Constraint penalty | 2 | 1 | 2.0 | 불필요 | 즉시 |
| B2 BO | 4 | 2 | 2.0 | 불필요 | 1개월 후 |
| B3 LLM RAG | 4 | 2 | 2.0 | 인덱싱 | 1개월 후 |
| B1 Surrogate | 5 | 3 | 1.67 | 경량 | 1개월 후 |
| C2 Diffusion | 5 | 5 | 1.0 | 본격 | 3-6개월 |
| C4 DRL | 5 | 5 | 1.0 | 본격 | 3-6개월 |

---

## Phase별 마일스톤

### Phase 1 — Quick Wins (1-3주, 학습 없음)
1. A5 Baseline 측정 (반나절)
2. **A6 Repair Operator (1주)** ⭐ — Hard constraint 강제. Flexity 격차 해소
3. A3 Constraint penalty 정교화 (3일)
4. A1 NSGA-III pymoo 통합 (1주)
5. A4 Evaluator 통일 (2일)
6. **A7 Constraint Visualizer (3-5일)** ⭐ — Cesium envelope + 매스 fit
7. A2 Radiance lite (1주)

**완료 조건**: 매스 100% feasible (envelope 위반 0건) + envelope 시각화 + NSGA-III/Radiance 검증.
**Phase 2 트리거**: Radiance가 GA 비실용화(50×30×30s = 12.5h) → B1 surrogate 즉시 시작.

### Phase 2 — Light Learning (1-2개월)
1. B1a Dataset 자가 생성 (2주)
2. B1b Surrogate 학습 (1주)
3. B2 BO 통합 (1주)
4. B3 LLM RAG (2주)
5. B4 Heterogeneous Island (3주)
6. B5 Typology 추천기 (1주)
7. **B6 Core Planner (2-3주)** ⭐ — 코어 자동 배치
8. **B7 Explanation Generator (1-2주)** ⭐ — 매스 결정 LLM 한국어 설명

**완료 조건**: BO 50평가 = GA 1500평가 hypervolume 동등, RAG 사례 3건, 코어 피난 30m 이내 95%, 한국어 설명 생성.

### Phase 3 — Redesign Track (3-6개월, 병렬)
1. C5 GPU 인프라 결정 (1주)
2. ds02 한국 매스 데이터셋 구축 (4-8주)
3. C1 SDF 매스 (4주) | C3 Differentiable Rendering (4-8주)
4. C2 Diffusion prior (8-12주)
5. C4 DRL Bootstrap (8-12주)

**완료 조건**: Diffusion init GA 수렴 30→10 gen 단축, DRL policy zero-shot ms 추론.

---

## 다음 행동 (Plan 승인 직후)

1. ✅ research/ 폴더 + 8개 하위 생성
2. ✅ 본 ROADMAP.md 작성
3. ⏳ 나머지 OVERVIEW 4개 + Phase 별 _README.md + 작업 .md placeholder
4. ⏳ 메모리 박제 (arr/mass-research-roadmap.md 등)
5. ⏳ 실제 코드 작업은 *별도 PR* 로 분리

---

## Critical Files (향후 수정 예정)

- `ARR/backend/design/engine/objects.py` (Phase 1 A1)
- `ARR/backend/design/services/mass_evaluator.py` (Phase 1 A2/A4)
- `ARR/backend/design/services/constraint_bridge.py` (Phase 1 A3)
- `ARR/backend/requirements.txt` (Phase 1 pymoo, Phase 2 sklearn/lightgbm)
- `ARR/backend/design/models/` (Phase 2 surrogate weight, 폴더 신규)
