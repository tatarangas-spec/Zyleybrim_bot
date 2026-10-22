
"""
REAL MONEY BOT - FINAL - BTCUSD OPTIONS - DCA WALANG SL - FIXED PRICE ERROR
Boss Zhykaeron - REAL EXECUTION - Oct 22 2026 - FINAL VERSION

REAL MONEY! HINDI SIMULATED!
- Real Deriv Options account - REAL MONEY!
- Real $1 per trade, real profit/loss!
- WALANG SL - HOLD lang
- DCA: Bili ulit pag -0.8% drop, with 2min cooldown
- Kapital: 5.91 USDT real!

DEMO vs REAL:
- DEMO token = account na nagsisimula sa VRW/VR - virtual money lang!
- REAL token = account na CR - real money!
- Sa logs makikita mo: REAL or DEMO!

PAANO GAWING REAL:
1. Sa Deriv: Settings > API Token > Create New Token
   - Select REAL account (CR), not demo (VR)
   - Scopes: Read, Trade, Trading Information, Payments
   - Copy token (starts with your token)
2. Sa Render: Dashboard > Environment > Add:
   DERIV_TOKEN = your real token
   DERIV_APP_ID = 34JwLLP8WeVqrXmBqY1iG (or 1089)
3. Save > Auto-deploy

FIXED: Price Error 'price' - Binance API minsan nag eerror, may fallback na!
"""
import time, threading, requests, json, websocket, os, sys
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="REAL MONEY DCA WALANG SL - FIXED")

# REAL ACCOUNT CONFIG - Galing sa Render Env!
DERIV_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("PAT_TOKEN", "").strip()
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("DERIV_PAT", "").strip()

DERIV_APP_ID_ENV = os.getenv("DERIV_APP_ID", "").strip()
if not DERIV_APP_ID_ENV:
    DERIV_APP_ID_ENV = os.getenv("APP_ID", "").strip()

try:
    DERIV_APP_ID = int(DERIV_APP_ID_ENV) if DERIV_APP_ID_ENV.isdigit() else DERIV_APP_ID_ENV
    if not DERIV_APP_ID:
        DERIV_APP_ID = "34JwLLP8WeVqrXmBqY1iG"
except:
    DERIV_APP_ID = DERIV_APP_ID_ENV if DERIV_APP_ID_ENV else "34JwLLP8WeVqrXmBqY1iG"

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "DERIV_SYMBOL": "cryBTCUSD",
    "NEAR_PCT": 0.7,
    "TP_PCT": 0.8,
    "SL_PCT": 100,  # WALANG SL - malaki para hindi ma-hit!
    "DCA_DROP_PCT": 0.8,
    "BUY_AMOUNT": 1,
    "LOOP_SECONDS": 60,
    "DERIV_ENABLED": True,
    "DERIV_APP_ID": DERIV_APP_ID,
    "DURATION": 5,
    "DURATION_UNIT": "m",
    "COOLDOWN_SECONDS": 120,
}

print(f"=== REAL MONEY BOT STARTING - FIXED VERSION ===", flush=True)
print(f"DERIV_TOKEN SET: {bool(DERIV_TOKEN)} Length: {len(DERIV_TOKEN) if DERIV_TOKEN else 0}", flush=True)
print(f"DERIV_APP_ID: {DERIV_APP_ID}", flush=True)

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT - REAL MONEY", "info": "Starting..."}
holdings = {"avg_price": 0.0, "total_buys": 0, "total_stake": 0.0, "last_buy_time": 0}
trades_today = 0

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_btc_price():
    # FIXED: Multiple fallbacks para hindi Price Error: 'price'
    # 1. Try Binance
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={CONFIG['SYMBOL']}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if 'price' in data:
            return float(data['price'])
        else:
            log(f"Binance Error Response: {data}")
    except Exception as e:
        log(f"Binance Price Error: {e}")

    # 2. Try Bybit
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={CONFIG['SYMBOL']}"
        r = requests.get(url, timeout=10).json()
        price = float(r['result']['list'][0]['lastPrice'])
        return price
    except Exception as e:
        log(f"Bybit Price Error: {e}")

    # 3. Try CoinGecko
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=10).json()
        return float(r['bitcoin']['usd'])
    except Exception as e:
        log(f"CoinGecko Price Error: {e}")

    # 4. Fallback - use Deriv cryBTCUSD via public API
    try:
        # Deriv public tick
        import websocket
        ws = websocket.create_connection(f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}", timeout=10)
        ws.send(json.dumps({"ticks": CONFIG["DERIV_SYMBOL"]}))
        tick = json.loads(ws.recv())
        if 'tick' in tick:
            price = float(tick['tick']['quote'])
            ws.close()
            return price
        ws.close()
    except Exception as e:
        log(f"Deriv Tick Price Error: {e}")

    log("Price Error: All sources failed, retry next loop")
    return None

def get_sr_levels(price):
    try:
        # Use Binance klines if price available, else simple levels
        if price:
            url = f"https://api.binance.com/api/v3/klines?symbol={CONFIG['SYMBOL']}&interval=15m&limit=50"
            data = requests.get(url, timeout=10).json()
            if isinstance(data, list) and len(data) > 0:
                lows = [float(c[3]) for c in data]
                highs = [float(c[2]) for c in data]
                supports = sorted(lows)[:7]
                resistances = sorted(highs, reverse=True)[:8]
                return supports, resistances
        # Fallback simple levels around price
        if price:
            return [price*0.998, price*0.996, price*0.994], [price*1.002, price*1.004, price*1.006]
        return [], []
    except Exception as e:
        log(f"SR Error: {e}")
        if price:
            return [price*0.998], [price*1.002]
        return [], []

def trade_deriv_real(direction, entry_price, is_dca=False):
    global last_signal, holdings, trades_today
    if not CONFIG["DERIV_ENABLED"]:
        log("Deriv OFF")
        return False
    if not DERIV_TOKEN or len(DERIV_TOKEN) < 10:
        log("❌ WALA PANG DERIV_TOKEN! Lagay mo sa Render Env Variables - DERIV_TOKEN")
        last_signal["deriv"] = "NO TOKEN - ADD DERIV_TOKEN IN RENDER"
        return False
    
    time_since_last = time.time() - holdings.get("last_buy_time", 0)
    if time_since_last < CONFIG["COOLDOWN_SECONDS"] and holdings["total_buys"] > 0:
        log(f"⏳ Cooldown pa {CONFIG['COOLDOWN_SECONDS'] - time_since_last:.0f}s - skip muna!")
        return False

    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        log(f"🔌 Connecting to Deriv REAL for {direction} @ ${entry_price:.2f} | App ID: {CONFIG['DERIV_APP_ID']}")
        ws = websocket.create_connection(ws_url, timeout=20)
        
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        if "error" in auth_res:
            log(f"❌ Deriv Auth Error: {auth_res['error']['message']}")
            log(f"👉 Check token mo! Dapat REAL account token, hindi DEMO!")
            last_signal["deriv"] = f"AUTH FAILED: {auth_res['error']['message']}"
            ws.close()
            return False
        
        loginid = auth_res['authorize']['loginid']
        balance = auth_res['authorize'].get('balance', 'N/A')
        is_real = not loginid.startswith('VR')
        account_type = "REAL" if is_real else "DEMO"
        
        log(f"✅ Deriv Auth OK: {loginid} | Type: {account_type} | Balance: {balance}")
        if not is_real:
            log(f"⚠️ DEMO ACCOUNT: {loginid} - Virtual money lang! Palitan mo ng REAL token para real money!")
            log(f"👉 Paano kumuha ng REAL token: Deriv > Settings > API Token > Select REAL account (CR) > Create")
        else:
            log(f"💰 REAL ACCOUNT: {loginid} - REAL MONEY TO BOSS! Balance ${balance}")
        
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

        dca_text = "DCA BUY" if is_dca else "INITIAL BUY"
        log(f"📤 {account_type} {dca_text}: {direction} {CONFIG['DERIV_SYMBOL']} ${CONFIG['BUY_AMOUNT']} | Entry ${entry_price:.2f}")
        ws.send(json.dumps(proposal))
        prop_res = json.loads(ws.recv())
        
        if "error" in prop_res:
            log(f"❌ Proposal Error: {prop_res['error']['message']}")
            last_signal["deriv"] = f"PROPOSAL FAIL: {prop_res['error']['message']}"
            ws.close()
            return False

        proposal_id = prop_res["proposal"]["id"]
        ask_price = prop_res["proposal"]["ask_price"]
        log(f"✅ Proposal OK: ID {proposal_id} Ask ${ask_price}")
        
        ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_res = json.loads(ws.recv())
        
        if "error" in buy_res:
            log(f"❌ Buy Error: {buy_res['error']['message']}")
            last_signal["deriv"] = f"BUY FAIL: {buy_res['error']['message']}"
            ws.close()
            return False
        
        contract_id = buy_res['buy']['contract_id']
        transaction_id = buy_res['buy']['transaction_id']
        buy_price = buy_res['buy']['buy_price']
        
        log(f"🎉 {account_type} TRADE EXECUTED! 🎉")
        log(f"✅ BOUGHT {contract_type} {CONFIG['DERIV_SYMBOL']} ${CONFIG['BUY_AMOUNT']} | {account_type}")
        log(f"Contract ID: {contract_id} | Buy Price: ${buy_price}")
        if is_real:
            log(f"💰 REAL MONEY NA TO BOSS! Check Deriv app > Portfolio!")
        else:
            log(f"⚠️ DEMO TRADE - Virtual money! Palitan ng REAL token para real money!")
        
        if holdings["total_buys"] == 0:
            holdings["avg_price"] = entry_price
        else:
            holdings["avg_price"] = (holdings["avg_price"] * holdings["total_buys"] + entry_price) / (holdings["total_buys"] + 1)
        holdings["total_buys"] += 1
        holdings["total_stake"] += CONFIG["BUY_AMOUNT"]
        holdings["last_buy_time"] = time.time()
        trades_today += 1
        
        last_signal["deriv"] = f"{account_type} TRADED {direction} ID:{contract_id} ${buy_price}"
        ws.close()
        return True

    except Exception as e:
        log(f"❌ Deriv Trade Error: {e}")
        import traceback
        log(traceback.format_exc()[:500])
        last_signal["deriv"] = f"ERROR: {e}"
        return False

def bot_logic():
    global last_signal, holdings
    try:
        price = get_btc_price()
        if not price:
            log("No price - retry next loop")
            return
        
        supports, resistances = get_sr_levels(price)
        log(f"\n=== REAL BOT CHECK BTC ${price:.2f} | Buys {holdings['total_buys']} Avg ${holdings['avg_price']:.2f} ===")

        profit_pct = 0
        drop_pct = 0
        if holdings["total_buys"] > 0 and holdings["avg_price"] > 0:
            profit_pct = (price - holdings["avg_price"]) / holdings["avg_price"] * 100
            drop_pct = (holdings["avg_price"] - price) / holdings["avg_price"] * 100
            log(f"P&L: {profit_pct:+.2f}% | Drop: {drop_pct:.2f}% | Target DCA: -{CONFIG['DCA_DROP_PCT']}%")

        # DCA LOGIC
        if holdings["total_buys"] > 0:
            if drop_pct >= CONFIG["DCA_DROP_PCT"]:
                time_since = time.time() - holdings.get("last_buy_time", 0)
                if time_since >= CONFIG["COOLDOWN_SECONDS"]:
                    log(f"🟢 DCA SIGNAL! Drop {drop_pct:.2f}% >= {CONFIG['DCA_DROP_PCT']}%")
                    trade_deriv_real("LONG", price, is_dca=True)
                    return
                else:
                    log(f"⏳ DCA ready pero cooldown pa {CONFIG['COOLDOWN_SECONDS'] - time_since:.0f}s")

        # INITIAL BUY
        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"]:
                if holdings["total_buys"] == 0:
                    log(f"🟢 INITIAL BUY SIGNAL! Near SUP {sup:.2f} ({dist:.2f}%)")
                    trade_deriv_real("LONG", price, is_dca=False)
                    return

        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"]:
                if holdings["total_buys"] == 0:
                    log(f"🔴 SHORT SIGNAL! Near RES {res:.2f} ({dist:.2f}%)")
                    trade_deriv_real("SHORT", price, is_dca=False)
                    return

        if holdings["total_buys"] > 0:
            log(f"💎 HODL - WALANG SL! Buys {holdings['total_buys']} Avg ${holdings['avg_price']:.2f} P&L {profit_pct:+.2f}%")
            last_signal = {"time": datetime.now().isoformat(), "signal": "HODL", "price": price, "pnl": profit_pct, "avg": holdings["avg_price"], "buys": holdings["total_buys"], "deriv": last_signal.get("deriv", "ON")}
        else:
            log(f"⏳ WAITING... Price ${price:.2f} | Need near SUP/RES {CONFIG['NEAR_PCT']}%")
            last_signal = {"time": datetime.now().isoformat(), "signal": "WAITING", "price": price, "deriv": last_signal.get("deriv", "WAITING")}
        
    except Exception as e:
        log(f"Bot Error: {e}")

def bot_loop():
    log("🚀 REAL MONEY BOT LOOP STARTED - FIXED PRICE ERROR - REAL EXECUTION!")
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP - REAL MONEY BOT - FIXED ===")
    log(f"Token set: {bool(DERIV_TOKEN)} | App ID: {DERIV_APP_ID}")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()

@app.get("/")
def home():
    is_real = "REAL" if DERIV_TOKEN and len(DERIV_TOKEN) > 10 else "NO TOKEN"
    return {
        "status": "REAL MONEY BOT - DCA WALANG SL - FIXED PRICE ERROR!",
        "symbol": CONFIG["DERIV_SYMBOL"],
        "config": CONFIG,
        "last_signal": last_signal,
        "holdings": holdings,
        "trades_today": trades_today,
        "time": datetime.now().isoformat(),
        "token_set": bool(DERIV_TOKEN),
        "app_id": str(DERIV_APP_ID),
        "real_money_check": is_real,
        "note": "REAL MONEY if token is REAL account (CR), DEMO if VR account. Check logs!"
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "holdings": holdings, "token_set": bool(DERIV_TOKEN)}

@app.get("/config")
def get_config():
    return CONFIG
  
