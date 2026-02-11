# src/ml_logic.py
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import GRU, Dense, Dropout
from tensorflow.keras.utils import to_categorical
from sklearn.preprocessing import MinMaxScaler
import joblib
import os
from config import MODEL_PATH, SCALER_PATH

def prepare_data(df):
    """
    Features: close, MA5, SMMA35, RSI5, Stoch_K, Stoch_D
    Target: 
        0 = Neutre (< 2.5%)
        1 = Buy (>= 2.5%)
        2 = Sell (<= -2.5% mais on va utiliser la baisse comme classe séparée)
    """
    df['future_close'] = df['close'].shift(-1)
    df['pct_change'] = ((df['future_close'] - df['close']) / df['close']) * 100
    
    # Création des cibles (1: Hausse >= 2.5%, 2: Baisse >= 2.5% (approx), 0: Autres)
    # Note: Le prompt demande "2 si = 2", je suppose qu'on veut dire une classe distincte pour la baisse forte.
    conditions = [
        (df['pct_change'] >= 2.5),
        (df['pct_change'] <= -2.5) 
    ]
    choices = [1, 2]
    df['target'] = np.select(conditions, choices, default=0)
    
    feature_cols = ['close', 'MA5', 'SMMA35', 'RSI5', 'Stoch_K', 'Stoch_D']
    # Nettoyage des NaN générés par le shift et les indicateurs
    df_clean = df.dropna().copy()
    
    return df_clean[feature_cols].values, df_clean['target'].values

def build_model(input_shape):
    model = Sequential()
    # Couche 1
    model.add(GRU(64, return_sequences=True, input_shape=input_shape))
    model.add(Dropout(0.2))
    # Couche 2
    model.add(GRU(32, return_sequences=False))
    model.add(Dropout(0.2))
    # Sortie
    model.add(Dense(3, activation='softmax'))
    
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def train_gru_model(df):
    X_raw, y_raw = prepare_data(df)
    
    if len(X_raw) < 100:
        return "Pas assez de données pour l'entraînement."

    # Scaling
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X_raw)
    
    # Séquençage (Lookback)
    X, y = [], []
    look_back = 10 
    
    for i in range(look_back, len(X_scaled)):
        X.append(X_scaled[i-look_back:i])
        y.append(y_raw[i])
        
    X, y = np.array(X), np.array(y)
    y_cat = to_categorical(y, num_classes=3)
    
    # Création et Entraînement
    model = build_model((X.shape[1], X.shape[2]))
    history = model.fit(X, y_cat, epochs=10, batch_size=64, verbose=0)
    
    # Sauvegarde
    if not os.path.exists('models'): os.makedirs('models')
    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    
    acc = history.history['accuracy'][-1]
    return f"Modèle entraîné avec succès. Précision finale: {acc:.2%}"

def predict_next(df_window):
    """Prédit le mouvement basé sur les 10 dernières bougies"""
    try:
        if not os.path.exists(MODEL_PATH): return None, 0.0
        
        model = load_model(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        
        feature_cols = ['close', 'MA5', 'SMMA35', 'RSI5', 'Stoch_K', 'Stoch_D']
        data = df_window[feature_cols].values
        
        # Scale
        data_scaled = scaler.transform(data)
        # Reshape (1, 10, 6)
        X = data_scaled.reshape(1, 10, 6)
        
        pred_prob = model.predict(X, verbose=0)
        class_idx = np.argmax(pred_prob)
        confidence = np.max(pred_prob)
        
        return class_idx, confidence
    except Exception as e:
        return None, 0.0
