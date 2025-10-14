# app.py
import streamlit as st
from streamlit_folium import st_folium
import pandas as pd
import plotly.graph_objects as go
import folium

# 모듈화된 함수 임포트
from data_loader import load_data_and_model
from analysis import run_full_analysis
from ui_components import (
    create_main_map, create_road_traffic_map, create_public_transport_map,
    create_scenario_chart, create_road_detail_chart, generate_recommendation
)
from utils import get_price_from_data, find_nearest_road

# --- 1. 초기 설정 및 데이터 로드 ---
st.set_page_config(layout="wide", page_title="재건축 사업 타당성 분석", page_icon="🏗️")
st.title("🏗️ AI 기반 통합 인프라 분석 대시보드")

# ... (이하 데이터 로드 및 session state 초기화 코드는 동일)
data_tuple = load_data_and_model()
unique_apts, master_data, hourly_congestion_df, roads_data, model, price_df, station_data, bus_data = data_tuple
if unique_apts is None:
    st.stop()
session_keys = ['simulation_results', 'financial_results', 'public_impact_results', 'highlighted_road',
                'analysis_slot_1', 'analysis_slot_2', 'current_analysis', 'previous_apartment']
for key in session_keys:
    if key not in st.session_state: st.session_state[key] = None


def reset_selection_states():
    for key in ['simulation_results', 'financial_results', 'public_impact_results', 'highlighted_road',
                'current_analysis']: st.session_state[key] = None


# --- 3. 사이드바 UI ---
if 'map_clicked_apt' in st.session_state:
    clicked_apt_info = unique_apts[unique_apts['apt_name'] == st.session_state.map_clicked_apt].iloc[0]
    st.session_state.selected_gu = clicked_apt_info['gu']
    st.session_state.selected_apartment = st.session_state.map_clicked_apt
    del st.session_state['map_clicked_apt']
st.sidebar.header("Step 1: 분석 대상 선택")
gu_list = ["구를 선택하세요"] + sorted(unique_apts['gu'].unique())
selected_gu = st.sidebar.selectbox("구를 선택하세요.", gu_list, key='selected_gu')
apartments_in_gu_list = ["아파트를 선택하세요"]
if selected_gu != "구를 선택하세요":
    apartments_in_gu_list.extend(sorted(unique_apts[unique_apts['gu'] == selected_gu]['apt_name'].unique()))
selected_apartment = st.sidebar.selectbox("아파트를 선택하세요.", apartments_in_gu_list, key='selected_apartment')
if selected_apartment != st.session_state.previous_apartment:
    reset_selection_states()
    st.session_state.previous_apartment = selected_apartment

# --- 4. 메인 화면 구성 ---
if selected_apartment and selected_apartment != "아파트를 선택하세요":
    apt_info = unique_apts[unique_apts['apt_name'] == selected_apartment].iloc[0]

    # ... (사이드바 입력 변수 UI는 동일)
    st.sidebar.divider()
    st.sidebar.header("Step 2: 시뮬레이션 변수 조정")
    with st.sidebar.expander("사업 개요 설정", expanded=True):
        new_units = st.number_input("총 신축 세대수", min_value=int(apt_info['total_households']),
                                    value=int(apt_info['total_households'] * 1.5))
        new_avg_pyeong = st.number_input("전체 평균 평형(평)", 10.0, 80.0, 34.0, 0.5)
        project_duration_years = st.slider("예상 사업 기간 (년)", 3, 10, 5)
    with st.sidebar.expander("재무 변수 설정"):
        gu_avg_price = get_price_from_data(price_df, apt_info['gu'])
        current_price_per_pyeong = st.number_input("현재 평당 시세 (만원)", min_value=100.0, value=float(gu_avg_price),
                                                   help=f"{apt_info['gu']} 평균: {gu_avg_price:,.0f}만원")
        price_premium_pct = st.slider("목표 분양가 프리미엄 (%)", -20, 50, 10)
        construction_cost_per_pyeong = st.number_input("평당 건축비 (만원)", min_value=500, value=750)
        pf_interest_rate = st.slider("프로젝트 파이낸싱(PF) 금리 (%)", 3.0, 15.0, 5.5, 0.1)
    st.sidebar.divider()
    st.sidebar.header("Step 3: What-if 시나리오")
    market_fluctuation_pct = st.sidebar.slider("미래 시장 변동률 (%)", -20, 20, 0)
    cost_overrun_pct = st.sidebar.slider("공사비 증감률 (%)", -15, 15, 0)
    # ... (분석 실행 및 결과 저장 버튼 UI는 동일)
    if st.sidebar.button("🤖 AI로 종합 분석 실행", type="primary", use_container_width=True):
        st.session_state.highlighted_road = None
        with st.spinner('AI가 미래가치 및 통합 인프라 영향을 심층 분석합니다...'):
            analysis_inputs = {'apt_name': selected_apartment, 'new_units': new_units, 'new_avg_pyeong': new_avg_pyeong,
                               'duration': project_duration_years, 'current_price': current_price_per_pyeong,
                               'premium_pct': price_premium_pct, 'member_discount': 10,
                               'construction_cost': construction_cost_per_pyeong, 'other_costs_pct': 15.0,
                               'annual_rate': 3.5, 'pf_rate': pf_interest_rate,
                               'market_fluctuation': market_fluctuation_pct, 'cost_overrun': cost_overrun_pct}
            sim_res, fin_res, pub_res = run_full_analysis(analysis_inputs, data_tuple)
            st.session_state.simulation_results, st.session_state.financial_results, st.session_state.public_impact_results = sim_res, fin_res, pub_res
            st.session_state.current_analysis = {"apartment_name": selected_apartment,
                                                 "scenario_inputs": {k: v for k, v in analysis_inputs.items() if
                                                                     k not in ['apt_name', 'current_price']},
                                                 "financial_results": fin_res, "public_impact_results": pub_res}
        st.success("✅ 심층 분석 완료!")
    if st.session_state.get('current_analysis'):
        st.sidebar.divider()
        st.sidebar.header("Step 4: 분석 결과 저장")
        col1, col2 = st.sidebar.columns(2)
        if col1.button("결과 1에 저장",
                       use_container_width=True): st.session_state.analysis_slot_1 = st.session_state.current_analysis; st.toast(
            "분석 결과를 '결과 1'에 저장했습니다.")
        if col2.button("결과 2에 저장",
                       use_container_width=True): st.session_state.analysis_slot_2 = st.session_state.current_analysis; st.toast(
            "분석 결과를 '결과 2'에 저장했습니다.")
    s1_text = f"**결과 1:** {st.session_state.analysis_slot_1['apartment_name'] if st.session_state.analysis_slot_1 else '비어있음'}"
    s2_text = f"**결과 2:** {st.session_state.analysis_slot_2['apartment_name'] if st.session_state.analysis_slot_2 else '비어있음'}"
    st.sidebar.markdown(f"<div style='font-size: 0.9em;'>{s1_text}<br>{s2_text}</div>", unsafe_allow_html=True)

    st.markdown(f"### 📍 **{selected_apartment}** 재건축 사업 분석")

    map_tab1, map_tab2 = st.tabs(["🚦 **도로 교통 지도**", "🚇 **대중교통 지도**"])
    with map_tab1:
        road_map = create_road_traffic_map(apt_info, roads_data, master_data, st.session_state.simulation_results,
                                           st.session_state.highlighted_road)
        st_folium(road_map, width="100%", height=400, key="road_map")

        # [수정] 도로 혼잡도 범례 추가
        st.markdown(
            """<div style="text-align: right; font-size: 0.9em; margin-top: -10px;">
            <span style="background-color: green; color: white; padding: 2px 5px; border-radius: 3px; margin: 0 2px;">원활 (0.0-0.3)</span>
            <span style="background-color: yellow; color: black; padding: 2px 5px; border-radius: 3px; margin: 0 2px;">서행 (0.3-0.6)</span>
            <span style="background-color: orange; color: white; padding: 2px 5px; border-radius: 3px; margin: 0 2px;">지체 (0.6-0.8)</span>
            <span style="background-color: red; color: white; padding: 2px 5px; border-radius: 3px; margin: 0 2px;">정체 (0.8+)</span>
            </div>""", unsafe_allow_html=True
        )
        # ... (이하 지도 클릭 로직은 동일)
        map_output = st.session_state.get("road_map")
        if map_output and map_output.get("last_clicked"):
            surrounding_links = master_data[master_data['apt_name'] == apt_info['apt_name']]['LINK ID'].unique()
            surrounding_roads = roads_data[roads_data['level5.5_link_id'].isin(surrounding_links)]
            clicked_road_id = find_nearest_road(surrounding_roads, map_output['last_clicked']['lat'],
                                                map_output['last_clicked']['lng'])
            if clicked_road_id and st.session_state.highlighted_road != clicked_road_id:
                st.session_state.highlighted_road = clicked_road_id;
                st.rerun()

    with map_tab2:
        apt_info_map = unique_apts[unique_apts['apt_name'] == selected_apartment].iloc[0]
        apt_center_map = [apt_info_map['latitude'], apt_info_map['longitude']]
        m_public = folium.Map(location=apt_center_map, zoom_start=15, tiles="CartoDB positron")
        nearby_stations = station_data[
            ((station_data['위도'] - apt_center_map[0]) ** 2 + (station_data['경도'] - apt_center_map[1]) ** 2) < 0.02 ** 2]
        for _, station in nearby_stations.iterrows():
            # [KeyError 방지] .get() 사용 및 호선 개수 안전 처리
            hosun_count = station['호선명'].count(',') + 1 if pd.notna(station['호선명']) else 1
            transfer_weight = station.get('환승_가중치', 0)

            popup_html = f"""
                <b>🚇 {station['최종_역사명']}</b>
                <hr style='margin: 4px 0;'>
                <b>호선 정보:</b> {station['호선명']} ({hosun_count}개 호선)
                <br><b>환승 가중치:</b> {transfer_weight:.2f}
                <hr style='margin: 4px 0;'>
                <b>🌞 출근 승차 평균:</b> {int(station['출근시간_승차평균']):,}명
                <br><b>🌙 퇴근 하차 평균:</b> {int(station['퇴근시간_하차평균']):,}명
            """
            folium.Marker(location=[station['위도'], station['경도']],
                          icon=folium.Icon(color='blue', icon='train', prefix='fa'), tooltip=f"🚇 {station['최종_역사명']}",
                          popup=folium.Popup(popup_html, max_width=400)).add_to(m_public)

        # [수정] 분석된 버스정류장 강조 표시
        nearby_bus_stops_map = bus_data[((bus_data['latitude'] - apt_center_map[0]) ** 2 + (
                bus_data['longitude'] - apt_center_map[1]) ** 2) < 0.015 ** 2]
        analyzed_ars_list = st.session_state.public_impact_results.get('analyzed_bus_stops_ars',
                                                                       []) if st.session_state.public_impact_results else []
        for _, bus_stop in nearby_bus_stops_map.iterrows():
            is_analyzed = bus_stop['버스정류장ARS번호'] in analyzed_ars_list
            icon_color = 'orange' if is_analyzed else 'green'
            tooltip_text = f"🚌 {bus_stop['역명']} (분석 대상)" if is_analyzed else f"🚌 {bus_stop['역명']}"

            # [KeyError 방지] .get()을 사용하여 KeyError 방지 및 변수 분리
            출근_승차 = bus_stop.get('출근_승차', 0)
            출근_하차 = bus_stop.get('출근_하차', 0)
            퇴근_승차 = bus_stop.get('퇴근_승차', 0)
            퇴근_하차 = bus_stop.get('퇴근_하차', 0)
            출근_활성도 = bus_stop.get('출근_활성도', 0)
            퇴근_활성도 = bus_stop.get('퇴근_활성도', 0)
            총_활성도 = 출근_활성도 + 퇴근_활성도

            popup_html = f"""
                <b>🚌 {tooltip_text}</b>
                <hr style='margin: 4px 0;'>
                <b>ARS 번호:</b> {bus_stop['버스정류장ARS번호']}
                <hr style='margin: 4px 0;'>
                <b>🌞 출근 시간 (07-09시):</b>
                <br>&nbsp; 승차: {int(출근_승차):,}명 / 하차: {int(출근_하차):,}명
                <br><b>🌙 퇴근 시간 (18-20시):</b>
                <br>&nbsp; 승차: {int(퇴근_승차):,}명 / 하차: {int(퇴근_하차):,}명
                <hr style='margin: 4px 0;'>
                <b>📊 출퇴근 활성도:</b>
                <br>&nbsp; 출근 활성도: {int(출근_활성도):,}명
                <br>&nbsp; 퇴근 활성도: {int(퇴근_활성도):,}명
                <br><span style='font-size: 0.8em; color: gray;'>
                (활성도: 해당 시간대 승/하차 인원의 합계로, 정류장 이용 빈도를 나타냄)
                </span>
            """

            folium.Marker(location=[bus_stop['latitude'], bus_stop['longitude']],
                          icon=folium.Icon(color=icon_color, icon='bus', prefix='fa'), tooltip=tooltip_text,
                          popup=folium.Popup(popup_html, max_width=400)).add_to(m_public)

        # 지도 객체는 m_public에 저장되어 있습니다.
        folium.Marker(location=apt_center_map, tooltip=apt_info_map['apt_name'],
                      icon=folium.Icon(color='purple', icon='star')).add_to(m_public)

        # [수정 완료] m_public 변수를 st_folium에 전달합니다. (NameError 해결)
        st_folium(m_public, width="100%", height=400, key="public_transport_map")

    st.divider()

    tab_names = ["**📊 종합 대시보드**", "**📈 프로젝트 사업성 분석**", "**🚗 도로 심층 분석**", "**🏙️ 광역 영향 분석**"]
    if st.session_state.analysis_slot_1 and st.session_state.analysis_slot_2: tab_names.append("**🆚 결과 비교 분석**")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        if st.session_state.financial_results and st.session_state.public_impact_results:
            fin_res, pub_res = st.session_state.financial_results, st.session_state.public_impact_results

            # --- [수정] 프로젝트 개요 섹션: 메트릭과 차트를 함께 표시 ---
            st.markdown("##### **Executive Summary: 프로젝트 개요**")
            col1, col2 = st.columns([1, 1.2])  # 컬럼 비율 조정

            with col1:
                st.metric("💰 프로젝트 순이익 (세전)", f"{fin_res['project_profit']:,.1f} 억원",
                          help="총 예상 매출에서 총 사업비(공사비+기타비용+PF이자)를 제외한 세전 순이익입니다. \n\n**수식:** `순이익 = 총매출 - 총사업비`")
                st.metric("📈 프로젝트 이익률", f"{fin_res['project_profit_margin']:.1f}%",
                          help="프로젝트 순이익을 총 매출로 나눈 값으로, 사업의 수익성을 나타내는 지표입니다.\n\n**수식:** `이익률(%) = (순이익 / 총매출) * 100`")
                st.metric("💵 총 예상 매출", f"{fin_res['total_revenue']:,.1f} 억원",
                          help="일반 분양 및 조합원 분양을 통해 발생할 것으로 예상되는 총 매출액입니다.")

            with col2:
                # 비용 구조를 보여주는 도넛 차트 추가
                total_cost = fin_res['total_project_cost']
                construction_cost = fin_res['total_construction_cost']
                other_costs = total_cost - construction_cost

                labels = ['총 공사비', '기타 사업비/이자']
                values = [construction_cost, other_costs]

                fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, textinfo='label+percent',
                                             marker_colors=['#0072B2', '#D55E00'])])
                fig.update_layout(
                    title_text=f"<b>총 사업비 구성 (총 {total_cost:,.1f} 억원)</b>",
                    showlegend=False,
                    height=280,
                    margin=dict(t=60, b=20, l=0, r=0),
                    annotations=[dict(text='비용 구조', x=0.5, y=0.5, font_size=20, showarrow=False)]
                )
                st.plotly_chart(fig, use_container_width=True)

            st.write("---")

            # --- [수정] 인프라 영향 섹션: 새 지표 추가 ---
            st.markdown("##### **Executive Summary: 인프라 영향**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("<h6 style='text-align: center;'>🚦 도로 영향</h6>", unsafe_allow_html=True)
                st.metric(
                    label="🚗 출퇴근길 지연 도로",
                    value=f"{pub_res['significant_delay_roads']} 개",
                    help="재건축 후 출퇴근 시간(07-08, 18-19시)대 통과 시간이 **1분 이상** 증가하여 체감 교통 여건이 크게 악화될 것으로 예상되는 도로의 수입니다."
                )
                st.metric(
                    label="⏱️ 최대 통행 시간 증가",
                    value=f"{pub_res['max_time_increase']:.1f} 분",
                    help="가장 심하게 정체되는 도로에서 출퇴근 시간대 통과 시간이 최대로 늘어나는 시간입니다."
                )
                st.metric(label="💸 연간 교통 지연 비용", value=f"{pub_res['annual_social_cost'] / 1e8:,.1f} 억원",
                          # 수식 추가 (단위 포함)
                          help="재건축으로 인해 증가하는 주변 차량 통행 시간 지연을 화폐 가치로 환산한 연간 총 사회적 비용입니다. (시간당 15,000원 기준)\n\n**수식:** `(총 지연 시간(분) / 60) * 15,000원 * 250일`")

            with col2:
                st.markdown("<h6 style='text-align: center;'>🌞 출근길 영향</h6>", unsafe_allow_html=True)
                st.metric(label="🚇 지하철 혼잡도", value=f"{pub_res['subway_m_cong_after']:.1f}%",
                          delta=f"{pub_res['subway_m_cong_after'] - pub_res['subway_m_cong_before']:.1f}%p",
                          # 수식 추가
                          help="가장 가까운 지하철역의 출근 시간(07-09시)대 최고 혼잡도 변화 예측치입니다. (승차인원/열차용량)\n\n**수식:** `혼잡도(%) = (시간당 승차 인원 / 열차 용량) * 100`")
                st.metric(label="🚌 버스 이용객 증가", value=f"{pub_res['morning_bus_increase_rate']:.1f}% ▲",
                          # 수식 추가
                          help="반경 300m 내 버스 정류장의 출근 시간대 총 이용객 수 증가율 예측치입니다.\n\n**수식:** `증가율(%) = (신규 통근자(버스) / 기존 출근 활성도 합계) * 100`")

            with col3:
                st.markdown("<h6 style='text-align: center;'>🌙 퇴근길 영향</h6>", unsafe_allow_html=True)
                st.metric(label="🚇 지하철 혼잡도", value=f"{pub_res['subway_e_cong_after']:.1f}%",
                          delta=f"{pub_res['subway_e_cong_after'] - pub_res['subway_e_cong_before']:.1f}%p",
                          # 수식 추가 (출근길과 동일한 계산식)
                          help="가장 가까운 지하철역의 퇴근 시간(18-20시)대 최고 혼잡도 변화 예측치입니다. (하차인원/열차용량)\n\n**수식:** `혼잡도(%) = (시간당 하차 인원 / 열차 용량) * 100`")
                st.metric(label="🚌 버스 이용객 증가", value=f"{pub_res['evening_bus_increase_rate']:.1f}% ▲",
                          # 수식 추가 (출근길과 동일한 계산식)
                          help="반경 300m 내 버스 정류장의 퇴근 시간대 총 이용객 수 증가율 예측치입니다.\n\n**수식:** `증가율(%) = (신규 통근자(버스) / 기존 퇴근 활성도 합계) * 100`")
        else:
            st.info("사이드바에서 변수를 조정한 후 'AI로 종합 분석 실행' 버튼을 눌러주세요.")

    # ... (이하 나머지 탭 코드는 변경 없음)
    with tabs[1]:
        if st.session_state.financial_results:
            fin_res = st.session_state.financial_results
            fin_col1, fin_col2 = st.columns(2)
            with fin_col1:
                st.markdown("##### **What-if 시나리오별 순이익**")
                fig = create_scenario_chart(fin_res)
                st.plotly_chart(fig, use_container_width=True)
            with fin_col2:
                st.markdown("##### **프로젝트 현금흐름 (기본 시나리오)**")
                fig_w = go.Figure(go.Waterfall(orientation="v", measure=["relative", "relative", "total"],
                                               x=["총 예상 매출", "총 사업비", "프로젝트 순이익"], text=[f"{v:,.1f}" for v in
                                                                                         [fin_res['total_revenue'],
                                                                                          -fin_res[
                                                                                              'total_project_cost'],
                                                                                          fin_res['project_profit']]],
                                               y=[fin_res['total_revenue'], -fin_res['total_project_cost'], 0],
                                               connector={"line": {"color": "rgb(63, 63, 63)"}}))
                fig_w.update_layout(title="매출-비용 구조", showlegend=False, height=400, margin=dict(t=30, b=10, l=10, r=10))
                st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.info("사이드바에서 분석을 실행해주세요.")
    with tabs[2]:
        if st.session_state.simulation_results is not None and st.session_state.highlighted_road:
            road_data = st.session_state.simulation_results[
                st.session_state.simulation_results['LINK ID'] == st.session_state.highlighted_road]
            road_name_series = roads_data.loc[
                roads_data['level5.5_link_id'] == st.session_state.highlighted_road, 'road_name']
            road_name = road_name_series.iloc[0] if not road_name_series.empty and pd.notna(
                road_name_series.iloc[0]) else f"ID: {st.session_state.highlighted_road}"
            if not road_data.empty:
                fig = create_road_detail_chart(road_data, road_name)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("🚦 **도로 교통 지도**에서 분석할 도로를 클릭해주세요.")
    with tabs[3]:
        if st.session_state.public_impact_results:
            pub_res = st.session_state.public_impact_results
            st.markdown(f"###### **최인접 지하철역 영향 ({pub_res['nearest_station_name']})**")
            st.info(
                f"**🚇 출근길(승차) 최고 혼잡도**가 **{pub_res['subway_m_cong_before']:.1f}%** → **{pub_res['subway_m_cong_after']:.1f}%** 로, **퇴근길(하차) 최고 혼잡도**가 **{pub_res['subway_e_cong_before']:.1f}%** → **{pub_res['subway_e_cong_after']:.1f}%** 로 증가할 것으로 예상됩니다.")
            st.markdown("###### **주변 버스 네트워크 영향 (반경 300m)**")
            st.info(
                f"**🚌 주변 정류장 전체**의 **출근길 이용객**은 약 **{pub_res.get('morning_bus_increase_rate', 0):.1f}%** ▲, **퇴근길 이용객**은 약 **{pub_res.get('evening_bus_increase_rate', 0):.1f}%** ▲ 증가할 것으로 예상됩니다.")
        else:
            st.info("사이드바에서 분석을 실행해주세요.")

    if len(tabs) == 5:
        with tabs[4]:
            s1, s2 = st.session_state.analysis_slot_1, st.session_state.analysis_slot_2
            st.markdown("### 🆚 시나리오 비교 분석")


            # ... (이하 비교분석 탭의 시나리오 변수 테이블 UI는 동일)
            def create_scenario_table(scenario_inputs):
                translation_map = {'new_units': '신축 세대수', 'new_avg_pyeong': '평균 평형', 'duration': '사업 기간 (년)',
                                   'premium_pct': '분양가 프리미엄 (%)', 'construction_cost': '평당 건축비 (만원)',
                                   'pf_rate': 'PF 금리 (%)', 'market_fluctuation': '시장 변동률 (%)',
                                   'cost_overrun': '공사비 증감률 (%)'}
                filtered_inputs = {k: v for k, v in scenario_inputs.items() if k in translation_map}
                df = pd.DataFrame.from_dict(filtered_inputs, orient='index', columns=['설정값']);
                df.index = df.index.map(translation_map)
                return df

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"#### 🔵 결과 1: {s1['apartment_name']}")
                with st.expander("시나리오 변수 보기", expanded=True):
                    st.dataframe(create_scenario_table(s1['scenario_inputs']), use_container_width=True)
                st.markdown("---")
                st.markdown("##### 프로젝트 사업성")
                fin1 = s1['financial_results']
                st.metric("💰 프로젝트 순이익", f"{fin1['project_profit']:,.1f} 억원")
                st.metric("📈 프로젝트 이익률", f"{fin1['project_profit_margin']:.1f}%")
                st.markdown("##### 인프라 영향")
                pub1 = s1['public_impact_results']
                st.metric("💸 연간 교통 지연 비용", f"{pub1['annual_social_cost'] / 1e8:,.1f} 억원")
                st.metric("🚇 출근길 지하철 혼잡도", f"{pub1['subway_m_cong_after']:.1f}%")
                st.metric("🚌 출근길 버스 이용객", f"{pub1['morning_bus_increase_rate']:.1f}% ▲")
            with col2:
                st.markdown(f"#### 🟢 결과 2: {s2['apartment_name']}")
                with st.expander("시나리오 변수 보기", expanded=True):
                    st.dataframe(create_scenario_table(s2['scenario_inputs']), use_container_width=True)
                st.markdown("---")
                st.markdown("##### 프로젝트 사업성")
                fin2 = s2['financial_results']
                st.metric("💰 프로젝트 순이익", f"{fin2['project_profit']:,.1f} 억원", delta=f"{fin2['project_profit'] - fin1['project_profit']:,.1f} 억원")
                st.metric("📈 프로젝트 이익률", f"{fin2['project_profit_margin']:.1f}%", delta=f"{fin2['project_profit_margin'] - fin1['project_profit_margin']:.1f}%p")
                st.markdown("##### 인프라 영향")
                pub2 = s2['public_impact_results']
                st.metric("💸 연간 교통 지연 비용", f"{pub2['annual_social_cost'] / 1e8:,.1f} 억원", delta=f"{(pub2['annual_social_cost'] - pub1['annual_social_cost']) / 1e8:,.1f} 억원", delta_color="inverse")
                st.metric("🚇 출근길 지하철 혼잡도", f"{pub2['subway_m_cong_after']:.1f}%", delta=f"{pub2['subway_m_cong_after'] - pub1['subway_m_cong_after']:.1f}%p", delta_color="inverse")
                st.metric("🚌 출근길 버스 이용객", f"{pub2['morning_bus_increase_rate']:.1f}% ▲", delta=f"{pub2['morning_bus_increase_rate'] - pub1['morning_bus_increase_rate']:.1f}%p", delta_color="inverse")
            st.divider()

            # [수정] 강화된 추천 로직 호출 및 결과 표시
            title, summary, details = generate_recommendation(s1, s2)
            st.markdown(title)
            st.info(summary)
            with st.expander("상세 비교 분석 보기"):
                st.markdown(details)

# --- 6. 초기 화면 (아파트 미선택 시) ---
else:
    # ... (이하 코드는 동일)
    st.markdown("### 데이터 기반의 빠르고 정확한 재건축 사업 타당성 검토를 지원합니다.")
    st.markdown("좌측 사이드바에서 분석할 **'구'**를 선택하거나, 지도에서 직접 아파트를 클릭하여 분석을 시작하세요.")
    initial_map = create_main_map(unique_apts, selected_gu)
    map_output = st_folium(initial_map, width="100%", height=500, key="initial_map")
    if map_output and map_output.get("last_object_clicked_tooltip"):
        clicked_apt_name = map_output.get("last_object_clicked_tooltip")
        if clicked_apt_name in unique_apts['apt_name'].tolist():
            st.session_state.map_clicked_apt = clicked_apt_name;
            st.rerun()