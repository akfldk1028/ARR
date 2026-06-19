# ARR design/maas

이 폴더는 `clone/MAAS`의 쓸모 있는 구조만 ARR에 맞게 얇게 가져온 **MAAS legal-envelope generator**다.

역할은 명확히 제한한다. 핵심 목표는 export가 아니라 **법규에 맞는 다양한
mass mesh 후보를 만들고 최적화하는 것**이다. Export는 그 결과를 확인하거나
외부 도구로 넘기기 위한 부가 산출물이다.

```text
ARR law constraints / site polygon / sunlight envelope
→ design.maas.legal_envelope
→ design.maas.seed_library (legacy 10종은 seed/operator로만 사용)
→ design.maas morphology / mesh operators
→ ARR repair / validator 재검증
→ diverse legal mass candidates
→ optional OpenSCAD .scad/.stl/.png export
```

## 모듈 경계

- `legal_envelope.py`: 법규 constraint를 buildable/capacity boundary로 변환하는 중심 모듈
- `seed_library.py`: 기존 ARR 10종/선택 매스를 다양성 seed/operator library로 격하해 쓰는 모듈
- `morphology_operators.py`: notch, courtyard, stepback, bcr_fill 같은 형상 조작 모음
- `legal_mesh_optimizer.py`: 후보를 repair하고 BCR/FAR/height/sunlight 검증 후 랭킹하는 orchestrator
- `geometry_exporter.py`, `openscad_provider.py`: 결과 export adapter

## 가져온 MAAS 구조

- compiler-like pipeline: seed/operator → explicit geometry → validator 재검증
- provider separation: 생성/검증/렌더/export 분리
- `geometry_exporter.py`: MAAS `coma_render_samples.py`의 polygon extrusion 아이디어를 ARR `mass_geojson`에 맞춘 구현
- `openscad_provider.py`: MAAS `providers/openscad_provider.py`의 OpenSCAD CLI wrapper
- `PLANMODE.md`: 다음 AI가 이 기능을 이어받을 때 따라야 할 계획과 금지선

## 안 가져온 것

- MAAS neural/diffusion pipeline: ARR 법규형 massing의 원본 생성기로 쓰기엔 아직 맞지 않음
- MAAS verb grammar 전체: 나중에 morphology 후보 생성기로 붙일 수 있지만, 지금은 legal source of truth가 아님
- PNG 필수 렌더링: 사용자는 상호작용 중 즉시 결과를 봐야 하므로 `.scad` 생성은 가능해야 하고, OpenSCAD 렌더는 설치된 경우만 optional

## 원칙

`mass_geojson`이 원본이고 `.scad/.stl/.png`는 파생물이다. LLM이나 MAAS가 만든 geometry는 반드시 ARR evaluator/validator를 다시 통과해야 한다.

## 왜 필요한가

현재 ARR의 `mass_evaluator.py`는 10개 알고리즘을 제공하지만, 대부분은 사전에
정한 typology builder와 gene range 조합이다. 이 방식은 알고리즘 이름을 늘릴수록
후보가 늘어나는 구조라서 다양성이 "노가다식 template 추가"에 묶인다.

따라서 MAAS의 중심은 기존 10종 유지가 아니라 **법규 envelope 기반 generator**다.
기존 10종은 seed/operator library로 쓸 수는 있지만 용량 산정의 기준이 아니다.

MAAS 쪽에서 가져올 핵심은 OpenSCAD export가 아니라 다음 구조다.

- verb/morphology vocabulary: `cave`, `notch`, `taper`, `split`, `shift`, `pack`, `stack` 같은 조작 단위
- compiler-like pipeline: 조작 sequence를 명시적 geometry로 변환
- provider separation: 생성/검증/렌더를 분리

ARR에서는 이 구조를 `legal_envelope` + `legal morphology operators`로 바꿔야 한다.
