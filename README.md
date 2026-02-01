# 🤖 IA Deriv Trading Bot

Ce projet est une application de trading algorithmique utilisant l'Intelligence Artificielle (TensorFlow) pour prédire les mouvements des indices synthétiques sur la plateforme Deriv.

## 🚀 Installation & Lancement

### 1. Activer l'environnement virtuel
Ouvre ton terminal dans le dossier du projet et tape :
```bash
source venv/bin/python/activate
# Ou simplement si tu es déjà dans le dossier :
source venv/bin/activate

### 2. Lancer l'interface utilisateur

#L'application se pilote entièrement via le navigateur
streamlit run main.py


🛠️ Utilisation du Bot (Ordre des étapes)

    Extraction : Sélectionne une catégorie (Volatility, Step) et un indice. Clique sur "Actualiser les données". Cela remplit la base de données SQLite.

    Entraînement : Une fois les données récupérées, clique sur "Entraîner l'IA". Le bot va créer un modèle mon_ia_deriv.h5 dans le dossier models/.

    Analyse : Coche la case "🚀 Activer signaux LIVE" pour voir les prédictions en temps réel basées sur ton modèle.

    📂 Organisation des fichiers

    main.py : Interface Streamlit et tableau de bord.

    config.py : Liste des indices et paramètres techniques.

    src/indicators.py : Calculs mathématiques (RSI, EMA, Stochastique).

    src/data_fetcher.py : Connexion WebSocket API Deriv.

    src/train_model.py : Entraînement du réseau de neurones.

    src/trader.py : Logique de prédiction et chargement du modèle.


    ⚠️ Notes Importantes

    Scalping : Le bot est actuellement configuré pour des signaux de confirmation.

    Sécurité : Ne partage jamais ton API Token si tu l'ajoutes dans config.py.

    Mode Démo : Toujours tester les signaux sur un compte démo avant toute utilisation réelle.