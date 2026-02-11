import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import json
import ssl
import websocket
from datetime import date, datetime, timedelta

from config import ASSETS, TIMEFRAMES, APP_ID, WS_URL
from src.data_fetcher import DataFetcher
from src.indicators import add_indicators
from src.ml_logic import train_gru_model, predict_next

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="OtmAnalytics", layout="wide", page_icon="📈")
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 36px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 OtmAnalytics - Deriv Trader (Reverse Fetch)")

if 'fetcher' not in st.session_state:
    st.session_state.fetcher = DataFetcher()

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
category = st.sidebar.selectbox("Catégorie", list(ASSETS.keys()))
symbol = st.sidebar.selectbox("Actif", ASSETS[category])
tf_label = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES.keys()))
tf_seconds = TIMEFRAMES[tf_label]

if st.sidebar.button("Test Connexion"):
    if st.session_state.fetcher.connect_ws():
        st.sidebar.success("Connecté !")
    else:
        st.sidebar.error("Erreur.")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📥 Données", "🧠 Modèle IA", "🔴 Live Trading"])

# --- TAB 1 : DONNÉES ---
with tab1:
    st.subheader("Gestion de l'Historique")
    
    col1, col2 = st.columns(2)
    with col1:
        # Par défaut, 1 mois en arrière
        default_start = date.today() - timedelta(days=30)
        start_d = st.date_input("Date DÉBUT (Min)", default_start)
    with col2:
        end_d = st.date_input("Date FIN (Max)", date.today())

    # --- AFFICHAGE DU NOMBRE DE BOUGIES EXISTANTES ---
    start_dt = datetime.combine(start_d, datetime.min.time())
    end_dt = datetime.combine(end_d, datetime.max.time())
    
    # On compte ce qu'on a déjà en base pour cet intervalle précis
    existing_count = st.session_state.fetcher.count_period(symbol, tf_seconds, start_dt, end_dt)
    
    # Affichage stylé avec des colonnes
    m1, m2 = st.columns(2)
    m1.metric("Bougies existantes (Intervalle)", f"{existing_count}")
    
    st.markdown("---")
    
    if st.button("🔄 Lancer le Téléchargement (Fin -> Début)", type="primary"):
        prog_bar = st.progress(0, text="Connexion...")
        # Appel de la méthode REVERSE
        new_count = st.session_state.fetcher.fetch_history_reverse(symbol, tf_seconds, start_dt, end_dt, prog_bar)
        
        st.success(f"Opération terminée. {new_count} bougies ajoutées/mises à jour.")
        time.sleep(1)
        st.rerun() # Rafraîchir pour mettre à jour le compteur

    # Graphique
    st.divider()
    df = st.session_state.fetcher.load_data(symbol, tf_seconds)
    
    if not df.empty:
        # Filtre local pour l'affichage graphique uniquement sur la période
        mask = (df['date'] >= pd.Timestamp(start_dt)) & (df['date'] <= pd.Timestamp(end_dt))
        df_view = df.loc[mask]
        
        if not df_view.empty:
            df_view = add_indicators(df_view)
            fig = go.Figure(data=[go.Candlestick(
                x=df_view['date'], open=df_view['open'], high=df_view['high'],
                low=df_view['low'], close=df_view['close'], name='Prix'
            )])
            fig.add_trace(go.Scatter(x=df_view['date'], y=df_view['MA5'], line=dict(color='orange'), name='MA5'))
            fig.update_layout(height=500, template="plotly_dark", title=f"{symbol} ({tf_label})")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Des données existent, mais pas dans l'intervalle de dates sélectionné ci-dessus.")
    else:
        st.info("Base de données vide pour cet actif.")

# --- TAB 2 : IA ---
with tab2:
    st.write("Entraînement sur les données téléchargées.")
    if st.button("Entraîner le Modèle"):
        df_train = st.session_state.fetcher.load_data(symbol, tf_seconds)
        if len(df_train) > 100:
            df_train = add_indicators(df_train)
            with st.spinner("Entraînement..."):
                res = train_gru_model(df_train)
                st.success(res)
        else:
            st.error("Pas assez de données.")

# --- TAB 3 : LIVE ---
with tab3:
    st.header("🔴 Live Market")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        live_on = st.checkbox("Activer Connexion Live")
        st.divider()
        price_metric = st.empty()
        signal_box = st.empty()
        
    with c2:
        chart_live = st.empty()

    if live_on:
        try:
            full_url = f"{WS_URL}?app_id={APP_ID}"
            ws = websocket.create_connection(full_url, sslopt={"cert_reqs": ssl.CERT_NONE})
            ws.send(json.dumps({"ticks": symbol}))
            
            last_p = 0.0
            ticks = []
            
            while live_on:
                data = json.loads(ws.recv())
                if 'tick' in data:
                    p = float(data['tick']['quote'])
                    delta = p - last_p if last_p != 0 else 0
                    
                    price_metric.metric("Prix", f"{p:.2f}", f"{delta:.2f}")
                    last_p = p
                    
                    # Logique Signal Simple
                    df_live = st.session_state.fetcher.load_data(symbol, tf_seconds)
                    if len(df_live) > 50:
                        df_live = add_indicators(df_live)
                        pred, conf = predict_next(df_live.tail(10))
                        
                        color = "gray"
                        txt = "ATTENTE"
                        if pred == 1: color, txt = "#00FF00", "ACHAT 🚀"
                        if pred == 2: color, txt = "#FF0000", "VENTE 📉"
                        
                        signal_box.markdown(f"""
                        <div style='background:{color};padding:15px;text-align:center;border-radius:10px;'>
                            <h3 style='margin:0;color:black;'>{txt}</h3>
                            <small style='color:black;'>Confiance: {conf:.1%}</small>
                        </div>
                        """, unsafe_allow_html=True)

                    # Graphique Tick
                    ticks.append(p)
                    if len(ticks) > 50: ticks.pop(0)
                    f_live = go.Figure(go.Scatter(y=ticks))
                    f_live.update_layout(height=300, margin=dict(t=0,b=0,l=0,r=0), template="plotly_dark")
                    chart_live.plotly_chart(f_live, use_container_width=True)

                time.sleep(0.05)
        except Exception as e:
            st.error(f"Erreur Live: {e}")
