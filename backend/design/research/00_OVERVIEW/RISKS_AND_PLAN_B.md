# 위험 / Plan B

**질문**: "학습이 안 되거나, 데이터셋 못 모으거나, GPU 비용 폭발하면?"

---

## 위험 요소 + 대응

| 위험 | 발생 가능성 | 영향 | 대응 (Plan B) |
|---|---|---|---|
| **R1**: ds02 한국 건축 매스 1k+ 확보 실패 | 중간 | Phase 3 차단 | ds03 해외 공개(BuildingNet) + transfer learning |
| **R2**: Phase 2 surrogate 학습 실패 (MSE plateau) | 낮음 | B 트랙 일부 무력화 | Phase 1 + B3 RAG + B4만으로 마무리, C 트랙 보류 |
| **R3**: Phase 3 GPU 비용 과다 (vast.ai 월 $500+) | 중간 | C2/C4 차단 | C3 Differentiable Rendering(학습 불요)만 우선 |
| **R4**: 박스 적층 영원히 deprecate 못 함 | 높음 | 코드 부채 누적 | 사용자 모드 분리(MVP/Research) — 둘 다 운영 |
| **R5**: SDF/Diffusion이 한국 법규 hard constraint 못 강제 | 중간 | C 트랙 효용 의문 | hard constraint를 *학습 후 검증 단계* 로 이동 |
| **R6**: 시스템 통합 자산(법규 31K, PNU, Vworld, SSE) 우연히 단절 | 낮음 | 핵심 가치 손실 | 회귀 테스트 의무화 (Phase 1 시작 시 baseline 필수) |
| **R7**: pyradiance/honeybee-radiance Windows 환경 설치 실패 | 중간 | A2 차단 | Docker 컨테이너 또는 WSL2로 우회 |
| **R8**: pymoo NSGA-III와 기존 SSIEAJob 충돌 | 낮음 | A1 차단 | NSGA-III를 *별도 클래스* 로 추가, SSIEAJob 유지 |

---

## Plan B 시나리오

### 시나리오 1 — Phase 2 학습 실패
**증상**: Surrogate validation MSE plateau (0.3 이하 못 내려감)

**대응**:
- B1 (surrogate) 보류
- B3 (RAG) + B4 (Heterogeneous Island) 만으로 진행
- Phase 3는 보류 또는 *학습 없는 C3 Differentiable Rendering* 만

**결과**: SOTA 미달, 그러나 *학계 3년치 격차 메움*. 발표/논문 가치는 충분.

### 시나리오 2 — 데이터셋 확보 실패
**증상**: ds02 한국 건축 매스 1k+ 라이선스 또는 수집 불가

**대응**:
- ds03 해외 공개 데이터셋 (BuildingNet, KIT, ShapeNet 일부) + transfer learning
- 한국 특화는 *prompt/fine-tune* 으로만 (사례 100건 정도)

**결과**: C 트랙 가능, 단 한국 특화는 약화

### 시나리오 3 — GPU 비용 과다
**증상**: vast.ai A100 $1.5/h × 1주 = $250+, 월 $1000 넘음

**대응**:
- C3 Differentiable Rendering 우선 (학습 불요, Mitsuba 3로 inference)
- C2 Diffusion은 *기존 pretrained 모델* fine-tune (LoRA 5GB GPU로 가능)
- C4 DRL 보류 또는 *작은 환경* 부터 (10×10 부지)

**결과**: C 트랙 일부 가능

### 시나리오 4 — 모든 학습 트랙 실패 (최악)
**증상**: Phase 2 학습 실패 + 데이터셋 실패 + GPU 비용 과다

**대응 (최종 Plan B)**:
- Phase 1 (A1-A5) + B3 RAG + B4 Hetero Island 만으로 마무리
- *시스템 통합* 강점에 집중 (한국 법규 + 실시간 SSE)
- 박스 적층 GA는 *MVP 그대로 유지*

**결과**: 학계 SOTA 미달이지만 *발표/논문 가치 충분*. 향후 GPU 인프라 확보 시 C 트랙 재시도.

---

## 핵심 자산 보호 (Phase 1-3 모두 유지)

다음은 *어떤 시나리오에도 손상되지 않아야* 함:

1. **한국 법규 31,126 노드 Neo4j 그래프** — 학계에 없는 자산
2. **PNU + Vworld 자동 연동** — 한국 부지 자동 분석
3. **실시간 SSE 스트리밍 UI** — 실무 사용성
4. **land/ 41 규제 파이프라인** — 도메인 전문성

`00_OVERVIEW/ASSETS_TO_PRESERVE.md` 에서 코드 경로 cross-reference.

**위험 R6 회피**: Phase 1 시작 시 *회귀 테스트 의무화*. 위 4개 자산이 시스템 변경 후에도 정상 작동하는지 자동 검증.
