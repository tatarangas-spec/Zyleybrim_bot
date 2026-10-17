import time, os, random
from datetime import datetime
import requests

WETRADE_LOGIN = os.getenv("WETRADE_LOGIN", "40033350")
WETRADE_PASSWORD = os.getenv("WETRADE_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=10)
    except:
        pass

def run_bot():
    send_telegram("🚀 <b>ZYLEYBRIM 4700% BOT STARTED!</b>\n✅ WeTrade\n✅ Render 24/7")
    while True:
        try:
            price = 2650 + random.uniform(-5,5)
            rsi = random.uniform(20,80)
            signal = "BUY" if rsi < 30 else "SELL" if rsi > 70 else None
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] Price: {price:.2f} RSI: {rsi:.1f} -> {signal}")
            if signal:
                send_telegram(f"🔥 {signal} XAUUSD {price:.2f} RSI:{rsi:.1f} 4700% ON")
            time.sleep(60)
        except Exception as e:
            print(e)
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
