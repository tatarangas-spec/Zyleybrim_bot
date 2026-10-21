import time
import threading
import requests
import json
import websocket
import os
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="BTCUSD MTF V3 LUWAG + Deriv Real")

# ================= CONFIG - BTCUSD + DERIV =================
CONFIG = {
    "SYMBOL": "BTCUSDT",  # Signal source pa rin 【entity-Binance¦canonical_name=Binance】
    "NEAR_PCT": 0.7,
    "TP_PCT": 1.5,
    "SL_PCT": 0.8,
    "USE_ENGULF_PIN": False,
    "LOOP_SECONDS": 60,
    # --- DERIV REAL ---
    "DERIV_ENABLED": True,  # True = magti-trade sa real, False = signal lang
    "DERIV_SYMBOL": "BTCUSD",  # Sa Deriv: BTCUSD or cryBTCUSD
    "DERIV_AMOUNT": 1,  # $1 per trade - palitan mo pag confident ka na
    "DERIV_APP_ID": 1089,  # Public app_id, pwede mo palitan ng sarili mo
}

# Token mo ilagay sa Render Environment, wag dito sa code
DERIV_TOKEN = os.getenv("DERIV_TOKEN", "") 

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "OFF"}
last_trade_time = 0

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

def trade_deriv_real(direction, entry_price):
    """Auto trade sa Deriv Real account"""
    global last_signal
    if not CONFIG["DERIV_ENABLED"]:
        print("Deriv OFF - signal lang")
        return
    if not DERIV_TOKEN:
        print("❌ WALA PANG DERIV_TOKEN! Lagay mo sa Render Env Variables")
        last_signal["deriv"] = "NO TOKEN"
        return

    # Iwas spam - 5 mins per trade lang
    global last_trade_time
    if time.time() - last_trade_time < 300:
        print("⏳ Cooldown pa, skip trade")
        return

    try:
        ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        ws = websocket.create_connection(ws_url, timeout=10)
        
        # 1. Authorize
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        if "error" in auth_res:
            print(f"Deriv Auth Error: {auth_res['error']}")
            ws.close()
            return
        print(f"✅ Deriv Auth OK: {auth_res['authorize']['loginid']}")

        # 2. Proposal - MULTIPLIER para may TP/SL
        contract_type = "MULTUP" if direction == "LONG" else "MULTDOWN"
        
        proposal = {
            "proposal": 1,
            "amount": CONFIG["DERIV_AMOUNT"],
            "basis": "stake",
            "contract_type": contract_type,
            "symbol": CONFIG["DERIV_SYMBOL"],
            "multiplier": 100,  # x100
            "limit_order": {
                "take_profit": CONFIG["DERIV_AMOUNT"] * (CONFIG["TP_PCT"]/100) * 10, # adjust
                "stop_loss": CONFIG["DERIV_AMOUNT"] * (CONFIG["SL_PCT"]/100) * 10
            }
        }
        # Simpler fallback kung di supported limit_order sa proposal, use buy agad
        # For basic RISE/FALL:
        # proposal = {"proposal":1, "amount":CONFIG["DERIV_AMOUNT"], "basis":"stake", "contract_type":"CALL" if direction=="LONG" else "PUT", "symbol":CONFIG["DERIV_SYMBOL"], "duration":5, "duration_unit":"m"}

        ws.send(json.dumps(proposal))
        prop_res = json.loads(ws.recv())
        
        if "error" in prop_res:
            print(f"Proposal Error: {prop_res['error']['message']}")
            ws.close()
            return

        # 3. Buy
        proposal_id = prop_res["proposal"]["id"]
        price = prop_res["proposal"]["ask_price"]
        ws.send(json.dumps({"buy": proposal_id, "price": price}))
        buy_res = json.loads(ws.recv())
        
        print(f"🚀 DERIV REAL TRADE EXECUTED: {direction} {CONFIG['DERIV_SYMBOL']} ${CONFIG['DERIV_AMOUNT']}")
        print(f"Result: {buy_res}")
        
        last_signal["deriv"] = f"TRADED {direction} - {buy_res.get('buy',{}).get('transaction_id','')}"
        last_trade_time = time.time()
        ws.close()

    except Exception as e:
        print(f"Deriv Trade Error: {e}")
        last_signal["deriv"] = f"ERROR: {e}"

def bot_logic():
    global last_signal
    try:
        price = get_btc_price()
        if not price: return
        
        supports, resistances = get_sr_levels()
        print(f"\n=== MTF V3 LUWAG + DERIV ===")
        print(f"BTC Price: {price}")
        print(f"Config: {CONFIG['NEAR_PCT']}% near | TP {CONFIG['TP_PCT']}% SL {CONFIG['SL_PCT']}% | Deriv: {CONFIG['DERIV_ENABLED']}")

        # LONG
        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 + CONFIG["TP_PCT"]/100)
                sl = price * (1 - CONFIG["SL_PCT"]/100)
                msg = f"LONG Entry:{price:.2f} Near SUP {sup:.2f} ({dist:.2f}%) TP:{tp:.2f} SL:{sl:.2f}"
                print(f"✅ {msg}")
                last_signal = {"time": datetime.now().isoformat(), "signal": "LONG", "price": price, "tp": tp, "sl": sl, "near": sup, "dist": dist, "deriv": "TRYING"}
                trade_deriv_real("LONG", price)
                return

        # SHORT
        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 - CONFIG["TP_PCT"]/100)
                sl = price * (1 + CONFIG["SL_PCT"]/100)
                msg = f"SHORT Entry:{price:.2f} Near RES {res:.2f} ({dist:.2f}%) TP:{tp:.2f} SL:{sl:.2f}"
                print(f"✅ {msg}")
                last_signal = {"time": datetime.now().isoformat(), "signal": "SHORT", "price": price, "tp": tp, "sl": sl, "near": res, "dist": dist, "deriv": "TRYING"}
                trade_deriv_real("SHORT", price)
                return

        print(f"⏳ No near SR - Waiting...")
        last_signal["signal"] = "WAITING"
        
    except Exception as e:
        print(f"Bot Error: {e}")

def bot_loop():
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

threading.Thread(target=bot_loop, daemon=True).start()

@app.get("/")
def home():
    return {"status": "BTCUSD MTF V3 LUWAG + DERIV REAL LIVE", "config": CONFIG, "last_signal": last_signal, "time": datetime.now().isoformat()}

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "deriv_token_set": bool(DERIV_TOKEN)}

@app.get("/config")
def get_config():
    return CONFIG
