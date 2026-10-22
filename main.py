"""
FIXED V2 - Compatible sa lumang websockets version sa Render
Tanggal na extra_headers na nag-eerror
"""
import asyncio
import random
import json
import time
from fastapi import FastAPI
import websockets

app = FastAPI()

last_price = {"symbol": "R_100", "price": None, "time": None, "error": None}
DERIV_SYMBOL = "R_100"
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "price": last_price, "uptime": time.time()}

@app.get("/price")
async def get_price():
    return last_price

async def fetch_deriv_tick():
    try:
        # WALANG extra_headers para compatible sa lahat ng version
        async with websockets.connect(
            DERIV_WS_URL,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5
        ) as ws:
            await ws.send(json.dumps({"ticks": DERIV_SYMBOL}))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(raw)
            
            if "tick" in data:
                return float(data["tick"]["quote"])
            else:
                # Pangalawang message minsan yung tick
                raw2 = await asyncio.wait_for(ws.recv(), timeout=10)
                data2 = json.loads(raw2)
                if "tick" in data2:
                    return float(data2["tick"]["quote"])
                raise Exception(f"Unexpected: {data2}")

    except Exception as e:
        # Isama lahat ng error para ma-retry
        raise Exception(f"Deriv Error: {e} code:{'520' if '520' in str(e) else 'other'}")

async def price_loop():
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
            retries = 0
            await asyncio.sleep(1.5)

        except Exception as e:
            err_str = str(e)
            last_price["error"] = err_str
            print(f"[gq6k5] Deriv Price Error: {err_str}")

            if "520" in err_str:
                wait = min(2 ** retries + random.uniform(1, 3), 60)
                print(f"[gq6k5] 520 hit - waiting {wait:.1f}s")
            else:
                wait = 3 + random.uniform(0, 2)

            retries += 1
            print(f"[gq6k5] No price - retry in {wait:.1f}s")
            await asyncio.sleep(wait)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(price_loop())
          
