# 'thefuzz' 라이브러리가 없다면 먼저 설치해야 합니다.
# 터미널이나 명령 프롬프트에서 아래 명령어를 실행해주세요.
# pip install thefuzz python-Levenshtein
import pandas as pd
from thefuzz import process
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent # <-- 추가
# --- 설정 ---
passengers_raw_file = PROJECT_ROOT / 'source/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv' # 경로 수정
station_master_file = PROJECT_ROOT / 'source/서울시 역사마스터 정보.csv' # 경로 수정
output_file = PROJECT_ROOT / 'data/station_data_final_with_coords.csv' # 경로 수정

DAYS_IN_MONTH = 30.5
SCORE_CUTOFF = 85
manual_mapping = {
    '총신대입구(이수)': '이수',
    '신촌(경의중앙선)': '신촌',
}

try:
    # --- 1. 원본 승하차 데이터를 읽고 '일 평균' 계산 ---
    print("1단계: 원본 승하차 데이터를 읽고 '일 평균' 인원을 계산합니다...")
    df_raw = pd.read_csv(passengers_raw_file, encoding='cp949')
    passenger_cols = [col for col in df_raw.columns if '승차' in col or '하차' in col]
    for col in passenger_cols:
        df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0)

    # ✅ 핵심 수정: '역명'과 '호선명'을 기준으로 먼저 월 평균을 구합니다.
    df_monthly_avg = df_raw.groupby(['호선명', '역사명'])[passenger_cols].mean().reset_index()

    for col in passenger_cols:
        df_monthly_avg[col] = df_monthly_avg[col] / DAYS_IN_MONTH
    print("✅ '일 평균' 계산 완료.")


    # --- 2. 역사 마스터 데이터 준비 ---
    print("\n2단계: 역사 마스터 데이터를 준비합니다...")
    df_master_raw = pd.read_csv(station_master_file, encoding='cp949')
    df_master = df_master_raw[['역사명', '위도', '경도']].drop_duplicates('역사명').copy()
    master_station_names = df_master['역사명'].tolist()
    print("✅ 마스터 데이터 준비 완료.")


    # --- 3. 유사도 기반으로 '공식 역사명' 매칭 ---
    print("\n3단계: 두 데이터의 역 이름을 매칭합니다...")
    def find_best_match(name, choices, mapping, cutoff):
        if name in mapping:
            return mapping[name]
        match = process.extractOne(name, choices, score_cutoff=cutoff)
        return match[0] if match else name # 매칭 실패 시 원본 이름 사용

    # '역명'을 기준으로 매칭된 이름을 새 컬럼에 추가
    df_monthly_avg['최종_역사명'] = df_monthly_avg['역사명'].apply(
        lambda x: find_best_match(x, master_station_names, manual_mapping, SCORE_CUTOFF)
    )
    print("✅ 이름 매칭 완료.")


    # --- 4. ✅ 핵심 수정: '최종_역사명'으로 환승역 데이터 최종 통합 ---
    print("\n4단계: 매칭된 '최종_역사명'을 기준으로 환승역 데이터를 통합합니다...")
    # 집계 규칙 정의 (승하차 인원은 합산, 호선명은 쉼표로 연결)
    agg_dict = {col: 'sum' for col in passenger_cols}
    agg_dict['호선명'] = lambda lines: ', '.join(sorted(lines.unique()))

    # '최종_역사명'을 기준으로 그룹화하여 합산
    df_final_passengers = df_monthly_avg.groupby('최종_역사명').agg(agg_dict).reset_index()
    print("✅ 환승역 통합 완료.")


    # --- 5. 최종 좌표 병합 및 저장 ---
    print("\n5단계: 최종 데이터에 좌표를 병합하고 저장합니다...")
    df_final = pd.merge(
        df_final_passengers,
        df_master,
        left_on='최종_역사명',
        right_on='역사명',
        how='left'
    )
    df_final.drop(columns=['역사명'], inplace=True, errors='ignore')

    # 컬럼명 정리
    new_column_names = {col: col.replace('인원', '일평균').replace('시-', '-') for col in passenger_cols}
    df_final.rename(columns=new_column_names, inplace=True)

    df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n🎉 최종 통합 파일 '{output_file}'을 성공적으로 생성했습니다.")
    print("최종 데이터의 샘플은 다음과 같습니다:")
    print(df_final.head())

except FileNotFoundError as e:
    print(f"❗️ 오류: 필요한 파일을 찾을 수 없습니다 - {e.filename}")
except Exception as e:
    print(f"❗️ 오류가 발생했습니다: {e}")