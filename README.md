Zyleybrim_bot - BTCUSD MTF V3 LUWAG + TP/SL
Live trading bot for BTCUSD running 24/7 on Render.com

Strategy
Asset: BTCUSDT (Binance)
15M SR Detection: Auto Support/Resistance from 15m candles
Entry: 1M 2Candle Second Fully Closed near SR (0.7% LUWAG MODE)
Filter: OFF - Trade agad basta near SR (LUWAG MODE)
TP: 1.5% | SL: 0.8% | RR 1.87
Endpoints
/ - Bot status + last signal + config
/health - Health check
/config - Current config
Deploy on Render.com
Build: pip install -r requirements.txt
Start: uvicorn main:app --host 0.0.0.0 --port $PORT

Config
NEAR_PCT = 0.7% (from 0.5% strict to 0.7% luwag)
TP_PCT = 1.5%
SL_PCT = 0.8%

Live: https://zyleybrim-bot.onrender.com

Author: Zyleybrim

