import pandas as pd
import numpy as np

def apply_indicators(df):
    # On s'assure que les données sont triées par le temps (epoch)
    df = df.sort_values(by='epoch', ascending=True).copy()

    # --- 1. MA 5 (Moyenne Mobile Simple) ---
    df['MA_5'] = df['close'].rolling(window=5).mean()

    # --- 2. EMA 100 (Moyenne Mobile Exponentielle) ---
    df['EMA_100'] = df['close'].ewm(span=100, adjust=False).mean()

    # --- 3. RSI 5 (Relative Strength Index) ---
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=5).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=5).mean()
    rs = gain / loss
    df['RSI_5'] = 100 - (100 / (1 + rs))

    # --- 4. STOCHASTIQUE (47, 14, 15) ---
    # %K = (Clôture actuelle - Plus bas N) / (Plus haut N - Plus bas N) * 100
    low_min = df['low'].rolling(window=47).min()
    high_max = df['high'].rolling(window=47).max()
    
    # Calcul du %K brut
    df['stoch_k_raw'] = ((df['close'] - low_min) / (high_max - low_min)) * 100
    
    # Lissage %K (smooth_k=15)
    df['STOCHk_47_14_15'] = df['stoch_k_raw'].rolling(window=15).mean()
    
    # Calcul du %D (moyenne mobile de %K sur 14 périodes)
    df['STOCHd_47_14_15'] = df['STOCHk_47_14_15'].rolling(window=14).mean()

    # Nettoyage : On supprime les colonnes temporaires et les lignes vides (NaN)
    df.drop(columns=['stoch_k_raw'], inplace=True)
    df = df.dropna()
    
    return df