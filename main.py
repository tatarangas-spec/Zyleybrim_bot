from flask import Flask
import threading, time, os
from datetime import datetime
app = Flask(__name__)
BOT = {"signal":"HOLD","price":"$65000","rsi":55,"last":"--:--:--"}
def loop():
 import random
 while True:
  BOT["signal"]=random.choice(["BUY","SELL","HOLD"])
  BOT["price"]=f"${random.randint(60000,70000)}"
  BOT["rsi"]=random.randint(40,75)
  BOT["last"]=datetime.now().strftime("%H:%M:%S")
  time.sleep(60)
@app.route('/')
def home():
 return f"<body style='background:#0a0e13;color:#0aff6f;font-family:monospace;padding:20px'><h1>ZYLEYBRIM BOT BUHI NA BOSS!</h1><h2 style='font-size:40px'>SIGNAL: {BOT['signal']}</h2><p>Price: {BOT['price']} | RSI: {BOT['rsi']}</p><p>Last: {BOT['last']}</p><p>Bisan OFF imo CP - BUHI GIHAPON!</p><script>setTimeout(()=>location.reload(),30000)</script></body>"
threading.Thread(target=loop, daemon=True).start()
if __name__ == '__main__':
 app.run(host='0.0.0.0', port=int(os.environ.get('PORT',8000)))
