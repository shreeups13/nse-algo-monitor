import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

# --- SESSION STATE ---
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    default_stocks = "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL"
    user_input = st.text_area("Stocks", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    if st.button("Clear History"):
        st.session_state.active_trades = {}
        st.rerun()

# --- HEADER ---
ist_now = get_ist()
st.title("📈 Persistent Signal Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')}")

table_placeholder = st.empty()

# --- DATA FETCHING ---
def update_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    
    try:
        # Use a single batch download for speed
        data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            
            df = data[ticker_str].dropna()
            if df.empty or len(df) < 15: continue
            
            # Trend Indicators (EMA 9/21)
            df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
            
            last = df.iloc[-1]
            cmp = float(last['Close'])
            
            # 1. Exit Logic
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                hit_target = (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'SELL' and cmp <= t['target'])
                hit_sl = (t['type'] == 'BUY' and cmp <= t['sl']) or (t['type'] == 'SELL' and cmp >= t['sl'])
                
                if hit_target or hit_sl:
                    del st.session_state.active_trades[symbol]

            # 2. Signal Detection
            status = "WAITING"
            if symbol not in st.session_state.active_trades:
                if last['EMA_9'] > last['EMA_21']:
                    status = "BUY"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1+target_pct), 'sl': cmp*(1-sl_pct), 'type': 'BUY', 'time': ist_now.strftime("%H:%M")}
                else:
                    status = "SELL"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1-target_pct), 'sl': cmp*(1+sl_pct), 'type': 'SELL', 'time': ist_now.strftime("%H:%M")}

            trade_info = st.session_state.active_trades.get(symbol)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else "-",
                "Target": round(trade_info['target'], 2) if trade_info else "-",
                "SL": round(trade_info['sl'], 2) if trade_info else "-",
                "Type": trade_info['type'] if trade_info else status,
                "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M")
            })
            
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- EXECUTION & STYLING ---
df_final = update_dashboard()

if not df_final.empty:
    with table_placeholder.container():
        def style_rows(row):
            styles = [''] * len(row)
            # Check row type/status for coloring
            if row['Type'] == 'BUY' or "BUY" in row['Status']:
                # Background Green, Text Black for Stock Name
                styles[0] = 'background-color: #90ee90; color: black; font-weight: bold;'
                # Background Green for entire row (Light version)
                for i in range(1, len(row)):
                    styles[i] = 'background-color: #d4edda; color: black;'
                    
            elif row['Type'] == 'SELL' or "SELL" in row['Status']:
                # Background Red, Text Black for Stock Name
                styles[0] = 'background-color: #ffcccb; color: black; font-weight: bold;'
                # Background Red for entire row (Light version)
                for i in range(1, len(row)):
                    styles[i] = 'background-color: #f8d7da; color: black;'
            
            # Highlight "IN TRADE" status differently if needed
            if row['Status'] == "IN TRADE":
                styles[2] = 'font-weight: bold; border: 1px solid black;'

            return styles

        # Remove the 'Type' helper column before displaying
        display_df = df_final.copy()
        
        st.dataframe(
            display_df.style.apply(style_rows, axis=1), 
            use_container_width=True, 
            hide_index=True
        )

# --- REFRESH ---
st.write(f"🔄 Last Sync: {ist_now.strftime('%H:%M:%S')}. Refreshing in 120s...")
time.sleep(120)
st.rerun()
