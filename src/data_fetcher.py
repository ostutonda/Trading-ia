# src/data_fetcher.py

    def fetch_history_stream(self, symbol, timeframe_sec, start_dt, end_dt, progress_bar):
        """
        Récupère TOUTES les bougies sans exception entre start_dt et end_dt.
        Gère les gaps de marché et la pagination par 5000.
        """
        if not self.ws or not self.ws.connected:
            if not self.connect_ws(): return 0

        # Conversion précise en timestamps
        start_epoch = int(start_dt.timestamp())
        target_end_epoch = int(end_dt.timestamp())
        
        current_ptr = start_epoch
        total_count = 0
        
        # Durée totale pour le calcul du % de progression
        total_duration = target_end_epoch - start_epoch
        if total_duration <= 0:
            st.warning("La date de fin doit être après le début.")
            return 0

        st.info(f"🚀 Récupération exhaustive pour {symbol}...")

        # Boucle tant qu'on n'a pas atteint la date cible
        while current_ptr < target_end_epoch:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 5000,
                "start": current_ptr,
                "end": target_end_epoch,
                "style": "candles",
                "granularity": timeframe_sec
            }
            
            try:
                self.ws.send(json.dumps(req))
                resp = self.ws.recv()
                data = json.loads(resp)

                if 'error' in data:
                    # Si l'erreur dit que le start est après le end, on a fini
                    if "start time is after end time" in data['error']['message'].lower():
                        break
                    st.error(f"API Error: {data['error']['message']}")
                    break

                candles = data.get('candles', [])

                if not candles:
                    # --- GESTION DES GAPS (Week-ends / Maintenance) ---
                    # Si l'API ne renvoie rien, on avance le pointeur de 1 jour 
                    # pour chercher plus loin, sinon on reste bloqué dans le vide.
                    current_ptr += 86400 # Saut de 24h
                    if current_ptr > target_end_epoch:
                        break
                    continue

                # On prépare les données pour SQLite
                batch = []
                last_epoch_received = candles[-1]['epoch']
                
                for c in candles:
                    # Sécurité : on ne dépasse jamais la date de fin demandée
                    if c['epoch'] <= target_end_epoch:
                        batch.append((
                            symbol, timeframe_sec, c['epoch'],
                            c['open'], c['high'], c['low'], c['close']
                        ))

                # Sauvegarde immédiate du lot
                if batch:
                    self.save_to_db(batch)
                    total_count += len(batch)

                # Mise à jour de l'UI
                progress = min(1.0, (last_epoch_received - start_epoch) / total_duration)
                date_str = datetime.fromtimestamp(last_epoch_received).strftime('%Y-%m-%d %H:%M')
                progress_bar.progress(progress, text=f"📦 {total_count} bougies | Actuel: {date_str}")

                # --- CONDITION DE PROGRESSION ---
                # On repart de la dernière bougie reçue + timeframe pour ne pas avoir de doublon
                if last_epoch_received >= target_end_epoch:
                    break
                
                # Si on a reçu moins de 5000 bougies, on a peut-être atteint la fin des données dispo
                if len(candles) < 5000:
                    # On vérifie si on est proche du "Maintenant" (à 2 bougies près)
                    if last_epoch_received >= (int(time.time()) - (timeframe_sec * 2)):
                        break
                    else:
                        # On est sur un gap (ex: vendredi soir), on saute au lundi
                        current_ptr = last_epoch_received + 3600 # On avance d'une heure pour chercher
                else:
                    current_ptr = last_epoch_received + timeframe_sec

                # Respecter les limites de débit de l'API (Rate limiting)
                time.sleep(0.1)

            except Exception as e:
                st.error(f"Interruption : {e}")
                break

        progress_bar.progress(1.0, text=f"✅ Terminé : {total_count} bougies en base.")
        return total_count
