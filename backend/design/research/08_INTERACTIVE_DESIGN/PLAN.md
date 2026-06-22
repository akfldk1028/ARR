# PLAN — 상호소통형 매스 설계 루프

## 1. 문제 정의

현재 시스템은 자동 생성에는 강하지만, 사용자가 설계 의도를 직접 반영하는 루프가 약하다.

현재 흐름:

```text
PNU/VWorld/법규
→ optimizer
→ mass_geojson
→ Cesium 3D 표시
→ 코어/평면/설명
```

개선 목표:

```text
생성된 매스
→ 사용자가 자연어로 수정 요청
→ 시스템이 안전한 파라미터 patch로 변환
→ 법규/면적/일조 재검증
→ 화면에서 즉시 비교
```

## 2. 핵심 원칙

### Source of truth

OpenSCAD나 STL이 원본이 되면 안 된다. 원본은 계속 다음 데이터다.

```text
site polygon
regulation constraints
mass inputs
mass_geojson
evaluator metrics
core plan
```

OpenSCAD는 파생 산출물이다.

```text
mass_geojson → .scad → STL/3MF/PNG
```

### Validator gate

LLM/agent가 어떤 수정안을 내더라도 최종 채택은 validator가 결정한다.

```text
Agent proposal
→ parameter patch
→ rebuild mass
→ regulation_validator / sunlight envelope / BCR / FAR
→ pass only
```

### Direct `.scad` editing is secondary

LLM이 `.scad`만 직접 고치면 DB의 설계 파라미터, GeoJSON, 법규 지표와 불일치가 생긴다. 따라서 우선순위는 다음과 같다.

1. 자연어 → mass parameter patch
2. patch → 기존 evaluator 재실행
3. pass한 결과만 OpenSCAD export

## 3. Agent 구조

```text
Design Chat Agent
  사용자 발화를 intent로 정규화

Constraint Agent
  깨면 안 되는 법규/제약을 요약

Patch Agent
  mass inputs 또는 typology parameter 변경안 생성

Validator Agent
  FAR/BCR/height/setback/sunlight/core 검증

Critic Agent
  매스 형태와 사용자 요구의 정성 평가

Explanation Agent
  왜 바뀌었는지 한국어 설명

Export Agent
  필요할 때 OpenSCAD/STL/3MF 생성
```

## 4. 사용자 요청을 patch로 바꾸는 예

### 예 A — 상부 후퇴 부드럽게

사용자:

```text
북측 일조 때문에 꺾인 부분이 너무 딱딱해. 4단으로 자연스럽게 후퇴시켜봐.
용적률은 5% 이상 잃으면 안 돼.
```

Patch:

```json
{
  "intent": "smooth_stepback",
  "target_side": "north",
  "num_steps": 4,
  "max_far_loss_pct": 5,
  "constraints": ["north_sunlight", "far"]
}
```

### 예 B — 저층부 강화

사용자:

```text
도로 쪽 저층부가 너무 약해. 포디움처럼 3층까지는 더 넓게 잡아줘.
```

Patch:

```json
{
  "intent": "strengthen_podium",
  "target_side": "road",
  "podium_floors": 3,
  "podium_scale_delta": 0.12,
  "constraints": ["bcr", "road_setback", "far"]
}
```

### 예 C — 코어 위치 수정

사용자:

```text
코어가 가운데 있어서 평면이 답답해. 동측으로 붙여봐.
```

Patch:

```json
{
  "intent": "move_core",
  "target": "east",
  "preserve_escape_distance_m": 30,
  "constraints": ["inside_footprint", "egress_distance"]
}
```

## 5. OpenSCAD가 들어가는 위치

OpenSCAD는 실시간 수정 루프의 중심이 아니다. 다음 세 경우에 쓴다.

1. 최종 후보를 `.scad/.stl/.3mf`로 export
2. 외부 벤치마크 또는 교수님 데모용 재현 산출물 생성
3. LLM CAD-code benchmark를 만들 때 공통 형상 언어로 사용

## 6. 성공 기준

- 사용자가 자연어 요청을 입력하면 1개 이상의 안전한 patch 후보가 나온다.
- 각 후보는 법규 재검증 결과와 함께 표시된다.
- 원안/수정안의 FAR/BCR/일조/코어 차이가 설명된다.
- OpenSCAD export는 선택 사항이며, export 실패가 설계 루프를 막지 않는다.
