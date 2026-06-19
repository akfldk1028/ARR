# MAAS Optimization Review

## 현재 코드 판단

현재 ARR massing은 10개 algorithm 이름을 갖고 있지만, 실제 구조는 다음에 가깝다.

```text
algorithm name
→ fixed builder function
→ fixed gene layout
→ Shapely footprint
→ optional repair
→ BCR/FAR/height/setback/daylight proxy evaluation
```

이 방식은 빠르고 안정적이지만, 다양성을 만들려면 builder를 계속 손으로 추가해야
한다. 그래서 "10종 노가다"라는 판단이 맞다.

## 법규 적합성의 현재 위치

- `views.job_stream()`은 `evaluate_designs(..., enable_repair=True)`를 사용한다.
- `repair_operator.py`가 site clip, setback clip, BCR clamp, FAR/height floor clamp를 수행한다.
- `mass_evaluator.py`는 repair 후 metrics를 계산하고, `Design.set_outputs()`가 constraint penalty를 계산한다.

즉 법규는 generation 안에 완전히 녹아 있다기보다는 **후처리 repair + penalty**
방식이다.

## 문제

1. 10개 builder는 서로 다른 generator가 아니라 template family에 가깝다.
2. repair가 geometry를 바꿔도 그 변경이 원래 gene으로 역전파되지 않는다.
3. stepback은 전 알고리즘 공통 global gene 2개뿐이라 다단 매스 표현력이 약하다.
4. `daylight_score`는 proxy라서 형태 다양성을 과대평가할 수 있다.
5. MAAS verb sequence는 아직 optimizer genome에 없다.

## 목표 구조

```text
seed candidate
→ legal base repair
→ MAAS morphology operators
→ repair/evaluate
→ diversity-aware selection
→ user interactive preview
```

## 우선 구현할 operator

법규 위반 위험이 낮은 순서:

- `notch`: 일부 corner/edge를 빼서 BCR/FAR를 줄임
- `cave`: courtyard/void를 만들어 채광 proxy와 다양성 증가
- `taper`: 상층 footprint를 줄여 일조/스카이라인 대응
- `split/terrace`: 현재 2-tier stepback을 다단화
- `shift`: tower/core 상층 위치 이동, 단 site/envelope 재검증 필수

위험한 operator:

- `expand`, `stack`, `lift`, `extrude`: FAR/BCR/height를 키우므로 repair 전제 없이는 금지
- `twist`, `bend`: 시각적으로는 좋지만 법규 footprint/층별 면적 계산과 왕복 변환이 어려워 후순위

## 코드 위치 제안

```text
design/maas/
  morphology_operators.py   # mass_geojson/shapely -> variant geometries
  legal_mesh_optimizer.py   # operator 후보 생성 + repair/evaluate + diversity rerank
  diversity.py              # IoU/compactness/height/stepback diversity score
  geometry_exporter.py      # 현재 구현된 export, 후순위
```

첫 구현은 기존 optimizer를 갈아엎지 않고, Pareto 후보 위에 post-process로 붙이는 게 맞다.
