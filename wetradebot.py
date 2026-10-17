import yfinance as yf
import pandas as pd

SYMBOL = "BTC-USD"

def get_price():
    try:
        ticker = yf.Ticker(SYMBOL)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 0
    except:
        return 0

def get_trading_signal():
    try:
        # Kuha ug 1 day data, 5min interval
        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period="5d", interval="15m")
        if df.empty or len(df) < 20:
            return "HOLD", get_price(), 0, 0, 50
        
        close = df['Close']
        sma5 = close.rolling(5).mean().iloc[-1]
        sma20 = close.rolling(20).mean().iloc[-1]
        
        # RSI calc
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        
        price = float(close.iloc[-1])
        
        # Logic: SMA5 cross SMA20 + RSI
        if sma5 > sma20 and rsi_val < 70:
            signal = "BUY"
        elif sma5 < sma20 and rsi_val > 30:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        return signal, price, float(sma5), float(sma20), float(rsi_val)
    except Exception as e:
        print(f"Signal error: {e}")
        return "HOLD", 0, 0, 0, 50
