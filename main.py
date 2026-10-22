"""
BTCUSD MTF V3 LUWAG + WORKING DERIV - PURE DERIV DATA
No Binance - lahat galing Deriv cryBTCUSD
"""
import json, time, urllib.request, urllib.error, websocket, os, threading
from fastapi import FastAPI
from datetime import datetime
import sys

PAT_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not PAT_TOKEN:
    PAT_TOKEN = "pat_4bde30379135747a3544db14e78654ea412c775bb69170dbf3c0c05ccac63589"

APP_ID = "34JwLLP8WeVqrXmBqY1iG"
SYMBOL = "cryBTCUSD"
STAKE = 0.35
NEAR_PCT = 0.7
LOOP_SECONDS = 45

app = FastAPI(title="BTCUSD MTF V3 PURE DERIV")
REST = "https://api.derivws.com"
last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT", "pnl": 0, "info": "Starting..."}
pnl_total = 0
trades_today = 0
last_trade_time = 0

def log(msg):
    print(msg, flush=True)

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Deriv-App-ID": str(APP_ID),
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) Pydroid3",
    "Accept": "application/json",
}
_req = 0

def rest(method, path):
    req = urllib.request.Request(REST + path, method=method, headers=HEADERS, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def find_real_account():
    accounts = rest("GET", "/trading/v1/options/accounts")["data"]
    log(f"📋 Accounts found: {len(accounts)}")
    for a in accounts:
        if str(a.get("account_type", "")).lower() == "real":
            log(f"✅ REAL: {a.get('account_id')} Bal {a.get('balance')}")
            return a
    return accounts[0] if accounts else None

def connect(account_id):
    url = rest("POST", f"/trading/v1/options/accounts/{account_id}/otp")["data"]["url"]
    return websocket.create_connection(url, timeout=30, header=["User-Agent: " + HEADERS["User-Agent"]], origin="https://developers.deriv.com")

def call(ws, payload):
    global _req
    _req += 1
    payload["req_id"] = _req
    ws.send(json.dumps(payload))
    deadline = time.time() + 25
    while time.time() < deadline:
        data = json.loads(ws.recv())
        if data.get("req_id") == _req:
            if "error" in data:
                raise RuntimeError(f"{data['error'].get('code')}: {data['error'].get('message')}")
            return data
    raise RuntimeError("No response")

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def get_ticks(ws, count=50):
    r = call(ws, {"ticks_history": SYMBOL, "count": count, "end": "latest", "style": "ticks"})
    h = r.get("history")
    return [float(x) for x in h["prices"]], h["times"][-1]

def get_candles(ws, granularity, count=100):
    r = call(ws, {"ticks_history": SYMBOL, "adjust_start_time": 1, "count": count, "end": "latest", "granularity": granularity, "style": "candles"})
    return r.get("candles")

def get_m5_trend(ws):
    try:
        candles = get_candles(ws, 300, 100)
        closes = [float(c["close"]) for c in candles]
        e5, e8, e13 = ema(closes, 5), ema(closes, 8), ema(closes, 13)
        if e5 is None:
            return None, "Kulang"
        trend = "UPTREND" if e5 > e8 > e13 else "DOWNTREND" if e5 < e8 < e13 else "SIDEWAYS"
        info = f"M5 {trend} E5={e5:.2f} E8={e8:.2f} E13={e13:.2f}"
        return {"trend": trend, "e5": e5, "e8": e8, "e13": e13, "info": info}, info
    except Exception as e:
        return None, f"M5 Error {e}"

def evaluate(ws, m5_data, supports, resistances, price):
    try:
        ticks, _ = get_ticks(ws, 50)
        price = ticks[-1]
        e5, e8 = ema(ticks, 5), ema(ticks, 8)
        if e5 is None:
            return None, "Kulang EMA"
        low_r, high_r = min(ticks[-10:]), max(ticks[-10:])
        up_mom = ticks[-1] > ticks[-2] > ticks[-3]
        down_mom = ticks[-1] < ticks[-2] < ticks[-3]
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
        m5_trend = m5_data["trend"] if m5_data else "UNKNOWN"
        base = f"BTC ${price:.2f} | {m5_data['info'] if m5_data else 'M5 N/A'} | SUP:{near_sup}({d_sup:.2f}%) RES:{near_res}({d_res:.2f}%)"
        if near_sup and m5_trend != "DOWNTREND":
            if low_r <= e8*1.002 and price > e5 and up_mom:
                return "CALL", base + f" | 🟢 LONG SUP {near_sup:.2f}"
            if d_sup <= NEAR_PCT:
                return "CALL", base + f" | 🟢 LONG LUWAG"
        if near_res and m5_trend != "UPTREND":
            if high_r >= e8*0.998 and price < e5 and down_mom:
                return "PUT", base + f" | 🔴 SHORT RES {near_res:.2f}"
            if d_res <= NEAR_PCT:
                return "PUT", base + f" | 🔴 SHORT LUWAG"
        return None, base + " | ⏳ Waiting"
    except Exception as e:
        return None, f"Eval {e}"

def buy(ws, side):
    r = call(ws, {"buy": "1", "price": STAKE, "parameters": {"amount": STAKE, "basis": "stake", "contract_type": side.split()[0], "currency": "USD", "duration": 5, "duration_unit": "t", "underlying_symbol": SYMBOL}})
    return r["buy"]["contract_id"]

def wait_result(ws, cid):
    while True:
        time.sleep(2)
        poc = call(ws, {"proposal_open_contract": 1, "contract_id": cid})["proposal_open_contract"]
        if poc.get("is_sold") or poc.get("status") in ("won", "lost"):
            return float(poc.get("profit", 0))

def bot_loop():
    global last_signal, pnl_total, trades_today, last_trade_time
    log("🚀 BTCUSD MTF V3 PURE DERIV - NO BINANCE - STARTING")
    acc = find_real_account()
    if not acc:
        last_signal["deriv"] = "NO ACCOUNT"
        return
    acc_id = acc["account_id"]
    log(f"✅ Account {acc_id}")
    ws = connect(acc_id)
    log("🔌 CONNECTED TO DERIV - PURE DERIV MODE")
    last_signal["deriv"] = f"ON - {acc_id} Bal {acc.get('balance')}"
    last_m5 = 0
    m5_data = None
    candles_15m = []
    shown = 0
    while True:
        try:
            if time.time() - last_m5 > 30 or not candles_15m:
                m5_data, _ = get_m5_trend(ws)
                candles_15m = get_candles(ws, 900, 50)
                last_m5 = time.time()
                if m5_data:
                    log(f"🔍 {m5_data['info']} | 15m {len(candles_15m)}")
            ticks, _ = get_ticks(ws, 50)
            price = ticks[-1]
            lows = [float(c["low"]) for c in candles_15m]
            highs = [float(c["high"]) for c in candles_15m]
            supports = sorted(lows)[:7]
            resistances = sorted(highs, reverse=True)[:8]
            side, info = evaluate(ws, m5_data, supports, resistances, price)
            shown += 1
            if side or shown % 3 == 1:
                log(f"{time.strftime('%H:%M:%S')} {info}")
            last_signal.update({"time": datetime.now().isoformat(), "signal": side or "WAITING", "price": price, "info": info, "pnl": pnl_total, "trades": trades_today})
            if side and time.time() - last_trade_time > 90:
                log(f"📤 BUYING {side} Stake ${STAKE}")
                cid = buy(ws, side)
                trades_today += 1
                log(f"✅ BOUGHT {side} ID:{cid}")
                profit = wait_result(ws, cid)
                pnl_total += profit
                last_trade_time = time.time()
                log(f"📊 {'✅ PANALO' if profit>0 else '❌ TALO'} ${profit:+.2f} TOTAL ${pnl_total:+.2f}")
            time.sleep(LOOP_SECONDS)
        except Exception as e:
            log(f"⚠️ {e} - reconnect 5s")
            time.sleep(5)
            try:
                ws = connect(acc_id)
                log("🔌 RECONNECTED")
            except:
                time.sleep(10)

@app.on_event("startup")
def startup_event():
    log("=== STARTUP PURE DERIV ===")
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()

@app.get("/")
def home():
    return {"status": "BTCUSD MTF V3 PURE DERIV - WORKING", "symbol": SYMBOL, "last_signal": last_signal, "pnl": pnl_total, "trades": trades_today, "token_set": bool(PAT_TOKEN)}

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "pnl": pnl_total}

if __name__ == "__main__":
    bot_loop()
