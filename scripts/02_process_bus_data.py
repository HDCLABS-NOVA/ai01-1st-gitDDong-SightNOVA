import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent # <-- 추가
# 원본 파일명 리스트 (경로 없이 파일 이름만)
RAW_FILES = [
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(01월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(02월).csv",
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(03월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(04월).csv",
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(05월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(06월).csv",
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(07월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(08월).csv",
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(09월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(10월).csv",
    "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(11월).csv", "2023년_버스노선별_정류장별_시간대별_승하차_인원_정보(12월).csv"
]

# 리스트 컴프리헨션을 사용하여 'source/' 경로를 추가한 최종 리스트 생성
MONTHLY_FILES = [PROJECT_ROOT / "source" / f for f in RAW_FILES]
LOCATION_FILE = PROJECT_ROOT / "source/서울시 버스정류소 위치정보.csv" # 경로 수정
OUTPUT_FILE = PROJECT_ROOT / "data/bus_station_daily_avg_final.csv" # 경로 수정

DAYS_IN_YEAR = 365
GROUP_COL = '버스정류장ARS번호'

# --- 2. 데이터 처리 및 분석 ---
try:
    print("▶ 2023년 12개월치 승하차 데이터를 통합합니다...")
    dfs = []
    for file in MONTHLY_FILES:
        try:
            # ✅ FIX: dtype을 지정하여 DtypeWarning 해결 및 안정성 확보
            df = pd.read_csv(file, encoding='cp949', dtype={GROUP_COL: str})
            dfs.append(df)
        except FileNotFoundError:
            print(f"  - 경고: '{file}' 파일을 찾을 수 없어 건너뜁니다.")

    all_data = pd.concat(dfs, ignore_index=True)
    print("✅ 데이터 통합 완료.")

    print("\n▶ 연간 총 승객 수를 합산하고 '일평균' 값을 계산합니다...")
    passenger_cols = [col for col in all_data.columns if '총승객수' in col]
    all_data[passenger_cols] = all_data[passenger_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    df_yearly_total = all_data.groupby(GROUP_COL)[passenger_cols].sum()
    df_daily_avg = df_yearly_total / DAYS_IN_YEAR
    df_daily_avg.columns = [col.replace('총승객수', '일평균') for col in passenger_cols]
    df_daily_avg.reset_index(inplace=True)
    print("✅ '일평균' 계산 완료.")

    print("\n▶ 정류장 이름과 좌표 정보를 추가합니다...")
    station_names = all_data.groupby(GROUP_COL)['역명'].apply(
        lambda s: s.mode()[0] if not s.mode().empty else '이름없음').reset_index()

    # ✅ FIX: 위치 파일도 ARS번호를 str로 읽어오도록 수정
    df_location = pd.read_csv(LOCATION_FILE, encoding='cp949', dtype={'정류소번호': str})
    df_location = df_location[['정류소번호', 'Y좌표', 'X좌표']].rename(columns={
        '정류소번호': GROUP_COL, 'Y좌표': 'latitude', 'X좌표': 'longitude'
    })

    df_final = pd.merge(df_daily_avg, station_names, on=GROUP_COL, how='left')
    df_final = pd.merge(df_final, df_location, on=GROUP_COL, how='left')
    df_final.dropna(subset=['latitude', 'longitude'], inplace=True)
    print("✅ 이름 및 좌표 병합 완료.")

    ordered_cols = [GROUP_COL, '역명', 'latitude', 'longitude'] + [col for col in df_final.columns if '일평균' in col]
    df_final = df_final[ordered_cols]

    df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

    print(f"\n🎉 최종 파일 '{OUTPUT_FILE}' 생성이 완료되었습니다.")
    print("\n--- 최종 데이터 샘플 (상위 5개) ---")
    print(df_final.head())

except FileNotFoundError as e:
    # ✅ FIX: 어떤 파일이 없는지 명확하게 알려주도록 수정
    print(f"❗️ 처리 중 오류가 발생했습니다: '{e.filename}' 파일을 찾을 수 없습니다.")
    print("   스크립트와 동일한 폴더에 파일이 있는지, 파일 이름에 오타가 없는지 확인해주세요.")
except Exception as e:
    print(f"❗️ 처리 중 오류가 발생했습니다: {e}")