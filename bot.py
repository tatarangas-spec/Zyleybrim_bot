import asyncio
from deriv_api import DerivAPI
import requests
import time

# --- ILISI BOSS ---
DERIV_APP_ID = 1089
TELEGRAM_TOKEN = "IMONG TELEGRAM TOKEN"
CHAT_ID = "IMONG CHAT ID"
SYMBOL = "CRASH_1000"
# ------------------

last_signal = 0
trade_count = 0

def tg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def is_spike_down(candles):
    if len(candles) < 12: return False
    last = candles[-2] # Last closed 1-min candle
    body = last['open'] - last['close']
    if body <= 0: return False # Dili red pababa

    avg = sum(abs(c['open']-c['close']) for c in candles[-12:-2]) / 10
    return body > (avg * 3.5)

async def main():
    api = DerivAPI(app_id=DERIV_APP_ID)
    tg(f"✅ *CRASH 1000 SIGNAL BOT ON - RENDER*\nMode: SIGNAL ONLY\nSymbol: {SYMBOL}\nTarget: $0.20\nCP Ready boss!")

    while True:
        try:
            # Kuha 1-min candles gikan Deriv
            hist = await api.ticks_history({
                "ticks_history": SYMBOL,
                "style": "candles",
                "granularity": 60,
                "count": 20,
                "end": "latest"
            })
            candles = hist['candles']

            global last_signal, trade_count
            if is_spike_down(candles) and (time.time() - last_signal > 70):
                last_signal = time.time()
                trade_count += 1

                if trade_count == 1:
                    tg(f"⚡ *SPIKE PABABA DETECTED!*\n\n"
                       f"Symbol: *CRASH 1000*\n"
                       f"Signal: *BUY NOW* sa MT5\n"
                       f"Reason: Dako red candle sa 1-min\n"
                       f"Trade: *#1*\n"
                       f"Target: $0.20 profit\n\n"
                       f"👉 Manual BUY sa MT5 Deriv app boss!")
                elif trade_count == 2:
                    tg(f"⚡ *2ND SPIKE PABABA!*\n\n"
                       f"Symbol: *CRASH 1000*\n"
                       f"Signal: *BUY AGAIN* #2\n"
                       f"Duha na ka running trades\n"
                       f"Hulat $0.20 total profit\n\n"
                       f"👉 Manual BUY ulit!")

                if trade_count >= 2:
                    tg(f"📊 *WAITING $0.20 PROFIT*\nClose tanan pag abot $0.20\nPaabot napud ug laing spike after.")
                    trade_count = 0

            await asyncio.sleep(5)

        except Exception as e:
            print(f"Error: {e}, reconnecting...")
            await asyncio.sleep(5)
            api = DerivAPI(app_id=DERIV_APP_ID)

asyncio.run(main())
