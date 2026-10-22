
"""
REAL MONEY BOT - FINAL - BTCUSD OPTIONS - DCA WALANG SL
Boss Zhykaeron - REAL EXECUTION - Oct 22 2026

REAL MONEY! HINDI SIMULATED!
- Real Deriv Options account ROT92765017
- Real $1 per trade, real profit/loss!
- WALANG SL - HOLD lang
- DCA: Bili ulit pag -0.8% drop, with 2min cooldown para hindi pare-parehas
- SELL: +0.8% profit concept - pero sa Options, auto-settle sa expiry 5min
- Kapital: 5.91 USDT real!

PAANO GUMAGANA REAL:
- Bumibili ng REAL CALL/PUT contracts sa Deriv via WebSocket
- Real money, real balance, real profit/loss!
- Check sa Deriv app > Portfolio > Options history

Deploy to: https://zyleybrim-bot.onrender.com/
"""
import time, threading, requests, json, websocket, os, sys
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="REAL MONEY DCA WALANG SL")

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "DERIV_SYMBOL": "cryBTCUSD",
    "NEAR_PCT": 0.6,
    "TP_PCT": 0.8,  # +0.8% profit target
    "DCA_DROP_PCT": 0.8,  # -0.8% DCA
    "BUY_AMOUNT": 1,  # $1 real per trade!
    "LOOP_SECONDS": 60,
    "DERIV_ENABLED": True,
    "DERIV_APP_ID": 1089,
    "DURATION": 5,
    "DURATION_UNIT": "m",
    "COOLDOWN_SECONDS": 120,  # 2min cooldown para hindi pare-parehas!
}

DERIV_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
# Your PAT token for real trading - if not in env, use placeholder that will fail safely
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("PAT_TOKEN", "").strip()

print(f"=== REAL MONEY BOT STARTING ===", flush=True)
print(f"DERIV_TOKEN SET: {bool(DERIV_TOKEN)} Length: {len(DERIV_TOKEN) if DERIV_TOKEN else 0}", flush=True)

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT - REAL MONEY", "info": "Starting REAL bot..."}
holdings = {"avg_price": 0.0, "total_buys": 0, "total_stake": 0.0, "last_buy_time": 0}
trades_today = 0
pnl_total = 0.0

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_btc_price():
    try:
        # Use Deriv cryBTCUSD ticks for real price
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

def trade_deriv_real(direction, entry_price, is_dca=False):
    global last_signal, holdings, trades_today, pnl_total
    if not CONFIG["DERIV_ENABLED"]:
        log("Deriv OFF")
        return False
    if not DERIV_TOKEN or len(DERIV_TOKEN) < 10:
        log("❌ WALA PANG DERIV_TOKEN! Lagay mo sa Render Env Variables - DERIV_TOKEN")
        last_signal["deriv"] = "NO TOKEN - ADD DERIV_TOKEN IN RENDER"
        log("👉 Paano mag lagay: Render Dashboard > Environment > Add DERIV_TOKEN = your PAT token")
        return False
    
    # Cooldown check para hindi pare-parehas bili!
    time_since_last = time.time() - holdings.get("last_buy_time", 0)
    if time_since_last < CONFIG["COOLDOWN_SECONDS"] and holdings["total_buys"] > 0:
        log(f"⏳ Cooldown pa {CONFIG['COOLDOWN_SECONDS'] - time_since_last:.0f}s - skip muna para hindi pare-parehas!")
        return False

    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        log(f"🔌 Connecting to Deriv REAL for {direction} @ ${entry_price:.2f}")
        ws = websocket.create_connection(ws_url, timeout=20)
        
        # Authorize
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        if "error" in auth_res:
            log(f"❌ Deriv Auth Error: {auth_res['error']['message']}")
            last_signal["deriv"] = f"AUTH FAILED: {auth_res['error']['message']} - Check token!"
            ws.close()
            return False
        
        loginid = auth_res['authorize']['loginid']
        balance = auth_res['authorize'].get('balance', 'N/A')
        log(f"✅ Deriv Auth OK: {loginid} | Balance: {balance} - REAL MONEY TO BOSS!")
        
        # Check if real account
        is_real = not loginid.startswith('VR')
        if not is_real:
            log(f"⚠️ DEMO ACCOUNT: {loginid} - Hindi real money! Gamit ka REAL account CR!")
        
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
        log(f"📤 REAL {dca_text}: {direction} {CONFIG['DERIV_SYMBOL']} ${CONFIG['BUY_AMOUNT']} | Entry ${entry_price:.2f}")
        log(f"Proposal: {proposal}")
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
        
        # BUY - REAL MONEY!
        ws.send(json.dumps({"buy": proposal_id, "price": ask_price}))
        buy_res = json.loads(ws.recv())
        
        if "error" in buy_res:
            log(f"❌ Buy Error: {buy_res['error']['message']}")
            last_signal["deriv"] = f"BUY FAIL: {buy_res['error']['message']}"
            ws.close()
            return False
        
        # SUCCESS - REAL TRADE!
        contract_id = buy_res['buy']['contract_id']
        transaction_id = buy_res['buy']['transaction_id']
        buy_price = buy_res['buy']['buy_price']
        
        log(f"🎉 REAL TRADE EXECUTED! 🎉")
        log(f"✅ BOUGHT {contract_type} {CONFIG['DERIV_SYMBOL']} ${CONFIG['BUY_AMOUNT']}")
        log(f"Contract ID: {contract_id} | Transaction: {transaction_id} | Buy Price: ${buy_price}")
        log(f"Entry Price: ${entry_price:.2f} | REAL MONEY NA TO BOSS!")
        
        # Update holdings - DCA WALANG SL!
        if holdings["total_buys"] == 0:
            holdings["avg_price"] = entry_price
        else:
            # Average price
            holdings["avg_price"] = (holdings["avg_price"] * holdings["total_buys"] + entry_price) / (holdings["total_buys"] + 1)
        holdings["total_buys"] += 1
        holdings["total_stake"] += CONFIG["BUY_AMOUNT"]
        holdings["last_buy_time"] = time.time()
        trades_today += 1
        
        last_signal["deriv"] = f"REAL TRADED {direction} ID:{contract_id} ${buy_price} - REAL MONEY!"
        last_signal["info"] = f"REAL BUY {direction} @ ${entry_price:.2f} | Avg ${holdings['avg_price']:.2f} | Buys {holdings['total_buys']} | REAL!"
        
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
            log("No price - retry")
            return
        
        supports, resistances = get_sr_levels()
        log(f"\n=== REAL BOT CHECK BTC ${price:.2f} ===")
        log(f"Holdings: Avg ${holdings['avg_price']:.2f} Buys {holdings['total_buys']} Stake ${holdings['total_stake']}")

        # Calculate profit/drop
        profit_pct = 0
        drop_pct = 0
        if holdings["total_buys"] > 0 and holdings["avg_price"] > 0:
            profit_pct = (price - holdings["avg_price"]) / holdings["avg_price"] * 100
            drop_pct = (holdings["avg_price"] - price) / holdings["avg_price"] * 100
            log(f"P&L: {profit_pct:+.2f}% | Drop: {drop_pct:.2f}% | Target DCA: -{CONFIG['DCA_DROP_PCT']}% | SELL: +{CONFIG['TP_PCT']}%")

        # DCA LOGIC - Bili pag -0.8% drop + cooldown para hindi pare-parehas!
        if holdings["total_buys"] > 0:
            if drop_pct >= CONFIG["DCA_DROP_PCT"]:
                time_since = time.time() - holdings.get("last_buy_time", 0)
                if time_since >= CONFIG["COOLDOWN_SECONDS"]:
                    log(f"🟢 DCA SIGNAL! Drop {drop_pct:.2f}% >= {CONFIG['DCA_DROP_PCT']}% + Cooldown OK {time_since:.0f}s")
                    # REAL BUY!
                    success = trade_deriv_real("LONG", price, is_dca=True)
                    if success:
                        last_signal = {"time": datetime.now().isoformat(), "signal": "DCA_BUY", "price": price, "avg": holdings["avg_price"], "buys": holdings["total_buys"], "drop": drop_pct, "deriv": last_signal["deriv"], "info": f"DCA BUY @ ${price:.2f} Drop {drop_pct:.2f}%"}
                    return
                else:
                    log(f"⏳ DCA ready pero cooldown pa {CONFIG['COOLDOWN_SECONDS'] - time_since:.0f}s")

        # INITIAL BUY - Near support
        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= CONFIG["NEAR_PCT"]:
                if holdings["total_buys"] == 0:  # Only if wala pa holdings
                    log(f"🟢 INITIAL BUY SIGNAL! Near SUP {sup:.2f} ({dist:.2f}%) Entry ${price:.2f}")
                    success = trade_deriv_real("LONG", price, is_dca=False)
                    if success:
                        last_signal = {"time": datetime.now().isoformat(), "signal": "BUY", "price": price, "near": sup, "dist": dist, "deriv": last_signal["deriv"], "info": f"BUY @ ${price:.2f} Near SUP {sup:.2f}"}
                    return

        # SHORT near resistance
        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= CONFIG["NEAR_PCT"]:
                if holdings["total_buys"] == 0:
                    log(f"🔴 SHORT SIGNAL! Near RES {res:.2f} ({dist:.2f}%) Entry ${price:.2f}")
                    success = trade_deriv_real("SHORT", price, is_dca=False)
                    if success:
                        last_signal = {"time": datetime.now().isoformat(), "signal": "SHORT", "price": price, "near": res, "dist": dist, "deriv": last_signal["deriv"], "info": f"SHORT @ ${price:.2f} Near RES {res:.2f}"}
                    return

        # HODL - WALANG SL!
        if holdings["total_buys"] > 0:
            log(f"💎 HODL - WALANG SL! Buys {holdings['total_buys']} Avg ${holdings['avg_price']:.2f} P&L {profit_pct:+.2f}%")
            last_signal = {"time": datetime.now().isoformat(), "signal": "HODL", "price": price, "pnl": profit_pct, "drop": drop_pct, "avg": holdings["avg_price"], "buys": holdings["total_buys"], "deriv": last_signal.get("deriv", "ON"), "info": f"HODL {holdings['total_buys']}x Avg ${holdings['avg_price']:.2f} P&L {profit_pct:+.2f}%"}
        else:
            log(f"⏳ WAITING FOR SIGNAL... Price ${price:.2f}")
            last_signal = {"time": datetime.now().isoformat(), "signal": "WAITING", "price": price, "deriv": last_signal.get("deriv", "WAITING"), "info": f"Waiting near support/resistance"}
        
    except Exception as e:
        log(f"Bot Error: {e}")
        import traceback
        log(traceback.format_exc()[:500])

def bot_loop():
    log("🚀 REAL MONEY BOT LOOP STARTED - EVERY 60 SECONDS CHECK - REAL EXECUTION!")
    while True:
        bot_logic()
        time.sleep(CONFIG["LOOP_SECONDS"])

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP - REAL MONEY BOT - DCA WALANG SL ===")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    log("Real bot thread started! Check DERIV_TOKEN env variable!")

@app.get("/")
def home():
    return {
        "status": "REAL MONEY BOT - DCA WALANG SL - REAL EXECUTION!",
        "symbol": CONFIG["DERIV_SYMBOL"],
        "config": CONFIG,
        "last_signal": last_signal,
        "holdings": holdings,
        "trades_today": trades_today,
        "pnl": pnl_total,
        "time": datetime.now().isoformat(),
        "token_set": bool(DERIV_TOKEN and len(DERIV_TOKEN) > 10),
        "real_money": True,
        "note": "REAL MONEY! Check Deriv app > Portfolio > Options history for real trades!"
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "holdings": holdings, "token_set": bool(DERIV_TOKEN), "real_money": True}

@app.get("/config")
def get_config():
    return CONFIG
      
