# config.py
APP_ID = 122241
WS_URL = "wss://ws.deriv.com/websockets/v3"

# Listes d'actifs demandés
ASSETS = {
    'Forex / Métaux': ['frxXAUUSD'], # Gold
    'Volatilité': [f'R_{i}' for i in [10, 25, 50, 75, 100]],
    'Volatilité (1s)': [f'1HZ{i}V' for i in [10, 25, 50, 75, 100]],
    'Step Indices': ['STEP_INDEX'] 
}

# Timeframes en secondes (pour l'API) et label pour l'UI
TIMEFRAMES = {
    '1 Minute': 60,
    '2 Minutes': 120,
    '5 Minutes': 300,
    '15 Minutes': 900,
    '30 Minutes': 1800,
    '45 Minutes': 2700,
    '1 Heure': 3600
}

DB_PATH = 'database/trading_history.db'
MODEL_PATH = 'models/model_v1.h5'
SCALER_PATH = 'models/scaler.pkl'
