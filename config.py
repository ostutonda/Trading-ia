# Configuration de l'API
APP_ID = "122241" # Ton APP_ID
DB_PATH = "database/trading_history.db"
DERIV_TOKEN = "***********KBqI" # Token de compte Démo

# Dictionnaire complet des indices par catégorie
INDICES_CATEGORIES = {
    "Indices de Volatilité": {
        "Volatility 10": "R_10",
        "Volatility 25": "R_25",
        "Volatility 50": "R_50",
        "Volatility 75": "R_75",
        "Volatility 100": "R_100"
    },
    "Indices de Volatilité (1s)": {
        "Volatility 10 (1s)": "1HZ10V",
        "Volatility 25 (1s)": "1HZ25V",
        "Volatility 50 (1s)": "1HZ50V",
        "Volatility 75 (1s)": "1HZ75V",
        "Volatility 100 (1s)": "1HZ100V"
    },
    "Step Indices": {
        "Step Index": "R_STP",
        "Step Index 200": "STP_200",
        "Step Index 500": "STP_500"
    }
}

# Configuration des Timeframes (en secondes)
TIMEFRAMES = {
    "1 minute": 60,
    "2 minutes": 120,
    "3 minutes": 180,
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 heure": 3600,
    "4 heure": 1400
}