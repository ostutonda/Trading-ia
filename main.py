# main.py
import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_lightweight_charts import renderLightweightCharts
import numpy as np

# Imports internes
from config import ASSETS, TIMEFRAMES, WS_URL
from src.data_fetcher import DerivClient
from src.ml_logic import TradingModel

# --- Configuration de la page ---
st.set_page_config(page_title="OtmAnalytics", layout="wide", page_icon="📈")

# --- Gestion de l'état (Session State) ---
if 'deriv' not in st.session_state:
    st.session_state.deriv = DerivClient()
if 'trading_model' not in st.session_state:
    st.session_state.trading_model = TradingModel()
if 'selected_asset_code' not in st.session_state:
    st.session_state.selected_asset_code = None

client = st.session_state.deriv

# --- Sidebar : Configuration ---
st.sidebar.title("⚙️ OtmAnalytics Config")

# 1. Connexion API
st.sidebar.subheader("Connexion Deriv API")
ws_status = st.sidebar.empty()

if client.connected:
    ws_status.success("Connecté à wss://ws.deriv.com")
else:
    ws_status.error("Déconnecté")

if st.sidebar.button("Tester Connexion / Reconnecter"):
    client.connect()
    time.sleep(1)
    st.rerun()

# 2. Paramètres Actifs
st.sidebar.markdown("---")
st.sidebar.subheader("Sélection Actif")

selected_asset_name = st.sidebar.selectbox("Choisir l'actif", list(ASSETS.keys()))
selected_asset_code = ASSETS[selected_asset_name]
st.session_state.selected_asset_code = selected_asset_code

# Info DB vs Live
db_pct = client.check_db_completeness(selected_asset_code)
st.sidebar.progress(db_pct / 100, text=f"Données locales: {db_pct}% à jour")

timeframe_name = st.sidebar.selectbox("Timeframe", list(TIMEFRAMES.keys()))
granularity = TIMEFRAMES[timeframe_name]

# 3. Paramètres Date
st.sidebar.markdown("---")
mode_date = st.sidebar.radio("Mode Période", ["Plage de dates", "Date unique"])
if mode_date == "Plage de dates":
    d_start = st.sidebar.date_input("Début", datetime.now() - timedelta(days=7))
    d_end = st.sidebar.date_input("Fin", datetime.now())
else:
    d_single = st.sidebar.date_input("Date", datetime.now())
    d_start = d_single
    d_end = d_single + timedelta(days=1)

# --- Interface Principale ---

tab1, tab2, tab3 = st.tabs(["📊 Dashboard Live", "💾 Données & Historique", "🧠 IA & Backtesting"])

# === TAB 1: DASHBOARD ===
with tab1:
    st.subheader(f"Suivi Temps Réel: {selected_asset_name}")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Zone Graphique (Chart.js / TradingView style via Streamlit wrapper)
        # On charge un peu d'historique DB pour afficher le graph
        df_display = client.get_db_data(selected_asset_code)
        
        if not df_display.empty:
            # Formatage pour lightweight-charts
            candles_data = []
            for index, row in df_display.tail(200).iterrows():
                candles_data.append({
                    "time": int(index.timestamp()),
                    "open": row['open'],
                    "high": row['high'],
                    "low": row['low'],
                    "close": row['close']
                })

            chart_options = {
                "layout": {"textColor": "white", "background": {"type": "solid", "color": "#1E1E1E"}},
                "grid": {"vertLines": {"color": "#333"}, "horzLines": {"color": "#333"}}
            }
            
            series = [{
                "type": "Candlestick",
                "data": candles_data,
                "options": {
                    "upColor": "#26a69a",
                    "downColor": "#ef5350",
                    "borderVisible": False,
                    "wickUpColor": "#26a69a",
                    "wickDownColor": "#ef5350"
                }
            }]
            
            st.markdown("### Graphique Technique")
            renderLightweightCharts(series, options=chart_options, height=400)
        else:
            st.info("Aucune donnée historique trouvée. Veuillez télécharger les données dans l'onglet 'Données'.")

    with col2:
        st.markdown("### Prix Live")
        price_placeholder = st.empty()
        
        # Abonnement Live
        if client.connected:
            client.subscribe(selected_asset_code)
            
            # Affichage boucle simple (simulation temps réel dans Streamlit)
            # Note: En prod, on utiliserait st.experimental_rerun() avec parcimonie ou stream
            if client.latest_tick['symbol'] == selected_asset_code:
                price = client.latest_tick['price']
                price_placeholder.metric("Prix", f"{price:.2f}")
            else:
                price_placeholder.markdown("En attente de tick...")
        
        st.markdown("---")
        st.markdown("### Prédiction IA")
        # Placeholder pour l'ordre
        st.info("ORDRE: --")
        st.text("Entrée: --")
        st.text("TP: --")
        st.text("SL: --")

# === TAB 2: DONNÉES ===
with tab2:
    st.header("Gestion des Données Historiques")
    
    st.write(f"Télécharger les données pour **{selected_asset_name}** ({timeframe_name})")
    
    if st.button("Lancer le téléchargement"):
        start_epoch = int(datetime.combine(d_start, datetime.min.time()).timestamp())
        end_epoch = int(datetime.combine(d_end, datetime.max.time()).timestamp())
        
        progress_bar = st.progress(0, text="Initialisation...")
        
        def update_prog(p):
            progress_bar.progress(p, text=f"Sauvegarde en cours: {int(p*100)}%")
            
        count = client.fetch_and_store_history(selected_asset_code, granularity, start_epoch, end_epoch, update_prog)
        
        progress_bar.progress(100, text="Terminé !")
        st.success(f"{count} bougies sauvegardées dans SQLite.")

    st.markdown("---")
    st.subheader("Aperçu de la Base de Données")
    df = client.get_db_data(selected_asset_code)
    st.dataframe(df.tail(10))

# === TAB 3: IA & BACKTESTING ===
with tab3:
    st.header("Modèle GRU & Backtesting")
    
    col_train, col_test = st.columns(2)
    
    with col_train:
        st.subheader("Entraînement")
        st.write("Architecture: 2 couches GRU, Dropout 0.2, Softmax, Batch 64")
        
        if st.button("Entraîner le modèle (Nouveau)"):
            with st.spinner("Chargement des données et calcul des indicateurs..."):
                df_train = client.get_db_data(selected_asset_code)
                if not df_train.empty:
                    res = st.session_state.trading_model.train(df_train)
                    st.success(res)
                else:
                    st.error("Base de données vide pour cet actif.")
                    
    with col_test:
        st.subheader("Backtesting")
        if st.button("Lancer Backtest sur Historique"):
            df_bt = client.get_db_data(selected_asset_code)
            if not df_bt.empty:
                results = st.session_state.trading_model.backtest(df_bt)
                if not results.empty:
                    st.dataframe(results)
                    
                    # Stats sommaires
                    total_trades = len(results)
                    wins = len(results[results['Resultat'] > 0])
                    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
                    profit = results['Resultat'].sum()
                    
                    st.metric("Profit Total", f"{profit:.2f}")
                    st.metric("Win Rate", f"{win_rate:.2f}%")
                    st.line_chart(results['Balance'])
                else:
                    st.warning("Pas assez de données ou pas de modèle chargé.")
            else:
                st.error("Pas de données.")

# Refresh automatique pour le Live tick (méthode simple)
if client.connected:
    time.sleep(1)
    st.rerun()
