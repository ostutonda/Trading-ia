# src/data_fetcher.py
import json
import websocket
import sqlite3
import threading
import time
import pandas as pd
from datetime import datetime
from config import APP_ID, WS_URL, DB_PATH

class DerivClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.latest_tick = {"price": 0.0, "symbol": ""}
        self.error_msg = None
        
        # Init DB
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS candles 
                     (symbol TEXT, epoch INTEGER, open REAL, high REAL, low REAL, close REAL, 
                     PRIMARY KEY (symbol, epoch))''')
        conn.commit()
        conn.close()

    # --- WebSocket Live ---
    def connect(self):
        def on_message(ws, message):
            data = json.loads(message)
            if 'tick' in data:
                self.latest_tick = {
                    "price": data['tick']['quote'],
                    "symbol": data['tick']['symbol']
                }
            if 'error' in data:
                self.error_msg = data['error']['message']

        def on_open(ws):
            self.connected = True
            print("WS Connected")

        def on_close(ws, *args):
            self.connected = False
            print("WS Closed")

        self.ws = websocket.WebSocketApp(
            f"{WS_URL}?app_id={APP_ID}",
            on_message=on_message,
            on_open=on_open,
            on_close=on_close
        )
        
        # Lancer dans un thread pour ne pas bloquer Streamlit
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def subscribe(self, symbol):
        if self.connected:
            req = {"ticks": symbol, "subscribe": 1}
            self.ws.send(json.dumps(req))
            return True
        return False

    # --- Gestion Historique & DB ---
    def fetch_and_store_history(self, symbol, granularity, start_epoch, end_epoch, progress_callback):
        """Récupère l'historique par paquets et stocke en DB"""
        
        # Deriv API candles limit is usually 1000 or 5000 depending on call
        # On va simplifier en demandant 'candles'
        
        # Connexion temporaire synchrone pour le téléchargement
        ws_sync = websocket.create_connection(f"{WS_URL}?app_id={APP_ID}")
        
        try:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000, # Max possible
                "end": end_epoch,
                "start": start_epoch,
                "style": "candles",
                "granularity": granularity
            }
            
            ws_sync.send(json.dumps(req))
            res = ws_sync.recv()
            data = json.loads(res)
            
            if 'candles' in data:
                candles = data['candles']
                total = len(candles)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                
                for i, candle in enumerate(candles):
                    c.execute("INSERT OR IGNORE INTO candles VALUES (?, ?, ?, ?, ?, ?)",
                              (symbol, candle['epoch'], candle['open'], candle['high'], candle['low'], candle['close']))
                    
                    if i % 50 == 0 and progress_callback:
                        progress_callback(i / total)
                
                conn.commit()
                conn.close()
                return total
            elif 'error' in data:
                print("API Error:", data['error'])
                return 0
                
        except Exception as e:
            print(f"Error fetching history: {e}")
            return 0
        finally:
            ws_sync.close()

    def get_db_data(self, symbol):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"SELECT * FROM candles WHERE symbol='{symbol}' ORDER BY epoch ASC", conn)
        conn.close()
        if not df.empty:
            df['date'] = pd.to_datetime(df['epoch'], unit='s')
            df.set_index('date', inplace=True)
        return df

    def check_db_completeness(self, symbol):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"SELECT MAX(epoch) FROM candles WHERE symbol='{symbol}'")
        last_epoch = cursor.fetchone()[0]
        conn.close()
        
        if not last_epoch:
            return 0
        
        now = int(time.time())
        # Estimation très brute
        diff = now - last_epoch
        # Si la dernière donnée date d'il y a longtemps, le % est faible
        # On considère "complet" si moins de 1h de décalage
        if diff < 3600: return 100
        return 50 # Valeur arbitraire pour l'exemple UI
