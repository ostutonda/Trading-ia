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

    def get_db_connection(self):
        return sqlite3.connect(DB_PATH)

    def init_db(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT,
                timeframe INTEGER,
                epoch INTEGER,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                PRIMARY KEY (symbol, timeframe, epoch)
            )
        ''')
        conn.commit()
        conn.close()

    def connect_ws(self):
        # --- GESTION SSL CONTEXT (Fix Pylance/Cert errors) ---
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            self.ws = websocket.create_connection(
                f"{WS_URL}?app_id={APP_ID}",
                sslopt={"cert_reqs": ssl.CERT_NONE}
            )
            return True
        except Exception as e:
            st.error(f"Erreur WebSocket: {e}")
            return False

    def get_stored_count(self, symbol, timeframe):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        if not self.ws or not self.ws.connected:
            if not self.connect_ws(): return

        start_epoch = int(start_dt.timestamp())
        end_epoch = int(end_dt.timestamp())
        current_start = start_epoch
        
        total_candles = 0
        
        # Estimer le nombre total de bougies pour la barre de progression
        estimated_total = (end_epoch - start_epoch) // timeframe_sec
        if estimated_total == 0: estimated_total = 1

        while current_start < end_epoch:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "end": "latest",
                "start": current_start,
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            self.ws.send(json.dumps(req))
            resp = self.ws.recv()
            data = json.loads(resp)

            if 'error' in data:
                st.error(f"API Error: {data['error']['message']}")
                break

            candles = data.get('candles', [])
            if not candles:
                break

            # Filtrage et Préparation
            batch_data = []
            last_epoch = candles[-1]['epoch']
            
            for c in candles:
                if c['epoch'] <= end_epoch:
                    batch_data.append((
                        symbol, timeframe_sec, c['epoch'],
                        c['open'], c['high'], c['low'], c['close']
                    ))
            
            # Sauvegarde DB
            self.save_to_db(batch_data)
            total_candles += len(batch_data)
            
            # Mise à jour UI
            prog = min(1.0, (current_start - start_epoch) / (end_epoch - start_epoch))
            progress_bar.progress(prog, text=f"Téléchargement: {total_candles} bougies...")

            if last_epoch == current_start: break
            current_start = last_epoch + 1
            time.sleep(0.2) # Rate limit protection

        progress_bar.progress(1.0, text="Téléchargement terminé !")
        return total_candles

    def save_to_db(self, data):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.executemany('INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?)', data)
        conn.commit()
        conn.close()

    def load_data(self, symbol, timeframe):
        conn = self.get_db_connection()
        df = pd.read_sql(
            "SELECT * FROM candles WHERE symbol=? AND timeframe=? ORDER BY epoch ASC",
            conn, params=(symbol, timeframe)
        )
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['epoch'], unit='s')
        return df
