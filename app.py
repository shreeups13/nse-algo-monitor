import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

# File to keep trades persistent even if app restarts
TRADES_FILE = "trade_history.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f)

# --- NSE HOLIDAYS 2026 ---
NSE_HOLIDAYS = [
    date(2026, 1, 26), date(2026, 3, 6), date(2026, 3, 20), date(2026, 3, 25),
    date(2026, 4, 2), date(2026, 4, 10), date(2026, 4, 14), date(2026, 5, 1),
    date(2026, 8, 15), date(2026, 10, 2), date(2026, 10, 23), date(2026, 12, 25)
]

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

def is_market_open():
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    
    start_time = now.replace(hour=9, minute=5, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=40, second=0, microsecond=0)
    
    if start_time <= now <= end_time:
        return True, "🟢 MARKET OPEN"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

# --- SESSION STATE ---
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🛠️ Indicators")
    use_avg = st.checkbox("Moving Average (20)")
    use_ema = st.checkbox("EMA (9)")
    use_sma = st.checkbox("SMA (50)")
    use_lrc = st.checkbox("LRC (Linear Reg)")
    
    st.markdown("---")
    default_stocks = "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL"
    user_input = st.text_area("Watchlist (Comma Separated)", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("Clear History & Reset"):
        st.session_state.active_trades = {}
        if os.path.exists(TRADES_FILE):
            os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER (INDICES) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices_data = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)
    def get_index_ui(ticker, label):
        curr = indices_data['Close'][ticker].iloc[-1]
        prev = indices_data['Close'][ticker].iloc[0]
        pct = ((curr - prev) / prev) * 100
        color = "green" if pct >= 0 else "red"
        return f"{label}: **{curr:,.2f}** (:{color}[{pct:+.2f}%])"

    st.markdown(f"### {get_index_ui('^NSEI', 'NIFTY 50')} | {get_index_ui('^BSESN', 'SENSEX')}")
except:
    st.markdown("### Indices: `Service Unavailable`")

st.subheader(f"IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")
table_placeholder = st.empty()

# --- LOGIC ---
def update_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    
    try:
        # Fetching data for symbols
        data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            df = data[ticker_str].dropna()
            if len(df) < 20: continue
            
            last = df.iloc[-1]
            cmp = float(last['Close'])
            
            # Indicator Calculations
            sigs = []
            if use_avg: sigs.append("Above Avg" if cmp > df['Close'].rolling(20).mean().iloc[-1] else "Below Avg")
            if use_ema: sigs.append("Above EMA" if cmp > df['Close'].ewm(span=9).mean().iloc[-1] else "Below EMA")
            if use_sma: sigs.append("Above SMA" if cmp > df['Close'].rolling(50).mean().iloc[-1] else "Below SMA")
            sig_msg = " | ".join(sigs) if sigs else "Neutral"
            
            # Volume Strategy
            vol_surge = last['Volume'] > (df['Volume'].rolling(10).mean().iloc[-1] * 1.2)
            
            # Management
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                if (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'BUY' and cmp <= t['sl']) or \
                   (t['type'] == 'SELL' and cmp <= t['target']) or (t['type'] == 'SELL' and cmp >= t['sl']):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)

            # Signal Trigger
            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if last['Close'] > last['Open']:
                    status = "🔥 BUY"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1+target_pct), 'sl': cmp*(1-sl_pct), 'type': 'BUY', 'time': ist_now.strftime("%H:%M")}
                elif last['Close'] < last['Open']:
                    status = "❄️ SELL"
                    st.session_state.active_trades[symbol] = {'entry': cmp, 'target': cmp*(1-target_pct), 'sl': cmp*(1+sl_pct), 'type': 'SELL', 'time': ist_now.strftime("%H:%M")}
                save_persistent_trades(st.session_state.active_trades)

            trade_info = st.session_state.active_trades.get(symbol)
            results.append({
                "Stock": symbol, "CMP": cmp, "Status": "IN TRADE" if trade_info else status,
                "Entry": trade_info['entry'] if trade_info else 0.0,
                "Target": trade_info['target'] if trade_info else 0.0,
                "SL": trade_info['sl'] if trade_info else 0.0,
                "Signal": sig_msg, "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M"),
                "Sort": 1 if trade_info else 0
            })
        
        return pd.DataFrame(results).sort_values(by="Sort", ascending=False).drop(columns=["Sort"])
    except: return pd.DataFrame()

# --- RENDER ---
df_final = update_dashboard()

if not df_final.empty:
    with table_placeholder.container():
        def style_rows(row):
            styles = [''] * len(row)
            if row['Status'] != "WAITING":
                # CMP Column
                styles[1] = 'background-color: #90ee90; color: black;' if float(row['CMP']) >= float(row['Entry']) else 'background-color: #ffcccb; color: black;'
                # Row Color (Buy vs Sell direction)
                row_c = 'background-color: #d4edda; color: black;' if float(row['Target']) > float(row['Entry']) else 'background-color: #f8d7da; color: black;'
                for i in [0, 2, 3, 4, 5, 6, 7]: styles[i] = row_c
            return styles

        # 2-Decimal Display Formatting
        for col in ["CMP", "Entry", "Target", "SL"]:
            df_final[col] = df_final[col].apply(lambda x: f"{float(x):.2f}" if float(x) != 0 else "-")

        st.dataframe(df_final.style.apply(style_rows, axis=1), use_container_width=True, hide_index=True)

# --- TIMER ---
if open_status:
    st.write(f"🔄 Auto-refreshing in 120s...")
    time.sleep(120)
    st.rerun()
else:
    st.info("Market is currently closed. Sleeping for 5 minutes...")
    time.sleep(300)
    st.rerun()
