import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import streamlit.components.v1 as components

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide")

# --- SOUND & NOTIFICATION COMPONENT ---
def trigger_alerts(stock_name):
    # HTML/JS for Sound and Browser Alert
    notification_html = f"""
    <script>
    var audio = new Audio('https://google.com');
    audio.play();
    alert("🚀 STRONG BUY SIGNAL: {stock_name}");
    </script>
    """
    components.html(notification_html, height=0)

st.title("📈 1% Strategy Live Monitor")

# --- SIDEBAR: PARAMETERS ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.slider("Target Profit (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    user_symbols = st.text_area("Stocks (Comma separated)", "RELIANCE, TCS, ZOMATO, INFY")
    SYMBOLS = [s.strip().upper() for s in user_symbols.split(",") if s.strip()]

# --- LOGIC ---
def analyze_logic(df):
    if len(df) < 30: return None
    # EMA/RSI logic here (same as previous code)
    df['EMA'] = df['Close'].ewm(span=20, adjust=False).mean()
    # ... [Insert the rest of your RSI/Vol calculation logic here] ...
    last = df.iloc[-2]
    # Simple logic for demonstration:
    if last['Close'] > last['EMA'] and last['Volume'] > df['Volume'].tail(10).mean():
        return True
    return False

# --- MAIN DASHBOARD ---
placeholder = st.empty()

while True:
    with placeholder.container():
        st.write(f"Last Scan: {datetime.now().strftime('%H:%M:%S')}")
        raw_data = yf.download([f"{t}.NS" for t in SYMBOLS], period='2d', interval='5m', group_by='ticker', progress=False)
        
        found_signal = False
        for stock in SYMBOLS:
            ticker = f"{stock}.NS"
            if ticker in raw_data.columns.get_level_values(0):
                df_stock = raw_data[ticker].dropna()
                if analyze_logic(df_stock):
                    st.success(f"🔥 BUY SIGNAL: {stock}")
                    trigger_alerts(stock) # THIS PLAYS THE SOUND
                    found_signal = True
        
        if not found_signal:
            st.info("Scanning... No strong signals yet.")
            
        time.sleep(300)
        st.rerun()
