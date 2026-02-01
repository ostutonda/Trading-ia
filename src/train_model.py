import sqlite3
import pandas as pd
import numpy as np
import config
from src.indicators import apply_indicators
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential # type: ignore
from tensorflow.keras.layers import Dense, Dropout # type: ignore
import os

def train_ia_model():
    # 1. Chargement des données
    conn = sqlite3.connect(config.DB_PATH)
    df_raw = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()

    if len(df_raw) < 500:
        return "Pas assez de données pour l'entraînement (min 500)."

    # 2. Calcul des indicateurs
    df = apply_indicators(df_raw)

    # 3. Création de la cible (Target)
    # On veut prédire si le prix sera PLUS HAUT dans 5 bougies (1 = Oui, 0 = Non)
    df['target'] = (df['close'].shift(-5) > df['close']).astype(int)
    df.dropna(inplace=True)

    # 4. Sélection des caractéristiques (Features)
    features = ['RSI_5', 'EMA_100', 'MA_5', 'STOCHk_47_14_15', 'STOCHd_47_14_15']
    X = df[features].values
    y = df['target'].values

    # 5. Normalisation (Mettre tout entre 0 et 1)
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)

    # 6. Architecture du Réseau de Neurones
    model = Sequential([
        Dense(64, activation='relu', input_shape=(len(features),)),
        Dropout(0.2), # Pour éviter que l'IA n'apprenne par cœur (overfitting)
        Dense(32, activation='relu'),
        Dense(16, activation='relu'),
        Dense(1, activation='sigmoid') # Sortie : probabilité entre 0 et 1
    ])

    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

    # 7. Entraînement
    print("🧠 Entraînement en cours...")
    model.fit(X_scaled, y, epochs=20, batch_size=32, verbose=0)

    # 8. Sauvegarde
    if not os.path.exists('models'): os.makedirs('models')
    model.save('models/mon_ia_deriv.h5')
    
    return "✅ Modèle entraîné et sauvegardé dans models/mon_ia_deriv.h5"