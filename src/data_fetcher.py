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

   # src/data_fetcher.py

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """
        Récupère TOUTES les bougies sans exception entre start_dt et end_dt.
        Gère les gaps de marché et la pagination par 5000.
        """
        if not self.ws or not self.ws.connected:
            if not self.connect_ws(): return 0

        # Conversion précise en timestamps
        start_epoch = int(start_dt.timestamp())
        target_end_epoch = int(end_dt.timestamp())
        
        current_ptr = start_epoch
        total_count = 0
        
        # Durée totale pour le calcul du % de progression
        total_duration = target_end_epoch - start_epoch
        if total_duration <= 0:
            st.warning("La date de fin doit être après le début.")
            return 0

        st.info(f"🚀 Récupération exhaustive pour {symbol}...")

        # Boucle tant qu'on n'a pas atteint la date cible
        while current_ptr < target_end_epoch:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "start": current_ptr,
                "end": target_end_epoch,
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            try:
                self.ws.send(json.dumps(req))
                resp = self.ws.recv()
                data = json.loads(resp)

                if 'error' in data:
                    # Si l'erreur dit que le start est après le end, on a fini
                    if "start time is after end time" in data['error']['message'].lower():
                        break
                    st.error(f"API Error: {data['error']['message']}")
                    break

                candles = data.get('candles', [])

                if not candles:
                    # --- GESTION DES GAPS (Week-ends / Maintenance) ---
                    # Si l'API ne renvoie rien, on avance le pointeur de 1 jour 
                    # pour chercher plus loin, sinon on reste bloqué dans le vide.
                    current_ptr += 86400 # Saut de 24h
                    if current_ptr > target_end_epoch:
                        break
                    continue

                # On prépare les données pour SQLite
                batch = []
                last_epoch_received = candles[-1]['epoch']
                
                for c in candles:
                    # Sécurité : on ne dépasse jamais la date de fin demandée
                    if c['epoch'] <= target_end_epoch:
                        batch.append((
                            symbol, timeframe_sec, c['epoch'],
                            c['open'], c['high'], c['low'], c['close']
                        ))

                # Sauvegarde immédiate du lot
                if batch:
                    self.save_to_db(batch)
                    total_count += len(batch)

                # Mise à jour de l'UI
                progress = min(1.0, (last_epoch_received - start_epoch) / total_duration)
                date_str = datetime.fromtimestamp(last_epoch_received).strftime('%Y-%m-%d %H:%M')
                progress_bar.progress(progress, text=f"📦 {total_count} bougies | Actuel: {date_str}")

                # --- CONDITION DE PROGRESSION ---
                # On repart de la dernière bougie reçue + timeframe pour ne pas avoir de doublon
                if last_epoch_received >= target_end_epoch:
                    break
                
                # Si on a reçu moins de 5000 bougies, on a peut-être atteint la fin des données dispo
                if len(candles) < 5000:
                    # On vérifie si on est proche du "Maintenant" (à 2 bougies près)
                    if last_epoch_received >= (int(time.time()) - (timeframe_sec * 2)):
                        break
                    else:
                        # On est sur un gap (ex: vendredi soir), on saute au lundi
                        current_ptr = last_epoch_received + 3600 # On avance d'une heure pour chercher
                else:
                    current_ptr = last_epoch_received + timeframe_sec

                # Respecter les limites de débit de l'API (Rate limiting)
                time.sleep(0.1)

            except Exception as e:
                st.error(f"Interruption : {e}")
                break

        progress_bar.progress(1.0, text=f"✅ Terminé : {total_count} bougies en base.")
        return total_count
 



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
