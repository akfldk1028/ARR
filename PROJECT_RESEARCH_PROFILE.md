# ARR Project Research Profile

## 1. 프로젝트 개요

ARR은 토지, 건축법규, 3D 공간정보, 생성형 AI 에이전트를 결합해 초기 건축 매스 계획을 자동화하고 검토하는 연구/개발 프로젝트다. 단순히 법규 정보를 검색하거나 3D 지도를 보여주는 도구가 아니라, 사용자가 특정 필지(PNU)를 선택하면 해당 대지의 형상, 면적, 도로/인접대지 조건, 건폐율, 용적률, 높이제한, 일조 사선 등 건축 제약을 계산하고, 그 제약 안에서 가능한 건축 매스를 생성, 평가, 수정하는 것을 목표로 한다.

핵심 목표는 “법규를 위반한 뒤 후보를 설명하는 시스템”이 아니라 “처음부터 법규 envelope 안에서 다양한 massing candidate를 만들고, 사용자가 AI agent와 대화하거나 직접 조작하면서 합법성과 사업성을 동시에 최적화하는 시스템”을 만드는 것이다.

## 2. 왜 만들게 되었는가

건축 초기 기획 단계에서는 대지의 잠재 용적과 가능한 건축 형태를 빠르게 판단해야 한다. 하지만 실제 업무에서는 다음 문제가 반복된다.

1. 법규 검토와 3D 매스 스터디가 분리되어 있다.
   설계자는 법규 자료를 따로 확인하고, CAD/SketchUp/BIM 도구에서 별도로 매스를 만든 뒤, 다시 법규 위반 여부를 수작업으로 확인한다.

2. 초기 매스 후보가 제한적이다.
   많은 자동화 도구는 몇 개의 고정된 형태, 예를 들어 box, tower, courtyard 같은 template을 생성하는 수준에 머문다. 이 경우 필지 형상이나 일조 사선, setback envelope에 맞춘 다양하고 합법적인 형태 탐색이 어렵다.

3. 법규 위반 검토가 사후적이다.
   사용자가 만든 매스를 나중에 검사하고 “어디가 틀렸는지” 알려주는 방식은 가능하지만, 실제 기획에서는 위반하지 않는 범위 안에서 용적률과 건폐율을 최대한 채우는 생성 과정이 더 중요하다.

4. AI agent와 공간 조작이 연결되어 있지 않다.
   최근 설계 흐름은 사용자가 “이쪽 면을 2m 밀고, 일조 위반 없게 용적률을 최대한 채워줘”처럼 대화형으로 설계를 수정하는 방향으로 이동하고 있다. 하지만 일반 LLM은 법규, GIS 좌표계, 3D geometry, 최적화 결과를 일관되게 다루기 어렵다.

ARR은 이 문제를 해결하기 위해 만들어졌다. 즉, 법규와 3D geometry를 별도로 다루지 않고, 법규 기반 envelope와 MAAS-style mass generation을 중심에 두고, agent가 그 결과를 해석하고 수정 방향을 제안하는 통합 실험 플랫폼이다.

## 3. 연구 질문

ARR이 다루는 주요 연구 질문은 다음과 같다.

1. 법규를 constraint로 formalize했을 때, 건축 매스를 어떻게 자동 생성할 수 있는가?

2. 건폐율(BCR), 용적률(FAR), 높이제한, setback, 일조 사선 등 서로 다른 규제가 충돌할 때 어떤 방식으로 feasible envelope를 계산하고 mass candidate를 최적화할 수 있는가?

3. 기존 template 기반 10종 massing logic을 유지하되, 이를 최종 생성 방식이 아니라 seed/operator library로 격하하고, envelope-first generator가 중심이 되는 구조를 어떻게 만들 수 있는가?

4. 사용자가 SketchUp처럼 push/pull 방식으로 mass를 직접 조작할 때, 법규 적합성, FAR/BCR metric, agent review를 실시간에 가깝게 동기화할 수 있는가?

5. LLM/agent가 geometry generation 자체를 직접 수행하는 것이 아니라, 법규 검토 agent, geometry repair agent, optimization agent, review agent로 역할을 나누면 더 안정적인 설계 보조가 가능한가?

## 4. 시스템 구조

ARR은 크게 frontend, Django backend, FastAPI/Eigent agent server, 외부 GIS/법규 데이터 계층으로 구성된다.

### 4.1 Frontend

주요 역할:

- VWorld 기반 2D/3D 지도 표시
- 필지 선택 및 PNU 기반 분석 요청
- 법규 envelope, setback, sunlight plane, mass geometry 시각화
- interactive mass operation UI 제공
- A2UI-style agent review panel 표시
- 사용자 입력, 대화, 설계 조작, 결과 비교 인터페이스 제공

주요 경로:

- `frontend/src/design/`
- `frontend/src/land/`
- `frontend/src/law/`
- `frontend/src/design/components/SiteMapPanel.tsx`
- `frontend/src/design/components/InteractiveDesignPanel.tsx`
- `frontend/src/design/components/A2UISurfaceRenderer.tsx`

### 4.2 Django Backend

주요 역할:

- 필지/토지 분석
- 법규 constraint 구성
- mass 후보 생성
- legal envelope 계산
- SCAD/export 및 geometry 변환
- interactive mass operation 처리
- MAAS generator 및 agent review orchestration

주요 경로:

- `backend/design/`
- `backend/design/maas/`
- `backend/design/maas/legal_envelope.py`
- `backend/design/maas/legal_mesh_optimizer.py`
- `backend/design/maas/seed_library.py`
- `backend/design/maas/interactive/`
- `backend/design/maas/agents/`
- `backend/design/services/mass_operations.py`

### 4.3 FastAPI/Eigent Agent Server

기존 Eigent 기반 agent UI/worker/chat 기능을 담당한다. ARR은 이 구조를 유지하면서 `/api` 프록시, local dev 기본값, auth 안정성을 보강했다. 추후 multi-agent collaboration과 설계 대화 기능을 연결하기 위한 기반 서버로 사용할 수 있다.

주요 경로:

- `frontend/server/`
- `frontend/server/app/controller/`
- `frontend/server/app/component/auth.py`
- `frontend/server/app/component/database.py`
- `frontend/server/app/component/environment.py`

## 5. 핵심 알고리즘 방향

### 5.1 Legal Envelope First

ARR의 mass generation은 최종적으로 legal envelope 기반이 되어야 한다. 즉, 먼저 법규가 허용하는 3D 가능 공간을 계산하고, 그 공간 안에서 mass candidate를 생성한다.

기본 입력:

- 대지 polygon
- 대지 면적
- 도로/인접대지 방향
- 건폐율 제한
- 용적률 제한
- 높이 제한
- setback 조건
- 정북일조/사선제한
- 층고 및 최대 층수

기본 출력:

- legal floor plate stack
- floor별 buildable footprint
- FAR/BCR/height metric
- rejected candidate와 위반 사유
- agent review message

중요한 점은 “매스를 만들고 검사”하는 방식이 아니라 “층별 허용 footprint를 깎아가며 채우는 방식”이다. 예를 들어 정북일조 사선 때문에 상층부에서 허용 폭이 줄어들면, generator는 각 층의 polygon을 별도로 clip하고, 그 안에서 FAR을 최대한 채우는 plate stack을 만든다.

### 5.2 기존 10종 Mass Logic의 위치

초기에는 여러 고정 mass shape을 생성하는 10종 logic이 있었다. 그러나 이 방식은 다양성은 줄 수 있지만 법규 최적화의 중심이 되기 어렵다. 현재 프로젝트 방향은 다음과 같다.

- 기존 10종 logic은 유지 가능
- 단, primary generator가 아니라 seed/operator library로 사용
- 최종 후보는 legal envelope repair와 optimizer를 통과해야 함
- 법규 위반 후보는 설명용/debug용으로 남기되, 사용자에게 기본 제안되는 mass는 legal-first여야 함

즉, template은 “형태 다양성의 출발점”이고, MAAS generator가 “법규 적합성과 최적화의 중심”이다.

### 5.3 MAAS-style Generator

MAAS 방향의 generator는 다음 책임을 가진다.

- 다양한 seed mass 생성
- 층별 footprint mutation
- setback/sunlight/height envelope repair
- FAR/BCR 목표치에 대한 scoring
- 너무 단순한 box뿐 아니라 stepped, terraced, split, courtyard, slab-tower hybrid 같은 후보 생성
- 후보별 agent review 및 rejection reason 생성

구현상 핵심 모듈:

- `seed_library.py`: seed/operator 후보 생성
- `legal_mesh_optimizer.py`: legal repair, scoring, variant sorting
- `legal_envelope.py`: 법규 기반 buildable geometry 계산
- `interactive/geometry_ops.py`: push/pull, offset, scale, floor trim
- `interactive/orchestrator.py`: 사용자 조작 → legal repair → agent review 흐름

## 6. Direct Manipulation과 Agent Collaboration

ARR은 단순히 “생성 버튼을 누르면 매스가 나오는” 도구를 목표로 하지 않는다. 사용자는 SketchUp처럼 건축 매스를 보면서 다음과 같은 조작을 할 수 있어야 한다.

- 특정 면을 밀거나 당김
- 층을 추가하거나 제거
- footprint를 scale
- 특정 edge를 offset
- 법규 위반 없이 FAR을 더 채우도록 요청
- agent에게 “이 후보가 왜 좋은지/왜 위반인지” 질문

현재 구현된 방향:

- `push_pull_face`
- `scale_footprint`
- `offset_edge`
- `reshape_floor_plate`
- operation history 저장
- law/geometry/optimization/review agent의 deterministic review 생성
- A2UI-style message로 agent review UI 렌더링

중요한 설계 원칙:

- 사용자가 조작한 geometry를 그대로 신뢰하지 않음
- 조작 후 항상 legal repair와 metric recomputation 수행
- direct operation 결과가 기존 최고점 template 후보에 덮이지 않도록 `interactive_seed_repaired` 후보를 우선 유지
- agent는 geometry를 “상상해서” 말하는 것이 아니라, 계산된 metrics와 rejected reason을 기반으로 설명

## 7. A2UI와 Agent UI 방향

ARR은 agent와 UI가 서로 구조화된 메시지를 주고받는 방향을 실험한다. 참고 구현으로 Google A2UI repository를 clone해 분석했고, 현재 ARR에는 최소 A2UI-like renderer가 들어가 있다.

참고 repo:

- `/mnt/d/Data/25_ACE/clone/A2UI`

현재 ARR 적용:

- backend에서 `createSurface`, `updateComponents`, `updateDataModel` 형태의 message 생성
- frontend에서 `A2UISurfaceRenderer.tsx`가 이를 받아 metric strip과 agent review card 렌더링
- 추후 official `@a2ui/react` 또는 더 강한 schema 기반 renderer로 교체 가능

이 접근의 장점:

- agent 응답을 단순 text가 아니라 UI component state로 표현 가능
- law agent, geometry agent, optimization agent의 판단을 분리해 표시 가능
- 사용자가 조작한 mass에 대해 실시간 review panel을 구성할 수 있음

## 8. 법규 최적화의 핵심 지표

ARR mass candidate는 다음 지표를 중심으로 평가된다.

- FAR: 용적률. 목표는 법규 한도에 최대한 근접하되 초과하지 않는 것.
- BCR: 건폐율. ground footprint가 제한을 넘지 않도록 제어.
- height: 전체 높이. 높이제한과 일조 사선 envelope를 동시에 고려.
- usable floor area: 유효 연면적.
- envelope compliance: setback, sunlight, height, floor plate validity.
- diversity score: 후보 간 형태 차이.
- maas_score: 법규 적합성과 사업성, 형태 품질을 합산한 내부 scoring.

상용 수준으로 발전시키려면 단순히 score를 높이는 것이 아니라 다음이 필요하다.

- 위반 후보가 절대 기본 선택되지 않도록 hard constraint 적용
- 법규 해석의 출처와 조항 근거 연결
- geometry robustness 확보
- PNU별 여러 케이스 regression test
- 현업 설계자의 manual override와 agent explanation 동시 지원

## 9. OpenSCAD의 역할

OpenSCAD는 BIM이 아니다. IFC/Revit 같은 건축 정보 모델링 시스템도 아니다. ARR에서 OpenSCAD를 활용한다면 역할은 다음에 가깝다.

- procedural geometry export
- mass candidate를 코드 기반으로 재현하는 중간 표현
- LLM/agent가 geometry operation을 명시적으로 기록하는 format
- 빠른 shape debugging 또는 external render/export pipeline

따라서 ARR의 중심은 OpenSCAD가 아니라 legal-envelope MAAS generator다. OpenSCAD는 “법규 기반 mass를 코드로 재현하거나 외부 도구로 넘기기 위한 보조 표현”으로 보는 것이 정확하다.

## 10. 기술적으로 중요한 구현 포인트

### 10.1 좌표계와 Geometry

법규 계산은 WGS84 좌표 그대로 하면 면적/거리 오차가 커질 수 있다. ARR은 대지 polygon을 UTM 기반 metric coordinate로 변환해 면적, setback, offset, floor plate 계산을 수행하는 방향을 사용한다.

중요한 처리:

- GeoJSON polygon parsing
- WGS84 ↔ UTM 변환
- polygon validity repair
- floor plate clipping
- edge offset
- height extrusion
- 3D entity rendering

### 10.2 법규 Envelope

법규 envelope는 단순 bounding box가 아니다. 각 층별로 허용되는 footprint가 다를 수 있다.

예:

- 저층부는 건폐율 한도까지 넓게 가능
- 상층부는 정북일조 사선 때문에 북측 edge가 깎임
- setback 때문에 도로 또는 인접대지 edge에서 일정 거리 후퇴
- 높이제한 때문에 층수 제한

이 구조 때문에 “하나의 footprint를 높이로 extrude”하는 방식은 부족하다. ARR은 floor별 buildable plate stack을 중심으로 발전해야 한다.

### 10.3 Agent Review

현재 agent review는 deterministic contract 형태로 시작했다. 이는 연구 초기 단계에서 LLM hallucination을 줄이기 위한 선택이다.

agent 역할:

- geometry_agent: geometry operation과 repair 결과 설명
- law_agent: 법규 constraint 통과/위반 검토
- optimization_agent: FAR/BCR/height 효율 평가
- review_agent: 사용자가 이해할 수 있는 요약 판단

추후에는 각 agent를 실제 LLM 또는 tool-using agent로 대체할 수 있다. 단, 법규 적합성 판단은 LLM 단독이 아니라 deterministic validator가 우선해야 한다.

## 11. 검증 상태

최근 검증 기준:

- Django backend `design` test: 194 tests OK
- Frontend TypeScript check: `npm run type-check` OK
- Frontend production build: Vite web/main/preload OK
- Electron packaging: 진행 확인 필요 또는 별도 CI에서 반복 검증 권장
- Playwright browser verification:
  - Chromium DOM load OK
  - Chromium screenshot은 환경 문제로 timeout 발생
  - Firefox Playwright screenshot OK
  - console errors 0
  - page errors 0
  - 4xx/5xx responses 0

로컬 개발 서버:

- FastAPI/Eigent server: `http://127.0.0.1:3001`
- Vite frontend: `http://127.0.0.1:5195`

## 12. 현재 한계와 향후 연구 과제

현재 ARR은 상용화 최종본이라기보다는 연구개발형 prototype에서 product-grade system으로 넘어가는 단계다.

남은 핵심 과제:

1. 정밀한 법규 해석
   실제 인허가 수준에서는 조례, 용도지역, 지구단위계획, 도로 사선, 일조, 대지안의 공지 등 다양한 조건이 결합된다. ARR은 이들을 데이터화하고 constraint graph로 관리해야 한다.

2. Robust geometry kernel
   현재 direct manipulation은 초기 수준의 polygon offset/scale/trim이다. 상용 수준의 SketchUp-like push/pull을 위해서는 더 강한 BRep 또는 mesh operation layer가 필요하다.

3. 최적화 알고리즘 고도화
   단순 greedy/floor clipping을 넘어 simulated annealing, evolutionary search, constraint programming, differentiable geometry optimization 등을 비교할 수 있다.

4. Multi-agent collaboration
   agent가 단순 설명자가 아니라, 법규 검토, 대안 생성, 수익성 판단, 설계 의도 반영, UI 조작 제안을 나눠 수행하는 구조로 확장해야 한다.

5. BIM/IFC 연계
   OpenSCAD는 mass 코드화에는 유용하지만 BIM은 아니다. 상용화를 위해서는 IFC, Speckle, Revit/Dynamo, BlenderBIM 등의 연계 가능성을 검토해야 한다.

6. PNU regression dataset
   여러 필지에 대해 법규 계산, mass generation, FAR/BCR optimization 결과를 저장하고 회귀 테스트해야 한다. 사용자가 지적한 PNU 혼동을 방지하기 위해 test fixture와 case naming이 중요하다.

## 13. 이력서/포트폴리오 설명 예시

ARR 프로젝트는 건축 법규, GIS, 3D geometry, AI agent orchestration을 결합한 초기 설계 자동화 시스템이다. 사용자가 필지를 선택하면 대지 형상과 법규 constraint를 기반으로 legal envelope를 계산하고, 그 안에서 건폐율과 용적률을 최대화하는 다양한 3D mass candidate를 생성한다. 기존 template 기반 매스 생성 방식을 seed/operator library로 재구성하고, MAAS-style legal mesh optimizer를 중심으로 floor-by-floor footprint clipping, setback repair, sunlight envelope validation, FAR/BCR scoring을 수행하도록 설계했다.

또한 사용자가 SketchUp처럼 mass를 push/pull하거나 edge offset을 수행하면, 시스템이 해당 geometry를 법규 envelope 안으로 repair하고, law/geometry/optimization/review agent가 결과를 구조화된 A2UI-style UI message로 설명한다. 이를 통해 단순 법규 검색이나 후처리 검토가 아니라, 법규 적합성과 설계 다양성을 동시에 만족하는 interactive AI-assisted massing workflow를 실험했다.

## 14. 한 줄 요약

ARR은 “토지 필지와 건축법규를 이해하는 AI-assisted legal massing system”이며, 목표는 법규를 위반하지 않는 범위에서 용적률과 건폐율을 최대화하는 다양한 3D 건축 매스를 생성하고, 사용자가 agent와 대화하며 직접 조작할 수 있는 설계 보조 플랫폼을 만드는 것이다.
