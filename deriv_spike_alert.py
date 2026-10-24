import asyncio
import json
import os
import urllib.parse
import urllib.request

import websockets

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SYMBOL = os.environ.get("SYMBOL", "BOOM1000")
APP_ID = os.environ.get("DERIV_APP_ID", "1089")
SPIKE_MULT = float(os.environ.get("SPIKE_MULT", "4"))
AVG_PERIOD = 20

URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

candles = {}
last_open = None


def _send_telegram_sync(text):
    data = urllib.parse.urlencode(
        {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=data
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


async def send_telegram(text):
    print(text)
    await asyncio.to_thread(_send_telegram_sync, text)


def parse_candle(c):
    ot = int(c.get("open_time") or c.get("epoch"))
    return ot, (float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]))


async def check_spike(closed_ot):
    prev = sorted(k for k in candles if k < closed_ot)[-AVG_PERIOD:]
    if len(prev) < AVG_PERIOD or closed_ot not in candles:
        return
    avg_range = sum(candles[k][1] - candles[k][2] for k in prev) / AVG_PERIOD
    o, h, l, c = candles[closed_ot]
    body = c - o
    if avg_range > 0 and body > 0 and body >= SPIKE_MULT * avg_range:
        await send_telegram(
            f"SPIKE on {SYMBOL} (M1)\n"
            f"Candle moved {body:.3f} (avg range {avg_range:.3f})\n"
            f"Your rule: SELL now, close at +$0.20.\n"
            f"Close price: {c}"
        )


async def on_candle(c):
    global last_open
    ot, ohlc = parse_candle(c)
    candles[ot] = ohlc
    if last_open is None:
        last_open = ot
    elif ot > last_open:
        await check_spike(last_open)
        last_open = ot
    for k in sorted(candles)[:-100]:
        del candles[k]


async def keepalive(ws):
    while True:
        await asyncio.sleep(30)
        await ws.send(json.dumps({"ping": 1}))


async def run():
    global last_open
    async with websockets.connect(URL, ping_interval=20) as ws:
        candles.clear()
        last_open = None
        await ws.send(json.dumps({
            "ticks_history": SYMBOL,
            "adjust_start_time": 1,
            "count": 40,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": 60,
            "subscribe": 1,
        }))
        ka = asyncio.create_task(keepalive(ws))
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if "error" in msg:
                    print("API error:", msg["error"])
                    continue
                t = msg.get("msg_type")
                if t == "candles":
                    for c in msg["candles"]:
                        await on_candle(c)
                    await send_telegram(f"Spike watcher online: {SYMBOL} M1")
                elif t == "ohlc":
                    await on_candle(msg["ohlc"])
        finally:
            ka.cancel()


async def main():
    while True:
        try:
            await run()
        except Exception as e:
            print("Connection lost:", e, "- retrying in 5s")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
