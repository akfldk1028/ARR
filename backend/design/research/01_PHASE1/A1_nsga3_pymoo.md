# A1 — NSGA-III (pymoo 통합)

**기간**: 1주
**학습**: ❌
**효과**: ★★★★ / 비용: ★ / **ROI 4.0**

## 목적

목적함수가 4개 이상인 many-objective 문제(면적·일조·이격·조경·동선·경관…)에서 NSGA-II는 다양성을 잃는다. NSGA-III는 *reference point* 기반 선택으로 4-15개 목적함수까지 안정.

## 작업

### 코드 변경 위치
- `ARR/backend/design/engine/objects.py` — `NSGA3Job` 클래스 신규 (기존 `Job`/`SSIEAJob` 옆)
- `ARR/backend/requirements.txt` — `pymoo>=0.6` 추가

### 구현 흐름
```python
# objects.py 추가
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.util.ref_dirs import get_reference_directions

class NSGA3Job:
    def __init__(self, job_spec):
        n_obj = len(job_spec.get('objectives', []))
        self.ref_dirs = get_reference_directions("das-dennis", n_obj, n_partitions=12)
        self.algorithm = NSGA3(pop_size=75, ref_dirs=self.ref_dirs)
```

### 인터페이스
- 기존 `Job.step(evaluate_fn)` 시그니처와 호환
- `views.py` 에서 algorithm 옵션으로 선택 가능

## 검증

- `tests.py` 에 NSGA-III 단위 테스트 추가
- `05_EXPERIMENTS/exp002_nsga3_vs_nsga2.md` 실험 결과 기록
- 동일 부지에서 NSGA-II 대비 hypervolume 향상 확인

## 참고

- Deb, K., & Jain, H. (2014). NSGA-III. IEEE Transactions on Evolutionary Computation
- Zhao+ 2022 *Applied Energy* — dormitory daylight optimization NSGA-III +41% 검증
- pymoo 라이브러리: https://pymoo.org
