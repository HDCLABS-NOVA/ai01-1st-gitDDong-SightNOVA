
# data_loader.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import joblib


@st.cache_data
def load_data_and_model():
    """대시보드에 필요한 모든 데이터를 로드하고 전처리합니다. (수정된 버전)"""
    try:
        # 파일 경로
        apt_master_df = pd.read_csv("data/master_data_with_radius(3km).csv")
        hourly_congestion_df = pd.read_csv("data/all_traffic_data_for_simulation.csv")
        roads_gdf = gpd.read_file("data/seoul_roads_with_congestion.geojson")
        speed_model = joblib.load("model/speed_prediction_model.joblib")
        price_df = pd.read_csv("data/gu_average_price.csv")
        station_df = pd.read_csv("data/station_data_final_with_coords.csv")
        bus_df = pd.read_csv("data/bus_station_daily_avg_final.csv")
    except FileNotFoundError as e:
        st.error(f"오류: '{e.filename}' 파일을 찾을 수 없습니다. 모든 필수 파일이 올바른 경로에 있는지 확인해주세요.")
        return [None] * 8

    # --- [핵심 수정] ID 컬럼들의 데이터 타입을 '문자열'로 강제 통일 ---
    apt_master_df['LINK ID'] = apt_master_df['LINK ID'].astype(str)
    hourly_congestion_df['LINK ID'] = hourly_congestion_df['LINK ID'].astype(str)
    roads_gdf['level5.5_link_id'] = roads_gdf['level5.5_link_id'].astype(str)

    # --- 기존 데이터 전처리 ---
    price_df.rename(columns={'지역구': 'gu', '평균_평단가': 'price_per_pyeong'}, inplace=True)
    price_df['gu'] = price_df['gu'].str.strip()

    apt_master_df.dropna(subset=['address'], inplace=True)
    apt_master_df['gu'] = apt_master_df['address'].apply(
        lambda x: x.split()[1] if isinstance(x, str) and len(x.split()) > 1 else None)
    apt_master_df.dropna(subset=['gu'], inplace=True)
    unique_apts_df = apt_master_df.drop_duplicates(subset=['apt_name']).copy()

    # 지하철 데이터 전처리
    station_df.dropna(subset=['위도', '경도'], inplace=True)
    morning_cols_st = [col for col in station_df.columns if '승차일평균' in col and ('07-08' in col or '08-09' in col)]
    evening_cols_st = [col for col in station_df.columns if '하차일평균' in col and ('18-19' in col or '19-20' in col)]
    station_df['출근시간_승차평균'] = station_df[morning_cols_st].sum(axis=1)
    station_df['퇴근시간_하차평균'] = station_df[evening_cols_st].sum(axis=1)
    station_df['환승_가중치'] = station_df['호선명'].apply(lambda x: 1 + (x.count(',') * 0.25))

    # 버스 데이터 전처리
    bus_df.dropna(subset=['latitude', 'longitude'], inplace=True)
    morning_on_cols = ['7시승차일평균', '8시승차일평균']
    morning_off_cols = ['7시하차일평균', '8시하차일평균']
    evening_on_cols = ['18시승차일평균', '19시승차일평균']
    evening_off_cols = ['18시하차일평균', '19시하차일평균']

    for col in morning_on_cols + morning_off_cols + evening_on_cols + evening_off_cols:
        if col not in bus_df.columns:
            bus_df[col] = 0  # <-- 이 코드가 실행되었다는 것은 컬럼 이름이 일치하지 않는다는 의미입니다.

    bus_df['출근_승차'] = bus_df[morning_on_cols].sum(axis=1)
    bus_df['출근_하차'] = bus_df[morning_off_cols].sum(axis=1)
    bus_df['퇴근_승차'] = bus_df[evening_on_cols].sum(axis=1)
    bus_df['퇴근_하차'] = bus_df[evening_off_cols].sum(axis=1)
    bus_df['출근_활성도'] = bus_df['출근_승차'] + bus_df['출근_하차']
    bus_df['퇴근_활성도'] = bus_df['퇴근_승차'] + bus_df['퇴근_하차']

    return unique_apts_df, apt_master_df, hourly_congestion_df, roads_gdf, speed_model, price_df, station_df, bus_df