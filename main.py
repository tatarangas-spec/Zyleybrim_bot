"""
BTCUSD MTF V3 LUWAG + WORKING DERIV CONNECTION (Pydroid Style)
- Koneksyon: PAT REST + OTP (yung gumagana sa Pydroid mo boss)
- Symbol: cryBTCUSD (BTCUSD sa Deriv)
- Strategy: MTF V3 Support/Resistance + EMA 5/8/13 M5 Trend Filter + Pullback
"""
import json
import time
import urllib.request
import urllib.error
import websocket
import os
import threading
import requests
from fastapi import FastAPI
from datetime import datetime
import sys

PAT_TOKEN = os.getenv("DERIV_TOKEN", "pat_4bde30379135747a3544db14e78654ea412c775bb69170dbf3c0c05ccac63589").strip()
APP_ID = "34JwLLP8WeVqrXmBqY1iG"
SYMBOL = "cryBTCUSD"
SYMBOL_BINANCE = "BTCUSDT"
EMA_FAST, EMA_MID, EMA_SLOW = 5, 8, 13
DURATION_TICKS = 5
STAKE = 1
CURRENCY = "USD"
NEAR_PCT = 0.7
TP_PCT = 1.5
SL_PCT = 0.8
LOOP_SECONDS = 60
MAX_TRADES_PER_DAY = 50
MAX_LOSS = 10.0
MAX_WIN = 20.0

app = FastAPI(title="BTCUSD MTF V3 LUWAG - WORKING DERIV")

REST = "https://api.derivws.com"
last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "OFF", "pnl": 0}
pnl_total = 0
trades_today = 0
last_trade_time = 0

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Deriv-App-ID": str(APP_ID),
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) Pydroid3",
    "Accept": "application/json",
}

_req = 0

def rest(method, path):
    req = urllib.request.Request(REST + path, method=method, headers=HEADERS,
                                 data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"REST {e.code}: {e.read().decode()[:300]}")

def find_real_account():
    try:
        accounts = rest("GET", "/trading/v1/options/accounts")["data"]
        log(f"📋 Accounts: {[(a.get('account_id'), a.get('account_type'), a.get('balance')) for a in accounts]}")
        for a in accounts:
            if str(a.get("account_type", "")).lower() == "real":
                log(f"✅ REAL NA: {a.get('account_id')} Bal {a.get('balance')}")
                return a
        log("⚠️ No REAL account, using first DEMO")
        return accounts[0] if accounts else None
    except Exception as e:
        log(f"❌ find_real_account Error: {e}")
        return None

def connect(account_id):
    url = rest("POST", f"/trading/v1/options/accounts/{account_id}/otp")["data"]["url"]
    return websocket.create_connection(
        url, timeout=30,
        header=["User-Agent: " + HEADERS["User-Agent"]],
        origin="https://developers.deriv.com")

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
                err = data["error"]
                raise RuntimeError(f"{err.get('code')}: {err.get('message')}")
            return data
    raise RuntimeError("Walang sagot sa server")

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def get_btc_price_binance():
    sources = [
        "https://api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
        "https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    ]
    for url in sources:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}).json()
            if "price" in r:
                return float(r["price"])
            if "bitcoin" in r:
                return float(r["bitcoin"]["usd"])
        except:
            continue
    return None

def get_sr_levels_binance():
    try:
        url = "https://api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=50"
        data = requests.get(url, timeout=10).json()
        if isinstance(data, list):
            lows = [float(c[3]) for c in data]
            highs = [float(c[2]) for c in data]
            supports = sorted(lows)[:7]
            resistances = sorted(highs, reverse=True)[:8]
            return supports, resistances
    except Exception as e:
        log(f"SR Error: {e}")
    return [], []

def get_ticks_deriv(ws, count=50):
    r = call(ws, {"ticks_history": SYMBOL, "count": count, "end": "latest", "style": "ticks"})
    h = r.get("history")
    if not h:
        raise RuntimeError("Hindi makuha ang ticks")
    return [float(x) for x in h["prices"]], h["times"][-1]

def get_m5_trend_deriv(ws):
    try:
        r = call(ws, {"ticks_history": SYMBOL, "adjust_start_time": 1, "count": 100, "end": "latest", "granularity": 300, "style": "candles"})
        candles = r.get("candles")
        if not candles:
            return None, "Walang M5 candles"
        closes = [float(c["close"]) for c in candles]
        e5 = ema(closes, EMA_FAST)
        e8 = ema(closes, EMA_MID)
        e13 = ema(closes, EMA_SLOW)
        if e5 is None or e8 is None or e13 is None:
            return None, "Kulang M5 data"
        if e5 > e8 > e13:
            trend = "UPTREND"
        elif e5 < e8 < e13:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"
        info = f"M5 {trend} EMA5={e5:.2f} EMA8={e8:.2f} EMA13={e13:.2f}"
        return {"trend": trend, "e5": e5, "e8": e8, "e13": e13, "closes": closes, "info": info}, info
    except Exception as e:
        return None, f"M5 Error: {e}"

def evaluate_btcusd_mtf_v3(ws, m5_data, supports, resistances, btc_price):
    try:
        ticks, _ = get_ticks_deriv(ws, 50)
        price = ticks[-1] if ticks else btc_price
        if not price:
            return None, "No price"
        
        e5 = ema(ticks, EMA_FAST)
        e8 = ema(ticks, EMA_MID)
        e13 = ema(ticks, EMA_SLOW)
        if e5 is None:
            return None, "Kulang tick EMA"

        recent_prices = ticks[-10:]
        lowest_recent = min(recent_prices)
        highest_recent = max(recent_prices)
        t1, t2, t3 = ticks[-1], ticks[-2], ticks[-3]
        up_momentum = t1 > t2 > t3
        down_momentum = t1 < t2 < t3

        near_support = None
        near_resistance = None
        dist_sup = 100
        dist_res = 100

        for sup in supports:
            dist = abs(price - sup) / sup * 100
            if dist <= NEAR_PCT and dist < dist_sup:
                dist_sup = dist
                near_support = sup

        for res in resistances:
            dist = abs(price - res) / res * 100
            if dist <= NEAR_PCT and dist < dist_res:
                dist_res = dist
                near_resistance = res

        m5_trend = m5_data["trend"] if m5_data else "UNKNOWN"
        info_base = f"BTC ${price:.2f} | {m5_data['info'] if m5_data else 'M5 N/A'} | Near SUP:{near_support}({dist_sup:.2f}%) RES:{near_resistance}({dist_res:.2f}%)"

        if near_support:
            had_pullback = lowest_recent <= e8 * 1.001
            bounce = price > e5 and up_momentum
            if m5_trend == "UPTREND" and had_pullback and bounce:
                return "CALL", info_base + f" | 🟢 LONG MTF V3 + UPTREND + PULLBACK"

        if near_resistance:
            had_pullback_up = highest_recent >= e8 * 0.999
            bounce_down = price < e5 and down_momentum
            if m5_trend == "DOWNTREND" and had_pullback_up and bounce_down:
                return "PUT", info_base + f" | 🔴 SHORT MTF V3 + DOWNTREND + PULLBACK"

        if not m5_data:
            if near_support:
                return "CALL", info_base + f" | 🟢 LONG LUWAG (no M5) Near SUP"
            if near_resistance:
                return "PUT", info_base + f" | 🔴 SHORT LUWAG (no M5) Near RES"

        return None, info_base + " | ⏳ Waiting - No confluence"

    except Exception as e:
        return None, f"Evaluate Error: {e}"

def buy(ws, side):
    r = call(ws, {"buy": "1", "price": STAKE, "parameters": {
        "amount": STAKE, "basis": "stake", "contract_type": side.split()[0], "currency": CURRENCY,
        "duration": DURATION_TICKS, "duration_unit": "t", "underlying_symbol": SYMBOL}})
    return r["buy"]["contract_id"]

def wait_result(ws, contract_id):
    while True:
        time.sleep(2)
        poc = call(ws, {"proposal_open_contract": 1, "contract_id": contract_id})["proposal_open_contract"]
        if poc.get("is_sold") or poc.get("status") in ("won", "lost"):
            return float(poc.get("profit", 0))

def bot_loop_render():
    global last_signal, pnl_total, trades_today, last_trade_time
    log("🚀 BTCUSD MTF V3 + WORKING DERIV - STARTING")
    acc = find_real_account()
    if not acc:
        log("❌ WALANG ACCOUNT - Check DERIV_TOKEN")
        last_signal["deriv"] = "NO ACCOUNT - CHECK TOKEN"
        return
    acc_id = acc["account_id"]
    log(f"✅ Account: {acc_id} | Balance: {acc.get('balance')}")
    try:
        ws = connect(acc_id)
        log("🔌 KONEKTADO NA SA DERIV! MTF V3 + M5 TREND MODE")
        last_signal["deriv"] = f"ON - Connected {acc_id}"
    except Exception as e:
        log(f"❌ Connect failed: {e}")
        last_signal["deriv"] = f"CONNECT FAIL: {e}"
        return

    last_m5_check = 0
    m5_data = None
    shown = 0

    while True:
        try:
            btc_price = get_btc_price_binance()
            supports, resistances = get_sr_levels_binance()

            if time.time() - last_m5_check > 30:
                m5_data, m5_info = get_m5_trend_deriv(ws)
                last_m5_check = time.time()
                if m5_data:
                    log(f"🔍 {m5_info}")

            side, info = evaluate_btcusd_mtf_v3(ws, m5_data, supports, resistances, btc_price)
            shown += 1
            if side or shown % 5 == 1:
                log(f"{time.strftime('%H:%M:%S')} {info}")

            last_signal = {
                "time": datetime.now().isoformat(),
                "signal": side if side else "WAITING",
                "price": btc_price or 0,
                "info": info,
                "deriv": last_signal.get("deriv", "ON"),
                "pnl": pnl_total,
                "trades": trades_today
            }

            if side and time.time() - last_trade_time > 60:
                try:
                    log(f"📤 BUYING {side} - Trade #{trades_today+1}...")
                    cid = buy(ws, side)
                    trades_today += 1
                    log(f"✅ BOUGHT {side} ID:{cid}")
                    profit = wait_result(ws, cid)
                    pnl_total += profit
                    last_trade_time = time.time()
                    status = "✅ PANALO" if profit > 0 else "❌ TALO"
                    log(f"📊 {status} | {side} | ${profit:+.2f} | TOTAL: ${pnl_total:+.2f}")
                    last_signal["deriv"] = f"ON - LAST {side} ${profit:+.2f}"
                except RuntimeError as e:
                    log(f"❌ BUY REJECTED: {e}")
                    time.sleep(5)

            time.sleep(LOOP_SECONDS)

        except (websocket.WebSocketException, OSError) as e:
            log(f"🔌 NAWALA - Reconnect in 5s... {e}")
            time.sleep(5)
            try:
                ws = connect(acc_id)
                log("🔌 RECONNECTED!")
            except Exception as e2:
                log(f"❌ Reconnect fail: {e2}")
                time.sleep(10)
        except Exception as e:
            log(f"⚠️ Loop Error: {e}")
            time.sleep(10)

@app.on_event("startup")
def startup_event():
    log("=== APP STARTUP - STARTING BOT THREAD ===")
    t = threading.Thread(target=bot_loop_render, daemon=True)
    t.start()
    log("✅ Bot thread started - BTCUSD MTF V3 WORKING DERIV!")

@app.get("/")
def home():
    return {
        "status": "BTCUSD MTF V3 LUWAG + WORKING DERIV (Pydroid Style)",
        "symbol": SYMBOL,
        "last_signal": last_signal,
        "pnl": pnl_total,
        "trades": trades_today,
        "time": datetime.now().isoformat(),
        "token_set": bool(PAT_TOKEN),
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "token_set": bool(PAT_TOKEN), "pnl": pnl_total}

if __name__ == "__main__":
    bot_loop_render()
    
