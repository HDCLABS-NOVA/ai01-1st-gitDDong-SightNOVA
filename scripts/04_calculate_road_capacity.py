import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent # <-- 추가

try:
    # ----------------------------------------------------------------------
    # 1. 데이터 불러오기 및 결합
    # ----------------------------------------------------------------------
    # 기본 데이터 로드 (전체 교통량 및 도로 정보)
    df_vol = pd.read_csv(PROJECT_ROOT / 'source/volume.csv', encoding='utf-8', skiprows=8, header=None) # 경로 수정

    # 버스/트럭 교통량 로드
    df_bus_truck = pd.read_csv(PROJECT_ROOT / 'source/BUSVolume(LINK).csv', encoding='utf-8', skiprows=8,
                               header=None)  # 경로 수정

    # 필요한 컬럼만 추출하여 df_analysis 생성
    info_cols_indices = [0, 2, 3, 5, 6]
    hourly_volume_cols_indices = list(range(8, 32))
    df_analysis = df_vol[info_cols_indices + hourly_volume_cols_indices].copy()
    info_col_names = ['LINK ID', '도로등급', '도로명', '연장(km)', '차선수']
    hourly_volume_col_names = [f'volume_{i}' for i in range(24)]
    df_analysis.columns = info_col_names + hourly_volume_col_names

    # 버스/트럭 데이터에서 일일 총량만 추출하여 결합
    df_heavy_vol = df_bus_truck[[0, 7, 32]].copy()  # LINK ID, 버스-전일, 트럭-전일
    df_heavy_vol.columns = ['LINK ID', 'Bus_Volume', 'Truck_Volume']

    # 메인 데이터프레임과 버스/트럭 데이터 결합
    df_analysis = pd.merge(df_analysis, df_heavy_vol, on='LINK ID')

    # 데이터 타입 변환 및 정리
    for col in df_analysis.columns:
        if col not in ['도로등급', '도로명']:
            df_analysis[col] = pd.to_numeric(df_analysis[col], errors='coerce')
    df_analysis.dropna(inplace=True)
    df_analysis['LINK ID'] = df_analysis['LINK ID'].astype(int)

    print("✅ 1. 데이터 불러오기 및 결합 완료")

    # ----------------------------------------------------------------------
    # 2. '최종 실질적 수용 능력' 계산
    # ----------------------------------------------------------------------
    volume_cols = [f'volume_{i}' for i in range(24)]
    # 일일 총 교통량은 시간별 교통량의 합으로 재계산하여 정확도 확보
    df_analysis['Total_Volume'] = df_analysis[volume_cols].sum(axis=1)

    # 1) 통계적 기준용량 (95th percentile) 계산
    df_analysis['Stat_Capacity'] = df_analysis[volume_cols].quantile(q=0.95, axis=1)

    # 2) 가중치 계산
    # W_length: 도로 길이 가중치
    avg_length = df_analysis['연장(km)'].mean()
    df_analysis['W_length'] = df_analysis['연장(km)'] / avg_length

    # W_lanes: 도로명 그룹별 차선 가중치
    avg_lanes_by_road = df_analysis.groupby('도로명')['차선수'].transform('mean')
    df_analysis['W_lanes'] = df_analysis['차선수'] / avg_lanes_by_road

    # W_class: 도로 등급 가중치
    class_weights = {'고속도로': 1.5, '도시고속도로': 1.5, '일반국도': 1.2, '특별광역시도': 1.2, '국가지원지방도': 1.0, '지방도': 1.0, '시군도': 1.0,
                     '연결로': 1.0}
    df_analysis['W_class'] = df_analysis['도로등급'].map(class_weights).fillna(1.0)

    # W_heavy: 중차량 보정계수 (수정된 최종 공식 적용)
    # PCE(승용차 환산계수)는 일반적으로 2.0을 사용
    PCE = 2.0
    df_analysis['P_heavy'] = (df_analysis['Bus_Volume'] + df_analysis['Truck_Volume']) / df_analysis['Total_Volume']
    df_analysis['W_heavy'] = 1 / (1 + df_analysis['P_heavy'] * (PCE - 1))
    # 중차량 비율이 100%여도 수용능력이 0이 되지 않도록 보정
    df_analysis.fillna({'W_heavy': 1.0}, inplace=True)  # Total_Volume이 0일 경우 NaN이 될 수 있으므로 1.0으로 대체

    # 3) 최종 실질적 수용 능력 계산 (모든 가중치 곱하기)
    df_analysis['Final_Capacity'] = df_analysis['Stat_Capacity'] * df_analysis['W_length'] * df_analysis['W_lanes'] * \
                                    df_analysis['W_class'] * df_analysis['W_heavy']

    # 수용 능력이 0이 되는 경우를 방지
    df_analysis['Final_Capacity'] = df_analysis['Final_Capacity'].replace(0, np.nan)
    df_analysis.dropna(subset=['Final_Capacity'], inplace=True)

    print("✅ 2. '최종 실질적 수용 능력' 계산 완료")

    # ----------------------------------------------------------------------
    # 3. 시간당 최종 혼잡도 계산 및 파일 저장
    # ----------------------------------------------------------------------
    final_congestion_cols = []
    for i in range(24):
        final_col_name = f'Final_Congestion_Hour_{i}'
        df_analysis[final_col_name] = df_analysis[f'volume_{i}'] / df_analysis['Final_Capacity']
        final_congestion_cols.append(final_col_name)

    # 최종 결과 CSV 파일로 저장
    df_final_result = df_analysis[['LINK ID'] + final_congestion_cols]
    output_filename = PROJECT_ROOT / 'data/ultimate_final-final_hourly_congestion.csv'  # 경로 수정
    df_final_result.to_csv(output_filename, index=False, encoding='utf-8-sig')


    print("✅ 3. 시간당 최종 혼잡도 계산 완료")
    print(f"✅ 전체 결과가 '{output_filename}' 파일로 저장되었습니다.")
    print("\n[계산된 시간당 최종 혼잡도 데이터 샘플]")
    print(df_final_result.head())
    all_data_filename = PROJECT_ROOT / 'data/all_traffic_data_for_simulation.csv' # 경로 수정
    df_analysis.to_csv(all_data_filename, index=False, encoding='utf-8-sig')
    print(f"\n✅ 시뮬레이션용 전체 데이터가 '{all_data_filename}' 파일로 저장되었습니다.")

except FileNotFoundError as e:
    print(f"오류: 파일을 찾을 수 없습니다. '{e.filename}' 파일이 스크립트와 같은 폴더에 있는지 확인해주세요.")
except Exception as e:
    print(f"데이터 처리 중 오류 발생: {e}")