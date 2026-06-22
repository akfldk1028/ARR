# 04_DATASETS/data/

자가 생성 / 외부 데이터셋의 *실제 binary/json 파일* 저장 위치.

## 저장 정책
- `.gitignore` 로 *.json / *.parquet / *.csv 추적 X (용량)
- 본 `_README.md` + `.gitignore` 만 git 추적
- 실제 파일은 로컬에서만 생성 / 별도 백업 (B2 / NAS)

## 파일

| 파일 | 생성 스크립트 | 크기 | 용도 |
|---|---|---|---|
| ds01_self_generated_ga.json | `05_EXPERIMENTS/scripts/dataset_generation.py` | ~1-3MB (3000 sample) | B1 Surrogate 학습 |
| ds02_korean_buildings.json | (Phase 3 TBD) | TBD | C2 Diffusion prior |
| ds03_external_buildingnet.json | (Phase 3 TBD) | TBD | Plan B (해외 매스) |
| ds04_typology_labels.json | (Phase 2 TBD) | TBD | B5 Typology 분류기 |

## 재생성 절차
```bash
cd ARR/backend
DJANGO_SETTINGS_MODULE=backend.settings python -c "
import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
import django; django.setup()
import dataset_generation
dataset_generation.run(target_size=3000)
"
```
