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

TRADES_FILE = "trade_history.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f: json.dump(trades, f)

# --- NSE HOLIDAYS 2026 ---
NSE_HOLIDAYS = [
    date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28),
    date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25)
]

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

def is_market_open():
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    start_time, end_time = now.replace(hour=9, minute=15, second=0), now.replace(hour=15, minute=30, second=0)
    if start_time <= now <= end_time: return True, "🟢 MARKET OPEN"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    capital = st.number_input("Trading Capital (₹)", min_value=1000, value=50000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🛠️ Indicators")
    use_avg = st.checkbox("Moving Average (20)", value=True)
    use_ema = st.checkbox("EMA (9)", value=True)
    use_roc = st.checkbox("ROC (5)", value=True)
    use_lrc = st.checkbox("LRC (Linear Reg)", value=True)
    
    st.markdown("---")
    default_stocks = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("Clear History"):
        st.session_state.active_trades = {}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)
    def get_index_ui(ticker, label):
        close_series = indices['Close'][ticker].dropna()
        if close_series.empty: return f"{label}: N/A"
        curr = close_series.iloc[-1]
        prev = close_series.iloc[0]
        pct = ((curr - prev) / prev) * 100
        color = "green" if pct >= 0 else "red"
        return f"{label}: **{curr:,.2f}** (:{color}[{pct:+.2f}%])"
    st.markdown(f"### {get_index_ui('^NSEI', 'NIFTY 50')} | {get_index_ui('^BSESN', 'SENSEX')}")
except:
    st.markdown("### Indices: `Service Busy`")

st.subheader(f"IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")
table_placeholder = st.empty()

# --- LOGIC ---
def update_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        # Fetching 7 days to ensure enough 5m candles are available
        data = yf.download(tickers, period='7d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        # Structure check for single vs multi-ticker
        if len(SYMBOLS) == 1:
            ticker_str = f"{SYMBOLS[0]}.NS"
            data = {ticker_str: data}

        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            
            df = data[ticker_str].dropna()
            if df.empty or len(df) < 20: continue
            
            cmp = float(df['Close'].iloc[-1])
            qty = int(capital // cmp)
            
            sigs = []
            roc_val = 0.0
            prob_score = 0
            
            # LRC Logic
            y = df['Close'].tail(14).values
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            if use_lrc: sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
            
            # ROC Logic
            p5 = df['Close'].iloc[-6]
            roc_val = ((cmp - p5) / p5) * 100
            if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
            
            # Additional Indicators
            if use_avg: sigs.append("↑Avg" if cmp > df['Close'].rolling(20).mean().iloc[-1] else "↓Avg")
            if use_ema: sigs.append("↑EMA" if cmp > df['Close'].ewm(span=9).mean().iloc[-1] else "↓EMA")

            # Probability Scoring
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
            if vol_surge: prob_score += 1
            if abs(roc_val) > 0.5: prob_score += 1
            
            sig_msg = " | ".join(sigs) if sigs else "Neutral"
            
            # Trade Update
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                if (t['type'] == 'BUY' and (cmp >= t['target'] or cmp <= t['sl'])) or \
                   (t['type'] == 'SELL' and (cmp <= t['target'] or cmp >= t['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)

            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if df['Close'].iloc[-1] > df['Open'].iloc[-1]:
                    status, t_type = "🔥 BUY", "BUY"
                    if lrc_dir == "UP": prob_score += 1
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1+target_pct), 'sl': cmp*(1-sl_pct), 
                        'type': t_type, 'time': ist_now.strftime("%H:%M"), 'prob': prob_score
                    }
                elif df['Close'].iloc[-1] < df['Open'].iloc[-1]:
                    status, t_type = "❄️ SELL", "SELL"
                    if lrc_dir == "DOWN": prob_score += 1
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1-target_pct), 'sl': cmp*(1+sl_pct), 
                        'type': t_type, 'time': ist_now.strftime("%H:%M"), 'prob': prob_score
                    }
                save_persistent_trades(st.session_state.active_trades)

            trade = st.session_state.active_trades.get(symbol)
            current_prob = trade['prob'] if trade else prob_score
            prob_text = "LOW" if current_prob <= 1 else "MED" if current_prob == 2 else "HIGH"

            results.append({
                "Stock": symbol, "Qty": qty, "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Signal": sig_msg, "Prob": prob_text,
                "Time": trade['time'] if trade else ist_now.strftime("%H:%M"),
                "Status": "IN TRADE" if trade else status,
                "InTrade": 1 if trade else 0,
                "ROC_Sort": abs(roc_val) if abs(roc_val) > 1 else 0
            })
        
        return pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Sort"], ascending=False).drop(columns=["InTrade", "ROC_Sort"])
    except:
        return pd.DataFrame()

# --- RENDER ---
df_result = update_dashboard()
if not df_result.empty:
    with table_placeholder.container():
        def style_rows(row):
            styles = [''] * len(row)
            if row['Status'] == "IN TRADE":
                color = '#d4edda' if float(row['Target']) > float(row['Entry']) else '#f8d7da'
                styles = [f'background-color: {color}; color: black;'] * len(row)
            return styles

        display_df = df_result.copy()
        for col in ["CMP", "Entry", "Target", "SL"]:
            display_df[col] = display_df[col].apply(lambda x: f"{float(x):.2f}" if float(x) != 0 else "-")

        st.dataframe(display_df.style.apply(style_rows, axis=1), use_container_width=True, hide_index=True)

time.sleep(120 if open_status else 300)
st.rerun()
