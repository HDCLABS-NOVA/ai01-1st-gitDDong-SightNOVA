import pandas as pd
from pathlib import Path


def prepare_ml_training_data_fixed():
    """
    (수정) 속도 데이터의 타입을 숫자로 명확하게 변환하여
    머신러닝 학습에 적합한 최종 데이터셋을 생성합니다.
    """
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    print("🚀 1단계 (수정): AI 학습용 데이터 생성을 시작합니다...")

    try:
        df_congestion = pd.read_csv(PROJECT_ROOT / "data/ultimate_final-final_hourly_congestion.csv")
        df_speed = pd.read_csv(PROJECT_ROOT / "source/AverageSpeed(LINK).csv")
        print("✅ 2개의 소스 데이터를 성공적으로 로드했습니다.")
    except FileNotFoundError as e:
        print(f"❌ 파일 로드 실패: '{e.filename}' 파일을 찾을 수 없습니다.")
        return

    # --- 2. 데이터 정제 및 재구성 ---
    print("⏳ 데이터를 정제하고 AI가 학습하기 좋은 형태로 재구성합니다...")

    # [2-1] 혼잡도 데이터 재구성 (이전과 동일)
    congestion_long = pd.melt(
        df_congestion,
        id_vars=['LINK ID'],
        value_vars=[f'Final_Congestion_Hour_{i}' for i in range(24)],
        var_name='hour_str',
        value_name='congestion'
    )
    congestion_long['hour'] = congestion_long['hour_str'].str.extract(r'(\d+)').astype(int)
    congestion_long.drop(columns='hour_str', inplace=True)

    # [2-2] 속도 데이터 정제 및 재구성
    speed_time_cols = [f'{i}~{i + 1}시' for i in range(24)]
    df_speed.rename(columns={'5.5 LINK ID': 'LINK ID'}, inplace=True)

    # (✨ 핵심 수정!) 속도 컬럼들을 강제로 숫자 타입으로 변환합니다.
    # 변환할 수 없는 값(예: 텍스트)은 NaN(결측치)으로 처리됩니다.
    for col in speed_time_cols:
        df_speed[col] = pd.to_numeric(df_speed[col], errors='coerce')

    speed_long = pd.melt(
        df_speed,
        id_vars=['LINK ID'],
        value_vars=speed_time_cols,
        var_name='hour_str',
        value_name='speed'
    )
    speed_long['hour'] = speed_long['hour_str'].str.extract(r'^(\d+)').astype(int)
    speed_long.drop(columns='hour_str', inplace=True)

    print("✅ 데이터 정제 및 재구성 완료.")

    # --- 3. 최종 데이터 결합 및 저장 ---
    print("⏳ 재구성된 두 데이터를 최종 결합합니다...")

    df_final_ml = pd.merge(congestion_long, speed_long, on=['LINK ID', 'hour'])
    df_final_ml.dropna(inplace=True)  # speed가 NaN인 행들이 여기서 제거됩니다.
    df_final_ml['LINK ID'] = df_final_ml['LINK ID'].astype(int)

    output_filename = PROJECT_ROOT / 'data/ml_training_data.csv' # 경로 수정
    df_final_ml.to_csv(output_filename, index=False, encoding='utf-8-sig')

    print(f"\n🎉 1단계 성공! AI 학습용 문제집 '{output_filename}'이 생성되었습니다.")
    print(f"  - 총 {len(df_final_ml)}개의 학습 데이터가 준비되었습니다.")
    print("\n[생성된 데이터 샘플]")
    print(df_final_ml.head())


if __name__ == '__main__':
    prepare_ml_training_data_fixed()