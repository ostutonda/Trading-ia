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
        return sqlite3.connect(DB_PATH, timeout=10)

    def init_db(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        # On ajoute une contrainte UNIQUE pour éviter les doublons
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
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        try:
            full_url = f"{WS_URL}?app_id={APP_ID}"
            self.ws = websocket.create_connection(
                full_url, sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=10
            )
            return True
        except Exception as e:
            st.error(f"Erreur Connexion WebSocket: {e}")
            return False

    def count_period(self, symbol, timeframe, start_dt, end_dt):
        """Compte les bougies existantes DANS l'intervalle choisi."""
        try:
            start_epoch = int(start_dt.timestamp())
            end_epoch = int(end_dt.timestamp())
            conn = self.get_db_connection()
            cursor = conn.cursor()
            query = """
                SELECT COUNT(*) FROM candles 
                WHERE symbol=? AND timeframe=? 
                AND epoch >= ? AND epoch <= ?
            """
            cursor.execute(query, (symbol, timeframe, start_epoch, end_epoch))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

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

    def save_to_db(self, data):
        if not data: return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.executemany('INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?)', data)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erreur DB Save: {e}")

    def fetch_history_reverse(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """
        Récupère l'historique en partant de la FIN vers le DÉBUT (Reverse).
        C'est plus fiable pour éviter les blocages sur les dates vides.
        """
        if not self.ws or not self.ws.connected:
            if not self.connect_ws(): return 0

        start_epoch = int(start_dt.timestamp())
        end_epoch = int(end_dt.timestamp())
        
        # Le curseur commence à la fin
        current_request_end = end_epoch
        total_fetched = 0
        
        # Pour la barre de progression (inversée visuellement)
        total_duration = end_epoch - start_epoch
        
        st.info(f"🔙 Démarrage récupération inversée (du {end_dt} vers {start_dt})...")

        while current_request_end > start_epoch:
            # On demande 5000 bougies qui se terminent à 'current_request_end'
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "end": current_request_end,
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            try:
                self.ws.send(json.dumps(req))
                resp = self.ws.recv()
                data = json.loads(resp)

                if 'error' in data:
                    st.error(f"API Error: {data['error']['message']}")
                    break

                candles = data.get('candles', [])

                if not candles:
                    # Si vide, on essaie de sauter une semaine en arrière pour trouver des données
                    current_request_end -= (86400 * 7)
                    continue

                # Filtrage : On ne garde que ce qui est >= start_epoch
                # Les bougies arrivent du plus vieux [0] au plus récent [-1]
                batch_data = []
                oldest_candle_epoch = candles[0]['epoch']
                
                for c in candles:
                    if c['epoch'] >= start_epoch and c['epoch'] <= end_epoch:
                        batch_data.append((
                            symbol, timeframe_sec, c['epoch'],
                            c['open'], c['high'], c['low'], c['close']
                        ))

                self.save_to_db(batch_data)
                total_fetched += len(batch_data)

                # --- MISE A JOUR BARRE PROGRESSION ---
                # Plus oldest_candle_epoch se rapproche de start_epoch, plus on a fini.
                covered = end_epoch - oldest_candle_epoch
                prog = min(1.0, max(0.0, covered / total_duration))
                current_date_str = datetime.fromtimestamp(oldest_candle_epoch).strftime('%Y-%m-%d')
                progress_bar.progress(prog, text=f"📥 {total_fetched} bougies... (Arrivé au : {current_date_str})")

                # --- CONDITION DE SORTIE ---
                # Si la plus vieille bougie reçue est déjà avant notre date de début, on a tout.
                if oldest_candle_epoch <= start_epoch:
                    break
                
                # --- PREPARATION DU PROCHAIN BATCH ---
                # On demande la suite en finissant juste avant la plus vieille bougie reçue
                current_request_end = oldest_candle_epoch - 1
                
                time.sleep(0.2) # Pause anti-ban

            except Exception as e:
                st.error(f"Erreur fetch loop: {e}")
                self.connect_ws()
                time.sleep(1)

        progress_bar.progress(1.0, text=f"✅ Terminé ! {total_fetched} bougies sauvegardées.")
        return total_fetched
