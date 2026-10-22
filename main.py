"""
Copy-paste main.py - Fix for 520 + /health 404
Requirement: pip install fastapi uvicorn websockets
"""
import asyncio
import random
import json
import time
from fastapi import FastAPI
import websockets
from websockets.exceptions import InvalidStatusCode, ConnectionClosed

app = FastAPI()

# --- GLOBAL PRICE STORAGE ---
last_price = {"symbol": "R_100", "price": None, "time": None, "error": None}
# Palitan mo symbol kung iba gamit mo: R_10, R_25, VOLATILITY 100 etc
DERIV_SYMBOL = "R_100"
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

# --- 1. HEALTH ENDPOINT - FIX SA 404 ---
@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "price": last_price, "uptime": time.time()}

@app.get("/price")
async def get_price():
    return last_price

# --- 2. DERIV CLIENT NA MATIBAY SA 520 ---
async def fetch_deriv_tick():
    """
    Kumukuha ng isang tick, may sariling connection.
    Pag 520, mag error para ma-handle sa loop.
    """
    try:
        # Important: Gumawa ng bagong connection per attempt
        # May header para di i-block ni Cloudflare
        async with websockets.connect(
            DERIV_WS_URL,
            extra_headers={
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://deriv.com"
            },
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5
        ) as ws:
            # Subscribe sa ticks
            await ws.send(json.dumps({"ticks": DERIV_SYMBOL}))
            
            # Hintay ng response - 10 sec timeout
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(raw)
            
            if "tick" in data:
                return float(data["tick"]["quote"])
            elif "error" in data:
                # Pag error galing kay Deriv mismo
                raise Exception(f"Deriv error: {data['error']}")
            else:
                # Minsan unang message is authorization, hintay pa isa
                raw2 = await asyncio.wait_for(ws.recv(), timeout=10)
                data2 = json.loads(raw2)
                if "tick" in data2:
                    return float(data2["tick"]["quote"])
                raise Exception(f"Unexpected response: {data2}")

    except InvalidStatusCode as e:
        # DITO LUMALABAS YUNG 520 MO BOSS
        raise Exception(f"Handshake status {e.status_code} <none> - Cloudflare 520")
    except Exception as e:
        raise e

async def price_loop():
    """Background loop na di namamatay kahit 520"""
    global last_price
    retries = 0
    print(f"[gq6k5] Starting Deriv loop for {DERIV_SYMBOL}")
    
    while True:
        try:
            price = await fetch_deriv_tick()
            last_price["price"] = price
            last_price["time"] = time.time()
            last_price["error"] = None
            print(f"[gq6k5] Price OK: {price}")
            retries = 0  # reset pag success
            await asyncio.sleep(1)  # 1 sec interval, wag masyado mabilis

        except Exception as e:
            err_str = str(e)
            last_price["error"] = err_str
            print(f"[gq6k5] Deriv Price Error: {err_str}")

            # Exponential backoff para sa 520
            if "520" in err_str or "Handshake" in err_str:
                wait = min(2 ** retries + random.uniform(1, 3), 60)
                print(f"[gq6k5] 520 hit - waiting {wait:.1f}s before retry")
            else:
                wait = 2 + random.uniform(0, 2)

            retries += 1
            print(f"[gq6k5] No price - retry in {wait:.1f}s")
            await asyncio.sleep(wait)

# --- 3. START BACKGROUND TASK PAG START NG UVICORN ---
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(price_loop())

# --- PARA LOCAL TEST: uvicorn main_fixed:app --host 0.0.0.0 --port 8000 ---
