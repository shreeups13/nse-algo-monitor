import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

# --- SESSION STATE INITIALIZATION ---
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}

# --- HELPER FUNCTIONS ---
def get_ist():
    # Adjusted to handle timezone offset correctly
    return datetime.now() + timedelta(hours=5, minutes=30)

def trigger_alert(stock_name, price, signal_type):
    # This renders a small JS snippet to show a browser alert
    js_code = f"""<script>alert("🚨 {signal_type} ALERT: {stock_name} at {price}");</script>"""
    components.html(js_code, height=0)

# --- MARKET STATUS LOGIC ---
ist_now = get_ist()
current_day = ist_now.strftime('%A')
is_weekend = current_day in ['Saturday', 'Sunday']
# Market hours: 09:15 to 15:30
is_time_open = (ist_now.hour == 9 and ist_now.minute >= 15) or (10 <= ist_now.hour < 15) or (ist_now.hour == 15 and ist_now.minute <= 30)

market_status = "🟢 MARKET OPEN" if is_time_open and not is_weekend else "🔴 MARKET CLOSED"

st.title("📈 Persistent Signal Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')} | {market_status}")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Control Panel")
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    default_stocks = "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL"
    user_input = st.text_area("Stock Watchlist (NSE Symbols)", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("Clear Trade History"):
        st.session_state.active_trades = {}
        st.rerun()

# --- DATA PROCESSING FUNCTION ---
def fetch_and_analyze():
    results = []
    progress_bar = st.progress(0, text="Updating Market Data...")
    
    for idx, symbol in enumerate(SYMBOLS):
        try:
            # Update progress status
            progress_bar.progress((idx + 1) / len(SYMBOLS), text=f"Analyzing {symbol}...")
            
            # Fetch 5-minute interval data
            df = yf.download(f"{symbol}.NS", period='2d', interval='5m', auto_adjust=True, progress=False)
            
            if df.empty or len(df) < 10:
                continue
            
            # Basic Indicators
            df['Vol_Avg'] = df['Volume'].rolling(10).mean()
            last_row = df.iloc[-1]
            cmp = float(last_row['Close'])
            vol_surge = last_row['Volume'] > (last_row['Vol_Avg'] * 1.2)
            
            # 1. Check Existing Trades for Exit (Target/SL)
            if symbol in st.session_state.active_trades:
                trade = st.session_state.active_trades[symbol]
                hit_target = (trade['type'] == 'BUY' and cmp >= trade['target']) or (trade['type'] == 'SELL' and cmp <= trade['target'])
                hit_sl = (trade['type'] == 'BUY' and cmp <= trade['sl']) or (trade['type'] == 'SELL' and cmp >= trade['sl'])
                
                if hit_target or hit_sl:
                    st.toast(f"Trade Closed for {symbol}: {'TARGET ✅' if hit_target else 'STOP LOSS ❌'}")
                    del st.session_state.active_trades[symbol]

            # 2. Identify New Signals
            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if last_row['Close'] > last_row['Open']:
                    status = "🔥 STRONG BUY"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp * (1 + target_pct), 'sl': cmp * (1 - sl_pct), 'type': 'BUY', 'time': get_ist().strftime("%H:%M")
                    }
                    trigger_alert(symbol, cmp, "BUY")
                elif last_row['Close'] < last_row['Open']:
                    status = "❄️ STRONG SELL"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp * (1 - target_pct), 'sl': cmp * (1 + sl_pct), 'type': 'SELL', 'time': get_ist().strftime("%H:%M")
                    }
                    trigger_alert(symbol, cmp, "SELL")

            # 3. Compile Row Data
            trade_info = st.session_state.active_trades.get(symbol, None)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else "-",
                "Target": round(trade_info['target'], 2) if trade_info else "-",
                "StopLoss": round(trade_info['sl'], 2) if trade_info else "-",
                "Last Update": trade_info['time'] if trade_info else get_ist().strftime("%H:%M:%S")
            })
        except Exception:
            continue
            
    progress_bar.empty()
    return results

# --- MAIN DASHBOARD RENDER ---
data_list = fetch_and_analyze()

if data_list:
    df_final = pd.DataFrame(data_list)
    
    # Styling function for the dataframe
    def apply_row_styles(row):
        style = [''] * len(row)
        if "BUY" in row['Status']:
            style = ['background-color: #d4edda; color: #155724'] * len(row)
        elif "SELL" in row['Status']:
            style = ['background-color: #f8d7da; color: #721c24'] * len(row)
        elif row['Status'] == "IN TRADE":
            style = ['background-color: #fff3cd; color: #856404'] * len(row)
        return style

    st.dataframe(
        df_final.style.apply(apply_row_styles, axis=1), 
        use_container_width=True, 
        hide_index=True
    )

    if st.session_state.active_trades:
        with st.expander("📂 Active Trade Portfolio (Debug)"):
            st.write(st.session_state.active_trades)

# --- AUTO-REFRESH MECHANISM ---
st.info("🔄 Dashboard auto-refreshes every 2 minutes. Please wait...")
time.sleep(120)
st.rerun()

