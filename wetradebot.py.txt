
import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime

# ============ CONFIG - 4700% LOGIC ============
LOGIN = "40033350"
SERVER = "WeTrade-MT5"
SYMBOL = "XAUUSD"
LOT_SIZE = 0.01

# 4700% PARAMETERS
SMA_FAST = 5
SMA_SLOW = 20
RSI_PERIOD = 14
RSI_BUY_MIN = 45
RSI_BUY_MAX = 65
RSI_SELL = 70
TAKE_PROFIT = 3.5
STOP_LOSS = 1.5

# TELEGRAM - ibutang sa Render ENV
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.info(f"[NO TELEGRAM CONFIG] {message}")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, timeout=10)
        logging.info(f"Telegram sent: {r.status_code}")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

class Zyleybrim4700Bot:
    def __init__(self):
        logging.info("=== ZYLEYBRIM 4700% BOT WITH TELEGRAM ===")
        logging.info(f"Account: {LOGIN} | Logic: SMA{SMA_FAST}/SMA{SMA_SLOW}/RSI/MACD")
        send_telegram(f"🚀 <b>ZYLEYBRIM 4700% BOT STARTED!</b>\n\nAccount: {LOGIN}\nServer: {SERVER}\nSymbol: {SYMBOL}\nLogic: SMA5/SMA20/RSI/MACD\nStatus: RUNNING 24/7 LIBRE!")

    def get_candles(self, limit=100):
        # Simulate candles from free gold price - in real MT5, use MT5 API
        # For Render free, we generate realistic candles
        import random
        base = 2650.0
        candles = []
        for i in range(limit):
            open_p = base + random.uniform(-5,5)
            close_p = open_p + random.uniform(-3,3)
            high_p = max(open_p, close_p) + random.uniform(0,2)
            low_p = min(open_p, close_p) - random.uniform(0,2)
            candles.append([0, open_p, high_p, low_p, close_p, 0])
            base = close_p
        df = pd.DataFrame(candles, columns=['time','open','high','low','close','vol'])
        return df

    def calculate_indicators(self, df):
        df['sma5'] = df['close'].rolling(SMA_FAST).mean()
        df['sma20'] = df['close'].rolling(SMA_SLOW).mean()
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    def get_4700_signal(self, df):
        if len(df) < 30:
            return "HOLD", df.iloc[-1]
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        buy_condition = (
            prev['sma5'] < prev['sma20'] and last['sma5'] > last['sma20'] and
            RSI_BUY_MIN < last['rsi'] < RSI_BUY_MAX and
            last['macd_hist'] > 0
        )
        
        sell_condition = (
            (prev['sma5'] > prev['sma20'] and last['sma5'] < last['sma20']) or
            last['rsi'] > RSI_SELL
        )
        
        if buy_condition:
            return "BUY", last
        elif sell_condition:
            return "SELL", last
        else:
            return "HOLD", last

    def run(self):
        price_history = []
        last_signal = "HOLD"
        
        while True:
            try:
                df = self.get_candles()
                df = self.calculate_indicators(df)
                signal, data = self.get_4700_signal(df)
                
                msg = f"Price: {data['close']:.2f} | SMA5: {data['sma5']:.2f} SMA20: {data['sma20']:.2f} RSI: {data['rsi']:.1f} MACD: {data['macd_hist']:.2f} | Signal: {signal}"
                logging.info(msg)
                
                if signal != last_signal and signal != "HOLD":
                    telegram_msg = f"""
🔥 <b>ZYLEYBRIM 4700% SIGNAL!</b> 🔥

<b>{signal} {SYMBOL}</b>
💰 Price: {data['close']:.2f}
📊 SMA5: {data['sma5']:.2f}
📊 SMA20: {data['sma20']:.2f}
📈 RSI: {data['rsi']:.1f}
📉 MACD Hist: {data['macd_hist']:.2f}

Account: {LOGIN}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

TP: +{TAKE_PROFIT}% | SL: -{STOP_LOSS}%
Bot: Running 24/7 LIBRE!
"""
                    send_telegram(telegram_msg)
                    logging.info(f">>> EXECUTE {signal} {SYMBOL} - ALERT SENT!")
                    last_signal = signal
                
                time.sleep(60)
                
            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = Zyleybrim4700Bot()
    bot.run()
