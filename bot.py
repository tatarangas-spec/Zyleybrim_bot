import asyncio, json, time, requests, websockets, os
from flask import Flask
import threading

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
SYMBOL = "CRASH_1000"
WS_URLS = [
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=1089"
]

last_signal = 0
trade_count = 0

def tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"TG Sent: {msg[:20]}")
    except Exception as e:
        print(f"TG Error: {e}")

def is_spike_down(candles):
    if len(candles) < 12: return False
    last = candles[-1]
    body = float(last['open']) - float(last['close'])
    if body <= 0: return False
    avg = sum(abs(float(c['open'])-float(c['close'])) for c in candles[-11:-1]) / 10
    return body > (avg * 3.2)

async def get_candles():
    for ws_url in WS_URLS:
        try:
            async with websockets.connect(ws_url) as ws:
                req = {"ticks_history": SYMBOL, "style": "candles", "granularity": 60, "count": 20, "end": "latest"}
                await ws.send(json.dumps(req))
                res = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if 'candles' in res: return res['candles']
        except: continue
    return []

async def bot_loop():
    global last_signal, trade_count
    print("Bot loop started...")
    tg("CRASH 1000 SIGNAL BOT ON - WEB SERVICE FREE\nSignal Only boss!")
    while True:
        try:
            candles = await get_candles()
            if candles and is_spike_down(candles) and (time.time() - last_signal > 70):
                last_signal = time.time()
                trade_count += 1
                if trade_count == 1:
                    tg(f"⚡ SPIKE PABABA! Crash 1000 BUY NOW sa MT5 - Trade #1 Target $0.20")
                else:
                    tg(f"⚡ 2ND SPIKE PABABA! Crash 1000 BUY AGAIN #2")
                if trade_count >= 2:
                    tg(f"WAITING $0.20 PROFIT - Close tanan pag abot")
                    trade_count = 0
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(10)

app = Flask(__name__)
@app.route('/')
def home():
    return "CRASH 1000 Bot Running - Signal Only Boss! CP Ready!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=lambda: asyncio.run(bot_loop()), daemon=True).start()

if __name__ == "__main__":
    run_flask()
