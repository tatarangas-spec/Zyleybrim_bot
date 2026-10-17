
from flask import Flask, jsonify
import threading
import time
from datetime import datetime

app = Flask(__name__)

BOT_STATUS = {
    "name": "ZYLEYBRIM BOT",
    "status": "BUHI NA BOSS!",
    "logic": "4700% - SMA5 / SMA20 / RSI / MACD",
    "mode": "DEMO (Safe)",
    "uptime_start": datetime.now().isoformat(),
    "last_signal": "HOLD",
    "price": "Loading...",
    "sma5": 0,
    "sma20": 0,
    "rsi": 50,
    "macd": 0,
    "trades_today": 0,
    "profit_today": "+0.00%"
}

def trading_loop():
    # Diri ang 4700% logic mo dagan kada 1 minute
    # Sa cloud version, mag fetch gikan OKX public API (walay API key need sa price)
    import random
    while True:
        try:
            # Mock signal for demo - sa real cloud version mag ccxt ta
            signals = ["BUY", "SELL", "HOLD"]
            BOT_STATUS["last_signal"] = random.choice(signals)
            BOT_STATUS["price"] = f"${random.randint(60000, 70000)}"
            BOT_STATUS["sma5"] = random.randint(65000, 67000)
            BOT_STATUS["sma20"] = random.randint(64000, 66000)
            BOT_STATUS["rsi"] = random.randint(40, 75)
            BOT_STATUS["macd"] = round(random.uniform(-100, 100), 2)
            BOT_STATUS["last_update"] = datetime.now().strftime("%H:%M:%S")
            time.sleep(60) # check kada minuto
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(10)

@app.route('/')
def home():
    return f"""
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body{{background:#0a0e13;color:#0aff6f;font-family:monospace;padding:20px}}
    .card{{background:#151a21;border:1px solid #0aff6f33;border-radius:12px;padding:20px;margin:10px 0}}
    .big{{font-size:32px;font-weight:bold}}
    .buy{{color:#00ff88}} .sell{{color:#ff4444}} .hold{{color:#ffcc00}}
    </style>
    </head>
    <body>
    <h1>ZYLEYBRIM BOT BUHI NA BOSS!</h1>
    <div class="card">
        <div>Logic: {BOT_STATUS['logic']}</div>
        <div>Mode: {BOT_STATUS['mode']}</div>
        <div>Uptime: {BOT_STATUS['uptime_start']}</div>
        <div>Last Update: {BOT_STATUS.get('last_update','--:--:--')}</div>
    </div>
    <div class="card">
        <div class="big {BOT_STATUS['last_signal'].lower()}">SIGNAL: {BOT_STATUS['last_signal']}</div>
        <div>Price: {BOT_STATUS['price']} | RSI: {BOT_STATUS['rsi']} | MACD: {BOT_STATUS['macd']}</div>
        <div>SMA5: {BOT_STATUS['sma5']} | SMA20: {BOT_STATUS['sma20']}</div>
    </div>
    <div class="card">
        <div>Trades Today: {BOT_STATUS['trades_today']} | PnL: {BOT_STATUS['profit_today']}</div>
        <div>Server: Render Cloud 24/7 - Bisan OFF imo CP, BUHI GIHAPON!</div>
    </div>
    <p>Auto refresh kada 30s</p>
    <script>setTimeout(()=>location.reload(),30000)</script>
    </body>
    </html>
    """

@app.route('/api/status')
def status():
    return jsonify(BOT_STATUS)

@app.route('/api/4700logic')
def logic_info():
    return jsonify({
        "buy_when": "SMA5 cross above SMA20 + RSI 45-65 + MACD > 0",
        "sell_when": "SMA5 cross below SMA20 or RSI >70 or TP 3.5% / SL 1.5%",
        "timeframe": "5m BTC/USDT",
        "note": "Demo mode - para testing, ayaw sa real money"
    })

# Start trading thread
threading.Thread(target=trading_loop, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
