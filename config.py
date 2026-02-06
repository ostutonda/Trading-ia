
# config.py
import os

APP_ID = 122241
WS_URL = "wss://ws.deriv.com/websockets/v3"
DB_PATH = os.path.join("database", "trading_history.db")
MODEL_PATH = os.path.join("models", "model_v1.h5")

DERIV_TOKEN = "***********KBqI" # Token de compte Démo



ASSETS = {
    "Volatilité 10": "R_10",
    "Volatilité 25": "R_25",
    "Volatilité 50": "R_50",
    "Volatilité 75": "R_75",
    "Volatilité 100": "R_100",
    "Volatilité 10 (1s)": "1HZ10V",
    "Volatilité 25 (1s)": "1HZ25V",
    "Volatilité 50 (1s)": "1HZ50V",
    "Volatilité 75 (1s)": "1HZ75V",
    "Volatilité 100 (1s)": "1HZ100V",
    "Step Index": "STEP",
    "Gold (USD)": "frxXAUUSD"
}

TIMEFRAMES = {
    "1 minute": 60,
    "2 minutes": 120,
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "45 minutes": 2700,
    "1 heure": 3600
}
