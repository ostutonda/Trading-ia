import asyncio
import websockets
import json
import config

class TradeExecutor:
    def __init__(self, token):
        self.token = token
        self.api_url = "wss://ws.derivws.com/websockets/v3?app_id=" + config.APP_ID
        self.active_contracts = []

    async def send_order(self, symbol, contract_type, amount, duration, duration_unit="m"):
        """
        Envoie un ordre d'achat (CALL ou PUT).
        duration_unit: 'm' pour minutes, 't' pour ticks, 's' pour secondes.
        """
        async with websockets.connect(self.api_url) as websocket:
            # 1. Authentification
            await websocket.send(json.dumps({"authorize": self.token}))
            auth_response = await websocket.recv()
            
            # 2. Envoi de l'ordre
            buy_request = {
                "buy": 1,
                "price": amount,
                "parameters": {
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": contract_type, # 'CALL' ou 'PUT'
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": duration_unit,
                    "symbol": symbol
                }
            }
            
            await websocket.send(json.dumps(buy_request))
            response = await websocket.recv()
            data = json.loads(response)

            if "error" in data:
                return {"status": "error", "message": data["error"]["message"]}
            
            # Stockage de l'ID pour suivi multi-positions
            contract_id = data["buy"]["contract_id"]
            self.active_contracts.append(contract_id)
            
            return {"status": "success", "contract_id": contract_id}

# Fonction utilitaire pour lancer l'ordre depuis main.py ou trader.py
def execute_trade(symbol, action, amount=1, duration=1):
    """
    Traduit l'action de l'IA en ordre réel.
    action: '🚀 SIGNAL ACHAT (CALL)' ou '📉 SIGNAL VENTE (PUT)'
    """
    contract_type = "CALL" if "ACHAT" in action else "PUT"
    
    # Création d'une boucle asynchrone pour l'envoi
    executor = TradeExecutor(config.DERIV_TOKEN)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(executor.send_order(symbol, contract_type, amount, duration))
    return result