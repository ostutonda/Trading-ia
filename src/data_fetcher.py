# src/data_fetcher.py
import json
import ssl
import sqlite3
import time
import websocket
import pandas as pd
from datetime import datetime
import streamlit as st
from config import APP_ID, WS_URL, DB_PATH

class DataFetcher:
    def __init__(self):
        self.ws = None
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT, timeframe INTEGER, epoch INTEGER,
                    open REAL, high REAL, low REAL, close REAL,
                    PRIMARY KEY (symbol, timeframe, epoch)
                )
            ''')

    def is_connected(self):
        """Vérifie si le socket est réellement ouvert."""
        try:
            return self.ws and self.ws.connected
        except:
            return False

    def connect_ws(self):
        """Tente une connexion avec gestion SSL."""
        try:
            self.ws = websocket.create_connection(
                f"{WS_URL}?app_id={APP_ID}",
                sslopt={"cert_reqs": ssl.CERT_NONE},
                timeout=10
            )
            return True
        except Exception as e:
            st.error(f"Échec de connexion : {e}")
            return False

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """Boucle de récupération robuste avec auto-reconnexion."""
        target_start = int(start_dt.timestamp())
        target_end = int(end_dt.timestamp())
        current_pointer = target_start
        total_saved = 0

        while current_pointer < target_end:
            # 1. Vérification / Réouverture de la connexion
            if not self.is_connected():
                if not self.connect_ws():
                    time.sleep(2) # Attendre avant de réessayer
                    continue

            # 2. Préparation de la requête par lots (max 5000)
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "start": current_pointer,
                "end": target_end,
                "style": "candles",
                "granularity": timeframe_sec
            }

            try:
                self.ws.send(json.dumps(req))
                response = json.loads(self.ws.recv())

                if 'error' in response:
                    st.error(f"Erreur API : {response['error']['message']}")
                    break

                candles = response.get('candles', [])
                if not candles:
                    # Si aucune donnée, on avance le curseur pour éviter la boucle infinie
                    current_pointer += 5000 * timeframe_sec
                    continue

                # 3. Traitement et sauvegarde
                batch = [
                    (symbol, timeframe_sec, c['epoch'], c['open'], c['high'], c['low'], c['close'])
                    for c in candles if c['epoch'] <= target_end
                ]
                
                self._save_batch(batch)
                total_saved += len(batch)
                
                # Mise à jour du pointeur pour le prochain lot
                last_epoch = candles[-1]['epoch']
                current_pointer = last_epoch + 1

                # 4. Feedback UI
                progress = min(1.0, (current_pointer - target_start) / (target_end - target_start))
                progress_bar.progress(progress, text=f"Récupéré : {total_saved} bougies...")

                # Pause respectueuse pour l'API
                time.sleep(0.3)

            except Exception as e:
                st.warning(f"Interruption détectée ({e}). Tentative de reconnexion...")
                self.ws = None # Forcer la reconnexion au prochain tour

        return total_saved

    def _save_batch(self, data):
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany('INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?)', data)

    def load_data(self, symbol, timeframe):
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(
                "SELECT * FROM candles WHERE symbol=? AND timeframe=? ORDER BY epoch ASC",
                conn, params=(symbol, timeframe)
            )
        if not df.empty:
            df['date'] = pd.to_datetime(df['epoch'], unit='s')
        return df
