# config.py
APP_ID = 122241  # Remplacez par votre ID si nécessaire
WS_URL = "wss://ws.derivws.com/websockets/v3"

ASSETS = {
    'Forex / Métaux': ['frxXAUUSD'],
    'Volatilité': [f'R_{i}' for i in [10, 25, 50, 75, 100]],
    'Volatilité (1s)': [f'1HZ{i}V' for i in [10, 25, 50, 75, 100]],
    'Step Indices': ['STEP_INDEX'] 
}

TIMEFRAMES = {
    '1 Minute': 60,
    '5 Minutes': 300,
    '15 Minutes': 900,
    '1 Heure': 3600
}

DB_PATH = 'database/trading_history.db'
MODEL_PATH = 'models/model_v1.h5'
SCALER_PATH = 'models/scaler.pkl'
