import pandas as pd
import numpy as np
from pathlib import Path # <-- 이 줄을 추가

# 1. 프로젝트 루트 경로를 계산 (경로 오류 방지)
# 스크립트가 scripts/ 폴더에 있다고 가정
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. 입력 파일 이름의 불일치 문제 해결
# (파일명에 '(1)'이 붙어있는 경우로 가정하고 코드를 작성합니다. 실제 파일명과 반드시 일치해야 합니다.)
RAW_INPUT_FILENAME = '서울시 공동주택 아파트 정보.csv'

# 3. Pathlib을 사용하여 경로와 파일명을 안전하게 결합
source_file = PROJECT_ROOT / 'source' / RAW_INPUT_FILENAME
output_file = PROJECT_ROOT / 'data' / 'seoul_old_apartments_corrected.csv'

print(f">>> '{source_file}' 파일에서 재건축 후보 아파트 필터링 및 세대수 보정을 시작합니다.")

try:
    # 1. 원본 데이터 불러오기
    df = pd.read_csv(source_file, encoding='cp949')
    print("✅ 1. 원본 데이터 불러오기 완료")

    # 2. 분석에 필요한 컬럼 선택 및 이름 변경
    # ★★★ 원인 2: 실제 파일의 컬럼명과 코드의 컬럼명이 미세하게 달랐던 문제 수정 ★★★
    required_cols = {
        'k-아파트명': 'apt_name',
        # 'k-단지분류(아파트,주상복합등등)' -> 실제 파일에는 따옴표가 포함되어 있음
        'k-단지분류(아파트,주상복합등등)': 'apt_type',
        'kapt도로명주소': 'address',
        'k-사용검사일-사용승인일': 'build_date',
        'k-전체세대수': 'total_households',
        'k-연면적': 'total_floor_area',
        'k-전용면적별세대현황(60㎡이하)': 'hh_under_60',
        'k-전용면적별세대현황(60㎡~85㎡이하)': 'hh_60_to_85',
        'k-85㎡~135㎡이하': 'hh_85_to_135',
        '좌표Y': 'latitude',
        '좌표X': 'longitude'
    }
    # 안전장치: 코드 실행 전 파일에 필요한 컬럼이 모두 있는지 확인
    for col in required_cols.keys():
        if col not in df.columns:
            # 실제 파일에 있는 컬럼 목록을 보여주어 디버깅을 도움
            print("\n[실제 파일에 있는 컬럼 목록]")
            print(list(df.columns))
            raise KeyError(f"원본 CSV 파일에 '{col}' 컬럼이 없습니다. 위 목록과 비교해주세요.")

    df_filtered = df[list(required_cols.keys())].copy()
    df_filtered.rename(columns=required_cols, inplace=True)

    print("✅ 2. 필요 컬럼 선택 및 이름 변경 완료")

    # 3. 데이터 필터링 (이하 로직은 모두 정상)
    df_filtered = df_filtered[df_filtered['apt_type'] == '아파트'].copy()
    df_filtered['build_year'] = pd.to_datetime(df_filtered['build_date'], errors='coerce').dt.year
    df_filtered.dropna(subset=['build_year'], inplace=True)
    df_filtered['build_year'] = df_filtered['build_year'].astype(int)
    df_filtered = df_filtered[df_filtered['build_year'] <= 1995]
    df_filtered.dropna(subset=['latitude', 'longitude'], inplace=True)
    df_filtered = df_filtered[(df_filtered['latitude'] != 0) & (df_filtered['longitude'] != 0)]
    df_filtered = df_filtered[df_filtered['total_households'] >= 100]

    print("✅ 3. 모든 필터링 완료")

    # 4. '135㎡ 초과' 세대수 역산
    partial_household_cols = ['hh_under_60', 'hh_60_to_85', 'hh_85_to_135']
    for col in partial_household_cols:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)
    known_hh_sum = df_filtered[partial_household_cols].sum(axis=1)
    df_filtered['hh_over_135'] = (df_filtered['total_households'] - known_hh_sum).clip(lower=0)
    print("✅ 4. '135㎡ 초과' 세대수 역산 및 보정 완료")

    # 5. 최종 비율 계산
    total_households = df_filtered['total_households'].replace(0, np.nan)
    df_filtered['prop_under_60'] = (df_filtered['hh_under_60'] / total_households * 100).round(1)
    df_filtered['prop_60_to_85'] = (df_filtered['hh_60_to_85'] / total_households * 100).round(1)
    df_filtered['prop_85_to_135'] = (df_filtered['hh_85_to_135'] / total_households * 100).round(1)
    df_filtered['prop_over_135'] = (df_filtered['hh_over_135'] / total_households * 100).round(1)
    print("✅ 5. 최종 평형별 세대수 비율 계산 완료")

    # 6. 최종 결과 저장
    final_cols = [
        'apt_name', 'address', 'build_year', 'total_households', 'total_floor_area',
        'prop_under_60', 'prop_60_to_85', 'prop_85_to_135', 'prop_over_135',
        'latitude', 'longitude'
    ]
    df_final = df_filtered[final_cols]
    df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 최종 보정된 결과가 '{output_file}' 파일로 저장되었습니다.")
    print("\n[최종 데이터 샘플]")
    print(df_final.head())


except FileNotFoundError:
    print(f"\n[오류] 원본 파일('{source_file}')을 찾을 수 없습니다. 파일 이름을 확인해주세요.")
except KeyError as e:
    print(f"\n[오류] 원본 CSV 파일에서 필요한 컬럼을 찾을 수 없습니다: {e}")
except Exception as e:
    print(f"\n[오류] 데이터 처리 중 문제가 발생했습니다: {e}")