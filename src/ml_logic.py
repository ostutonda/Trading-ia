import tensorflow as tf
from tensorflow.keras.models import Sequential # type: ignore
from tensorflow.keras.layers import Dense, Dropout # type: ignore
import numpy as np

def create_model(input_shape):
    model = Sequential([
        # Couche d'entrée : reçoit tes indicateurs (RSI, Stoch, EMA, MA)
        Dense(64, activation='relu', input_shape=(input_shape,)),
        Dropout(0.2), # Évite le sur-apprentissage
        
        # Couches cachées
        Dense(32, activation='relu'),
        Dense(16, activation='relu'),
        
        # Couche de sortie : 1 neurone (Sigmoid donne une probabilité entre 0 et 1)
        Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def prepare_data_for_training(df):
    # On définit les "Features" (ce que l'IA regarde)
    # Note: vérifie bien les noms des colonnes générées par tes indicateurs
    features = ['RSI_5', 'EMA_100', 'MA_5'] 
    
    # On ajoute la colonne cible : 1 si le prix monte dans 5 bougies, sinon 0
    df['target'] = (df['close'].shift(-5) > df['close']).astype(int)
    
    X = df[features].values
    y = df['target'].values
    
    # On retire les dernières lignes qui n'ont pas de "futur" (à cause du shift -5)
    X = X[:-5]
    y = y[:-5]
    
    return X, y