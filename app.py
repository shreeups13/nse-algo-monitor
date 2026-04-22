import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}  # Format: {symbol: {entry, target, sl, type}}

# --- SOUND & POPUP COMPONENT ---
def trigger_alert(stock_name, price, signal_type):
    js_code = f"""
    <script>
    alert("🚨 {signal_type} ALERT: {stock_name} at {price}");
    </script>
    """
    components.html(js_code, height=0)

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

# --- MARKET LOGIC ---
ist_now = get_ist()
current_day = ist_now.strftime('%A')
is_weekend = current_day in ['Saturday', 'Sunday']
is_time_open = (ist_now.hour == 9 and ist_now.minute >= 15) or (10 <= ist_now.hour < 15) or (ist_now.hour == 15 and ist_now.minute <= 30)

market_status = "🟢 MARKET OPEN" if is_time_open and not is_weekend else "🔴 MARKET CLOSED"

st.title("📈 Persistent Signal Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')} | {market_status}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    user_input = st.text_area("Stocks", "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL")
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    if st.button("Clear Trade History"):
        st.session_state.active_trades = {}
        st.rerun()

# --- CORE LOGIC ---
def process_signals():
    results = []
    for symbol in SYMBOLS:
        try:
            df = yf.download(f"{symbol}.NS", period='2d', interval='5m', auto_adjust=True, progress=False)
            if df.empty or len(df) < 10: continue
            
            # Indicators (Simplified: Only Volume Avg)
            df['Vol_Avg'] = df['Volume'].rolling(10).mean()
            last = df.iloc[-1]
            cmp = last['Close']
            vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)
            
            # Check Active Trades First (Exit Logic)
            if symbol in st.session_state.active_trades:
                trade = st.session_state.active_trades[symbol]
                hit_target = (trade['type'] == 'BUY' and cmp >= trade['target']) or (trade['type'] == 'SELL' and cmp <= trade['target'])
                hit_sl = (trade['type'] == 'BUY' and cmp <= trade['sl']) or (trade['type'] == 'SELL' and cmp >= trade['sl'])
                
                if hit_target or hit_sl:
                    reason = "TARGET ✅" if hit_target else "STOP LOSS ❌"
                    st.toast(f"Trade Closed for {symbol}: {reason}")
                    del st.session_state.active_trades[symbol]
            
            # New Signal Detection (Entry Logic)
            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if last['Close'] > last['Open']:
                    status = "🔥 STRONG BUY"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp * (1 + target_pct), 'sl': cmp * (1 - sl_pct), 'type': 'BUY', 'time': get_ist().strftime("%H:%M")
                    }
                    trigger_alert(symbol, cmp, "BUY")
                elif last['Close'] < last['Open']:
                    status = "❄️ STRONG SELL"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp * (1 - target_pct), 'sl': cmp * (1 + sl_pct), 'type': 'SELL', 'time': get_ist().strftime("%H:%M")
                    }
                    trigger_alert(symbol, cmp, "SELL")

            # Update Table Data
            trade_info = st.session_state.active_trades.get(symbol, None)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else "-",
                "Target": round(trade_info['target'], 2) if trade_info else "-",
                "StopLoss": round(trade_info['sl'], 2) if trade_info else "-",
                "Time": trade_info['time'] if trade_info else get_ist().strftime("%H:%M:%S")
            })
        except: continue
    return results

# --- DASHBOARD RUNNER ---
placeholder = st.empty()
while True:
    with placeholder.container():
        data = process_signals()
        if data:
            df_res = pd.DataFrame(data)
            
            def highlight(row):
                color = ''
                if "BUY" in row['Status']: color = 'background-color: #90ee90; color: black'
                elif "SELL" in row['Status']: color = 'background-color: #ffcccb; color: black'
                elif row['Status'] == "IN TRADE": color = 'background-color: #e0f7fa; color: black'
                return [color] * len(row)

            st.dataframe(df_res.style.apply(highlight, axis=1), use_container_width=True, hide_index=True)
            
            if st.session_state.active_trades:
                st.write("### 📂 Live Trades Tracking")
                st.json(st.session_state.active_trades)
        
        time.sleep(300)
        st.rerun()
