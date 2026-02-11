# main.py
import streamlit as st
from datetime import date, datetime
import plotly.graph_objects as go
import json
import time

from config import ASSETS, TIMEFRAMES, APP_ID, WS_URL
from src.data_fetcher import DataFetcher
from src.indicators import add_indicators

st.set_page_config(page_title="OtmAnalytics Pro", layout="wide")
st.title("📈 OtmAnalytics - Dashboard de Trading")

if 'fetcher' not in st.session_state:
    st.session_state.fetcher = DataFetcher()

# Sidebar
st.sidebar.header("Paramètres")
category = st.sidebar.selectbox("Marché", list(ASSETS.keys()))
symbol = st.sidebar.selectbox("Actif", ASSETS[category])
tf_label = st.sidebar.selectbox("Périodicité", list(TIMEFRAMES.keys()))
tf_sec = TIMEFRAMES[tf_label]

tab1, tab2 = st.tabs(["📥 Historique", "🔴 Live & IA"])

# --- ONGLET 1 : RÉCUPÉRATION ---
with tab1:
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Depuis le", date(2024, 1, 1))
    end_date = col2.date_input("Jusqu'au", date.today())

    if st.button("Lancer la récupération forcée", type="primary"):
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        bar = st.progress(0, "Initialisation...")
        count = st.session_state.fetcher.fetch_history_stream(symbol, tf_sec, start_dt, end_dt, bar)
        st.success(f"Opération terminée : {count} bougies enregistrées.")

    # Graphique
    df = st.session_state.fetcher.load_data(symbol, tf_sec)
    if not df.empty:
        df = add_indicators(df)
        fig = go.Figure(data=[go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# --- ONGLET 2 : LIVE ---
with tab2:
    st.subheader(f"Trading Live : {symbol}")
    
    c1, c2 = st.columns([1, 2])
    run_live = c1.toggle("Démarrer le flux temps réel")
    price_metric = c1.empty()
    chart_live = c2.empty()

    if run_live:
        # On utilise une connexion dédiée au live
        if st.session_state.fetcher.connect_ws():
            ws = st.session_state.fetcher.ws
            ws.send(json.dumps({"ticks": symbol}))
            
            history_prices = []
            last_p = 0.0

            while run_live:
                try:
                    data = json.loads(ws.recv())
                    if 'tick' in data:
                        p = data['tick']['quote']
                        diff = p - last_p if last_p != 0 else 0
                        price_metric.metric("Prix Actuel", f"{p:.2f}", f"{diff:.2f}")
                        
                        history_prices.append(p)
                        if len(history_prices) > 50: history_prices.pop(0)
                        
                        # Graphique simplifié
                        fig_l = go.Figure(go.Scatter(y=history_prices, mode='lines+markers', line=dict(color='#00ff00')))
                        fig_l.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0))
                        chart_live.plotly_chart(fig_l, use_container_width=True)
                        
                        last_p = p
                except:
                    st.session_state.fetcher.connect_ws() # Reconnexion auto
                    ws = st.session_state.fetcher.ws
                    ws.send(json.dumps({"ticks": symbol}))
                time.sleep(0.1)
