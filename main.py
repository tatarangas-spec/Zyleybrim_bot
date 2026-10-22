
"""
BTCUSD SPOT DCA BOT - WALANG SL, DCA LANG!
Strategy: BTC Spot, Buy near support, DCA pag bumaba, Sell lang pag profit
- NO STOP LOSS - HOLD lang
- DCA: Bumili ulit pag -0.8% from avg
- SELL: Pag +0.8% profit or near resistance
"""
import json, time, urllib.request, urllib.error, websocket, os, threading, sys
from fastapi import FastAPI
from datetime import datetime

PAT_TOKEN = os.getenv("DERIV_TOKEN", "").strip()
if not PAT_TOKEN:
    PAT_TOKEN = "[STRIPPED 68 bytes]"

APP_ID = "34JwLLP8WeVqrXmBqY1iG"
SYMBOL = "cryBTCUSD"
SPOT_SYMBOL = "BTCUSDT"
BUY_AMOUNT_USDT = 1.0  # $1 per DCA boss
NEAR_PCT = 0.6  # Luwag para madalas makabili
SELL_PROFIT_PCT = 0.8  # Sell pag 0.8% profit - mabilis TP
DCA_DROP_PCT = 0.8  # DCA pag -0.8% from avg price
LOOP_SECONDS = 30

app = FastAPI(title="BTC SPOT DCA - WALANG SL")
REST = "https://api.derivws.com"
last_signal = {"time": None, "signal": "WAITING", "price": 0, "deriv": "INIT", "info": "Starting DCA..."}
trades_today = 0
pnl_total = 0
holdings = {"btc": 0.0, "avg_price": 0.0, "usdt": 5.91, "total_buys": 0}

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

HEADERS = {
    "Authorization": f"Bearer {PAT_TOKEN}",
    "Deriv-App-ID": str(APP_ID),
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) Pydroid3",
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

def bot_loop_dca():
    global last_signal, trades_today, pnl_total, holdings
    log("🚀 BTC SPOT DCA BOT - WALANG SL - STARTING")
    log(f"💰 BUY: ${BUY_AMOUNT_USDT} per DCA | NEAR: {NEAR_PCT}% | SELL: {SELL_PROFIT_PCT}% | DCA DROP: {DCA_DROP_PCT}%")
    log(f"💰 Initial USDT: {holdings['usdt']} | Strategy: DCA lang, walang SL!")
    
    try:
        ws, acc = connect_deriv()
        log(f"✅ CONNECTED {acc['account_id']} Bal {acc.get('balance')} - Price data from cryBTCUSD")
        last_signal["deriv"] = f"ON - {acc['account_id']} - DCA MODE WALANG SL"
    except Exception as e:
        log(f"❌ Connect failed: {e}")
        last_signal["deriv"] = f"CONNECT FAIL: {e}"
        ws = None

    last_m5 = 0
    m5_data = None
    candles_15m = []
    shown = 0
    
    log("📝 DCA MODE: BUY near support, DCA pag -0.8% drop, SELL pag +0.8% profit lang!")
    
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
                price = 83700
                candles_15m = [{"low": 83615, "high": 83880}]*50
            
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
            
            m5_trend = m5_data["trend"] if m5_data else "UNKNOWN"
            info = f"BTC ${price:.2f} | {m5_data['info'] if m5_data else 'M5 N/A'} | SUP:{near_sup}({d_sup:.2f}%) RES:{near_res}({d_res:.2f}%) | Holdings:{holdings['btc']:.6f} BTC Avg:${holdings['avg_price']:.2f} P&L:{profit_pct:+.2f}% Drop:{drop_from_avg:.2f}% | USDT:{holdings['usdt']:.2f} | Buys:{holdings['total_buys']}"
            
            side = None
            
            # BUY LOGIC - Initial Buy near support
            if holdings["btc"] == 0 and near_sup and holdings["usdt"] >= BUY_AMOUNT_USDT:
                if d_sup <= NEAR_PCT:
                    side = "BUY"
                    info += f" | 🟢 INITIAL BUY SUP {near_sup:.2f}"
            
            # DCA LOGIC - Buy more when price drops 0.8% from avg - WALANG SL!
            if holdings["btc"] > 0 and holdings["usdt"] >= BUY_AMOUNT_USDT:
                if drop_from_avg >= DCA_DROP_PCT:
                    side = "DCA_BUY"
                    info += f" | 🟢 DCA BUY -{drop_from_avg:.2f}% DROP! Avg ${holdings['avg_price']:.2f} -> ${price:.2f}"
                elif near_sup and d_sup <= 0.3 and drop_from_avg >= 0.3:
                    side = "DCA_BUY"
                    info += f" | 🟢 DCA BUY SUP + DROP {drop_from_avg:.2f}%"
            
            # SELL LOGIC - Sell only when profit - WALANG SL!
            if holdings["btc"] > 0:
                if profit_pct >= SELL_PROFIT_PCT:
                    side = "SELL"
                    info += f" | 🔴 SELL PROFIT +{profit_pct:.2f}% - DCA SUCCESS!"
                elif near_res and profit_pct >= 0.4:
                    side = "SELL"
                    info += f" | 🔴 SELL RESISTANCE +{profit_pct:.2f}%"
            
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
                "total_buys": holdings["total_buys"]
            })
            
            if side:
                if side == "BUY" or side == "DCA_BUY":
                    log(f"📤 {side} {SPOT_SYMBOL} ${BUY_AMOUNT_USDT} @ ${price:.2f} | Drop {drop_from_avg:.2f}% | USDT {holdings['usdt']:.2f}")
                    btc_bought = BUY_AMOUNT_USDT / price
                    if holdings["btc"] == 0:
                        holdings["avg_price"] = price
                    else:
                        holdings["avg_price"] = (holdings["avg_price"]*holdings["btc"] + price*btc_bought)/(holdings["btc"]+btc_bought)
                    holdings["btc"] += btc_bought
                    holdings["usdt"] -= BUY_AMOUNT_USDT
                    holdings["total_buys"] += 1
                    trades_today += 1
                    log(f"✅ {side}: {btc_bought:.6f} BTC @ ${price:.2f} | New Avg ${holdings['avg_price']:.2f} | BTC {holdings['btc']:.6f} | USDT {holdings['usdt']:.2f} | Total Buys {holdings['total_buys']}")
                    last_signal["deriv"] = f"{side} {btc_bought:.6f} BTC - DCA {holdings['total_buys']}x"
                
                elif side == "SELL":
                    log(f"📤 SELLING {holdings['btc']:.6f} BTC @ ${price:.2f} P&L +{profit_pct:.2f}% | Total Buys {holdings['total_buys']}")
                    usdt_got = holdings["btc"] * price
                    profit_usdt = usdt_got - (holdings["total_buys"] * BUY_AMOUNT_USDT)
                    holdings["usdt"] += usdt_got
                    pnl_total += profit_pct
                    log(f"✅ SELL SUCCESS: Sold @ ${price:.2f} Got ${usdt_got:.2f} | Profit ${profit_usdt:.2f} | New USDT {holdings['usdt']:.2f} | P&L +{profit_pct:.2f}%")
                    holdings["btc"] = 0
                    holdings["avg_price"] = 0
                    holdings["total_buys"] = 0
                    trades_today += 1
                    last_signal["deriv"] = f"SOLD +{profit_pct:.2f}% Profit ${profit_usdt:.2f}"
            
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
    log("=== STARTUP BTC SPOT DCA - WALANG SL ===")
    t = threading.Thread(target=bot_loop_dca, daemon=True)
    t.start()

@app.get("/")
def home():
    return {
        "status": "BTC SPOT DCA BOT - WALANG SL - DCA LANG!",
        "spot_symbol": SPOT_SYMBOL,
        "config": {"BUY": f"${BUY_AMOUNT_USDT}", "NEAR": f"{NEAR_PCT}%", "SELL": f"{SELL_PROFIT_PCT}%", "DCA_DROP": f"{DCA_DROP_PCT}%", "SL": "WALANG SL - HOLD LANG!"},
        "last_signal": last_signal,
        "holdings": holdings,
        "pnl": pnl_total,
        "trades": trades_today,
        "time": datetime.now().isoformat(),
    }

@app.get("/health")
def health():
    return {"ok": True, "last_signal": last_signal, "holdings": holdings}

if __name__ == "__main__":
    bot_loop_dca()
  
