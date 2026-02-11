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

    # Dans src/data_fetcher.py

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """
        Récupère l'historique strictement entre start_dt et end_dt.
        """
        if not self.ws or not self.ws.connected:
            if not self.connect_ws(): return 0

        # Conversion en timestamps (Epoch)
        start_epoch = int(start_dt.timestamp())
        target_end_epoch = int(end_dt.timestamp())
        
        current_request_start = start_epoch
        total_candles_fetched = 0
        
        # Estimation pour la barre de progression
        total_duration = target_end_epoch - start_epoch
        if total_duration <= 0:
            st.warning("La date de fin doit être postérieure à la date de début.")
            return 0

        st.info(f"⏳ Téléchargement de {symbol} du {start_dt} au {end_dt}...")
        
        while current_request_start < target_end_epoch:
            # REQUÊTE API STRICTE : On donne le Debut ET la Fin précise
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,          # On demande le max par page
                "start": current_request_start,
                "end": target_end_epoch, # <--- ICI : On bloque la date de fin
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            try:
                self.ws.send(json.dumps(req))
                resp = self.ws.recv()
                data = json.loads(resp)

                if 'error' in data:
                    # Certaines erreurs (comme "Start time is after end time") signifient qu'on a fini
                    if "after end time" in data['error']['message']:
                        break
                    st.error(f"API Error: {data['error']['message']}")
                    break

                candles = data.get('candles', [])
                
                # Si l'API ne renvoie rien, c'est qu'il n'y a pas de données sur cette période (ex: Week-end)
                if not candles:
                    # On avance le curseur pour ne pas boucler indéfiniment
                    # On ajoute l'équivalent de 5000 bougies en secondes
                    current_request_start += (5000 * timeframe_sec)
                    continue

                # Filtrage supplémentaire de sécurité (bien que l'API respecte 'end')
                batch_data = []
                last_epoch = candles[-1]['epoch']
                
                for c in candles:
                    batch_data.append((
                        symbol, timeframe_sec, c['epoch'],
                        c['open'], c['high'], c['low'], c['close']
                    ))
                
                # Sauvegarde
                self.save_to_db(batch_data)
                total_candles_fetched += len(batch_data)

                # Mise à jour barre progression
                elapsed = last_epoch - start_epoch
                prog = min(1.0, max(0.0, elapsed / total_duration))
                progress_bar.progress(prog, text=f"Recupéré: {total_candles_fetched} bougies. (Date: {datetime.fromtimestamp(last_epoch)})")

                # --- CONDITIONS DE SORTIE ET AVANCEMENT ---
                
                # Si la dernière bougie reçue est >= à notre date de fin cible
                if last_epoch >= target_end_epoch:
                    break
                
                # Si on a reçu moins de 5000 bougies, c'est que l'API n'en a plus jusqu'à la date 'end'
                if len(candles) < 5000:
                    break

                # On avance le curseur : Start devient la fin du dernier batch + 1 seconde
                current_request_start = last_epoch + 1
                
                time.sleep(0.2) # Rate limit

            except Exception as e:
                st.error(f"Erreur boucle: {e}")
                break

        progress_bar.progress(1.0, text="✅ Terminé !")
        return total_candles_fetched
