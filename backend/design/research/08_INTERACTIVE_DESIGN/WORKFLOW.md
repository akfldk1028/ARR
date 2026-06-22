# WORKFLOW — 사용자 상호작용 시나리오

## 시나리오 1 — Pareto 후보 선택 후 대화 수정

1. 사용자가 부지를 선택한다.
2. 시스템이 Pareto 후보 5개를 생성한다.
3. 사용자가 Cesium에서 `안 03 balanced`를 선택한다.
4. 사용자가 자연어로 말한다.

```text
이 안이 제일 괜찮은데 너무 박스 같아.
북측은 법규 때문에 어쩔 수 없으면 유지하고, 도로 쪽 저층부를 더 넓게 만들어줘.
```

5. 시스템은 요청을 분해한다.

```json
{
  "selected_design_id": 3,
  "preserve": ["north_sunlight_pass"],
  "change": ["road_side_podium"],
  "objective": "less_boxy",
  "risk": ["bcr", "far", "road_setback"]
}
```

6. Patch Agent가 후보 3개를 만든다.

```text
3A: 2층 포디움 + 상부 동일
3B: 3층 포디움 + 상부 8% 축소
3C: 도로측 1.5m 확장 + 코어 동측 이동
```

7. Validator Agent가 각 후보를 채점한다.

```text
3A pass: FAR -1.2%, BCR +3.1%, sunlight pass
3B pass: FAR -3.8%, BCR +4.5%, sunlight pass
3C fail: road setback violation
```

8. UI는 pass 후보만 비교 표시한다.
9. Explanation Agent가 변경 이유를 설명한다.

## 시나리오 2 — 법규 위반 요청을 안전하게 거절

사용자:

```text
용적률을 더 올려. 상층부 후퇴 없애도 돼.
```

Constraint Agent:

```text
상층부 후퇴 제거 시 정북일조 envelope 위반 가능성이 높음.
```

시스템 응답:

```text
상층부 후퇴를 완전히 없애는 안은 정북일조 기준을 위반합니다.
대신 9층 이상만 6% 확장하는 후보와, 8층부터 2단 후퇴로 완화하는 후보를 만들었습니다.
```

## 시나리오 3 — 최종 CAD export

1. 사용자가 최종안을 확정한다.
2. 시스템이 산출물을 만든다.

```text
final_design.json
final_mass.geojson
final_report.md
final_mass.scad
final_mass.stl
final_mass.3mf
```

3. OpenSCAD CLI가 없으면 `.scad`만 생성하고 export는 비활성화한다.

## 시나리오 4 — 교수님/심사용 비교 화면

UI 구성:

```text
왼쪽: 원안 Cesium
오른쪽: 수정안 Cesium
하단: FAR/BCR/height/daylight/core 비교표
우측: "왜 바뀌었는가" 설명
버튼: CAD export
```

핵심 메시지:

```text
사용자가 설계 의도를 말하면, AI가 법규를 깨지 않는 범위에서 대안을 만들고 즉시 비교한다.
```
