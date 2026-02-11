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
        # Timeout augmenté pour éviter les blocages database is locked
        return sqlite3.connect(DB_PATH, timeout=10)

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
        """Établit une connexion WebSocket sécurisée."""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Construction de l'URL complète
            full_url = f"{WS_URL}?app_id={APP_ID}"
            self.ws = websocket.create_connection(
                full_url,
                sslopt={"cert_reqs": ssl.CERT_NONE},
                timeout=10
            )
            return True
        except Exception as e:
            st.error(f"Erreur WebSocket: {e}")
            return False

    def get_stored_count(self, symbol, timeframe):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe=?", (symbol, timeframe))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """Récupère l'historique en bouclant sur l'API Deriv (pagination)."""
        
        # 1. Connexion
        if not self.ws or not self.ws.connected:
            if not self.connect_ws():
                return 0

        start_epoch = int(start_dt.timestamp())
        target_end_epoch = int(end_dt.timestamp())
        
        # On commence la requête à partir du début
        current_request_start = start_epoch
        total_candles_fetched = 0
        
        # Estimation pour la barre de progression
        estimated_total_seconds = target_end_epoch - start_epoch
        if estimated_total_seconds <= 0:
            st.warning("La date de fin doit être après la date de début.")
            return 0

        st.write(f"📥 Démarrage du téléchargement pour {symbol}...")
        
        while current_request_start < target_end_epoch:
            # Deriv API Request: style 'candles'
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,        # Max autorisé par Deriv
                "end": "latest",      # On filtre manuellement, mais on demande jusqu'au bout
                "start": current_request_start,
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            try:
                self.ws.send(json.dumps(req))
                resp = self.ws.recv()
                data = json.loads(resp)

                if 'error' in data:
                    st.error(f"API Error ({data['error']['code']}): {data['error']['message']}")
                    break

                candles = data.get('candles', [])
                
                if not candles:
                    # Aucune donnée retournée pour cette période (ex: week-end ou marché fermé)
                    # On avance le curseur pour éviter une boucle infinie
                    current_request_start += (5000 * timeframe_sec)
                    continue

                # Filtrage et Préparation du Batch
                batch_data = []
                last_candle_epoch = candles[-1]['epoch']
                
                for c in candles:
                    # On ne garde que ce qui est <= à la date de fin demandée
                    if c['epoch'] <= target_end_epoch:
                        batch_data.append((
                            symbol, 
                            timeframe_sec, 
                            c['epoch'],
                            c['open'], c['high'], c['low'], c['close']
                        ))
                
                # Sauvegarde en DB
                if batch_data:
                    self.save_to_db(batch_data)
                    total_candles_fetched += len(batch_data)

                # Mise à jour barre de progression
                # On calcule le % basé sur le temps parcouru vs temps total
                time_covered = last_candle_epoch - start_epoch
                prog = min(1.0, time_covered / estimated_total_seconds)
                progress_bar.progress(prog, text=f"Récupéré: {total_candles_fetched} bougies... (Date atteinte: {datetime.fromtimestamp(last_candle_epoch)})")

                # Condition de sortie : Si la dernière bougie reçue dépasse ou égale notre cible
                if last_candle_epoch >= target_end_epoch:
                    break
                
                # Condition de sortie : Si l'API renvoie moins de bougies que demandé (fin des données dispos)
                if len(candles) < 500: # Seuil de sécurité
                    # Vérifions si nous sommes vraiment à la fin des temps (proche de "maintenant")
                    if last_candle_epoch > (time.time() - timeframe_sec*10):
                        break

                # Préparation prochaine itération
                # Important : On repart de la dernière epoch reçue + 1 seconde
                current_request_start = last_candle_epoch + 1
                
                # Pause anti-ban (Rate Limit)
                time.sleep(0.2)

            except Exception as e:
                st.error(f"Erreur durant la boucle: {e}")
                self.connect_ws() # Tentative de reconnexion
                time.sleep(1)

        progress_bar.progress(1.0, text="✅ Téléchargement terminé !")
        return total_candles_fetched

    def save_to_db(self, data):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.executemany('INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?)', data)
            conn.commit()
            conn.close()
        except Exception as e:
            st.error(f"Erreur DB: {e}")

    def load_data(self, symbol, timeframe):
        conn = self.get_db_connection()
        # On charge avec tri par epoch croissant
        df = pd.read_sql(
            "SELECT * FROM candles WHERE symbol=? AND timeframe=? ORDER BY epoch ASC",
            conn, params=(symbol, timeframe)
        )
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['epoch'], unit='s')
        return df
