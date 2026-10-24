import asyncio, json, time, requests, websockets

TELEGRAM_TOKEN = "IMONG TOKEN DIRI - gikan @BotFather"
CHAT_ID = "IMONG CHAT ID - gikan @userinfobot, numbers lang ex: 123456789"
SYMBOL = "CRASH_1000"
APP_ID = 1089

last_signal = 0
trade_count = 0

def tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        # WA LANG MARKDOWN PARA DILI MAG 400 ERROR
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"Telegram sent: {msg[:30]}")
    except Exception as e:
        print(f"Telegram error: {e}")

def is_spike_down(candles):
    if len(candles) < 12: return False
    last = candles[-1]
    body = float(last['open']) - float(last['close'])
    if body <= 0: return False
    avg = sum(abs(float(c['open'])-float(c['close'])) for c in candles[-11:-1]) / 10
    return body > (avg * 3.2)

async def get_candles():
    uri = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    async with websockets.connect(uri) as ws:
        req = {"ticks_history": SYMBOL, "style": "candles", "granularity": 60, "count": 20, "end": "latest"}
        await ws.send(json.dumps(req))
        res = json.loads(await ws.recv())
        return res.get('candles', [])

async def main():
    global last_signal, trade_count
    tg(f"CRASH 1000 SIGNAL BOT ON - RENDER OK\nSignal Only Mode\nHulat ug spike pababa boss!")
    print("Bot started...")

    while True:
        try:
            candles = await get_candles()
            print(f"Checked candles: {len(candles)}")

            if is_spike_down(candles) and (time.time() - last_signal > 70):
                last_signal = time.time()
                trade_count += 1

                if trade_count == 1:
                    tg(f"⚡ SPIKE PABABA DETECTED!\nCrash 1000 - BUY NOW sa MT5\nTrade #1 - Target $0.20\nManual BUY na boss!")
                elif trade_count == 2:
                    tg(f"⚡ 2ND SPIKE PABABA!\nCrash 1000 - BUY AGAIN #2\nDuha na running - Hulat $0.20 total")
                
                if trade_count >= 2:
                    tg(f"WAITING $0.20 PROFIT - Close tanan pag abot\nPaabot napud ug laing spike after")
                    trade_count = 0

            await asyncio.sleep(10)

        except Exception as e:
            print(f"Loop error: {e} - retry in 5s")
            await asyncio.sleep(5)

asyncio.run(main())
