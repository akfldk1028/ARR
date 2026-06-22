# 🎯 우리 목표 (시각적 정의)

**Date**: 2026-05-06
**근거 이미지**: 사용자 제공 (중앙일보 광고 — *플렉시티(Flexity)*, 2026-05)
**한 줄 정의**: *"법규 사선 제한을 모두 피해서 매스를 자동 생성. envelope 시각화 + 매스 fit + 코어 계획 + 20년차 건축사 사고과정"*

---

## 🖼 이미지 요소 분석 (우리가 만들고 싶은 것)

### 시각자료 구성
| 요소 | 색상 | 의미 |
|------|------|------|
| **노란색 매스** | yellow | 자동 생성된 *최종 매스* |
| **녹색 envelope** | green (반투명) | *정북 일조 사선* 한계 면 |
| **빨간 점선** | red | *대지 안의 공지* (이격선) |
| **9m 라벨** | gray | *도로 후퇴* 거리 |
| **회색 박스** (매스 우상단) | dark gray | *코어 계획* (계단실/엘리베이터 자동 배치) |
| **라벨**: "정북 일조 사선", "코어 계획", "대지 안의 공지" | — | 사용자에게 *왜 이 형태가 되었는지* 설명 |

### 광고 헤드라인
> *"전문가 수준 AI 자동 기획설계. 20년차 전문 건축사의 사고과정 그대로"*

→ 단순 최적화 X. *건축사의 사고과정*을 모방. 즉 **법규 + 코어 + 매스 + 동선** 을 통합 자동화.

---

## 📋 시스템이 *반드시* 처리해야 할 제약 조건

### A. Hard Constraint (절대 위반 금지)
1. ✅ **정북 일조 사선** — `envelopes/sunlight.py` (LOCKED, 4단계 사선)
2. ⚠️ **도로 사선** — 일부 구현, hard constraint X
3. ⚠️ **인접대지 이격** — penalty만, hard X
4. ⚠️ **건폐율 (BCR)** — penalty만
5. ⚠️ **용적률 (FAR)** — penalty만
6. ⚠️ **높이 제한** — penalty만
7. ⚠️ **대지 안의 공지** (도로 후퇴) — 부분 구현
8. ❌ **문화재/경관 보호선** — 미구현
9. ❌ **소방법 (피난 거리)** — 미구현

### B. Soft Constraint (목적함수)
- 면적 (floor_area)
- 일조 점수 (daylight_score)
- 이격거리 점수
- 조경 면적 (landscaping_pct)
- 외부 공간 (open_pct)

### C. *플렉시티가 추가로* 다루는 것 (우리 미구현)
- **코어 계획** — 계단실/엘리베이터 자동 배치
- **20년차 건축사 사고과정** — 도메인 사례 학습
- **시각적 라벨** — 왜 이런 형태가 되었는지 사용자에게 설명

---

## 📊 우리 시스템의 *현재 위치* (정직 평가)

| 능력 | 우리 시스템 | 플렉시티 (광고) | 학계 SOTA |
|------|----------|----------|----------|
| **정북일조 envelope 계산** | ✅ LOCKED | ✅ | ✅ |
| **envelope 3D 시각화** | ✅ Cesium | ✅ | 부분 |
| **envelope hard constraint 강제** | ⚠️ penalty | ✅ (광고 기준) | 미해결 (학계 진행형) |
| **다양한 매스 형태 (10종)** | ✅ | ? | ✅ |
| **법규 자동 도출 (41 규제)** | ✅ ⭐ | ? | ❌ (학계 없음) |
| **PNU + Vworld 자동 부지** | ✅ ⭐ | ? | ❌ |
| **실시간 SSE 진행** | ✅ | ? | ❌ |
| **코어 계획 자동** | ❌ | ✅ | 부분 |
| **사례 학습 (20년차 사고)** | ❌ | ✅ (광고 기준) | 부분 (HouseGAN++ 등) |
| **시각적 설명 (왜 이렇게?)** | ⚠️ 부분 | ✅ | ❌ |

### 우리 진짜 강점 ⭐ (플렉시티에 없을 가능성 높음)
1. **한국 법규 31K 노드 Neo4j 그래프** (학계+업계 모두 없음)
2. **PNU/Vworld 한국 인프라 직접 연동** (한국 부지 자동)
3. **41개 규제 자동 도출** (BCR/FAR + 38개 추가)
4. **실시간 SSE UI** (사용자 친화)

### 우리 격차 (즉시 개선 필요)
1. ❌ **Hard constraint 강제 부족** — penalty가 아니라 *반드시* 통과
2. ❌ **코어 계획 자동화** — 매스 안에 계단/엘리베이터 자동 배치
3. ❌ **20년차 사고과정 학습** — 사례 RAG / Diffusion 미구현
4. ⚠️ **사용자 설명 부족** — *왜 이렇게 되었는가* UI 약함

---

## 🎯 격차를 좁히는 전략 (Phase별)

### Phase 1 (1-2주, 학습 X) — *Hard Constraint 강제*
- **A1 NSGA-III** — many-objective 처리
- **A6 Repair Operator (신규)** — envelope 위반 매스를 *자동 수정* 후 평가 (*penalty → hard*)
  - 정북일조선 위반 vertex → 해당 vertex를 envelope 면으로 *projection*
  - BCR/FAR 위반 → 매스 *축소* 자동
- **A7 Constraint Visualizer (신규)** — Cesium에 envelope + 매스 fit 동시 표시 (플렉시티 광고처럼)

### Phase 2 (1-2개월) — *코어 계획 + 사례 RAG*
- **B6 Core Planner (신규)** — 매스 결정 후 *코어(계단실/엘리베이터) 자동 배치*
  - 면적 비율 (5-10%) + 동선 거리 (피난 30m 이내) + 자연광 회피
- **B3 LLM RAG** — *20년차 건축사 사고* 일부 모방 (사례 기반)
- **B7 Explanation Generator (신규)** — *왜 이런 형태가 되었는지* LLM이 한국어 설명

### Phase 3 (3-6개월, 본격 학습) — *Constraint-Aware Generative*
- **C7 Hard Constraint Strategy** (이미 추가됨) — PGDM (Projected Diffusion) 채택
- envelope 안에서만 sampling 가능한 학습 기반 생성
- 한국 사례 1k+ 학습 (ds02)

---

## 🛡 핵심 메시지 (교수님께 답변용)

> *"플렉시티 광고 같은 결과는 우리도 가능합니다. 시스템 통합(법규 31K + PNU + Vworld)에서는 오히려 우리가 앞서고, hard constraint 강제는 Phase 1 A6 repair operator로 1-2주 내 동등 수준 도달 가능합니다. 코어 계획 + 사례 학습이 Phase 2-3 핵심 contribution입니다."*

---

## 📁 관련 자료

- `00_OVERVIEW/ROADMAP.md` — 3-Phase 로드맵
- `06_LITERATURE/constraint_aware_survey.md` — Hard constraint 학계 SOTA (PGDM, OptNet 등)
- `03_PHASE3/C7_hard_constraint_strategy.md` — Phase 3 hard constraint 전략
- `01_PHASE1/A6_repair_operator.md` — *신규 추가 예정* (즉시 시작 작업)
- `01_PHASE1/A7_constraint_visualizer.md` — *신규 추가 예정*

---

## 🆚 경쟁자: 플렉시티(Flexity)

- 광고 매체: 중앙일보, 다음 등 한국 주요 매체
- 광고 시점: 2026-05 (현재)
- 추정 위치: *우리와 직접 경쟁*. 한국 시장.
- 우리 차별점:
  - 학계 호환성 (논문 가능)
  - 시스템 통합 (법규 그래프)
  - Open question: 플렉시티가 *법규 그래프 31K 노드 수준 인프라* 가졌는지 미확인

**Open Question**: 플렉시티 기술 스택 / 데이터셋 / hard constraint 처리 방식 — 추후 조사 필요.
