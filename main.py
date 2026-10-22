"""
V3 DEMO TRADING BOT - Deriv
Para sa zyleybrim-bot.onrender.com
DEMO LANG MUNA - wag real account

Setup sa Render:
1. Dashboard > zyleybrim_bot > Environment > Add Variable
2. Name: DERIV_TOKEN , Value: yung demo token mo galing Deriv
3. Name: DERIV_APP_ID , Value: 1089
Save > Manual Deploy

Endpoints:
- /health - check kung buhay
- /price - last price
- /balance - balance mo (demo)
- /trade - history ng trades
- /start , /stop - control bot
"""
import asyncio
import json
import time
import os
import random
from fastapi import FastAPI
import websockets

app = FastAPI()

# --- CONFIG - PALITAN MO DITO STRATEGY MO ---
DERIV_SYMBOL = "R_100"
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
STAKE = 1  # $1 muna sa demo
# STRATEGY: "EVEN", "ODD", "RISE", "FALL" - dito mo palitan
STRATEGY_TYPE = "EVEN"  # Halimbawa: pag EVEN lang tayo bibili

# Storage
last_price = {"price": None, "time": None, "digit": None, "error": None}
balance_info = {"balance": None, "currency": "USD"}
trade_history = []
bot_state = {"running": False, "last_action": "Stopped - go to /start to run demo"}

DERIV_TOKEN = os.getenv("DERIV_TOKEN", "")  # Kunin sa Render Environment

async def deriv_connect():
    """Connect na walang extra_headers para di mag-error sa Render"""
    return await websockets.connect(
        DERIV_WS_URL,
        ping_interval=20,
        ping_timeout=10
    )

async def get_balance(ws):
    await ws.send(json.dumps({"balance": 1}))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
    if "balance" in resp:
        return resp["balance"]
    return None

async def buy_contract(ws, contract_type):
    """Bumili ng contract - DEMO ONLY"""
    # contract_type: DIGITEVEN, DIGITODD, CALL (Rise), PUT (Fall)
    buy_req = {
        "buy": 1,
        "price": STAKE,
        "parameters": {
            "amount": STAKE,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "t",
            "symbol": DERIV_SYMBOL
        }
    }
    await ws.send(json.dumps(buy_req))
    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
    return resp

@app.get("/")
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot_running": bot_state["running"],
        "price": last_price,
        "balance": balance_info,
        "last_action": bot_state["last_action"],
        "strategy": STRATEGY_TYPE
    }

@app.get("/price")
async def price():
    return last_price

@app.get("/balance")
async def balance():
    return balance_info

@app.get("/trade")
async def trades():
    return {"history": trade_history[-20:], "state": bot_state}

@app.get("/start")
async def start_bot():
    bot_state["running"] = True
    bot_state["last_action"] = "Demo bot started"
    return {"msg": "Demo trading started - check /trade"}

@app.get("/stop")
async def stop_bot():
    bot_state["running"] = False
    bot_state["last_action"] = "Stopped by user"
    return {"msg": "Bot stopped"}

async def trading_loop():
    global last_price, balance_info
    retries = 0
    print("[BOT] Demo trading loop started")

    while True:
        try:
            if not bot_state["running"]:
                await asyncio.sleep(2)
                continue

            if not DERIV_TOKEN:
                bot_state["last_action"] = "No DERIV_TOKEN set in Render Environment - set mo muna demo token"
                print("[BOT] No token")
                await asyncio.sleep(10)
                continue

            async with await deriv_connect() as ws:
                # 1. Authorize demo account
                await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
                auth_resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if "error" in auth_resp:
                    bot_state["last_action"] = f"Auth failed: {auth_resp['error']}"
                    print(f"[BOT] Auth fail {auth_resp['error']}")
                    await asyncio.sleep(10)
                    continue

                # 2. Get balance
                bal = await get_balance(ws)
                if bal:
                    balance_info = bal
                    print(f"[BOT] Balance: {bal}")

                # 3. Subscribe to ticks
                await ws.send(json.dumps({"ticks": DERIV_SYMBOL}))
                
                # 4. Loop ng ticks
                while bot_state["running"]:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        data = json.loads(raw)

                        if "tick" in data:
                            quote = float(data["tick"]["quote"])
                            digit = int(str(data["tick"]["quote"])[-1]) if "." in str(data["tick"]["quote"]) else int(str(quote)[-1])
                            last_price = {"price": quote, "digit": digit, "time": time.time(), "error": None}
                            
                            # --- DITO STRATEGY MO BOSS ---
                            should_buy = False
                            contract_type = "DIGITEVEN"

                            if STRATEGY_TYPE == "EVEN" and digit % 2 == 0:
                                should_buy = True
                                contract_type = "DIGITEVEN"
                            elif STRATEGY_TYPE == "ODD" and digit % 2 == 1:
                                should_buy = True
                                contract_type = "DIGITODD"

                            if should_buy:
                                print(f"[BOT] Signal {STRATEGY_TYPE} digit {digit} - BUYING DEMO {contract_type}")
                                bot_state["last_action"] = f"Buying {contract_type} at {quote} digit {digit}"
                                result = await buy_contract(ws, contract_type)
                                trade_history.append({"time": time.time(), "price": quote, "digit": digit, "result": result})
                                # Cooldown para di spam
                                await asyncio.sleep(5)
                            
                            retries = 0

                    except asyncio.TimeoutError:
                        print("[BOT] Tick timeout, reconnect")
                        break

        except Exception as e:
            err = str(e)
            print(f"[BOT] Error: {err}")
            last_price["error"] = err
            wait = min(2 ** retries + random.uniform(1, 3), 30)
            bot_state["last_action"] = f"Error {err} - retry in {wait:.1f}s"
            retries += 1
            await asyncio.sleep(wait)

@app.on_event("startup")
async def startup():
    asyncio.create_task(trading_loop())
      
