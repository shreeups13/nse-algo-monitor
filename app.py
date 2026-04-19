import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import time

st.set_page_config(page_title="NSE Pro Monitor", layout="wide")
st.title("📈 1% Strategy Live Monitor")

# --- SIDEBAR: SETTINGS & PARAMETERS ---
with st.sidebar:
    st.header("Strategy Settings")
    target_pct = st.slider("Target Profit (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.header("Manage Stocks")
    default_symbols = "UPL, COALINDIA, POWERGRID, ITC, NCC, TATASTEEL, WIPRO, ONGC, INFY, RELIANCE, ZOMATO"
    user_input = st.text_area("Symbols (Comma Separated)", default_symbols)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

def get_analysis(symbol, t_pct, s_pct):
    ticker = f"{symbol}.NS"
    # Fix for ValueError: multi_level_index=False
    df = yf.download(ticker, period='1mo', interval='5m', 
                     auto_adjust=True, multi_level_index=False, progress=False)
    
    if df.empty or len(df) < 30:
        return None

    # --- 1. Technical Indicators ---
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # Volume Avg
    df['Vol_Avg'] = df['Volume'].rolling(window=10).mean()

    # --- 2. Win Probability (Backtest 30 Days) ---
    df['Sig'] = (df['Close'] > df['Open']) & (df['Close'] > df['EMA20']) & \
                (df['RSI'].between(40, 70)) & (df['Volume'] > (df['Vol_Avg'] * 1.2))
    
    trades = []
    signals = df.index[df['Sig']]
    for idx in signals[-30:]: # Test last 30 signals
        entry = df.loc[idx, 'Close']
        target_val, sl_val = entry * (1 + t_pct), entry * (1 - s_pct)
        # Look ahead 12 candles (1 hour)
        future = df.loc[idx:].head(12)
        res = 0
        for _, row in future.iterrows():
            if row['High'] >= target_val: res = 1; break
            if row['Low'] <= sl_val: res = -1; break
        trades.append(res)
    
    win_prob = (trades.count(1) / len(trades) * 100) if trades else 0

    # --- 3. Live Status ---
    last = df.iloc[-1]
    cmp = last['Close']
    
    is_bullish = last['Close'] > last['Open']
    above_ema = last['Close'] > last['EMA20']
    rsi_ok = 40 < last['RSI'] < 70
    vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)

    status = "🔥 STRONG BUY" if (is_bullish and above_ema and rsi_ok and vol_surge) else "WAITING"
    
    return {
        "Stock": symbol,
        "CMP": round(cmp, 2),
        "Status": status,
        "Target": round(cmp * (1 + t_pct), 2),
        "StopLoss": round(cmp * (1 - s_pct), 2),
        "Win Prob": f"{win_prob:.1f}%",
        "RSI": round(last['RSI'], 1),
        "Time": datetime.now().strftime("%H:%M:%S")
    }

# --- DASHBOARD UI ---
placeholder = st.empty()

while True:
    with placeholder.container():
        results = []
        for stock in SYMBOLS:
            analysis = get_analysis(stock, target_pct, sl_pct)
            if analysis:
                results.append(analysis)
        
        if results:
            df_res = pd.DataFrame(results)
            
            # Styling
            def color_status(val):
                color = '#90ee90' if 'STRONG BUY' in val else 'white'
                return f'background-color: {color}'
            
            st.table(df_res.style.applymap(color_status, subset=['Status']))
        
        time.sleep(300)
        st.rerun()
