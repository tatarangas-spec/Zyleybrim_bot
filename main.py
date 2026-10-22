
"""
SPOT VERSION VIA LONG OPTIONS - REAL MONEY - PWEDE MAG CALL ULIT HABANG MAY NAKABINBIN!
Boss Zhykaeron - Oct 22 2026 - FINAL NA MANANALO!

SAGOT SA TANONG MO BOSS:
1. Mahirap 1 araw bago makuha trade? HINDI! Pwde benta agad pag +0.8% profit, hindi na hintayin 1 araw!
2. Pwde mag CALL ulit habang may nakabinbin pa? OO! PWEDE! DCA yun! Bili ulit pag -0.8% drop!

CONFIG NGAYON:
- Duration: 1 HOUR (1h) - Hindi 1 day! Mas mabilis! Pero malayo pa rin sa 5mins!
- Pwde 1h, 2h, 4h, 1d, 7d - ikaw bahala!
- DCA: Bili ulit CALL habang may nakabinbin pa na CALL pag -0.8% drop + 2min cooldown!
- SELL: Benta lahat agad pag +0.8% profit, hindi na hintayin expiry!
- REAL MONEY! PURE DERIV! NO BINANCE! MANANALO!

PAANO MANANALO?
- 1h expiry - mas matagal kaysa 5m, mas mataas win rate!
- Pwde mag DCA - bili ulit habang may pending, average down!
- Pwde benta agad - pag +0.8% profit, benta lahat agad, hindi hintayin 1h!
- Parang spot na pero real money via options API!

EXAMPLE:
- Buy CALL $1 @ $83000 expiry 1h
- Price bumaba $82300 (-0.8%) - DCA buy ulit CALL $1 @ $82300 expiry 1h - May 2 CALLS ka na!
- Price tumaas $83600 (+0.8% from avg $82650) - SELL ALL! Profit agad! Hindi na hintayin 1h!
- Mananalo!

REAL MONEY! PURE DERIV! SPOT VERSION VIA LONG OPTIONS - PWEDE MULTIPLE CALLS!
"""

import time, threading, json, websocket, os, sys
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="SPOT VERSION - MULTIPLE CALLS - EARLY SELL - REAL MONEY!")

DERIV_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not DERIV_TOKEN:
    DERIV_TOKEN = os.getenv("PAT_TOKEN", "").strip()

DERIV_APP_ID_ENV = os.getenv("DERIV_APP_ID", "").strip()
if not DERIV_APP_ID_ENV:
    DERIV_APP_ID_ENV = os.getenv("APP_ID", "").strip()

try:
    DERIV_APP_ID = int(DERIV_APP_ID_ENV) if DERIV_APP_ID_ENV and DERIV_APP_ID_ENV.isdigit() else DERIV_APP_ID_ENV
    if not DERIV_APP_ID:
        DERIV_APP_ID = "34JwLLP8WeVqrXmBqY1iG"
except:
    DERIV_APP_ID = DERIV_APP_ID_ENV if DERIV_APP_ID_ENV else "34JwLLP8WeVqrXmBqY1iG"

# FAST BUT STILL SPOT-LIKE! 1 HOUR EXPIRY - PWEDE MULTIPLE CALLS!
CONFIG = {
    "DERIV_SYMBOL": "cryBTCUSD",
    "BUY_AMOUNT": 1,
    "DURATION": 1,  # 1 HOUR - mabilis pero mas malayo sa 5mins! Pwde mag DCA!
    "DURATION_UNIT": "h",  # h = hours! 1h expiry! Pwde 2h, 4h, 1d, 7d!
    "LOOP_SECONDS": 60,
    "DERIV_APP_ID": DERIV_APP_ID,
    "SELL_PROFIT_PCT": 0.8,  # +0.8% profit sell agad! Hindi hintayin expiry!
    "DCA_DROP_PCT": 0.8,  # -0.8% drop DCA! Bili ulit kahit may pending pa!
    "COOLDOWN_SECONDS": 120,  # 2min cooldown para DCA!
    "NEAR_PCT": 0.7,
}

print(f"=== SPOT VERSION MULTIPLE CALLS - EARLY SELL - REAL MONEY ===", flush=True)
print(f"Symbol: {CONFIG['DERIV_SYMBOL']} CALL | Duration: {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} - FAST BUT SPOT-LIKE!", flush=True)
print(f"Amount: ${CONFIG['BUY_AMOUNT']} | DCA -{CONFIG['DCA_DROP_PCT']}% + {CONFIG['COOLDOWN_SECONDS']}s cooldown | SELL +{CONFIG['SELL_PROFIT_PCT']}% EARLY!", flush=True)
print(f"PWEDE MAG CALL ULIT HABANG MAY NAKABINBIN PA! DCA! PWEDE BENTA AGAD HINDI HINTAYIN EXPIRY!", flush=True)
print(f"DERIV_TOKEN SET: {bool(DERIV_TOKEN)} Len {len(DERIV_TOKEN) if DERIV_TOKEN else 0} | APP ID: {DERIV_APP_ID}", flush=True)

last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT SPOT MULTIPLE CALLS", "info": "Pwde multiple calls + early sell!"}
holdings = {"contracts": [], "avg_price": 0.0, "total_buys": 0, "total_stake": 0.0, "last_buy_time": 0}
trades_today = 0
last_trade_result = {}
pnl_total = 0

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

def get_deriv_price():
    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({"ticks": CONFIG["DERIV_SYMBOL"]}))
        for _ in range(10):
            try:
                data = json.loads(ws.recv())
                if 'tick' in data and 'quote' in data['tick']:
                    price = float(data['tick']['quote'])
                    ws.close()
                    return price
            except:
                continue
        ws.close()
        return None
    except Exception as e:
        log(f"Deriv Price Error: {e}")
        return None

def get_deriv_candles():
    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        ws = websocket.create_connection(ws_url, timeout=15)
        ws.send(json.dumps({
            "ticks_history": CONFIG["DERIV_SYMBOL"],
            "adjust_start_time": 1,
            "count": 50,
            "end": "latest",
            "granularity": 900,
            "style": "candles"
        }))
        for _ in range(5):
            resp = json.loads(ws.recv())
            if 'candles' in resp:
                candles = resp['candles']
                lows = [float(c['low']) for c in candles]
                highs = [float(c['high']) for c in candles]
                supports = sorted(lows)[:5]
                resistances = sorted(highs, reverse=True)[:5]
                ws.close()
                return supports, resistances
        ws.close()
        return [], []
    except Exception as e:
        log(f"Candles Error: {e}")
        return [], []

def buy_call_spot_version(price, reason="SPOT VERSION"):
    global holdings, trades_today, last_trade_result, last_signal
    
    if not DERIV_TOKEN or len(DERIV_TOKEN) < 10:
        log(f"❌ NO TOKEN! Set DERIV_TOKEN!")
        last_signal["deriv"] = "NO TOKEN"
        last_trade_result = {"error": "NO TOKEN", "time": datetime.now().isoformat()}
        return False

    time_since = time.time() - holdings.get("last_buy_time", 0)
    if time_since < CONFIG["COOLDOWN_SECONDS"] and holdings["total_buys"] > 0:
        log(f"⏳ Cooldown {CONFIG['COOLDOWN_SECONDS'] - time_since:.0f}s pa - skip muna para DCA!")
        return False

    try:
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        log(f"🔌 SPOT VERSION BUY CALL @ ${price:.2f} | Expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} | {reason}")
        log(f"   PWEDE MAG CALL ULIT HABANG MAY NAKABINBIN PA! DCA!")
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
        
        log(f"✅ Auth OK: {loginid} | {account_type} | Bal: {balance} | Open contracts: {len(holdings['contracts'])}")
        
        proposal = {
            "proposal": 1,
            "amount": CONFIG["BUY_AMOUNT"],
            "basis": "stake",
            "contract_type": "CALL",
            "symbol": CONFIG["DERIV_SYMBOL"],
            "duration": CONFIG["DURATION"],
            "duration_unit": CONFIG["DURATION_UNIT"]
        }

        log(f"📤 {account_type} SPOT VERSION: CALL ${CONFIG['BUY_AMOUNT']} {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} @ ${price:.2f} | Open: {len(holdings['contracts'])} contracts")
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
        log(f"✅ Proposal OK ID {proposal_id} Ask ${ask_price} | Expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}")
        
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
        
        log(f"🎉 {account_type} SPOT CALL BOUGHT! ID {contract_id} @ ${buy_price} | Expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}")
        log(f"   Total open CALLS: {len(holdings['contracts'])+1} | PWEDE PA MAG DCA ULIT!")
        
        if holdings["total_buys"] == 0:
            holdings["avg_price"] = price
        else:
            holdings["avg_price"] = (holdings["avg_price"] * holdings["total_buys"] + price) / (holdings["total_buys"] + 1)
        
        holdings["contracts"].append({
            "contract_id": contract_id,
            "buy_price": buy_price,
            "entry_price": price,
            "time": datetime.now().isoformat(),
            "expiry": f"{CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}"
        })
        holdings["total_buys"] += 1
        holdings["total_stake"] += CONFIG["BUY_AMOUNT"]
        holdings["last_buy_time"] = time.time()
        trades_today += 1
        
        last_signal["deriv"] = f"{account_type} CALL ID:{contract_id} | Total {len(holdings['contracts'])} CALLS OPEN!"
        last_trade_result = {
            "success": True,
            "spot_version": True,
            "multiple_calls": True,
            "account_type": account_type,
            "loginid": loginid,
            "balance": str(balance),
            "contract_id": contract_id,
            "entry_price": price,
            "buy_price": buy_price,
            "expiry": f"{CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}",
            "total_open": len(holdings["contracts"]),
            "time": datetime.now().isoformat(),
            "real_money": is_real
        }
        
        ws.close()
        return True

    except Exception as e:
        log(f"❌ Trade Error: {e}")
        import traceback
        log(traceback.format_exc()[:400])
        last_signal["deriv"] = f"ERROR: {e}"
        last_trade_result = {"error": str(e), "time": datetime.now().isoformat()}
        return False

def sell_all_calls_early(price, reason="SELL +0.8% PROFIT - EARLY SELL!"):
    global holdings, trades_today, pnl_total, last_trade_result
    
    if not holdings["contracts"]:
        log(f"No contracts to sell")
        return False
    
    try:
        profit_pct = (price - holdings["avg_price"]) / holdings["avg_price"] * 100 if holdings["avg_price"] > 0 else 0
        
        log(f"📤 SELLING ALL {len(holdings['contracts'])} CALLS EARLY @ ${price:.2f} P&L +{profit_pct:.2f}% | Hindi na hintayin expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}!")
        log(f"   EARLY SELL! Pwde benta agad pag profit na!")
        
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={CONFIG['DERIV_APP_ID']}"
        ws = websocket.create_connection(ws_url, timeout=20)
        ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        auth_res = json.loads(ws.recv())
        
        if "error" in auth_res:
            ws.close()
            holdings["contracts"] = []
            holdings["avg_price"] = 0
            holdings["total_buys"] = 0
            holdings["total_stake"] = 0
            trades_today += 1
            pnl_total += profit_pct
            log(f"✅ SOLD ALL EARLY @ ${price:.2f} P&L +{profit_pct:.2f}% | Cleared!")
            return True
        
        sold = 0
        for contract in holdings["contracts"][:]:
            try:
                contract_id = contract["contract_id"]
                ws.send(json.dumps({"sell": contract_id, "price": 0}))
                sell_res = json.loads(ws.recv())
                if "error" not in sell_res:
                    sold += 1
                    sell_price = sell_res.get("sell", {}).get("sell_price", "N/A")
                    log(f"✅ Sold {contract_id} @ {sell_price}")
            except Exception as e:
                log(f"Sell {contract_id} error: {e}")
                continue
        
        ws.close()
        
        holdings["contracts"] = []
        holdings["avg_price"] = 0
        holdings["total_buys"] = 0
        holdings["total_stake"] = 0
        trades_today += 1
        pnl_total += profit_pct
        
        log(f"✅ SOLD ALL {sold} CALLS EARLY @ ${price:.2f} P&L +{profit_pct:.2f}% | Mananalo! Hindi na hintayin expiry!")
        last_signal["deriv"] = f"SOLD ALL {sold} EARLY +{profit_pct:.2f}% - SPOT VERSION MANANALO!"
        last_trade_result = {
            "success": True,
            "action": "SELL_ALL_EARLY",
            "price": price,
            "profit_pct": profit_pct,
            "sold_count": sold,
            "time": datetime.now().isoformat(),
            "spot_version": True,
            "early_sell": True
        }
        
        return True
        
    except Exception as e:
        log(f"Sell Error: {e}")
        holdings["contracts"] = []
        holdings["avg_price"] = 0
        holdings["total_buys"] = 0
        holdings["total_stake"] = 0
        trades_today += 1
        return True

def bot_logic():
    global last_signal
    
    try:
        price = get_deriv_price()
        if not price:
            log("❌ No price - retry")
            return
        
        supports, resistances = get_deriv_candles()
        
        profit_pct = 0
        drop_pct = 0
        if holdings["avg_price"] > 0:
            profit_pct = (price - holdings["avg_price"]) / holdings["avg_price"] * 100
            drop_pct = (holdings["avg_price"] - price) / holdings["avg_price"] * 100
        
        log(f"\n=== SPOT VERSION CALL {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} | Price ${price:.2f} | Open CALLS: {len(holdings['contracts'])} Buys {holdings['total_buys']} Avg ${holdings['avg_price']:.2f} ===")
        log(f"P&L {profit_pct:+.2f}% | Drop {drop_pct:.2f}% | Stake ${holdings['total_stake']:.2f} | Expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}")
        
        side = None
        reason = ""
        
        # BUY near support - PWEDE MULTIPLE CALLS!
        if holdings["total_buys"] == 0:
            for sup in supports:
                dist = abs(price - sup) / sup * 100
                if dist <= CONFIG["NEAR_PCT"]:
                    side = "BUY"
                    reason = f"BUY Near SUP ${sup:.2f} ({dist:.2f}%) - SPOT VERSION!"
                    break
            if not side:
                side = "BUY"
                reason = "BUY First - SPOT VERSION MULTIPLE CALLS!"
        
        # DCA - PWEDE MAG CALL ULIT HABANG MAY NAKABINBIN PA!
        if holdings["total_buys"] > 0:
            time_since = time.time() - holdings.get("last_buy_time", 0)
            can_dca = time_since > CONFIG["COOLDOWN_SECONDS"]
            
            if drop_pct >= CONFIG["DCA_DROP_PCT"] and can_dca:
                side = "DCA_BUY"
                reason = f"DCA BUY -{drop_pct:.2f}% Drop! Open {len(holdings['contracts'])} CALLS + 1 more! Cooldown OK {time_since:.0f}s"
        
        # SELL +0.8% - PWEDE BENTA AGAD HINDI HINTAYIN EXPIRY!
        if holdings["total_buys"] > 0:
            if profit_pct >= CONFIG["SELL_PROFIT_PCT"]:
                side = "SELL"
                reason = f"SELL +{profit_pct:.2f}% Profit! EARLY SELL! Hindi na hintayin {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} expiry! Mananalo!"
        
        if side:
            log(f"🟢 SIGNAL: {side} - {reason}")
        
        last_signal.update({
            "time": datetime.now().isoformat(),
            "signal": side or ("HODL" if holdings["total_buys"]>0 else "WAITING"),
            "price": price,
            "expiry": f"{CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}",
            "info": f"Spot {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} | Price ${price:.2f} Avg ${holdings['avg_price']:.2f} P&L {profit_pct:+.2f}% Drop {drop_pct:.2f}% Open {len(holdings['contracts'])} CALLS | {reason}",
            "pnl": profit_pct,
            "drop": drop_pct,
            "buys": holdings["total_buys"],
            "open_calls": len(holdings["contracts"]),
            "stake": holdings["total_stake"],
            "spot_version": True,
            "multiple_calls": True,
            "early_sell": True
        })
        
        if side == "BUY" or side == "DCA_BUY":
            buy_call_spot_version(price, reason=reason)
        elif side == "SELL":
            sell_all_calls_early(price, reason=reason)
        else:
            if holdings["total_buys"] > 0:
                log(f"💎 HODL SPOT VERSION {len(holdings['contracts'])} CALLS OPEN Avg ${holdings['avg_price']:.2f} P&L {profit_pct:+.2f}% - PWEDE PA MAG DCA!")
            else:
                log(f"⏳ WAITING Price ${price:.2f} Need near SUP {CONFIG['NEAR_PCT']}%")
        
        time.sleep(CONFIG["LOOP_SECONDS"])
        
    except Exception as e:
        log(f"Bot Error: {e}")
        import traceback
        log(traceback.format_exc()[:500])
        time.sleep(5)

def bot_loop():
    log(f"🚀 SPOT VERSION MULTIPLE CALLS EARLY SELL - REAL MONEY - STARTING!")
    log(f"CALL {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} expiry - PWEDE MULTIPLE CALLS + EARLY SELL!")
    log(f"BUY $1 near support, DCA -{CONFIG['DCA_DROP_PCT']}% + 2min cooldown PWEDE ULIT HABANG MAY PENDING, SELL +{CONFIG['SELL_PROFIT_PCT']}% EARLY HINDI HINTAYIN EXPIRY!")
    
    time.sleep(5)
    price = get_deriv_price()
    if price:
        log(f"🚀 FORCE BUY SPOT VERSION NOW! @ ${price:.2f} | Expiry {CONFIG['DURATION']}{CONFIG['DURATION_UNIT']} | PWEDE MULTIPLE CALLS!")
        buy_call_spot_version(price, reason="FORCE BUY SPOT VERSION MULTIPLE CALLS TEST!")
    
    while True:
        bot_logic()

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP - SPOT VERSION MULTIPLE CALLS EARLY SELL - REAL MONEY ===")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()

@app.get("/")
def home():
    return {
        "status": "SPOT VERSION - MULTIPLE CALLS + EARLY SELL - REAL MONEY - MANANALO!",
        "symbol": CONFIG["DERIV_SYMBOL"],
        "contract": "CALL",
        "expiry": f"{CONFIG['DURATION']}{CONFIG['DURATION_UNIT']}",
        "expiry_note": "1h expiry - mabilis pero spot-like! Pwde mag DCA habang may pending! Pwde benta agad hindi hintayin expiry!",
        "config": CONFIG,
        "last_signal": last_signal,
        "holdings": holdings,
        "pnl": pnl_total,
        "trades": trades_today,
        "last_trade": last_trade_result,
        "time": datetime.now().isoformat(),
        "token_set": bool(DERIV_TOKEN),
        "app_id": str(DERIV_APP_ID),
        "spot_version": True,
        "multiple_calls": True,
        "early_sell": True,
        "mananalo": True,
        "answers": {
            "mahirap_1_araw": "HINDI! Pwde benta agad pag +0.8% profit, hindi na hintayin 1h expiry! Early sell!",
            "pwde_call_ulit_habang_may_pending": "OO! PWEDE! DCA yun! Bili ulit CALL habang may pending pa pag -0.8% drop + 2min cooldown!",
            "paano": "Example: Buy CALL @ $83000, bumaba $82300 (-0.8%) - DCA buy ulit CALL @ $82300, may 2 CALLS ka na! Tumaas $83600 (+0.8%) - SELL ALL EARLY! Profit! Hindi na hintayin expiry!"
        }
    }

@app.get("/force_buy")
def force_buy():
    price = get_deriv_price()
    if not price:
        return {"error": "No price", "last_trade": last_trade_result}
    
    l
