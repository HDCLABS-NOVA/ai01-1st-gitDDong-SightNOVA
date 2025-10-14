# analysis.py
import pandas as pd
import numpy as np
from shapely.geometry import Point
# [수정] utils.py에서 haversine_distance 함수를 가져오도록 업데이트
from utils import find_nearest_facility, get_los_grade, haversine_distance


def calculate_traffic_impact(apt_location, new_units, apt_info, master_data, hourly_congestion_df, roads_data, model):
    """도로 교통 영향을 시뮬레이션합니다."""
    VEHICLES_PER_UNIT = 0.8
    increase_in_units = new_units - apt_info['total_households']
    total_increase_in_vehicles = increase_in_units * VEHICLES_PER_UNIT

    surrounding_link_ids = master_data[master_data['apt_name'] == apt_info['apt_name']]['LINK ID'].unique()
    sim_df_hourly = hourly_congestion_df[hourly_congestion_df['LINK ID'].isin(surrounding_link_ids)].copy()

    if sim_df_hourly.empty:
        return pd.DataFrame()

    apartment_point = Point(apt_location['longitude'], apt_location['latitude'])
    surrounding_roads_gdf_sim = roads_data[roads_data['level5.5_link_id'].isin(surrounding_link_ids)].copy()
    surrounding_roads_gdf_sim['distance_from_apt'] = surrounding_roads_gdf_sim.geometry.distance(apartment_point)
    distance_df = surrounding_roads_gdf_sim[['level5.5_link_id', 'distance_from_apt']].rename(
        columns={'level5.5_link_id': 'LINK ID'})

    sim_df_hourly = pd.merge(sim_df_hourly, distance_df, on='LINK ID', how='left')
    sim_df_hourly['final_weight'] = 1 / (sim_df_hourly['distance_from_apt'] + 1e-5)
    total_weight_sum = sim_df_hourly['final_weight'].sum()
    sim_df_hourly['increase_in_vehicles_per_road'] = total_increase_in_vehicles * (
            sim_df_hourly['final_weight'] / total_weight_sum) if total_weight_sum > 0 else 0

    prediction_input_list = []
    volume_cols = [f'volume_{i}' for i in range(24)]

    for _, row in sim_df_hourly.iterrows():
        total_daily_volume = row[volume_cols].sum()
        if total_daily_volume == 0: continue

        hourly_traffic_ratio = row[volume_cols] / total_daily_volume
        increase_volume_per_hour = row['increase_in_vehicles_per_road'] * hourly_traffic_ratio

        for hour in range(24):
            old_volume, final_capacity = row[f'volume_{hour}'], row['Final_Capacity']
            cong = old_volume / final_capacity
            new_volume = old_volume + increase_volume_per_hour[f'volume_{hour}']
            after_cong = new_volume / final_capacity
            prediction_input_list.append({
                'LINK ID': row['LINK ID'], 'hour': hour, 'congestion': cong, 'after_congestion': after_cong,
                'volume_before': old_volume
            })

    df_predict = pd.DataFrame(prediction_input_list)
    if df_predict.empty:
        return pd.DataFrame()

    df_predict[['congestion', 'after_congestion']] = df_predict[['congestion', 'after_congestion']].clip(lower=0,
                                                                                                         upper=2)
    df_predict['LINK ID'] = df_predict['LINK ID'].astype('category')
    df_predict['predicted_speed_before'] = model.predict(df_predict[['congestion', 'LINK ID', 'hour']])
    df_predict['predicted_speed_after'] = model.predict(pd.DataFrame(
        {'congestion': df_predict['after_congestion'], 'LINK ID': df_predict['LINK ID'], 'hour': df_predict['hour']}))

    df_predict['predicted_speed_after'] = np.minimum(df_predict['predicted_speed_before'],
                                                     df_predict['predicted_speed_after'])
    df_predict[['predicted_speed_before', 'predicted_speed_after']] = df_predict[
        ['predicted_speed_before', 'predicted_speed_after']].clip(lower=5)

    road_lengths = roads_data[['level5.5_link_id', 'k_length']].rename(columns={'level5.5_link_id': 'LINK ID'})
    df_predict = pd.merge(df_predict, road_lengths, on='LINK ID')

    df_predict['time_before_min'] = (df_predict['k_length'] / df_predict['predicted_speed_before']) * 60
    df_predict['time_after_min'] = (df_predict['k_length'] / df_predict['predicted_speed_after']) * 60
    time_after_base_min = (df_predict['k_length'] / df_predict['predicted_speed_after']) * 60
    impact_factor = 1 + (df_predict['congestion'] ** 2)
    df_predict['time_after_min'] = time_after_base_min * impact_factor

    return df_predict


def calculate_project_financials(inputs):
    """프로젝트의 재무적 타당성을 계산합니다."""

    # 시나리오별 계산을 위한 내부 함수
    def _calculate(apt_info_local, market_change, cost_change):
        base_future_price = inputs['current_price'] * (1 + inputs['annual_rate'] / 100) ** inputs['duration']
        general_sale_price = base_future_price * (1 + inputs['premium_pct'] / 100) * (1 + market_change / 100)
        member_sale_price = general_sale_price * (1 - inputs['member_discount'] / 100)

        general_sale_units = inputs['new_units'] - apt_info_local['total_households']
        general_sale_revenue = general_sale_units * inputs[
            'new_avg_pyeong'] * general_sale_price if general_sale_units > 0 else 0
        member_sale_revenue = apt_info_local['total_households'] * inputs['new_avg_pyeong'] * member_sale_price

        total_revenue = (general_sale_revenue + member_sale_revenue) / 10000  # 억원 단위

        adjusted_construction_cost = inputs['construction_cost'] * (1 + cost_change / 100)
        total_construction_cost = (inputs['new_units'] * inputs['new_avg_pyeong'] * adjusted_construction_cost) / 10000
        other_costs = total_revenue * (inputs['other_costs_pct'] / 100)

        base_project_cost = total_construction_cost + other_costs
        pf_interest_cost = base_project_cost * (inputs['pf_rate'] / 100) * inputs['duration']
        total_project_cost = base_project_cost + pf_interest_cost

        project_profit = total_revenue - total_project_cost
        project_profit_margin = (project_profit / total_revenue) * 100 if total_revenue > 0 else 0

        return project_profit, project_profit_margin, total_revenue, total_project_cost, total_construction_cost

    base_profit, base_margin, base_revenue, base_cost, base_const_cost = _calculate(inputs['apt_info'], 0, 0)
    optimistic_profit, _, _, _, _ = _calculate(inputs['apt_info'], 20, -15)
    pessimistic_profit, _, _, _, _ = _calculate(inputs['apt_info'], -20, 15)
    scenario_profit, _, _, _, _ = _calculate(inputs['apt_info'], inputs['market_fluctuation'], inputs['cost_overrun'])

    return {
        'project_profit': base_profit, 'project_profit_margin': base_margin,
        'total_revenue': base_revenue, 'total_project_cost': base_cost,
        'total_construction_cost': base_const_cost, 'optimistic_profit': optimistic_profit,
        'pessimistic_profit': pessimistic_profit, 'scenario_profit': scenario_profit
    }


def calculate_public_impact(simulation_df, apt_location, new_units, apt_info, station_data, bus_data):
    """대중교통 등 공공 인프라 영향을 분석합니다. (Haversine 적용)"""
    significant_delay_roads = 0
    annual_social_cost = 0
    max_time_increase = 0

    if not simulation_df.empty:
        rush_hour_df = simulation_df[simulation_df['hour'].isin([7, 8, 18, 19])].copy()
        rush_hour_df['time_increase_min'] = rush_hour_df['time_after_min'] - rush_hour_df['time_before_min']

        road_max_delay = rush_hour_df.groupby('LINK ID')['time_increase_min'].max().reset_index()
        significant_delay_roads = road_max_delay[road_max_delay['time_increase_min'] >= 1].shape[0]

        max_time_increase = road_max_delay['time_increase_min'].max() if not road_max_delay.empty else 0

        rush_hour_df['total_delay_min'] = rush_hour_df['time_increase_min'] * rush_hour_df['volume_before']
        total_daily_delay_min = rush_hour_df['total_delay_min'].sum()
        annual_social_cost = (total_daily_delay_min / 60) * 15000 * 250

    # 지하철 분석
    new_commuters = (new_units - apt_info['total_households']) * 1.5
    nearest_station, _ = find_nearest_facility(station_data, apt_location['latitude'], apt_location['longitude'])
    TRAIN_CAPACITY_PER_HOUR = 160 * 8 * 18
    SUBWAY_SHARE = 0.6
    m_peak_before = nearest_station['출근시간_승차평균'];
    m_peak_after = m_peak_before + (new_commuters * SUBWAY_SHARE)
    subway_m_cong_before = (m_peak_before / TRAIN_CAPACITY_PER_HOUR * 100) if TRAIN_CAPACITY_PER_HOUR > 0 else 0
    subway_m_cong_after = (m_peak_after / TRAIN_CAPACITY_PER_HOUR * 100) if TRAIN_CAPACITY_PER_HOUR > 0 else 0
    e_peak_before = nearest_station['퇴근시간_하차평균'];
    e_peak_after = e_peak_before + (new_commuters * SUBWAY_SHARE)
    subway_e_cong_before = (e_peak_before / TRAIN_CAPACITY_PER_HOUR * 100) if TRAIN_CAPACITY_PER_HOUR > 0 else 0
    subway_e_cong_after = (e_peak_after / TRAIN_CAPACITY_PER_HOUR * 100) if TRAIN_CAPACITY_PER_HOUR > 0 else 0

    # 버스 분석: Haversine 공식 사용하여 반경 300m 내 정류장 필터링
    apt_lat, apt_lon = apt_location['latitude'], apt_location['longitude']

    bus_distances_m = haversine_distance(
        apt_lat, apt_lon,
        bus_data['latitude'], bus_data['longitude']
    )

    nearby_bus_stops = bus_data[bus_distances_m < 300].copy()  # 0.3km = 300m

    morning_bus_increase_rate, evening_bus_increase_rate = 0, 0;
    analyzed_bus_stops_ars = []
    if not nearby_bus_stops.empty:
        analyzed_bus_stops_ars = nearby_bus_stops['버스정류장ARS번호'].tolist()
        BUS_SHARE = 0.2
        new_bus_commuters = new_commuters * BUS_SHARE
        total_morning_activity = nearby_bus_stops['출근_활성도'].sum()
        if total_morning_activity > 0: morning_bus_increase_rate = (new_bus_commuters / total_morning_activity) * 100
        total_evening_activity = nearby_bus_stops['퇴근_활성도'].sum()
        if total_evening_activity > 0: evening_bus_increase_rate = (new_bus_commuters / total_evening_activity) * 100

    return {
        'significant_delay_roads': significant_delay_roads,
        'max_time_increase': max_time_increase,
        'annual_social_cost': annual_social_cost,
        'nearest_station_name': nearest_station['최종_역사명'],
        'subway_m_cong_before': subway_m_cong_before, 'subway_m_cong_after': subway_m_cong_after,
        'subway_e_cong_before': subway_e_cong_before, 'subway_e_cong_after': subway_e_cong_after,
        'morning_bus_increase_rate': morning_bus_increase_rate, 'evening_bus_increase_rate': evening_bus_increase_rate,
        'analyzed_bus_stops_ars': analyzed_bus_stops_ars
    }


def run_full_analysis(inputs, data):
    """모든 분석을 실행하고 결과를 통합하여 반환합니다."""
    # 데이터셋 분리
    unique_apts, master_data, hourly_congestion_df, roads_data, model, price_df, station_data, bus_data = data

    # 분석에 필요한 정보 추출
    apt_info = unique_apts[unique_apts['apt_name'] == inputs['apt_name']].iloc[0]
    apt_location = apt_info[['latitude', 'longitude']]

    # 1. 도로 교통 영향 분석
    simulation_results = calculate_traffic_impact(
        apt_location, inputs['new_units'], apt_info, master_data, hourly_congestion_df, roads_data, model
    )

    # 2. 프로젝트 사업성 분석
    financial_inputs = {**inputs, 'apt_info': apt_info}
    financial_results = calculate_project_financials(financial_inputs)

    # 3. 공공 인프라 영향 분석
    public_impact_results = calculate_public_impact(
        simulation_results, apt_location, inputs['new_units'], apt_info, station_data, bus_data
    )

    return simulation_results, financial_results, public_impact_results