import asyncio, json, time, requests, websockets

# ========= ILISI LANG DIRI BOSS =========
TELEGRAM_TOKEN = "PASTE IMONG TELEGRAM TOKEN DIRI"
CHAT_ID = "PASTE IMONG CHAT ID DIRI"
# ========================================

SYMBOL = "CRASH_1000"
WS_URLS = [
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=1089&brand=deriv",
    "wss://ws.derivws.com/websockets/v3?app_id=36858"
]

last_signal = 0
trade_count = 0

def tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"TG Error: {e}")

def is_spike_down(candles):
    if len(candles) < 12: return False
    last = candles[-1]
    body = float(last['open']) - float(last['close'])
    if body <= 0: return False
    avg = sum(abs(float(c['open'])-float(c['close'])) for c in candles[-11:-1]) / 10
    if avg == 0: return False
    return body > (avg * 3.2)

async def get_candles():
    for ws_url in WS_URLS:
        try:
            async with websockets.connect(ws_url, ping_interval=20) as ws:
                req = {"ticks_history": SYMBOL, "style": "candles", "granularity": 60, "count": 20, "end": "latest"}
                await ws.send(json.dumps(req))
                res = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if 'candles' in res:
                    return res['candles']
        except: continue
    return []

async def main():
    global last_signal, trade_count
    tg("CRASH 1000 SIGNAL BOT ON - RENDER\nSignal Only - Hulat ug spike pababa boss!")
    while True:
        try:
            candles = await get_candles()
            if not candles:
                await asyncio.sleep(10)
                continue
            if is_spike_down(candles) and (time.time() - last_signal > 70):
                last_signal = time.time()
                trade_count += 1
                if trade_count == 1:
                    tg(f"⚡ SPIKE PABABA DETECTED!\nCrash 1000 BUY NOW sa MT5\nTrade #1 - Target $0.20\nManual BUY na boss!")
                elif trade_count == 2:
                    tg(f"⚡ 2ND SPIKE PABABA!\nCrash 1000 BUY AGAIN #2\nDuha na running - Hulat $0.20 total")
                if trade_count >= 2:
                    tg(f"WAITING $0.20 PROFIT\nClose tanan pag abot $0.20\nPaabot napud ug laing spike")
                    trade_count = 0
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(10)

asyncio.run(main())
