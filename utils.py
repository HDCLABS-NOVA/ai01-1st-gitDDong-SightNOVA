# utils.py
import pandas as pd
import numpy as np
from shapely.geometry import Point


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Haversine 공식을 사용하여 두 위경도 좌표 간의 거리를 미터(m) 단위로 계산합니다.
    (lat1, lon1: 기준 위치, lat2, lon2: 비교 위치)
    """
    R = 6371000  # 지구의 평균 반경 (미터)

    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distance_m = R * c
    return distance_m

def find_nearest_road(roads_gdf, lat, lng):
    """클릭 위치에서 가장 가까운 도로의 ID를 찾습니다."""
    if roads_gdf is None or roads_gdf.empty: return None
    try:
        clicked_point = Point(lng, lat)
        return str(roads_gdf.loc[roads_gdf.geometry.distance(clicked_point).idxmin()]['level5.5_link_id'])
    except Exception:
        return None

def get_color_by_congestion(congestion):
    """혼잡도에 따라 색상을 반환합니다."""
    if pd.isna(congestion): return 'gray'
    if congestion < 0.3: return 'green'
    elif congestion < 0.6: return 'yellow'
    elif congestion < 0.8: return 'orange'
    else: return 'red'

def format_time_label(minutes_float):
    """분(float)을 'X분 Y초' 형태의 문자열로 변환합니다."""
    if pd.isna(minutes_float) or minutes_float < 0: return "N/A"
    minutes = int(minutes_float)
    seconds = int(round((minutes_float - minutes) * 60))
    if seconds == 60: minutes += 1; seconds = 0
    return f"{minutes}분 {seconds:02d}초"

def get_price_from_data(price_df, gu):
    """해당 구의 평균 평당 시세를 반환합니다."""
    filtered_price = price_df[price_df['gu'] == gu]
    return filtered_price['price_per_pyeong'].iloc[0] / 10000 if not filtered_price.empty else price_df['price_per_pyeong'].mean() / 10000

def find_nearest_facility(facility_df, apt_lat, apt_lon, lat_col='위도', lon_col='경도'):
    """아파트 위치에서 가장 가까운 시설(지하철역 등) 정보를 찾습니다."""
    lat_diff = facility_df[lat_col] - apt_lat
    lon_diff = facility_df[lon_col] - apt_lon
    distances_m = np.sqrt((lat_diff * 111000)**2 + (lon_diff * 88800)**2)
    nearest_idx = distances_m.idxmin()
    distance_km = distances_m.min() / 1000
    return facility_df.loc[nearest_idx], distance_km

def get_los_grade(congestion):
    """혼잡도에 따라 서비스 수준(LOS) 등급을 반환합니다."""
    grades = {'A (원활)': 0.3, 'B (양호)': 0.5, 'C (보통)': 0.7, 'D (서행)': 0.85, 'E (정체)': 1.0}
    for grade, threshold in grades.items():
        if congestion <= threshold:
            return grade
    return 'F (통행 불능)'

def normalize(val, min_val, max_val):
    """값을 0과 1 사이로 정규화합니다."""
    return 0.5 if max_val - min_val < 1e-6 else (val - min_val) / (max_val - min_val)