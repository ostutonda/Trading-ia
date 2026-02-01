import os
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model # type: ignore
from sklearn.preprocessing import MinMaxScaler
from src.indicators import apply_indicators

def live_prediction(df_raw):
    model_path = 'models/mon_ia_deriv.h5'
    
    # 1. Vérification : Si le fichier n'existe pas, on s'arrête gentiment
    if not os.path.exists(model_path):
        return "IA non entraînée (Fichier manquant)", 0.5
    
    try:
        # 2. Chargement du modèle
        model = load_model(model_path)
        
        # 3. Calcul des indicateurs
        df = apply_indicators(df_raw)
        if df.empty:
            return "Données insuffisantes", 0.5

        # 4. Préparation des caractéristiques
        features = ['RSI_5', 'EMA_100', 'MA_5', 'STOCHk_47_14_15', 'STOCHd_47_14_15']
        
        # On prend la toute dernière ligne pour la prédiction
        last_row = df[features].tail(1).values
        
        # 5. Normalisation rapide (MinMax manuel pour éviter d'autres erreurs)
        # Note : Dans une version pro, on utiliserait le scaler sauvegardé
        last_row_scaled = (last_row - 0) / (100 - 0) # Approximation pour RSI/Stoch
        
        # 6. Prédiction
        prediction = model.predict(last_row_scaled, verbose=0)[0][0]
        
        if prediction > 0.70:
            return "🚀 SIGNAL ACHAT (CALL)", prediction
        elif prediction < 0.30:
            return "📉 SIGNAL VENTE (PUT)", prediction
        else:
            return "⏳ ATTENTE (NEUTRE)", prediction

    except Exception as e:
        return f"Erreur lors de la lecture : {str(e)[:30]}", 0.5