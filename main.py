import os
import requests
from flask import Flask, jsonify, render_template_string
from datetime import datetime
import threading
import time
from wetradebot import get_trading_signal, get_price

app = Flask(__name__)

BOT_STATUS = {
    "name": "Zyleybrim_bot",
    "status": "BUHI NA BOSS!",
    "mode": "DEMO (Safe)",
    "logic": "4/00% - SMA5 / SMA20 / RSI",
    "uptime_start": datetime.now().isoformat(),
    "last_signal": "HOLD",
    "price": "Loading...",
    "sma5": 0,
    "sma20": 0,
    "rsi": 50,
    "last_telegram_sent": "Wala pa"
}

def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Wala pay TELEGRAM_BOT_TOKEN / CHAT_ID sa Render")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram sent: {r.text}")
        BOT_STATUS["last_telegram_sent"] = datetime.now().isoformat()
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def bot_loop():
    last_signal_sent = ""
    while True:
        try:
            signal, price, sma5, sma20, rsi = get_trading_signal()
            BOT_STATUS["price"] = price
            BOT_STATUS["sma5"] = round(sma5, 2)
            BOT_STATUS["sma20"] = round(sma20, 2)
            BOT_STATUS["rsi"] = round(rsi, 2)
            BOT_STATUS["last_signal"] = signal
            
            # Kung bag-o ang signal ug dili HOLD, send sa Telegram
            if signal != "HOLD" and signal != last_signal_sent:
                msg = f"""🚀 *ZYLEYBRIM BOT SIGNAL*

💰 Price: ${price}
📊 Signal: *{signal}*
📈 SMA5: {sma5:.2f} / SMA20: {sma20:.2f}
📉 RSI: {rsi:.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Buhi na boss!"""
                send_telegram(msg)
                last_signal_sent = signal
                
        except Exception as e:
            print(f"Bot loop error: {e}")
        time.sleep(60)  # check every 1 minute

@app.route("/")
def home():
    html = """
    <h1>🚀 Zyleybrim_bot - BUHI NA BOSS!</h1>
    <p>Status: {{s.status}}</p>
    <p>Mode: {{s.mode}}</p>
    <p>Price: {{s.price}}</p>
    <p>Last Signal: <b>{{s.last_signal}}</b></p>
    <p>SMA5: {{s.sma5}} | SMA20: {{s.sma20}} | RSI: {{s.rsi}}</p>
    <p>Last Telegram: {{s.last_telegram_sent}}</p>
    <p>Uptime: {{s.uptime_start}}</p>
    <hr>
    <p><a href='/status'>JSON Status</a></p>
    """
    return render_template_string(html, s=BOT_STATUS)

@app.route("/status")
def status():
    return jsonify(BOT_STATUS)

@app.route("/test-telegram")
def test_telegram():
    ok = send_telegram("✅ Zyleybrim_bot test message - BUHI NA BOSS! Kung nabasa nimo ni, connected na ang Telegram!")
    return jsonify({"sent": ok, "status": BOT_STATUS})

# Start bot loop sa background
threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
