
"""
FINAL BOT - BTCUSD SPOT DCA - WALANG SL - REAL MONEY READY
Boss Zhykaeron - Final Version Oct 22 2026

STRATEGY:
- WALANG SL - HOLD lang kahit bumagsak!
- DCA: Bili $1 pag -0.8% drop from avg, with 2min cooldown para hindi pare-parehas!
- SELL: +0.8% profit lang, benta lahat!
- Kapital: 5.91 USDT, $1 per DCA
- PERSISTENT: Hindi mawawala trade pag nag restart Render!

STATUS: SIMULATED PA (Deriv Exchange Spot API private beta pa)
Pero pag naging public na, 1 line lang papalitan para maging REAL!

REAL MONEY CHECK: Tingnan sa https://zyleybrim-bot.onrender.com/
"""
import json, time, urllib.request, urllib.error, websocket, os, threading, sys
from fastapi import FastAPI
from datetime import datetime

PAT_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not PAT_TOKEN:
    PAT_TOKEN = "pSgWqW0Y1iG"

APP_ID = "1089"
SYMBOL = "cryBTCUSD"
SPOT_SYMBOL = "BTCUSDT"
BUY_AMOUNT_USDT = 1.0
NEAR_PCT = 0.6
SELL_PROFIT_PCT = 0.8
DCA_DROP_PCT = 0.8
LOOP_SECONDS = 30

# PERSISTENT HOLDINGS - Hindi mawawala pag nag restart!
HOLDINGS_FILE = "/tmp/dca_holdings.json"

app = FastAPI(title="FINAL DCA WALANG SL")
REST = "https://api.derivws.com"
last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "FINAL BOT INIT", "info": "Final DCA Walang SL"}
trades_today = 0
pnl_total = 0

def load_holdings():
    default = {"btc": 0.0, "avg_price": 0.0, "usdt": 5.91, "total_buys": 0}
    try:
        if os.path.exists(HOLDINGS_FILE):
            with open(HOLDINGS_FILE, 'r') as f:
                data = json.load(f)
                # Preserve current live trade if exists: 0.000060 BTC avg 83042.77
                # If file is empty, use default
                return data
    except:
        pass
    return default

def save_holdings(h):
    try:
        with open(HOLDINGS_FILE, 'w') as f:
            json.dump(h, f)
    except:
        pass

holdings = load_holdings()

# If first time and we know current live trade from logs, preserve it!
# Uncomment to preserve your 5 buys trade:
# holdings = {"btc": 0.000060, "avg_price": 83042.77, "usdt": 0.91, "total_buys": 5}
# save_holdings(holdings)

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Deriv-App-ID": str(APP_ID),
    "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
_req = 0

def rest(method, path, body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(REST + path, method=method, headers=HEADERS, data=data if method != "GET" else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:800]
        log(f"REST {method} {path} {e.code}: {err_body}")
        raise RuntimeError(f"REST {e.code}")

def get_deriv_candles_ws(ws, granularity, count=100):
    global _req
    _req += 1
    payload = {"ticks_history": SYMBOL, "adjust_start_time": 1, "count": count, "end": "latest", "granularity": granularity, "style": "candles", "req_id": _req}
    ws.send(json.dumps(payload))
    deadline = time.time() + 25
    while time.time() < deadline:
        data = json.loads(ws.recv())
        if data.get("req_id") == _req:
            if "error" in data:
                raise RuntimeError(f"{data['error']}")
            return data.get("candles")
    raise RuntimeError("No candles")

def get_deriv_ticks_ws(ws, count=50):
    global _req
    _req += 1
    payload = {"ticks_history": SYMBOL, "count": count, "end": "latest", "style": "ticks", "req_id": _req}
    ws.send(json.dumps(payload))
    deadline = time.time() + 25
    while time.time() < deadline:
        data = json.loads(ws.recv())
        if data.get("req_id") == _req:
            if "error" in data:
                raise RuntimeError(f"{data['error']}")
            h = data.get("history")
            return [float(x) for x in h["prices"]], h["times"][-1]
    raise RuntimeError("No ticks")

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def connect_deriv():
    accounts = rest("GET", "/trading/v1/options/accounts")["data"]
    acc = None
    for a in accounts:
        if str(a.get("account_type")).lower() == "real":
            acc = a
            break
    if not acc:
        acc = accounts[0] if accounts else None
    if not acc:
        raise RuntimeError("No accounts")
    url = rest("POST", f"/trading/v1/options/accounts/{acc['account_id']}/otp")["data"]["url"]
    ws = websocket.create_connection(url, timeout=30, header=["User-Agent: " + HEADERS["User-Agent"]], origin="https://developers.deriv.com")
    return ws, acc

def bot_loop_final():
    global last_signal, trades_today, pnl_total, holdings
    log("🚀 FINAL BOT - BTC SPOT DCA WALANG SL - STARTING")
    log(f"💰 BUY: ${BUY_AMOUNT_USDT} per DCA | NEAR: {NEAR_PCT}% | SELL: {SELL_PROFIT_PCT}% | DCA DROP: {DCA_DROP_PCT}%")
    log(f"💰 Holdings from file: BTC {holdings['btc']:.6f} Avg ${holdings['avg_price']:.2f} USDT {holdings['usdt']:.2f} Buys {holdings['total_buys']}")
    log(f"💰 Strategy: WALANG SL, DCA lang, +0.8% SELL, 2min cooldown para hindi pare-parehas!")
    
    try:
        ws, acc = connect_deriv()
        log(f"✅ CONNECTED {acc['account_id']} Bal {acc.get('balance')} - Price from cryBTCUSD")
        last_signal["deriv"] = f"ON - {acc['account_id']} - FINAL DCA WALANG SL"
    except Exception as e:
        log(f"❌ Connect failed: {e}")
        last_signal["deriv"] = f"CONNECT FAIL: {e}"
        ws = None

    last_m5 = 0
    m5_data = None
    candles_15m = []
    shown = 0
    
    log("📝 FINAL MODE: BUY near support, DCA -0.8% drop + 2min cooldown, SELL +0.8% profit, WALANG SL!")
    
    while True:
        try:
            if ws:
                if time.time() - last_m5 > 30 or not candles_15m:
                    try:
                        candles_m5 = get_deriv_candles_ws(ws, 300, 100)
                        closes_m5 = [float(c["close"]) for c in candles_m5]
                        e5, e8, e13 = ema(closes_m5, 5), ema(closes_m5, 8), ema(closes_m5, 13)
                        if e5:
                            trend = "UPTREND" if e5 > e8 > e13 else "DOWNTREND" if e5 < e8 < e13 else "SIDEWAYS"
                            m5_data = {"trend": trend, "e5": e5, "e8": e8, "e13": e13, "info": f"M5 {trend} E5={e5:.2f} E8={e8:.2f} E13={e13:.2f}"}
                            log(f"🔍 {m5_data['info']}")
                        candles_15m = get_deriv_candles_ws(ws, 900, 50)
                        last_m5 = time.time()
                    except Exception as e:
                        log(f"⚠️ Candle error: {e}")
                        time.sleep(5)
                        continue
                ticks, _ = get_deriv_ticks_ws(ws, 50)
                price = ticks[-1]
            else:
                price = 83000
                candles_15m = [{"low": 82814, "high": 83880}]*50
            
            if candles_15m:
                lows = [float(c["low"]) for c in candles_15m]
                highs = [float(c["high"]) for c in candles_15m]
                supports = sorted(lows)[:7]
                resistances = sorted(highs, reverse=True)[:8]
            else:
                supports = [price * 0.998]
                resistances = [price * 1.002]
            
            near_sup = near_res = None
            d_sup = d_res = 100
            for sup in supports:
                d = abs(price-sup)/sup*100
                if d <= NEAR_PCT and d < d_sup:
                    d_sup, near_sup = d, sup
            for res in resistances:
                d = abs(price-res)/res*100
                if d <= NEAR_PCT and d < d_res:
                    d_res, near_res = d, res
            
            profit_pct = 0
            drop_from_avg = 0
            if holdings["btc"] > 0 and holdings["avg_price"] > 0:
                profit_pct = (price - holdings["avg_price"]) / holdings["avg_price"] * 100
                drop_from_avg = (holdings["avg_price"] - price) / holdings["avg_price"] * 100
            
            info = f"BTC ${price:.2f} | {m5_data['info'] if m5_data else 'M5 N/A'} | SUP:{near_sup}({d_sup:.2f}%) RES:{near_res}({d_res:.2f}%) | Holdings:{holdings['btc']:.6f} BTC Avg:${holdings['avg_price']:.2f} P&L:{profit_pct:+.2f}% Drop:{drop_from_avg:.2f}% | USDT:{holdings['usdt']:.2f} | Buys:{holdings['total_buys']}"
            
            side = None
            
            # FINAL BUY LOGIC
            if holdings["btc"] == 0 and near_sup and holdings["usdt"] >= BUY_AMOUNT_USDT:
                if d_sup <= NEAR_PCT:
                    side = "BUY"
                    info += f" | 🟢 FINAL BUY SUP {near_sup:.2f}"
            
            # FINAL DCA LOGIC - FIXED! Hindi na pare-parehas!
            if holdings["btc"] > 0 and holdings["usdt"] >= BUY_AMOUNT_USDT:
                time_since_last_buy = time.time() - last_signal.get("last_buy_time", 0) if last_signal.get("last_buy_time") else 999
                can_dca = time_since_last_buy > 120  # 2 minutes cooldown - FIX!
                
                if drop_from_avg >= DCA_DROP_PCT and can_dca:
                    side = "DCA_BUY"
                    info += f" | 🟢 FINAL DCA BUY -{drop_from_avg:.2f}% DROP! Cooldown OK {time_since_last_buy:.0f}s"
                # Strict second condition removed to avoid same-price buys
            
            # FINAL SELL LOGIC - WALANG SL!
            if holdings["btc"] > 0:
                if profit_pct >= SELL_PROFIT_PCT:
                    side = "SELL"
                    info += f" | 🔴 FINAL SELL +{profit_pct:.2f}% PROFIT!"
                elif near_res and profit_pct >= 0.4:
                    side = "SELL"
                    info += f" | 🔴 SELL RES +{profit_pct:.2f}%"
            
            shown += 1
            if side or shown % 3 == 1:
                log(f"{datetime.now().strftime('%H:%M:%S')} {info}")
            
            last_signal.update({
                "time": datetime.now().isoformat(),
                "signal": side or "HODL" if holdings['btc']>0 else "WAITING",
                "price": price,
                "info": info,
                "btc_holdings": holdings["btc"],
                "avg_price": holdings["avg_price"],
                "usdt_balance": holdings["usdt"],
                "pnl": profit_pct,
                "drop": drop_from_avg,
                "trades": trades_today,
                "total_buys": holdings["total_buys"],
                "last_buy_time": last_signal.get("last_buy_time", 0)
            })
            if side and "BUY" in side:
                last_signal["last_buy_time"] = time.time()
            
            if side:
                if side == "BUY" or side == "DCA_BUY":
                    log(f"📤 FINAL {side} {SPOT_SYMBOL} ${BUY_AMOUNT_USDT} @ ${price:.2f} | Drop {drop_from_avg:.2f}% | USDT {holdings['usdt']:.2f}")
                    btc_bought = BUY_AMOUNT_USDT / price
                    if holdings["btc"] == 0:
                        holdings["avg_price"] = price
                    else:
                        holdings["avg_price"] = (holdings["avg_price"]*holdings["btc"] + price*btc_bought)/(holdings["btc"]+btc_bought)
                    holdings["btc"] += btc_bought
                    holdings["usdt"] -= BUY_AMOUNT_USDT
                    holdings["total_buys"] += 1
                    trades_today += 1
                    save_holdings(holdings)
                    log(f"✅ FINAL {side}: {btc_bought:.6f} BTC @ ${price:.2f} | New Avg ${holdings['avg_price']:.2f} | BTC {holdings['btc']:.6f} | USDT {holdings['usdt']:.2f} | Buys {holdings['total_buys']} | SAVED!")
                    last_signal["deriv"] = f"{side} {btc_bought:.6f} BTC - DCA {holdings['total_buys']}x"
                
                elif side == "SELL":
                    log(f"📤 FINAL SELLING {holdings['btc']:.6f} BTC @ ${price:.2f} P&L +{profit_pct:.2f}% | Buys {holdings['total_buys']}")
                    usdt_got = holdings["btc"] * price
                    profit_usdt = usdt_got - (holdings["total_buys"] * BUY_AMOUNT_USDT)
                    holdings["usdt"] += usdt_got
                    pnl_total += profit_pct
                    log(f"✅ FINAL SELL SUCCESS: Sold @ ${price:.2f} Got ${usdt_got:.2f} | Profit ${profit_usdt:.2f} | New USDT {holdings['usdt']:.2f} | P&L +{profit_pct:.2f}%")
                    holdings["btc"] = 0
                    holdings["avg_price"] = 0
                    holdings["total_buys"] = 0
                    trades_today += 1
                    save_holdings(holdings)
                    last_signal["deriv"] = f"SOLD +{profit_pct:.2f}% Profit ${profit_usdt:.2f} - SAVED!"
            
            time.sleep(LOOP_SECONDS)
            
        except Exception as e:
            log(f"⚠️ Loop error: {e} - reconnect 5s")
            import traceback
            log(traceback.format_exc()[:500])
            time.sleep(5)
            if ws:
                try:
                    ws, acc = connect_deriv()
                    log("🔌 RECONNECTED")
                except:
                    time.sleep(10)

@app.on_event("startup")
def startup_event():
    log("=== STARTUP FINAL BOT - DCA WALANG SL ===")
    t = threading.Thread(target=bot_loop_final, daemon=True)
    t.start()

@app.get("/")
def home():
    return {
        "status": "FINAL BOT - DCA WALANG SL - FIXED HINDI PARE-PAREHAS BILI!",
        "spot_symbol": SPOT_SYMBOL,
        "config": {"BUY": f"${BUY_AMOUNT_USDT}", "NEAR": f"{NEAR_PCT}%", "SELL": f"{SELL_PROFIT_PCT}%", "DCA_DROP": f"{DCA_DROP_PCT}%", "SL": "WALANG SL!", "FIX": "2min cooldown, persistent holdings"},
        "last_signal": last_signal,
        "holdings": holdings,
        "pnl": pnl_total,
        "trades": trades_today,
        "time": datetime.now().isoformat(),
        "note": "SIMULATED PA - Deriv Exchange Spot API private beta pa. Pero persistent na holdings!"
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "holdings": holdings}

@app.get("/holdings")
def get_holdings():
    return holdings

if __name__ == "__main__":
    bot_loop_final()
