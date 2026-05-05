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

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=50000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("SL (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    default_stocks = "DELHIVERY, TTML, PETRONET, VEDL, AVANTIFEED, STAR, RAILTEL, COALINDIA, NCC, DELTACORP, UPL, ITC, WIPRO, ONGC, RELIANCE, PFC, BEL, PNB"
    user_input = st.text_area("Watchlist", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

# --- DATA FETCHING (PRE-LOAD) ---
def get_data():
    results = []
    # Batch download is faster to prevent "disappearing" data
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        raw_data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            t_str = f"{symbol}.NS"
            if t_str not in raw_data: continue
            df = raw_data[t_str].dropna()
            if len(df) < 20: continue

            cmp = float(df['Close'].iloc[-1])
            
            # Indicators
            y = df['Close'].tail(14).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            roc = ((cmp - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            vol_surge = df['Volume'].iloc[-1] > (df['Volume'].rolling(10).mean().iloc[-1] * 1.2)

            # Trade Logic
            trade = st.session_state.active_trades.get(symbol)
            status = "WAITING"
            
            if trade:
                status = "IN TRADE"
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)
            elif vol_surge:
                t_type = "BUY" if df['Close'].iloc[-1] > df['Open'].iloc[-1] else "SELL"
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                st.session_state.active_trades[symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': datetime.now().strftime("%H:%M")
                }
                save_persistent_trades(st.session_state.active_trades)

            results.append({
                "Stock": symbol, "Qty": int(capital // cmp), "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Signal": f"LRC:{'↑' if slope > 0 else '↓'} | ROC:{roc:.2f}%",
                "Status": status, "InTrade": 1 if trade else 0
            })
        return pd.DataFrame(results).sort_values("InTrade", ascending=False)
    except: return pd.DataFrame()

# --- START UI RENDERING ---
# 1. Fetch Indices First
try:
    idx_data = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)['Close']
    n_curr, s_curr = idx_data["^NSEI"].iloc[-1], idx_data["^BSESN"].iloc[-1]
    n_chg = ((n_curr - idx_data["^NSEI"].iloc[0]) / idx_data["^NSEI"].iloc[0]) * 100
    s_chg = ((s_curr - idx_data["^BSESN"].iloc[0]) / idx_data["^BSESN"].iloc[0]) * 100
    
    st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>0 else ':red'}[{s_chg:+.2f}%])")
except:
    st.markdown("### Indices: Data Temp Unavailable")

st.write(f"**IST: {datetime.now().strftime('%H:%M:%S')}** | 🟢 MARKET OPEN")

# 2. Show Table
df_final = get_data()

if not df_final.empty:
    def style_df(row):
        if row['Status'] == "IN TRADE":
            color = '#d4edda' if row['Target'] > row['Entry'] else '#f8d7da'
            return [f'background-color: {color}; color: black'] * len(row)
        return [''] * len(row)

    # Format numbers for display
    disp_df = df_final.copy()
    for col in ["CMP", "Entry", "Target", "SL"]:
        disp_df[col] = disp_df[col].apply(lambda x: f"{x:.2f}" if x > 0 else "-")

    st.dataframe(disp_df.drop(columns=["InTrade"]).style.apply(style_df, axis=1), use_container_width=True, hide_index=True)
else:
    st.warning("Fetching stock data... Please wait.")

# 3. Rerun Logic
time.sleep(60)
st.rerun()
