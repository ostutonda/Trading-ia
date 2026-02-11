# test_api.py
import websocket
import json
import ssl
import time

# On utilise l'APP ID public de test pour être sûr que ce n'est pas un problème de compte
WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

def test_symbol(symbol_code):
    print(f"\n--- TEST DU SYMBOLE : {symbol_code} ---")
    try:
        ws = websocket.create_connection(WS_URL, sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # On demande simplement les 10 dernières bougies (1 minute)
        req = {
            "ticks_history": symbol_code,
            "adjust_start_time": 1,
            "count": 10,
            "end": "latest",
            "style": "candles",
            "granularity": 60 # 1 Minute
        }
        
        ws.send(json.dumps(req))
        resp = ws.recv()
        data = json.loads(resp)
        ws.close()
        
        if 'error' in data:
            print(f"❌ ERREUR API : {data['error']['code']} - {data['error']['message']}")
            return False
        elif 'candles' in data:
            count = len(data['candles'])
            print(f"✅ SUCCÈS : {count} bougies reçues !")
            print(f"   Dernière bougie : {data['candles'][-1]}")
            return True
        else:
            print(f"⚠️ Réponse bizarre : {data}")
            return False
            
    except Exception as e:
        print(f"❌ CRASH : {e}")
        return False

# Liste des symboles suspectés
symboles_a_tester = [
    "R_100",        # Volatility 100 Index (Le plus classique)
    "1HZ100V",      # Volatility 100 (1s) Index
    "R_10",         # Volatility 10 Index
    "frxXAUUSD",    # Gold / USD
    "step_index",   # Step Index (Souvent problématique sur la casse)
    "STEP_INDEX",   # Essayons en majuscule
    "STPRNG"        # Autre code possible pour Step
]

print("Démarrage du diagnostic réseau...")
for s in symboles_a_tester:
    test_symbol(s)
