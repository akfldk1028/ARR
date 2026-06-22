# B1b — Surrogate 학습 절차

**기간**: 1주 | **학습**: ⚠️ 경량 (CPU, 분~시간)

## 절차
1. B1a 데이터 로드 (`ds01_self_generated_v1.parquet`)
2. 3 모델 학습 비교: GP, MLP, LightGBM
3. 5-fold CV → R² / MSE 측정
4. 최고 모델 선정 → `surrogate_v1.pkl` 저장
5. B2 BO에서 호출 인터페이스 노출

## 코드 (예정)
- `ARR/backend/design/services/surrogate_model.py`
- `train_surrogate(dataset_path, model_type='lightgbm')` 함수

## 검증
- R² > 0.85 (학계 표준)
- 5 targets 모두 균형 학습 (target별 R² 격차 < 0.1)

## 의존성
- scikit-learn (GP, MLP), lightgbm — `requirements.txt` 추가 필요
