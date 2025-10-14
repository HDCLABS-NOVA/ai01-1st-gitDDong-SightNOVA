import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# --- [설정] 파일 경로 ---
apartments_file = PROJECT_ROOT / 'data/seoul_old_apartments_corrected.csv' # 경로 수정
road_network_shapefile = PROJECT_ROOT / 'source/road_network.shp' # 경로 수정
congestion_file = PROJECT_ROOT / 'data/ultimate_final-final_hourly_congestion.csv' # 경로 수정
output_master_file = PROJECT_ROOT / 'data/master_data_with_radius(3km).csv'  # 경로 수정

print(">>> [Phase 1] '마스터 데이터' 생성을 시작합니다. (반경 5km 분석)")

try:
    # ----------------------------------------------------------------------
    # 1. 아파트 및 혼잡도 데이터 불러오기
    # ----------------------------------------------------------------------
    df_apartments = pd.read_csv(apartments_file)
    df_congestion = pd.read_csv(congestion_file)

    hourly_cols = [col for col in df_congestion.columns if 'Final_Congestion_Hour_' in col]
    df_congestion['avg_congestion'] = df_congestion[hourly_cols].mean(axis=1)
    df_congestion_final = df_congestion[['LINK ID', 'avg_congestion']]

    print("✅ 1. 아파트 및 혼잡도 데이터 불러오기 완료")

    # ----------------------------------------------------------------------
    # 2. 도로 네트워크 Shapefile 불러오기
    # ----------------------------------------------------------------------
    gdf_roads = gpd.read_file(road_network_shapefile)

    # 실제 LINK ID 컬럼명 'link_id' 적용
    ACTUAL_LINK_ID_COLUMN = 'k_link_id'

    if ACTUAL_LINK_ID_COLUMN not in gdf_roads.columns:
        raise KeyError(f"Shapefile에서 '{ACTUAL_LINK_ID_COLUMN}' 컬럼을 찾을 수 없습니다.")

    gdf_roads = gdf_roads[[ACTUAL_LINK_ID_COLUMN, 'geometry']]
    gdf_roads.rename(columns={ACTUAL_LINK_ID_COLUMN: 'LINK ID'}, inplace=True)

    print("✅ 2. 도로 네트워크 Shapefile 불러오기 완료")

    # ----------------------------------------------------------------------
    # 3. '공간 매칭': 반경 5km 내 모든 도로 찾기
    # ----------------------------------------------------------------------
    # 아파트 데이터를 GeoDataFrame으로 변환
    gdf_apartments = gpd.GeoDataFrame(
        df_apartments,
        geometry=gpd.points_from_xy(df_apartments.longitude, df_apartments.latitude),
        crs='EPSG:4326'  # WGS84
    )

    # 정확한 거리 계산을 위해 평면 좌표계(EPSG:5186)로 변환
    gdf_apartments_proj = gdf_apartments.to_crs('EPSG:5186')
    gdf_roads_proj = gdf_roads.to_crs('EPSG:5186')

    # ⭐️ [핵심 로직] 각 아파트 주변 3km(3000미터) 버퍼 생성
    gdf_apartments_proj['buffer_geometry'] = gdf_apartments_proj.geometry.buffer(3000)
    gdf_apartments_buffer = gdf_apartments_proj.set_geometry('buffer_geometry')

    # ⭐️ [핵심 로직] sjoin을 사용하여 버퍼와 교차(intersects)하는 모든 도로를 찾음
    gdf_master = gpd.sjoin(gdf_apartments_buffer, gdf_roads_proj, how='left', predicate='intersects')

    print("✅ 3. '공간 매칭'으로 반경 3km 내 모든 도로 연결 완료")

    # ----------------------------------------------------------------------
    # 4. 최종 데이터 결합 및 저장
    # ----------------------------------------------------------------------
    df_master_final = pd.merge(
        gdf_master,
        df_congestion_final,
        on='LINK ID',
        how='left'
    )

    # 불필요한 geometry 및 인덱스 컬럼 등 정리
    columns_to_drop = [col for col in ['geometry', 'buffer_geometry', 'index_right'] if col in df_master_final.columns]
    df_master_final = df_master_final.drop(columns=columns_to_drop)

    df_master_final.to_csv(output_master_file, index=False, encoding='utf-8-sig')

    print(f"\n🎉 [성공] 최종 '마스터 데이터'가 '{output_master_file}' 파일로 생성되었습니다!")
    print("\n[최종 마스터 데이터 샘플 (아파트별로 여러 행이 생성됨)]")
    print(df_master_final.head(10))  # 샘플을 10개 보여줘서 여러 행이 생성된 것을 확인


except FileNotFoundError as e:
    print(f"\n[오류] 필수 파일을 찾을 수 없습니다: {e.filename}")
except KeyError as e:
    print(f"\n[오류] 데이터에서 필요한 컬럼을 찾을 수 없습니다: {e}")
except Exception as e:
    print(f"\n[오류] 처리 중 문제가 발생했습니다: {e}")

