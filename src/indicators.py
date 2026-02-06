# src/indicators.py
import pandas as pd
import pandas_ta as ta

def add_indicators(df):
    """Calcule MA5, SMMA35, RSI5, Stoch(47,14,15)"""
    if df.empty: return df
    
    # Copie pour éviter les warnings
    df = df.copy()

    # 1. MA5
    df['MA5'] = ta.sma(df['close'], length=5)

    # 2. SMMA35 (Equivalent RMA dans pandas_ta)
    df['SMMA35'] = ta.rma(df['close'], length=35)

    # 3. RSI 5
    df['RSI5'] = ta.rsi(df['close'], length=5)

    # 4. Stochastique (47, 14, 15) -> %K et %D
    stoch = ta.stoch(df['high'], df['low'], df['close'], k=47, d=14, smooth_k=15)
    
    # Gestion des noms de colonnes dynamiques de pandas_ta
    k_col = [c for c in stoch.columns if c.startswith('STOCHk')][0]
    d_col = [c for c in stoch.columns if c.startswith('STOCHd')][0]
    
    df['STOCH_K'] = stoch[k_col]
    df['STOCH_D'] = stoch[d_col]

    df.dropna(inplace=True)
    return df
 