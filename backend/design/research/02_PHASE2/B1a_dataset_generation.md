# B1a — 자가 생성 데이터셋 ✅ DONE (2026-05-06)

**기간**: 2주 *예상이었으나 8.5초로 완료* | **학습**: ❌ (생성만) | 출력: **3000 매스 (Phase 2 진입)**

## 상태 (2026-05-06)

- ✅ **3000 sample 생성 완료** — `04_DATASETS/data/ds01_self_generated_ga.json`
- ✅ **99.97% feasible** (A6 repair on)
- ✅ **3 부지 균등 분포** (round-robin: 강남 1050 / 분당 1050 / 춘천 900)
- ✅ **8.5초 소요** (Radiance 비활성, geometric metric만)
- 스크립트: `05_EXPERIMENTS/scripts/dataset_generation.py`

⚠️ **Note**: Radiance UDI/sDA 는 *미포함* (exp005 BLOCKED). 현재 dataset은 *기하 metric only*. Radiance 활성화 후 v2 재생성 가능.

## 목적
B1 surrogate 학습용 데이터를 *외부 의존 없이 자가 생성*.

## 생성 흐름 (실행 완료)

1. SSIEAJob 5섬×15 + A6 repair on + A3 normalized
2. 3 부지 fixture round-robin (1 SSIEA run = 1050 designs)
3. 모든 design 의 gene_vector + outputs 수집
4. JSON 저장 (pandas dependency 없음)

## 데이터 형식

```json
{
  "metadata": { schema_version, generated_utc, target_size, actual_size, ... },
  "samples": [{
    "site_key": "gangnam_yeoksam_677",
    "site_area_m2": 2440.5,
    "site_bcr_limit": 80, "site_far_limit": 1300, "site_height_limit_m": 50,
    "gene_vector": [29 floats],
    "outputs": { floor_area, daylight_score, bcr, far, height,
                  min_setback, open_pct, compactness, stepback_factor },
    "feasible": true,
    "penalty": 0.0
  }, ...]
}
```

## 저장 위치
- `04_DATASETS/data/ds01_self_generated_ga.json` (1.86 MB, gitignore)
- `04_DATASETS/data/_README.md` 메타데이터
- 본 .md = 데이터셋 카드

## 다음 (B1b — Surrogate 학습)
- Input: gene_vector (29-D) + site context (3 limits)
- Output: outputs dict (floor_area / daylight / bcr / far 우선)
- 모델 후보: GP (sklearn.gaussian_process) / MLP (sklearn.neural_network) / LightGBM
- Train/test split: 2400/600 (80/20)

## 재생성

```bash
cd ARR/backend
DJANGO_SETTINGS_MODULE=backend.settings python -c "
import sys; sys.path.insert(0, 'design/research/05_EXPERIMENTS/scripts')
import django; django.setup()
import dataset_generation; dataset_generation.run(target_size=3000)
"
```
