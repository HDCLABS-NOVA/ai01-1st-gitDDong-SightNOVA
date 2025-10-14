# ui_components.py
import folium
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from folium.plugins import MarkerCluster
from utils import get_color_by_congestion, format_time_label, normalize


def create_main_map(unique_apts, selected_gu):
    """초기 화면에 표시될 지도를 생성합니다."""
    if selected_gu != "구를 선택하세요":
        gu_center = unique_apts[unique_apts['gu'] == selected_gu][['latitude', 'longitude']].mean()
        map_center = [gu_center['latitude'], gu_center['longitude']]
        zoom_level = 13
    else:
        map_center = [37.5665, 126.9780]
        zoom_level = 11

    m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

    if selected_gu != "구를 선택하세요":
        apts_in_gu = unique_apts[unique_apts['gu'] == selected_gu]
        mc = MarkerCluster()
        for _, apt in apts_in_gu.iterrows():
            mc.add_child(folium.Marker(location=[apt['latitude'], apt['longitude']], tooltip=apt['apt_name']))
        m.add_child(mc)

    return m


def create_road_traffic_map(apt_info, roads_data, master_data, sim_results, highlighted_road):
    """도로 교통 현황 지도를 생성합니다."""
    apt_center = [apt_info['latitude'], apt_info['longitude']]
    m = folium.Map(location=apt_center, zoom_start=15, tiles="CartoDB positron")

    surrounding_links = master_data[master_data['apt_name'] == apt_info['apt_name']]['LINK ID'].unique()
    surrounding_roads = roads_data[roads_data['level5.5_link_id'].isin(surrounding_links)].copy()

    if sim_results is not None and not sim_results.empty:
        avg_congestion = sim_results.groupby('LINK ID')['after_congestion'].mean().reset_index()
        surrounding_roads = pd.merge(surrounding_roads, avg_congestion, left_on='level5.5_link_id', right_on='LINK ID',
                                     how='left')
        tooltip_fields = ['road_name', 'after_congestion']
        tooltip_aliases = ['도로명:', '개발 후 혼잡도:']
        color_col = 'after_congestion'
    else:
        tooltip_fields = ['road_name', 'avg_congestion']
        tooltip_aliases = ['도로명:', '현재 혼잡도:']
        color_col = 'avg_congestion'

    if not surrounding_roads.empty:
        folium.GeoJson(
            surrounding_roads,
            style_function=lambda f: {'color': get_color_by_congestion(f['properties'].get(color_col)), 'weight': 6},
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields, aliases=tooltip_aliases)
        ).add_to(m)

    if highlighted_road:
        highlight_gdf = roads_data[roads_data['level5.5_link_id'] == highlighted_road]
        if not highlight_gdf.empty:
            folium.GeoJson(
                highlight_gdf,
                style_function=lambda x: {'color': '#FF00FF', 'weight': 12, 'opacity': 1},
                tooltip=f"선택된 도로: {highlighted_road}"
            ).add_to(m)

    folium.Marker(location=apt_center, tooltip=apt_info['apt_name'],
                  icon=folium.Icon(color='purple', icon='star')).add_to(m)
    return m


def create_public_transport_map(apt_info, station_data, bus_data, public_impact_results):
    """대중교통 현황 지도를 생성합니다."""
    apt_center = [apt_info['latitude'], apt_info['longitude']]
    m = folium.Map(location=apt_center, zoom_start=15, tiles="CartoDB positron")

    # 지하철역 표시
    nearby_stations = station_data[
        ((station_data['위도'] - apt_center[0]) ** 2 + (station_data['경도'] - apt_center[1]) ** 2) < 0.02 ** 2]
    for _, station in nearby_stations.iterrows():
        popup_html = f"<b>🚇 {station['최종_역사명']}</b><br><b>호선:</b> {station['호선명']}"
        folium.Marker(
            location=[station['위도'], station['경도']],
            icon=folium.Icon(color='blue', icon='train', prefix='fa'),
            tooltip=f"🚇 {station['최종_역사명']}",
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    # 버스 정류장 표시
    nearby_bus_stops = bus_data[
        ((bus_data['latitude'] - apt_center[0]) ** 2 + (bus_data['longitude'] - apt_center[1]) ** 2) < 0.015 ** 2]
    analyzed_ars_list = public_impact_results.get('analyzed_bus_stops_ars', []) if public_impact_results else []

    for _, bus_stop in nearby_bus_stops.iterrows():
        is_analyzed = bus_stop['버스정류장ARS번호'] in analyzed_ars_list
        icon_color = 'orange' if is_analyzed else 'green'
        tooltip_text = f"🚌 {bus_stop['역명']}" + (" (분석 대상)" if is_analyzed else "")
        popup_html = f"<b>{tooltip_text}</b><br><b>ARS:</b> {bus_stop['버스정류장ARS번호']}"
        folium.Marker(
            location=[bus_stop['latitude'], bus_stop['longitude']],
            icon=folium.Icon(color=icon_color, icon='bus', prefix='fa'),
            tooltip=tooltip_text,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    folium.Marker(location=apt_center, tooltip=apt_info['apt_name'],
                  icon=folium.Icon(color='purple', icon='star')).add_to(m)
    return m


def create_scenario_chart(fin_res):
    """시나리오별 순이익 비교 바 차트를 생성합니다."""
    fig = go.Figure()
    scenarios = ['최악', '현재 설정', '기본', '최상']
    profits = [fin_res['pessimistic_profit'], fin_res['scenario_profit'], fin_res['project_profit'],
               fin_res['optimistic_profit']]
    colors = ['#D55E00', '#0072B2', '#56B4E9', '#009E73']
    fig.add_trace(go.Bar(x=scenarios, y=profits, text=[f"{p:,.1f}억" for p in profits], textposition='outside',
                         marker_color=colors))
    max_p = max(profits) if profits else 0
    min_p = min(profits) if profits else 0
    fig.update_layout(
        yaxis_title="프로젝트 순이익 (억원)", height=400,
        yaxis_range=[min_p * 1.2 if min_p < 0 else 0, max_p * 1.3],
        margin=dict(t=30, b=10, l=10, r=10)
    )
    return fig


def create_road_detail_chart(road_data, road_name):
    """선택된 도로의 시간대별 통행 시간 변화 그래프를 생성합니다."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=road_data['hour'], y=road_data['time_before_min'], mode='lines', name='개발 전',
                             line=dict(color='#636EFA')))
    fig.add_trace(go.Scatter(x=road_data['hour'], y=road_data['time_after_min'], mode='lines', name='개발 후',
                             line=dict(color='#EF553B', dash='dash')))

    y_max = max(road_data['time_before_min'].max(), road_data['time_after_min'].max()) * 1.2
    tick_vals = np.arange(0, y_max + 0.5, 0.5)
    tick_texts = [format_time_label(val) for val in tick_vals]

    fig.add_vrect(x0=7, x1=9, fillcolor="red", opacity=0.1, layer="below", annotation_text="출근")
    fig.add_vrect(x0=18, x1=20, fillcolor="blue", opacity=0.1, layer="below", annotation_text="퇴근")

    fig.update_layout(
        template="plotly_white",
        title=f"<b>{road_name}</b> 시간대별 통과 소요 시간",
        xaxis_title="시간 (0시 - 23시)", yaxis_title="소요 시간",
        yaxis=dict(tickvals=tick_vals, ticktext=tick_texts, range=[0, y_max]),
        legend_title="시점"
    )
    return fig


def generate_recommendation(s1, s2):
    """두 시나리오를 상세히 비교하여 최종 추천 내용을 생성합니다."""
    # 데이터 추출
    fin1, pub1 = s1['financial_results'], s1['public_impact_results']
    fin2, pub2 = s2['financial_results'], s2['public_impact_results']

    # 점수 계산 (가중치: 수익성 60%, 사회적 비용 40%)
    p_min, p_max = min(fin1['project_profit'], fin2['project_profit']), max(fin1['project_profit'],
                                                                            fin2['project_profit'])
    c_min, c_max = min(pub1['annual_social_cost'], pub2['annual_social_cost']), max(pub1['annual_social_cost'],
                                                                                    pub2['annual_social_cost'])

    score1 = normalize(fin1['project_profit'], p_min, p_max) * 0.6 + (
                1 - normalize(pub1['annual_social_cost'], c_min, c_max)) * 0.4
    score2 = normalize(fin2['project_profit'], p_min, p_max) * 0.6 + (
                1 - normalize(pub2['annual_social_cost'], c_min, c_max)) * 0.4

    if abs(score1 - score2) < 0.05:  # 점수 차가 미미할 경우
        winner_name, loser_name = ("결과 1", "결과 2") if score1 > score2 else ("결과 2", "결과 1")
        title = f"##### ⚖️ 두 시나리오의 장단점이 유사하여 우열을 가리기 어렵습니다 (근소 우위: {winner_name})."
        summary = "두 대안 모두 장단점을 가지고 있어, 의사결정자의 우선순위에 따라 선택이 달라질 수 있습니다. 수익성을 극대화할지, 인프라 부담을 최소화할지 전략적 판단이 필요합니다."
    elif score1 > score2:
        winner, loser = s1, s2
        winner_name, loser_name = "결과 1", "결과 2"
        title = f"##### 🏆 최종 추천: 🔵 {winner_name} ({winner['apartment_name']})"
        summary = f"**{winner_name}**은(는) **{loser_name}**에 비해 프로젝트 수익성과 사회적 비용 측면에서 더 균형 잡힌 최적의 대안으로 판단됩니다."
    else:
        winner, loser = s2, s1
        winner_name, loser_name = "결과 2", "결과 1"
        title = f"##### 🏆 최종 추천: 🟢 {winner_name} ({winner['apartment_name']})"
        summary = f"**{winner_name}**은(는) **{loser_name}**에 비해 프로젝트 수익성과 사회적 비용 측면에서 더 균형 잡힌 최적의 대안으로 판단됩니다."

    # 상세 분석 내용 생성
    profit_diff = fin2['project_profit'] - fin1['project_profit']
    cost_diff = (pub2['annual_social_cost'] - pub1['annual_social_cost']) / 1e8

    details = f"""
    - **프로젝트 수익성**: **{winner_name}**의 예상 순이익은 약 **{winner['financial_results']['project_profit']:,.1f}억원**으로, {loser_name} 대비 **{abs(profit_diff):,.1f}억원** {'더 높습니다' if (winner_name == '결과 2' and profit_diff > 0) or (winner_name == '결과 1' and profit_diff < 0) else '낮지만'}.
    - **교통 인프라 영향**: **{winner_name}**으로 인한 연간 교통 지연 비용은 약 **{winner['public_impact_results']['annual_social_cost'] / 1e8:,.1f}억원**으로, {loser_name}보다 **{abs(cost_diff):,.1f}억원** {'적게 발생하여' if (winner_name == '결과 2' and cost_diff < 0) or (winner_name == '결과 1' and cost_diff > 0) else '많이 발생하지만'} 사회적 부담이 덜합니다.
    - **결론**: 이러한 분석을 종합했을 때, {'수익성이 다소 낮더라도' if (winner_name == '결과 1' and profit_diff > 0) or (winner_name == '결과 2' and profit_diff < 0) else ''} **{winner_name}**이(가) 장기적인 관점에서 더 안정적이고 합리적인 선택입니다.
    """

    return title, summary, details