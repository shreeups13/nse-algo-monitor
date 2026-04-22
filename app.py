import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components

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

# Create a placeholder for the table so it appears BEFORE the sleep timer
table_placeholder = st.empty()

# --- DATA FETCHING ---
def update_dashboard():
    results = []
    # Batch download all symbols at once (Significantly faster than one-by-one)
    tickers = [f"{s}.NS" for s in SYMBOLS]
    
    try:
        data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            df = data[ticker_str].dropna()
            
            if df.empty or len(df) < 5:
                continue
            
            # Logic
            df['Vol_Avg'] = df['Volume'].rolling(10).mean()
            last = df.iloc[-1]
            cmp = float(last['Close'])
            vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)
            
            # Trade Check
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                if (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'BUY' and cmp <= t['sl']):
                    del st.session_state.active_trades[symbol]
                elif (t['type'] == 'SELL' and cmp <= t['target']) or (t['type'] == 'SELL' and cmp >= t['sl']):
                    del st.session_state.active_trades[symbol]

            # Signal Detection
            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if last['Close'] > last['Open']:
                    status = "🔥 BUY"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1+target_pct), 'sl': cmp*(1-sl_pct), 'type': 'BUY', 'time': ist_now.strftime("%H:%M")}
                elif last['Close'] < last['Open']:
                    status = "❄️ SELL"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1-target_pct), 'sl': cmp*(1+sl_pct), 'type': 'SELL', 'time': ist_now.strftime("%H:%M")}

            trade_info = st.session_state.active_trades.get(symbol)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else "-",
                "Target": round(trade_info['target'], 2) if trade_info else "-",
                "SL": round(trade_info['sl'], 2) if trade_info else "-",
                "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M")
            })
            
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- EXECUTION ---
df_final = update_dashboard()

if not df_final.empty:
    with table_placeholder.container():
        def style_df(row):
            if "BUY" in row['Status']: return ['background-color: #d4edda'] * len(row)
            if "SELL" in row['Status']: return ['background-color: #f8d7da'] * len(row)
            if row['Status'] == "IN TRADE": return ['background-color: #fff3cd'] * len(row)
            return [''] * len(row)
        
        st.dataframe(df_final.style.apply(style_df, axis=1), use_container_width=True, hide_index=True)
else:
    table_placeholder.warning("No data found. Check your internet connection or stock symbols.")

# --- THE AUTO-REFRESH TRIGGER ---
st.write(f"🔄 Last Update: {ist_now.strftime('%H:%M:%S')}. Refreshing in 120s...")
time.sleep(120)
st.rerun()
