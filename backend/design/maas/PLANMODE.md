# PLANMODE — MAAS Integration

## 목표

교수님 피드백인 "사용자와 상호소통하면서 매스를 수정"하는 흐름을 유지하면서, MAAS/OpenSCAD는 최종 후보를 코드화하고 mesh로 내보내는 레이어로 붙인다.

정정: export가 핵심이 아니다. 이 폴더의 장기 목표는 **법규 feasible space 안에서
다양한 mass mesh를 생성하고 최적화하는 MAAS식 morphology layer**다. `.scad`
export는 확인/전달용 부가 기능이다.

## 현재 단계

M3-a: ARR `mass_geojson`을 OpenSCAD `.scad`로 변환한다. 이건 plumbing 단계다.

M3-b: MAAS verb 구조를 ARR geometry mutation operator로 바꾼다.

M3-c: mutation 결과를 ARR evaluator/repair/validator로 다시 통과시켜 legal candidate만 남긴다.

완료 조건:

- 선택된 mass candidate를 `linear_extrude()` 기반 SCAD로 변환
- stepback이 있으면 lower/upper mass를 분리 extrusion
- OpenSCAD CLI가 없어도 API는 SCAD 텍스트를 반환
- OpenSCAD CLI가 있으면 추후 STL/PNG를 생성할 수 있는 provider 준비

## 폴더 책임

```text
design/maas/
  __init__.py
  geometry_exporter.py    # ARR mass_geojson -> SCAD
  openscad_provider.py    # OpenSCAD binary discovery/render wrapper
  README.md
  PLANMODE.md
```

## 금지선

- MAAS를 ARR의 법규 엔진으로 쓰지 않는다.
- `.scad`를 설계 원본으로 취급하지 않는다.
- validator를 우회해서 사용자에게 "법규 통과"라고 말하지 않는다.
- `clone/MAAS`를 런타임 import path에 직접 걸지 않는다. 필요한 구조는 ARR 안에 명시적으로 가져온다.

## 다음 단계

1. `mass_evaluator.py`의 10 template builder를 대체하지 말고, 그 위에 morphology mutation layer를 추가한다.
2. safe verbs부터 geometry operator로 구현한다: `notch`, `cave`, `taper`, `split/terrace`, `shift`.
3. 각 operator 결과를 `repair_operator`와 `evaluate_designs(enable_repair=True)`로 재검증한다.
4. 다양성 metric을 추가한다: footprint IoU distance, compactness spread, stepback variation, height distribution.
5. `algorithm="all"`은 10종 병렬 노가다 모드로 남기고, 새 모드는 `algorithm="maas_morphology"` 또는 post-optimizer rerank로 붙인다.
6. `POST /design/maas/export-scad/` UI 연결은 후순위다.
