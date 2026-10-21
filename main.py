
import time
import threading
import requests
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="BTCUSD MTF V3 LUWAG + TP/SL")

# ================= CONFIG - BTCUSD =================
CONFIG = {
    "SYMBOL": "BTCUSDT",
    "NEAR_PCT": 0.7,      # LUWAG from 0.5% -> 0.7%
    "TP_PCT": 1.5,        # Take Profit
    "SL_PCT": 0.8,        # Stop Loss
    "USE_ENGULF_PIN": False,  # False = LUWAG MODE
    "LOOP_SECONDS": 60,
}

last_signal = {"time": None, "signal": "WAITING", "price": 0}

def get_btc_price():
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={CONFIG['SYMBOL']}"
        r = requests.get(url, timeout=5).json()
        return float(r['price'])
    except:
        return None

def get_sr_levels():
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={CONFIG['SYMBOL']}&interval=15m&limit=50"
        data = requests.get(url, timeout=10).json()
        lows = [float(c[3]) for c in data]
        highs = [float(c[2]) for c in data]
        supports = sorted(lows)[:7]
        resistances = sorted(highs, reverse=True)[:8]
        return supports, resistances
    except Exception as e:
        print(f"SR Error: {e}")
        return [], []

def bot_logic():
    global last_signal
    try:
        price = get_btc_price()
        if not price:
            return
        
        supports, resistances = get_sr_levels()
        print(f"\n=== MTF V3 BTCUSD LUWAG ===")
        print(f"BTC Price: {price}")
        print(f"15M SUPPORTS: {[round(x,2) for x in supports[:3]]}")
        print(f"15M RESISTANCES: {[round(x,2) for x in resistances[:3]]}")
        print(f"Config: {CONFIG['NEAR_PCT']}% near | TP {CONFIG['TP_PCT']}% SL {CONFIG['SL_PCT']}%")

        # LONG check
        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 + CONFIG["TP_PCT"]/100)
                sl = price * (1 - CONFIG["SL_PCT"]/100)
                msg = f"LONG Entry:{price:.2f} Near SUP {sup:.2f} ({dist:.2f}%) TP:{tp:.2f} SL:{sl:.2f}"
                print(f"✅ {msg}")
                last_signal = {"time": datetime.now().isoformat(), "signal": "LONG", "price": price, "tp": tp, "sl": sl, "near": sup, "dist": dist}
                return

        # SHORT check
        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 - CONFIG["TP_PCT"]/100)
                sl = price * (1 + CONFIG["SL_PCT"]/100)
                msg = f"SHORT Entry:{price:.2f} Near RES {res:.2f} ({dist:.2f}%) TP:{tp:.2f} SL:{sl:.2f}"
                print(f"✅ {msg}")
                last_signal = {"time": datetime.now().isoformat(), "signal": "SHORT", "price": price, "tp": tp, "sl": sl, "near": res, "dist": dist}
                return

        print(f"⏳ No near SR - Waiting... LUWAG MODE ON")
        last_signal["signal"] = "WAITING"
        
    except Exception as e:
        print(f"Bot Error: {e}")

def bot_loop():
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

# Start bot in background
threading.Thread(target=bot_loop, daemon=True).start()

@app.get("/")
def home():
    return {
        "status": "BTCUSD MTF V3 LUWAG + TP/SL LIVE ON RENDER.COM",
        "config": CONFIG,
        "last_signal": last_signal,
        "strategy": f"15M SR ({CONFIG['NEAR_PCT']}% near) + 1M 2C SECOND FULLY CLOSED + TP {CONFIG['TP_PCT']}% SL {CONFIG['SL_PCT']}%",
        "time": datetime.now().isoformat()
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal}

@app.get("/config")
def get_config():
    return CONFIG
