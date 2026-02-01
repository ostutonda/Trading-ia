import streamlit as st
import sqlite3
import pandas as pd
import config
from src.data_fetcher import fetch_and_save
from src.indicators import apply_indicators
from src.train_model import train_ia_model
from src.trader import live_prediction

st.set_page_config(page_title="Otm_ai_Trada", layout="wide")

# --- SIDEBAR ---
st.sidebar.header("\U0001f579\ufe0f Paramètres")

# Sélection Indice
cat = st.sidebar.selectbox("Catégorie", list(config.INDICES_CATEGORIES.keys()))
sym_nom = st.sidebar.selectbox("Indice", list(config.INDICES_CATEGORIES[cat].keys()))
sym_code = config.INDICES_CATEGORIES[cat][sym_nom]

# Sélection Timeframe
tf_nom = st.sidebar.selectbox("Timeframe", list(config.TIMEFRAMES.keys()))
tf_val = config.TIMEFRAMES[tf_nom]

# Nombre de bougies
nb_candles = st.sidebar.number_input("Bougies à extraire", min_value=100, max_value=250000, value=3000)

if st.sidebar.button("\U0001f4e5 Actualiser les données"):
    progress = st.progress(0)
    fetch_and_save(sym_code, tf_val, nb_candles, progress)
    st.sidebar.success("Données prêtes !")

st.sidebar.divider()

# Entra�nement
if st.sidebar.button("\U0001f393 Entraîner l'IA"):
    with st.spinner("Apprentissage..."):
        msg = train_ia_model()
        st.sidebar.success(msg)

# Mode Live
mode_live = st.sidebar.checkbox("\U0001f680 Activer signaux LIVE")

# --- CORPS PRINCIPAL ---
st.title(f"\U0001f4ca {sym_nom} | {tf_nom}")

try:
    conn = sqlite3.connect(config.DB_PATH)
    df_raw = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()

    if not df_raw.empty:
        df = apply_indicators(df_raw)
        
        # Affichage Signal Live si coch�
        if mode_live:
            signal, confiance = live_prediction(df_raw)
            color = "green" if "ACHAT" in signal else "red" if "VENTE" in signal else "gray"
            st.markdown(f"""
                <div style="background-color:rgba({255 if color=='red' else 0}, {255 if color=='green' else 0}, 0, 0.1); 
                            padding:20px; border-radius:10px; border:2px solid {color}; text-align:center;">
                    <h1 style="color:{color};">{signal}</h1>
                    <h3>Confiance : {confiance:.2%}</h3>
                </div>
            """, unsafe_allow_html=True)
            st.divider()

        # Graphiques
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Prix & Moyennes")
            st.line_chart(df.set_index('epoch')[['close', 'MA_5', 'EMA_100']])
        with col2:
            st.subheader("RSI (5)")
            st.line_chart(df.set_index('epoch')['RSI_5'])
            
        st.subheader("Stochastique (47, 14, 15)")
        st.line_chart(df.set_index('epoch')[['STOCHk_47_14_15', 'STOCHd_47_14_15']])
            
    else:
        st.info("Cliquez sur 'Actualiser les données' pour commencer.")

except Exception as e:
    st.warning("Aucune donnée détectée dans la base.")