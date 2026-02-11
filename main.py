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


# Dans main.py, remplace tout le contenu sous "with tab3:" par ceci :

with tab3:
    st.header("🔴 Trading en Temps Réel")
    
    col_live1, col_live2 = st.columns([1, 3])
    
    with col_live1:
        live_active = st.checkbox("Activer Connexion Live", value=False)
        st.divider()
        # --- PLACEHOLDERS POUR LE PRIX ---
        price_display = st.empty()
        status_display = st.empty()
        
    with col_live2:
        chart_placeholder = st.empty()
        
    if live_active:
        import ssl
        
        # Connexion dédiée au Live (Tick Stream)
        try:
            full_url = f"{WS_URL}?app_id={APP_ID}"
            ws_live = websocket.create_connection(full_url, sslopt={"cert_reqs": ssl.CERT_NONE})
            
            # S'abonner au flux de ticks pour l'actif choisi
            ws_live.send(json.dumps({"ticks": symbol}))
            
            live_prices = []
            last_price = 0.0
            
            status_display.info("En attente de ticks...")
            
            while live_active:
                resp = ws_live.recv()
                data = json.loads(resp)
                
                if 'tick' in data:
                    # Récupération du prix
                    current_price = float(data['tick']['quote'])
                    epoch = data['tick']['epoch']
                    
                    # --- AFFICHAGE DU PRIX (GROS) ---
                    delta = 0.0
                    if last_price > 0:
                        delta = current_price - last_price
                        
                    price_display.metric(
                        label=f"Prix {symbol}",
                        value=f"{current_price:.2f}",
                        delta=f"{delta:.2f}" # Affiche la variation en vert/rouge auto
                    )
                    
                    last_price = current_price
                    
                    # --- MISE A JOUR GRAPHIQUE LIVE ---
                    live_prices.append(current_price)
                    if len(live_prices) > 100: live_prices.pop(0) # Garder les 100 derniers ticks
                    
                    fig_live = go.Figure()
                    fig_live.add_trace(go.Scatter(
                        y=live_prices, 
                        mode='lines',
                        line=dict(color='#00CC96')
                    ))
                    fig_live.update_layout(
                        title="Flux Ticks (Temps Réel)",
                        margin=dict(l=0, r=0, t=30, b=0),
                        height=350,
                        template="plotly_dark"
                    )
                    chart_placeholder.plotly_chart(fig_live, use_container_width=True)
                    
                    # Ici tu pourras ajouter ta logique de prédiction IA plus tard...
                    
                # Gestion erreurs API live
                if 'error' in data:
                    status_display.error(f"Erreur Live: {data['error']['message']}")
                    break
                    
        except Exception as e:
            st.error(f"Erreur de connexion Live: {e}")
            live_active = False
