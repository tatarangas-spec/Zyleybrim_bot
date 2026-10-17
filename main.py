from flask import Flask
import os, requests

app = Flask(__name__)

def send_telegram(msg):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": msg})
    return r.text

@app.route('/')
def home():
    return "Zyleybrim_bot is LIVE boss! 🔥"

@app.route('/test-telegram')
def test():
    result = send_telegram("✅ Zyleybrim_bot test - BUHI NA BOSS!")
    return f"Telegram result: {result}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
