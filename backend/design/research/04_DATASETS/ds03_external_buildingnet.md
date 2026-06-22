# ds03 — 외부 공개 데이터셋 (Plan B)

**용도**: ds02 한국 데이터 확보 실패 시 fallback
**상태**: 후보 조사 단계

## 후보
1. **BuildingNet** (Selvaraju 2021) — 2k+ 건축 매스 mesh, 라벨 포함, 공개
2. **ShapeNet** (Stanford) — 51k+ 3D shape, 건축 부분만 추출
3. **KIT 건축 데이터** — 검토 필요
4. **Open3D Architecture** — 검토 필요

## Transfer Learning 전략
ds03으로 사전학습 → ds02 한국 데이터 100건 fine-tune (LoRA)

## 라이선스
- BuildingNet: CC BY-NC (학습 가능, 상업 사용 제한)
- ShapeNet: 학술 사용 허용

## 다음 행동
ds02 확보 가능성 결정 후 진행
