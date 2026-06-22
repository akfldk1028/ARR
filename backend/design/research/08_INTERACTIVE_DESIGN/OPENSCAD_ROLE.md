# OPENSCAD_ROLE — OpenSCAD의 역할과 한계

## 한 줄 결론

OpenSCAD는 BIM이 아니다. 우리 매스 생성기를 대체하지도 않는다.  
이 프로젝트에서 OpenSCAD는 **export / benchmark / mesh verification adapter**다.

## 할 수 있는 것

### 1. 매스 산출물 코드화

```text
mass_geojson + properties
→ final_mass.scad
```

예:

```scad
floor_height = 3.5;

module lower_mass() {
  linear_extrude(height = 28)
    polygon(points = [[0,0], [24,0], [24,18], [0,18]]);
}

module upper_mass() {
  translate([3, 2, 28])
    linear_extrude(height = 14)
      polygon(points = [[0,0], [18,0], [18,13], [0,13]]);
}

lower_mass();
upper_mass();
```

### 2. 최종 산출물 export

```text
.scad → .stl
.scad → .3mf
.scad → .png
```

### 3. LLM geometry benchmark

LLM에게 `.scad`를 만들게 하고, 우리 validator로 점수화한다.

```text
LLM-generated OpenSCAD
→ STL/mesh
→ footprint/height/volume extraction
→ FAR/BCR/sunlight/core validation
```

## 할 수 없는 것

- BIM 생성
- IFC property set 관리
- Revit/Archicad 대체
- 법규 엔진 대체
- Cesium 실시간 뷰어 대체
- 코어/평면 데이터의 source of truth 역할

## 우리 프로젝트에서의 정확한 위치

```text
                         ┌──────────────┐
                         │ OpenSCAD     │
                         │ export only  │
                         └──────▲───────┘
                                │
User ↔ Design Chat ↔ Patch ↔ mass_geojson ↔ Validator ↔ Cesium
                                │
                                ▼
                       final artifacts
```

## 리스크

### 리스크 1 — `.scad`가 원본처럼 취급됨

대응:

```text
DB/design result가 원본.
.scad/STL/3MF는 파생물.
```

### 리스크 2 — LLM이 `.scad`만 고쳐 법규와 불일치

대응:

```text
LLM 수정은 parameter patch로 환원.
validator pass한 결과만 export.
```

### 리스크 3 — 설치 의존성

대응:

```text
OpenSCAD CLI가 없어도 interactive design은 동작.
export만 unavailable 처리.
```

## 채택 기준

OpenSCAD 통합은 다음 중 하나 이상을 만족할 때만 유지한다.

1. 최종 설계 산출물 export 가치가 있다.
2. 교수님/고객 데모에서 "CAD 파일까지 나옴"이 설득력을 준다.
3. LLM geometry benchmark 실험에 재사용된다.
4. mesh 검증 단계에서 실제 오류를 잡는다.
