# main.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import ssl
import websocket
from datetime import date, datetime

from config import ASSETS, TIMEFRAMES, APP_ID, WS_URL
from src.data_fetcher import DataFetcher
from src.indicators import add_indicators
from src.ml_logic import train_gru_model, predict_next

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="OtmAnalytics", layout="wide", page_icon="📈")

# Style CSS personnalisé pour améliorer l'UI
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 45px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 OtmAnalytics - Deriv.com AI Trader")

# Instanciation unique du fetcher dans la session
if 'fetcher' not in st.session_state:
    st.session_state.fetcher = DataFetcher()

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("⚙️ Configuration")

category = st.sidebar.selectbox("Catégorie", list(ASSETS.keys()))
symbol = st.sidebar.selectbox("Actif", ASSETS[category])
tf_label = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES.keys()))
tf_seconds = TIMEFRAMES[tf_label]

if st.sidebar.button("Tester Connexion Deriv"):
    if st.session_state.fetcher.connect_ws():
        st.sidebar.success("Connexion réussie !")
    else:
        st.sidebar.error("Échec connexion.")

# Affichage des statistiques de la base de données
def update_sidebar_stats():
    count = st.session_state.fetcher.get_stored_count(symbol, tf_seconds)
    st.sidebar.info(f"📁 Bougies en base : {count}")

update_sidebar_stats()

# --- ONGLETS PRINCIPAUX ---
tab1, tab2, tab3 = st.tabs(["📥 Données & Graphique", "🧠 Entraînement IA", "🔴 Trading Live"])

# --- TAB 1: DONNÉES HISTORIQUES ---
with tab1:
    st.subheader("Récupération de l'Historique")
    col1, col2 = st.columns(2)
    with col1:
        start_d = st.date_input("Date Début", date(2024, 1, 1))
    with col2:
        end_d = st.date_input("Date Fin", date.today())
    
    if st.button("Lancer le téléchargement", type="primary"):
        # Conversion en datetime pour le fetcher
        start_dt = datetime.combine(start_d, datetime.min.time())
        end_dt = datetime.combine(end_d, datetime.max.time())
        
        prog_bar = st.progress(0, text="Initialisation...")
        total = st.session_state.fetcher.fetch_history_stream(symbol, tf_seconds, start_dt, end_dt, prog_bar)
        
        if total > 0:
            st.success(f"✅ {total} bougies récupérées avec succès !")
            update_sidebar_stats()
        else:
            st.warning("⚠️ Aucune nouvelle bougie récupérée. Vérifiez vos dates ou votre connexion.")

    st.divider()
    
    # Chargement et Visualisation
    df = st.session_state.fetcher.load_data(symbol, tf_seconds)
    if not df.empty:
        df = add_indicators(df)
        
        st.subheader(f"Analyse Graphique : {symbol}")
        fig = go.Figure(data=[go.Candlestick(
            x=df['date'], open=df['open'], high=df['high'],
            low=df['low'], close=df['close'], name='Prix'
        )])
        
        # Ajout des indicateurs techniques au graphique
        fig.add_trace(go.Scatter(x=df['date'], y=df['MA5'], line=dict(color='orange', width=1.5), name='MA5'))
        fig.add_trace(go.Scatter(x=df['date'], y=df['SMMA35'], line=dict(color='cyan', width=1.5), name='SMMA35'))
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Consulter les données brutes"):
            st.dataframe(df.tail(100), use_container_width=True)
    else:
        st.info("💡 Utilisez le bouton ci-dessus pour charger des données historiques.")

# --- TAB 2: ENTRAINEMENT IA ---
with tab2:
    st.subheader("Intelligence Artificielle (GRU)")
    st.write("Le modèle analyse les 10 dernières bougies pour prédire un mouvement significatif (>= 2.5%).")
    
    if st.button("Entraîner le Modèle maintenant"):
        df_train = st.session_state.fetcher.load_data(symbol, tf_seconds)
        if df_train.empty or len(df_train) < 100:
            st.error("Données insuffisantes pour l'entraînement (min. 100 bougies requises).")
        else:
            with st.spinner("Calcul des indicateurs et optimisation des poids du GRU..."):
                df_train = add_indicators(df_train)
                result = train_gru_model(df_train)
                st.success(result)

# --- TAB 3: TRADING LIVE ---
with tab3:
    st.subheader("🔴 Terminal de Trading Live")
    
    col_live1, col_live2 = st.columns([1, 2])
    
    with col_live1:
        live_active = st.checkbox("Activer la connexion Live", value=False)
        st.divider()
        # Zone d'affichage dynamique pour le prix
        price_placeholder = st.empty()
        # Zone pour le signal IA
        signal_placeholder = st.empty()
        
    with col_live2:
        chart_live_placeholder = st.empty()

    if live_active:
        try:
            full_url = f"{WS_URL}?app_id={APP_ID}"
            ws = websocket.create_connection(full_url, sslopt={"cert_reqs": ssl.CERT_NONE})
            
            # Souscription au flux de ticks
            ws.send(json.dumps({"ticks": symbol}))
            
            last_price = 0.0
            tick_history = []
            
            while live_active:
                resp = ws.recv()
                data = json.loads(resp)
                
                if 'tick' in data:
                    price = float(data['tick']['quote'])
                    
                    # --- 1. AFFICHAGE PRIX ACTUEL ---
                    delta = price - last_price if last_price != 0 else 0
                    price_placeholder.metric(
                        label=f"PRIX LIVE : {symbol}",
                        value=f"{price:.2f}",
                        delta=f"{delta:.2f}"
                    )
                    last_price = price
                    
                    # --- 2. LOGIQUE SIGNAL IA ---
                    # On récupère les données récentes pour le calcul des indicateurs en live
                    df_live = st.session_state.fetcher.load_data(symbol, tf_seconds)
                    if len(df_live) > 40:
                        df_live = add_indicators(df_live)
                        # On prend les 10 dernières bougies avec indicateurs calculés
                        pred_class, conf = predict_next(df_live.tail(10))
                        
                        if pred_class is not None:
                            colors = {0: "gray", 1: "#00FF7F", 2: "#FF4B4B"}
                            labels = {0: "NEUTRE", 1: "ACHAT (BUY)", 2: "VENTE (SELL)"}
                            
                            signal_html = f"""
                            <div style="background-color:{colors[pred_class]}; padding:20px; border-radius:10px; text-align:center;">
                                <h2 style="color:white; margin:0;">{labels[pred_class]}</h2>
                                <p style="color:white; margin:5px 0 0 0;">Confiance : {conf:.1%}</p>
                            </div>
                            """
                            signal_placeholder.markdown(signal_html, unsafe_allow_html=True)

                    # --- 3. GRAPHIQUE TICK-BY-TICK ---
                    tick_history.append(price)
                    if len(tick_history) > 60: tick_history.pop(0)
                    
                    fig_tick = go.Figure()
                    fig_tick.add_trace(go.Scatter(y=tick_history, mode='lines+markers', line=dict(color='#00CC96')))
                    fig_tick.update_layout(
                        title="Flux Ticks (60 derniers)", 
                        height=400, 
                        template="plotly_dark",
                        margin=dict(l=0, r=0, t=30, b=0)
                    )
                    chart_live_placeholder.plotly_chart(fig_tick, use_container_width=True)

                if 'error' in data:
                    st.error(f"Erreur flux : {data['error']['message']}")
                    break
                
                # Petite pause pour laisser Streamlit respirer
                time.sleep(0.1)
                
        except Exception as e:
            st.error(f"❌ Erreur de connexion : {e}")