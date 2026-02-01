import requests
import config

def send_telegram_msg(message):
    token = "8062210465:AAFCyxrFjns-AZwvXo3Eehs2AwbD9qbGm9k"
    chat_id = "1830651858"
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
    
    try:
        requests.get(url)
    except Exception as e:
        print(f"Erreur Telegram: {e}")
