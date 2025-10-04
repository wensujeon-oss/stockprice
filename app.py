import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 함수 정의 ---

def calculate_cmo(data, period):
    """Chande Momentum Oscillator (CMO) 계산"""
    delta = data.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    sum_up = up.rolling(window=period).sum()
    sum_down = down.rolling(window=period).sum()
    
    cmo = 100 * (sum_up - sum_down) / (sum_up + sum_down)
    return cmo.fillna(0)

def calculate_vidya(data, period, cmo_period=9):
    """VIDYA (Variable Index Dynamic Average) 계산"""
    close = data['Close']
    cmo = calculate_cmo(close, cmo_period)
    
    k = abs(cmo / 100)
    alpha = 2 / (period + 1)
    vidya = pd.Series(index=close.index, dtype='float64')
    
    vidya.iloc[period - 1] = close.iloc[:period].mean()
    
    for i in range(period, len(close)):
        vidya.iloc[i] = (alpha * k.iloc[i] * close.iloc[i]) + ((1 - alpha * k.iloc[i]) * vidya.iloc[i-1])
        
    return vidya

# --- Streamlit 앱 UI 설정 ---

st.set_page_config(layout="wide", page_title="VIDYA 지표 분석기", page_icon="📈")

st.title("📈 VIDYA 지표 분석")
st.markdown("""
VIDYA는 **'변동성 지수 동적 평균(Variable Index Dynamic Average)'**을 의미하며, 시장 변동성에 따라 동적으로 반응하는 '더 똑똑한 이동평균선'입니다.
""")

# --- 사용자 입력 ---
col1, col2 = st.columns(2)
with col1:
    predefined_tickers = ['TQQQ', 'FTEC', 'SPLG', 'SCHG', 'SPMO', 'QQQM', 'SMHX', 'SOXL']
    CUSTOM_TICKER_OPTION = "다른 종목 직접 입력..."
    
    ticker_options = predefined_tickers + [CUSTOM_TICKER_OPTION]
    
    try:
        default_index = ticker_options.index('TQQQ')
    except ValueError:
        default_index = 0

    selected_option = st.selectbox(
        "분석할 주식 티커를 선택하세요:",
        ticker_options,
        index=default_index
    )

    ticker_input = ""
    if selected_option == CUSTOM_TICKER_OPTION:
        ticker_input = st.text_input("사용자 정의 티커를 입력하세요:").upper()
        if not ticker_input:
            st.info("위에 티커를 입력하고 Enter 키를 누르세요.")
    else:
        ticker_input = selected_option
with col2:
    period_options = {
        "1년": 365,
        "3년": 3*365,
        "5년": 5*365,
        "10년": 10*365,
        "최대": None
    }
    selected_period_label = st.selectbox("분석 기간을 선택하세요:", list(period_options.keys()), index=1)

# --- 데이터 로딩 및 분석 ---
if ticker_input:
    with st.spinner(f'{ticker_input} 데이터를 로딩하고 분석하는 중입니다...'):
        # 기간 계산
        if period_options[selected_period_label] is None:
            start_date = None
            history_period = 'max'
        else:
            days = period_options[selected_period_label]
            start_date = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
            history_period = None

        # 데이터 가져오기
        ticker = yf.Ticker(ticker_input)
        if start_date:
            data = ticker.history(start=start_date, end=datetime.today().strftime('%Y-%m-%d'))
        else:
            data = ticker.history(period=history_period)

        if not data.empty:
            # VIDYA 계산
            data['VIDYA_2'] = calculate_vidya(data, period=2)
            data['VIDYA_120'] = calculate_vidya(data, period=120)
            data['VIDYA_200'] = calculate_vidya(data, period=200)

            # 200일 VIDYA 기울기 계산
            data['VIDYA_200_Slope'] = data['VIDYA_200'].diff()
            
            data = data.dropna()

            # 최저 기울기 지점 찾기 (200일 VIDYA 기준)
            min_slope_idx = data['VIDYA_200_Slope'].idxmin()
            min_slope_date = data.loc[min_slope_idx].name
            min_slope_value = data.loc[min_slope_idx, 'VIDYA_200']

            # 크로스 지점 찾기
            data['Signal'] = 0
            data.loc[(data['VIDYA_2'] > data['VIDYA_120']) & (data['VIDYA_2'].shift(1) <= data['VIDYA_120'].shift(1)), 'Signal'] = 1
            data.loc[(data['VIDYA_2'] < data['VIDYA_120']) & (data['VIDYA_2'].shift(1) >= data['VIDYA_120'].shift(1)), 'Signal'] = -1

            golden_crosses = data[data['Signal'] == 1]
            dead_crosses = data[data['Signal'] == -1]

            # --- 차트 시각화 ---
            st.subheader(f"{ticker_input} 주가 및 VIDYA 지표 ({selected_period_label})")
            fig = go.Figure()

            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='종가', line=dict(color='skyblue', width=2)))
            fig.add_trace(go.Scatter(x=data.index, y=data['VIDYA_2'], name='VIDYA (2일)', line=dict(color='orange', width=1.5)))
            fig.add_trace(go.Scatter(x=data.index, y=data['VIDYA_120'], name='VIDYA (120일)', line=dict(color='purple', width=2, dash='dot')))
            fig.add_trace(go.Scatter(x=data.index, y=data['VIDYA_200'], name='VIDYA (200일)', line=dict(color='lightgreen', width=2, dash='dash')))

            fig.add_trace(go.Scatter(x=golden_crosses.index, y=golden_crosses['VIDYA_120'], name='Golden Cross', mode='markers', marker=dict(color='red', size=10, symbol='triangle-up')))
            fig.add_trace(go.Scatter(x=dead_crosses.index, y=dead_crosses['VIDYA_120'], name='Dead Cross', mode='markers', marker=dict(color='blue', size=10, symbol='triangle-down')))
            
            fig.add_trace(go.Scatter(
                x=[min_slope_date], y=[min_slope_value],
                name='200일 VIDYA 최저 기울기', mode='markers+text',
                marker=dict(color='mediumorchid', size=12, symbol='star'),
                text=["최저점"], textposition="bottom center"
            ))

            fig.update_layout(
                yaxis_title='주가(USD)', xaxis_title=None,
                legend_title=None,
                template='plotly_dark', hovermode="x unified", height=600,
                xaxis_hoverformat='%Y-%m-%d' # 호버 시 날짜 형식을 '년-월-일'로 고정
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.error(f"'{ticker_input}'에 대한 데이터를 찾을 수 없습니다. 티커를 확인하고 다시 시도하세요.")
else:
    st.info("분석할 주식 티커를 입력하고 기간을 선택하세요.")
