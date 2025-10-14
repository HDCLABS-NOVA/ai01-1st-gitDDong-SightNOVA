import geopandas as gpd
import pandas as pd
import warnings
from pathlib import Path

warnings.filterwarnings('ignore', 'The Shapely GEOS version used')

def create_final_dataset_guaranteed():
    """
    데이터 비호환성 문제를 해결하고 100% 동작을 보장하기 위해,
    ID가 확실하게 일치하는 파일들만 사용하여 최종 결과물을 생성합니다.
    """
    PROJECT_ROOT = Path(__file__).resolve().parent.parent  # <-- 추가
    print("🚀 최종 데이터 생성 스크립트 (v9: 동작 보장 최종본)를 시작합니다...")

    # --- 1. 호환성이 검증된 파일만 로드 ---
    try:
        # Level 5.5 도로 데이터 (속성 + 기본 좌표)
        gdf_lv55 = gpd.read_file(PROJECT_ROOT / "source/seoul_link_lev5.5_2023.shp", encoding='cp949')  # 경로 수정
        # 혼잡도 데이터
        congestion_df = pd.read_csv(PROJECT_ROOT / "data/master_data_with_radius(3km).csv") # 경로 수정
        print("✅ 호환성이 검증된 2종류의 핵심 파일을 성공적으로 로드했습니다.")
    except Exception as e:
        print(f"❌ 파일 로드 중 오류 발생: {e}")
        return

    # --- 2. 두 데이터 결합 ---
    print("\n--- 2단계: 데이터 결합 ---")

    # [2-1] ID 컬럼명 및 타입 표준화
    gdf_lv55.rename(columns={'k_link_id': 'level5.5_link_id'}, inplace=True)
    congestion_df.rename(columns={'LINK ID': 'level5.5_link_id'}, inplace=True)
    gdf_lv55['level5.5_link_id'] = gdf_lv55['level5.5_link_id'].astype(int)
    congestion_df['level5.5_link_id'] = congestion_df['level5.5_link_id'].astype(int)

    # [2-2] 혼잡도 정보에서 필요한 컬럼만 추출 (중복 제거)
    # 하나의 도로 ID에 여러 아파트 정보가 연결되어 있을 수 있으므로, ID별로 중복을 제거합니다.
    congestion_attrs = congestion_df[['level5.5_link_id', 'avg_congestion']].drop_duplicates(subset=['level5.5_link_id'])
    print(f"  - [2-1] 고유한 혼잡도 정보 {len(congestion_attrs)}건 준비 완료.")

    # [2-3] Level 5.5 도로 데이터에 혼잡도 정보 결합 (inner join으로 양쪽에 모두 ID가 있는 데이터만 선택)
    final_gdf = pd.merge(gdf_lv55, congestion_attrs, on='level5.5_link_id', how='inner')
    final_gdf = gpd.GeoDataFrame(final_gdf, geometry='geometry')
    print(f"  - [2-2] 데이터 결합 완료.")

    # --- 3. 최종 결과 확인 및 저장 ---
    print("\n--- 최종 결과 ---")
    print(f"최종 파일의 컬럼 목록: {final_gdf.columns.tolist()}")
    print(f"🎉 최종 파일의 데이터 개수: {len(final_gdf)} 개")

    if len(final_gdf) > 0:
        final_gdf = final_gdf.to_crs(epsg=4326) # Folium 지도 표준 좌표계
        output_filename = PROJECT_ROOT / 'data/seoul_roads_with_congestion.geojson' # 경로 수정
        final_gdf.to_file(output_filename, driver='GeoJSON')
        print(f"\n🎉 모든 작업 완료! 최종 분석용 파일 '{output_filename}'이 생성되었습니다.")
    else:
        print("\n❌ 최종 데이터가 0개입니다. 두 핵심 파일 간에 공통된 ID가 없는 것으로 보입니다.")

if __name__ == '__main__':
    create_final_dataset_guaranteed()