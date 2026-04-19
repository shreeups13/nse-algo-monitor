import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="NSE Pro Monitor", layout="wide")
st.title("📈 1% Strategy Live Monitor")

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.sidebar.slider("Target Profit (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.sidebar.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    user_symbols = st.sidebar.text_area("Stocks", "RELIANCE, TCS, ZOMATO, INFY")
    SYMBOLS = [s.strip().upper() for s in user_symbols.split(",") if s.strip()]

# --- LOGIC: CALC WIN PROBABILITY & SIGNALS ---
def get_analysis(ticker, target, sl):
    df = yf.download(f"{ticker}.NS", period='1mo', interval='5m', progress=False)
    if df.empty or len(df) < 50: return None

    # Calculate Win Probability (Backtest last 1 month)
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['Signal'] = (df['Close'] > df['Open']) & (df['Close'] > df['EMA20'])
    
    trades = []
    signal_indices = df.index[df['Signal']]
    for idx in signal_indices[-50:]: # Check last 50 signals
        entry = df.loc[idx, 'Close']
        res = 0
        future = df.loc[idx:].head(12)
        for _, row in future.iterrows():
            if row['High'] >= entry * (1 + target): res = 1; break
            if row['Low'] <= entry * (1 - sl): res = -1; break
        trades.append(res)
    
    win_prob = (trades.count(1) / len(trades) * 100) if trades else 0
    
    # Live Status
    last = df.iloc[-1]
    sentiment = "STRONG BUY" if (last['Close'] > last['Open'] and last['Close'] > last['EMA20']) else "NO SIGNAL"
    
    return {
        "Stock": ticker,
        "CMP": round(last['Close'], 2),
        "Status": sentiment,
        "Target": round(last['Close'] * (1 + target), 2),
        "StopLoss": round(last['Close'] * (1 - sl), 2),
        "Win Prob": f"{win_prob:.1f}%",
        "Time": datetime.now().strftime("%H:%M:%S")
    }

# --- MAIN DASHBOARD ---
placeholder = st.empty()

while True:
    with placeholder.container():
        results = []
        for stock in SYMBOLS:
            data = get_analysis(stock, target_pct, sl_pct)
            if data: results.append(data)
        
        if results:
            df_display = pd.DataFrame(results)
            
            # Formatting the table for clarity
            st.table(df_display)
            
            # Highlighting Alerts
            for res in results:
                if res['Status'] == "STRONG BUY":
                    st.toast(f"🚀 BUY ALERT: {res['Stock']} at {res['CMP']}")
        
        time.sleep(300)
        st.rerun()
