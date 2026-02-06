# src/ml_logic.py
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import GRU, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
from config import MODEL_PATH
from src.indicators import add_indicators

class TradingModel:
    def __init__(self):
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        
    def prepare_data(self, df, lookback=60):
        """
        Prépare les séquences pour le GRU et calcule la Target.
        Target: 0=Neutre, 1=Achat (>2.5%), 2=Vente (< -2.5%)
        """
        df = add_indicators(df)
        if len(df) < lookback: return None, None, None

        # Création de la target (futur)
        # On regarde le max variation sur les 5 prochaines bougies
        future_period = 5
        df['future_close'] = df['close'].shift(-future_period)
        df['pct_change'] = (df['future_close'] - df['close']) / df['close'] * 100

        conditions = [
            (df['pct_change'] >= 2.5),  # Achat
            (df['pct_change'] <= -2.5)  # Vente
        ]
        choices = [1, 2]
        df['target'] = np.select(conditions, choices, default=0)
        
        # Drop NaN générés par shift et indicateurs
        df.dropna(inplace=True)
        
        features = ['close', 'MA5', 'SMMA35', 'RSI5', 'STOCH_K', 'STOCH_D']
        dataset = df[features].values
        y = df['target'].values
        
        scaled_data = self.scaler.fit_transform(dataset)
        
        X, Y = [], []
        for i in range(lookback, len(scaled_data)):
            X.append(scaled_data[i-lookback:i])
            Y.append(y[i])
            
        return np.array(X), np.array(Y), df.index[lookback:]

    def build_gru(self, input_shape):
        model = Sequential()
        # Couche 1 GRU
        model.add(GRU(units=50, return_sequences=True, input_shape=input_shape))
        model.add(Dropout(0.2)) # Dropout temporel 0.2
        
        # Couche 2 GRU
        model.add(GRU(units=50, return_sequences=False))
        model.add(Dropout(0.2))
        
        # Dense Softmax
        model.add(Dense(3, activation='softmax'))
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        return model

    def train(self, df):
        X, y, _ = self.prepare_data(df)
        if X is None or len(X) == 0:
            return "Pas assez de données."

        self.model = self.build_gru((X.shape[1], X.shape[2]))
        
        # Batch size 64
        history = self.model.fit(X, y, epochs=5, batch_size=64, validation_split=0.1, verbose=0)
        self.model.save(MODEL_PATH)
        
        acc = history.history['accuracy'][-1]
        return f"Modèle entraîné. Précision: {acc:.2%}"

    def predict(self, df_recent):
        """Prédiction sur les dernières données live"""
        try:
            self.model = load_model(MODEL_PATH)
        except:
            return None
            
        # On suppose que df_recent contient les 60 bougies nécessaires + indicateurs calculés
        # Simplified process
        pass 

    def backtest(self, df):
        """Simule le trading sur l'historique"""
        X, y, indices = self.prepare_data(df)
        if self.model is None:
            try:
                self.model = load_model(MODEL_PATH)
            except:
                return pd.DataFrame() # Vide

        predictions = self.model.predict(X, verbose=0)
        pred_classes = np.argmax(predictions, axis=1)
        
        # Simulation simple
        results = []
        balance = 1000
        
        for i, signal in enumerate(pred_classes):
            if signal == 0: continue
            
            price = df.iloc[i+60]['close'] # Approx entry price
            
            # Logique TP/SL fictive (ratio 1:2)
            tp_pct = 0.025
            sl_pct = 0.01
            
            outcome = 0
            # Si signal == 1 (Achat) et target réelle était 1 -> Win
            if signal == 1:
                if y[i] == 1: outcome = price * tp_pct
                else: outcome = -price * sl_pct
            elif signal == 2:
                if y[i] == 2: outcome = price * tp_pct
                else: outcome = -price * sl_pct
                
            balance += outcome
            results.append({
                "Date": indices[i],
                "Signal": "Achat" if signal == 1 else "Vente",
                "Prix Entrée": price,
                "Resultat": round(outcome, 2),
                "Balance": round(balance, 2)
            })
            
        return pd.DataFrame(results)
