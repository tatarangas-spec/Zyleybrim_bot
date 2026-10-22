
"""
REAL MONEY BOT - FINAL - FORCE TRADE VERSION - TEST REAL EXECUTION
Boss Zhykaeron - Oct 22 2026

PROBLEMA: Hindi nag trade kasi naghihintay ng near support (0.7%)
SOLUSYON: Force trade agad pag start para test real execution!

- Mag trade agad ng $1 CALL para test kung REAL or DEMO!
- May /force_trade endpoint para manual trade!
- Fixed Price Error
- Real token + Real App ID

Deploy to: https://zyleybrim-bot.onrender.com/
"""

import time, threading, requests, json, websocket, os, sys
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="REAL MONEY - FORCE TRADE TEST")

DERIV_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("PAT_TOKEN", "").strip()
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("DERIV_PAT", "").strip()

DERIV_APP_ID_ENV = os.getenv("DERIV_APP_ID", "").strip()
if not DERIV_APP_ID_ENV:
    DERIV_APP_ID_ENV = os.getenv("APP_ID", "").strip()

try:
    DERIV_APP_ID = int(DERIV_APP_ID_ENV) if DERIV_APP_ID_ENV and DERIV_APP_ID_ENV.isdigit() else DERIV_APP_ID_ENV
    if not DERIV_APP_ID:
        DERIV_APP_ID = "34JwLLP8WeVqrXmBqY1iG"
except:
    DERIV_APP_ID = DERIV_APP_ID_ENV if DERIV_APP_ID_ENV else "34JwLLP8WeVqrXmBqY1iG"

FORCE_TRADE = os.getenv("FORCE_TRADE", "true").lower() == "true"

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "DERIV_SYMBOL": "cryBTCUSD",
    "NEAR_PCT": 0.7,
    "BUY_AMOUNT": 1,
    "LOOP_SECONDS": 60,
    "DERIV_APP_ID": DERIV_APP_ID,
    "DURATION": 5,
    "DURATION_UNIT": "m",
    "FORCE_TRADE": FORCE_TRADE,
}

print(f"=== REAL MONEY BOT - FORCE TRADE TEST ===", flush=True)
print(f"DERIV_TOKEN SET: {bool(DERIV_TOKEN)} Length: {len(DERIV_TOKEN) if DERIV_TOKEN else 0}", flush=True)
print(f"DERIV_APP_ID: {DERIV_APP_ID}", flush=True)
print(f"FORCE_TRADE: {FORCE_TRADE}", flush=True)

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT", "info": "Starting..."}
holdings = {"avg_price": 0.0, "total_buys": 0, "total_stake": 0.0, "last_buy_time": 0}
trades_today = 0
last_trade_result = {}

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_btc_price():
    # Fixed with fallbacks
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={CONFIG['SYMBOL']}", timeout=10)
        data = r.json()
        if 'price' in data:
            return float(data['price'])
    except Exception as e:
        log(f"Binance fail: {e}")
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={CONFIG['SYMBOL']}", timeout=10).json()
        return float(r['result']['list'][0]['lastPrice'])
    except Exception as e:
        log(f"Bybit fail: {e}")
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=10).json()
        return float(r['bitcoin']['usd'])
    except Exception as e:
        log(f"CoinGecko fail: {e}")
    try:
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}", timeout=10)
        ws.send(json.dumps({"ticks": CONFIG["DERIV_SYMBOL"]}))
        for _ in range(5):
            tick = json.loads(ws.recv())
            if 'tick' in tick:
                price = float(tick['tick']['quote'])
                ws.close()
                return price
        ws.close()
    except Exception as e:
        log(f"Deriv tick fail: {e}")
    return None

def get_sr_levels(price):
    try:
        if price:
            url = f"https://api.binance.com/api/v3/klines?symbol={CONFIG['SYMBOL']}&interval=15m&limit=50"
            data = requests.get(url, timeout=10).json()
            if isinstance(data, list) and len(data) > 0:
                lows = [float(c[3]) for c in data]
                highs = [float(c[2]) for c in data]
                supports = sorted(lows)[:5]
                resistances = sorted(highs, reverse=True)[:5]
                return supports, resistances
        return [price*0.998] if price else [], [price*1.002] if price else []
    except:
        return [price*0.998] if price else [], [price*1.002] if price else []

def trade_deriv_real(direction, entry_price, reason="AUTO"):
    global last_signal, holdings, trades_today, last_trade_result
    if not DERIV_TOKEN or len(DERIV_TOKEN) < 10:
        log(f"❌ NO DERIV_TOKEN! Set in Render Env Variables!")
        last_signal["deriv"] = "NO TOKEN"
        last_trade_result = {"error": "NO TOKEN", "time": datetime.now().isoformat()}
        return False

    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        log(f"🔌 Connecting Deriv for {direction} @ ${entry_price:.2f} | Reason: {reason}")
        ws = websocket.create_connection(ws_url, timeout=20)
        
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        if "error" in auth_res:
            err = auth_res['error']['message']
            log(f"❌ Auth Error: {err}")
            last_signal["deriv"] = f"AUTH FAIL: {err}"
            last_trade_result = {"error": err, "time": datetime.now().isoformat()}
            ws.close()
            return False
        
        loginid = auth_res['authorize']['loginid']
        balance = auth_res['authorize'].get('balance', 'N/A')
        is_real = not loginid.startswith('VR')
        account_type = "REAL" if is_real else "DEMO"
        
        log(f"✅ Auth OK: {loginid} | Type: {account_type} | Bal: {balance}")
        if not is_real:
            log(f"⚠️ DEMO ACCOUNT {loginid} - Virtual lang! Palitan ng REAL token!")
        else:
            log(f"💰 REAL ACCOUNT {loginid} - REAL MONEY!")
        
        contract_type = "CALL" if direction == "LONG" else "PUT"
        proposal = {
            "proposal": 1,
            "amount": CONFIG["BUY_AMOUNT"],
            "basis": "stake",
            "contract_type": contract_type,
            "symbol": CONFIG["DERIV_SYMBOL"],
            "duration": CONFIG["DURATION"],
            "duration_unit": CONFIG["DURATION_UNIT"]
        }

        log(f"📤 {account_type} {reason}: {contract_type} ${CONFIG['BUY_AMOUNT']} @ ${entry_price:.2f}")
        ws.send(json.dumps(proposal))
        prop_res = json.loads(ws.recv())
        
        if "error" in prop_res:
            err = prop_res['error']['message']
            log(f"❌ Proposal Error: {err}")
            last_signal["deriv"] = f"PROPOSAL FAIL: {err}"
            last_trade_result = {"error": err, "account_type": account_type, "loginid": loginid, "time": datetime.now().isoformat()}
            ws.close()
            return False

        proposal_id = prop_res["proposal"]["id"]
        ask_price = prop_res["proposal"]["ask_price"]
        log(f"✅ Proposal OK ID {proposal_id} Ask ${ask_price}")
        
        ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_res = json.loads(ws.recv())
        
        if "error" in buy_res:
            err = buy_res['error']['message']
            log(f"❌ Buy Error: {err}")
            last_signal["deriv"] = f"BUY FAIL: {err}"
            last_trade_result = {"error": err, "account_type": account_type, "loginid": loginid, "time": datetime.now().isoformat()}
            ws.close()
            return False
        
        contract_id = buy_res['buy']['contract_id']
        buy_price = buy_res['buy']['buy_price']
        
        log(f"🎉 {account_type} TRADE EXECUTED! 🎉")
        log(f"✅ BOUGHT {contract_type} ${CONFIG['BUY_AMOUNT']} ID {contract_id} Price ${buy_price} | {account_type}")
        if is_real:
            log(f"💰 REAL MONEY! Check Deriv app > Portfolio > ID {contract_id}")
        else:
            log(f"⚠️ DEMO TRADE ID {contract_id} - Virtual!")
        
        holdings["avg_price"] = entry_price if holdings["total_buys"] == 0 else (holdings["avg_price"]*holdings["total_buys"]+entry_price)/(holdings["total_buys"]+1)
        holdings["total_buys"] += 1
        holdings["total_stake"] += CONFIG["BUY_AMOUNT"]
        holdings["last_buy_time"] = time.time()
        trades_today += 1
        
        last_signal["deriv"] = f"{account_type} TRADED {direction} ID:{contract_id}"
        last_trade_result = {
            "success": True,
            "account_type": account_type,
            "loginid": loginid,
            "balance": balance,
            "contract_id": contract_id,
            "contract_type": contract_type,
            "amount": CONFIG["BUY_AMOUNT"],
            "entry_price": entry_price,
            "buy_price": buy_price,
            "time": datetime.now().isoformat(),
            "real_money": is_real
        }
        
        ws.close()
        return True

    except Exception as e:
        log(f"❌ Trade Error: {e}")
        import traceback
        log(traceback.format_exc()[:300])
        last_signal["deriv"] = f"ERROR: {e}"
        last_trade_result = {"error": str(e), "time": datetime.now().isoformat()}
        return False

def bot_logic(force=False):
    global last_signal
    try:
        price = get_btc_price()
        if not price:
            log("No price - retry")
            return
        
        supports, resistances = get_sr_levels(price)
        log(f"\n=== BOT CHECK BTC ${price:.2f} | Buys {holdings['total_buys']} | Force={force} ===")

        # FORCE TRADE - para mag trade agad test real!
        if force or (FORCE_TRADE and holdings["total_buys"] == 0):
            log(f"🟢 FORCE TRADE! Bili agad para test real execution! Price ${price:.2f}")
            trade_deriv_real("LONG", price, reason="FORCE TEST - REAL EXECUTION TEST")
            return

        # Normal logic - near support
        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"] and holdings["total_buys"] == 0:
                log(f"🟢 BUY SIGNAL Near SUP {sup:.2f} ({dist:.2f}%)")
                trade_deriv_real("LONG", price, reason=f"Near SUP {sup:.2f}")
                return

        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"] and holdings["total_buys"] == 0:
                log(f"🔴 SHORT Near RES {res:.2f} ({dist:.2f}%)")
                trade_deriv_real("SHORT", price, reason=f"Near RES {res:.2f}")
                return

        if holdings["total_buys"] > 0:
            log(f"💎 HODL {holdings['total_buys']}x Avg ${holdings['avg_price']:.2f}")
            last_signal = {"time": datetime.now().isoformat(), "signal": "HODL", "price": price, "buys": holdings["total_buys"], "deriv": last_signal.get("deriv", "ON")}
        else:
            log(f"⏳ WAITING Price ${price:.2f} Need near SUP/RES {CONFIG['NEAR_PCT']}% or set FORCE_TRADE=true")
            last_signal = {"time": datetime.now().isoformat(), "signal": "WAITING", "price": price, "deriv": last_signal.get("deriv", "WAITING")}
        
    except Exception as e:
        log(f"Bot Error: {e}")

def bot_loop():
    log(f"🚀 BOT LOOP STARTED - FORCE_TRADE={FORCE_TRADE} - EVERY 60 SEC")
    # Force trade agad pag start kung wala pa holdings at FORCE_TRADE=true
    if FORCE_TRADE:
        time.sleep(10)  # Wait 10 sec for startup
        log(f"🚀 FORCE TRADE MODE - Trading agad para test!")
        bot_logic(force=True)
    
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP - FORCE TRADE TEST ===")
    log(f"Token set: {bool(DERIV_TOKEN)} | App ID: {DERIV_APP_ID} | Force: {FORCE_TRADE}")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()

@app.get("/")
def home():
    return {
        "status": "REAL MONEY BOT - FORCE TRADE TEST!",
        "symbol": CONFIG["DERIV_SYMBOL"],
        "config": CONFIG,
        "last_signal": last_signal,
        "holdings": holdings,
        "trades_today": trades_today,
        "last_trade": last_trade_result,
        "time": datetime.now().isoformat(),
        "token_set": bool(DERIV_TOKEN),
        "app_id": str(DERIV_APP_ID),
        "note": "If token is REAL (CR), real money! If DEMO (VR), virtual! Check /force_trade to manually trade!",
        "force_trade_url": "/force_trade?direction=LONG"
    }

@app.get("/force_trade")
def force_trade(direction: str = "LONG"):
    """Manual force trade para test real execution!"""
    price = get_btc_price()
    if not price:
        return {"error": "No price available", "last_trade": last_trade_result}
    
    direction = direction.upper()
    if direction not in ["LONG", "SHORT"]:
        direction = "LONG"
    
    log(f"🔥 MANUAL FORCE TRADE triggered! {direction} @ ${price:.2f}")
    success = trade_deriv_real(direction, price, reason="MANUAL FORCE TRADE FROM /force_trade")
    
    return {
        "success": success,
        "direction": direction,
        "price": price,
        "last_trade": last_trade_result,
        "holdings": holdings,
        "time": datetime.now().isoformat()
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "holdings": holdings, "token_set": bool(DERIV_TOKEN), "last_trade": last_trade_result}

@app.get("/config")
def get_config():
    return CONFIG
    
