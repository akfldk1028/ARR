# 실험 명명 규칙

## 파일 형식
- `expXXX_<short_name>.md` (예: `exp002_nsga3_vs_nsga2.md`)
- 모든 실험은 _LOG.md 에 한 줄로 등록

## .md 표준 양식
```markdown
# expXXX — 짧은 제목

**Date**: YYYY-MM-DD
**Phase**: 1/2/3
**작업 ID**: A1/B1/...
**부지**: 강남역삼677 / 분당XX / 춘천XX (3종)
**반복**: 5회

## 변경 사항
무엇을 바꿨는가 (1줄)

## 결과
| 지표 | Before | After | Δ |
|---|---|---|---|
| Hypervolume | 0.XX | 0.XX | +X% |
| Runtime (min) | XX | XX | -X% |

## 결론
2-3 문장. *변경이 효과 있었는가?* *다음 단계 필요한가?*

## 데이터
- raw: `data/expXXX_raw.parquet`
- script: `scripts/expXXX.py`
```

## 데이터 보관
- raw 데이터 (>10MB): gitignore, 별도 백업
- script: git 추적
- 결과 .md: git 추적
