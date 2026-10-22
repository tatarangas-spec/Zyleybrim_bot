import time
import threading
import requests
import json
import websocket
import os
from fastapi import FastAPI
from datetime import datetime
import sys

app = FastAPI(title="BTCUSD MTF V3 LUWAG + Deriv Real")

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "NEAR_PCT": 0.7,
    "TP_PCT": 1.5,
    "SL_PCT": 0.8,
    "USE_ENGULF_PIN": False,
    "LOOP_SECONDS": 60,
    "DERIV_ENABLED": True,
    "DERIV_SYMBOL": "cryBTCUSD",
    "DERIV_AMOUNT": 1,
    "DERIV_APP_ID": 1089,
}

DERIV_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
print(f"=== BOT STARTING ===", flush=True)
print(f"DERIV_TOKEN SET: {bool(DERIV_TOKEN)} Token length: {len(DERIV_TOKEN)}", flush=True)

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "OFF - WAITING TOKEN"}
last_trade_time = 0

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_btc_price():
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={CONFIG['SYMBOL']}"
        r = requests.get(url, timeout=10).json()
        return float(r['price'])
    except Exception as e:
        log(f"Price Error: {e}")
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
        log(f"SR Error: {e}")
        return [], []

def trade_deriv_real(direction, entry_price):
    global last_signal, last_trade_time
    if not CONFIG["DERIV_ENABLED"]:
        log("Deriv OFF - signal lang")
        return
    if not DERIV_TOKEN:
        log("WALA PANG DERIV_TOKEN! Lagay mo sa Render Env Variables")
        last_signal["deriv"] = "NO TOKEN - ADD DERIV_TOKEN"
        return
    if time.time() - last_trade_time < 300:
        log("Cooldown pa 5 mins, skip trade")
        return

    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        log(f"Connecting to Deriv: {ws_url}")
        ws = websocket.create_connection(ws_url, timeout=15)
        
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        if "error" in auth_res:
            log(f"Deriv Auth Error: {auth_res['error']}")
            last_signal["deriv"] = f"AUTH FAILED: {auth_res['error']['message']}"
            ws.close()
            return
        log(f"Deriv Auth OK: {auth_res['authorize']['loginid']} - BALANCE REAL NA TO BOSS!")

        contract_type = "CALL" if direction == "LONG" else "PUT"
        proposal = {
            "proposal": 1,
            "amount": CONFIG["DERIV_AMOUNT"],
            "basis": "stake",
            "contract_type": contract_type,
            "symbol": CONFIG["DERIV_SYMBOL"],
            "duration": 5,
            "duration_unit": "m"
        }

        log(f"Sending proposal: {direction} {proposal}")
        ws.send(json.dumps(proposal))
        prop_res = json.loads(ws.recv())
        
        if "error" in prop_res:
            log(f"Proposal Error: {prop_res['error']['message']}")
            last_signal["deriv"] = f"PROPOSAL FAIL: {prop_res['error']['message']}"
            ws.close()
            return

        proposal_id = prop_res["proposal"]["id"]
        price = prop_res["proposal"]["ask_price"]
        ws.send(json.dumps({"buy": proposal_id, "price": price}))
        buy_res = json.loads(ws.recv())
        
        log(f"DERIV REAL TRADE EXECUTED: {direction} {CONFIG['DERIV_SYMBOL']} ${CONFIG['DERIV_AMOUNT']}")
        log(f"Result: {buy_res}")
        
        last_signal["deriv"] = f"ON - TRADED {direction} ID:{buy_res.get('buy',{}).get('transaction_id','')}"
        last_trade_time = time.time()
        ws.close()

    except Exception as e:
        log(f"Deriv Trade Error: {e}")
        last_signal["deriv"] = f"ERROR: {e}"

def bot_logic():
    global last_signal
    try:
        price = get_btc_price()
        if not price:
            log("No price - retry next loop")
            return
        
        supports, resistances = get_sr_levels()
        log(f"\n=== MTF V3 CHECK ===")
        log(f"BTC Price: {price} | Deriv Enabled: {CONFIG['DERIV_ENABLED']} | Token: {bool(DERIV_TOKEN)}")

        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 + CONFIG["TP_PCT"]/100)
                sl = price * (1 - CONFIG["SL_PCT"]/100)
                log(f"LONG SIGNAL Entry:{price:.2f} Near SUP {sup:.2f} ({dist:.2f}%)")
                last_signal = {"time": datetime.now().isoformat(), "signal": "LONG", "price": price, "tp": tp, "sl": sl, "near": sup, "dist": dist, "deriv": "TRYING TO TRADE..."}
                trade_deriv_real("LONG", price)
                return

        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"]:
                tp = price * (1 - CONFIG["TP_PCT"]/100)
                sl = price * (1 + CONFIG["SL_PCT"]/100)
                log(f"SHORT SIGNAL Entry:{price:.2f} Near RES {res:.2f} ({dist:.2f}%)")
                last_signal = {"time": datetime.now().isoformat(), "signal": "SHORT", "price": price, "tp": tp, "sl": sl, "near": res, "dist": dist, "deriv": "TRYING TO TRADE..."}
                trade_deriv_real("SHORT", price)
                return

        log(f"No near SR - Waiting... Price {price}")
        last_signal["signal"] = "WAITING"
        if DERIV_TOKEN:
            last_signal["deriv"] = "ON - WAITING FOR SIGNAL"
        else:
            last_signal["deriv"] = "OFF - NO TOKEN"
        
    except Exception as e:
        log(f"Bot Error: {e}")

def bot_loop():
    log("BOT LOOP STARTED - EVERY 60 SECONDS MAG CHECHECK")
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP EVENT - STARTING BOT THREAD ===")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    log("Bot thread started!")

@app.get("/")
def home():
    return {"status": "BTCUSD MTF V3 LUWAG + DERIV REAL LIVE - AUTO TRADE ON", "config": CONFIG, "last_signal": last_signal, "time": datetime.now().isoformat(), "token_set": bool(DERIV_TOKEN)}

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "deriv_token_set": bool(DERIV_TOKEN), "token_len": len(DERIV_TOKEN) if DERIV_TOKEN else 0}

@app.get("/config")
def get_config():
    return CONFIG
      
