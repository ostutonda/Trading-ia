# src/indicators.py
import talib
import pandas as pd
import numpy as np

def calculate_smma(series, period):
    """Calcule la Smoothed Moving Average (SMMA) manuellement car TA-Lib ne l'a pas directement."""
    return series.ewm(alpha=1/period, adjust=False).mean()

def add_indicators(df):
    """
    Ajoute: MA5, SMMA35, RSI5, Stoch(47,14,15)
    """
    if df.empty:
        return df

    data = df.copy()
    close = data['close'].values
    high = data['high'].values
    low = data['low'].values

    # 1. MA5
    data['MA5'] = talib.SMA(close, timeperiod=5)

    # 2. SMMA 35 (Moyenne Mobile Lisse)
    data['SMMA35'] = calculate_smma(data['close'], 35)

    # 3. RSI 5
    data['RSI5'] = talib.RSI(close, timeperiod=5)

    # 4. Stochastique (47, 14, 15) -> %K et %D
    slowk, slowd = talib.STOCH(
        high, low, close,
        fastk_period=47,
        slowk_period=14,
        slowk_matype=0,
        slowd_period=15,
        slowd_matype=0
    )
    data['Stoch_K'] = slowk
    data['Stoch_D'] = slowd

    data.dropna(inplace=True)
    return data
