import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import lightgbm as lgb
import joblib
import numpy as np
from pathlib import Path


def train_speed_prediction_model():
    """
    'ml_training_data.csv'를 사용하여 혼잡도와 도로 ID를 기반으로
    속도를 예측하는 LightGBM 모델을 훈련하고 저장합니다.
    """
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    print("🚀 2단계: AI 모델 훈련을 시작합니다...")

    try:
        # 1. AI 학습용 데이터 로드
        df_ml = pd.read_csv(PROJECT_ROOT / "data/ml_training_data.csv") # 경로 수정
        print(f"✅ 학습용 데이터 '{df_ml.shape[0]}'건 로드 완료.")
    except FileNotFoundError:
        print("❌ 'ml_training_data.csv' 파일을 찾을 수 없습니다. 1단계 스크립트를 먼저 실행해주세요.")
        return

    # --- 2. 학습 데이터 준비 ---
    print("⏳ 모델이 학습할 '문제(X)'와 '정답(y)'을 준비합니다...")

    # '문제(X)': AI에게 주어지는 정보 (혼잡도, 도로ID, 시간)
    # LINK ID를 카테고리형 데이터로 명확하게 지정해주는 것이 성능에 중요합니다.
    df_ml['LINK ID'] = df_ml['LINK ID'].astype('category')
    X = df_ml[['congestion', 'LINK ID', 'hour']]

    # '정답(y)': AI가 맞춰야 하는 값 (속도)
    y = df_ml['speed']

    # 학습용 데이터와 성능 평가용 데이터로 분리 (80% 학습, 20% 평가)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print("✅ 학습/평가 데이터 분리 완료.")

    # --- 3. LightGBM 모델 훈련 ---
    print("🏃‍♂️ AI가 데이터 패턴을 학습합니다... (시간이 다소 소요될 수 있습니다)")

    # LightGBM 모델 생성 및 설정
    lgbm = lgb.LGBMRegressor(
        objective='regression',  # 회귀(값 예측) 문제
        n_estimators=1000,  # 1000번의 학습 주기 (나무의 개수)
        learning_rate=0.05,  # 학습 속도
        num_leaves=31,  # 각 나무의 최대 잎사귀 수
        n_jobs=-1,  # 모든 CPU 코어 사용
        random_state=42
    )

    # 모델 훈련
    lgbm.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric='rmse',  # 평가 지표: Root Mean Squared Error
        callbacks=[lgb.early_stopping(100, verbose=False)]  # 100번 동안 성능 향상이 없으면 조기 종료
    )

    print("✅ AI 모델 훈련 완료!")

    # --- 4. 모델 성능 평가 ---
    print("\n--- [AI 모델 성능 평가] ---")
    predictions = lgbm.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)

    print(f"  - 예측 오차 (RMSE): 약 {rmse:.2f} km/h")
    print(f"  - 모델 설명력 (R²): {r2:.2%}")
    if r2 > 0.8:
        print("  - 평가: 훌륭합니다! 모델이 데이터의 패턴을 매우 잘 학습했습니다.")
    elif r2 > 0.6:
        print("  - 평가: 좋습니다. 모델이 데이터의 패턴을 양호하게 학습했습니다.")
    else:
        print("  - 평가: 보통입니다. 모델의 성능을 더 개선할 여지가 있습니다.")

    # --- 5. 훈련된 모델 저장 ---
    output_filename = PROJECT_ROOT / 'model/speed_prediction_model.joblib' # 경로 수정
    joblib.dump(lgbm, output_filename)

    print(f"\n🎉 2단계 성공! 훈련된 AI 모델이 '{output_filename}' 파일로 저장되었습니다.")
    print("이제 이 AI 모델을 대시보드에 탑재할 수 있습니다.")


if __name__ == '__main__':
    train_speed_prediction_model()