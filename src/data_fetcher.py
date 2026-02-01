import websocket
import json
import sqlite3
import pandas as pd
import config

def fetch_and_save(symbol, timeframe, count, progress_bar):
    ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={config.APP_ID}"
    
    def on_open(ws):
        # On demande l'historique
        msg = {
            "ticks_history": symbol,
            "end": "latest",
            "style": "candles",
            "granularity": timeframe,
            "count": count
        }
        ws.send(json.dumps(msg))

    def on_message(ws, message):
        data = json.loads(message)
        if 'candles' in data:
            df = pd.DataFrame(data['candles'])
            conn = sqlite3.connect(config.DB_PATH)
            # On remplace les anciennes données par les nouvelles pour cet indice
            df.to_sql('market_data', conn, if_exists='replace', index=False)
            conn.close()
            progress_bar.progress(100) # Terminé
            ws.close()

    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
    ws.run_forever()