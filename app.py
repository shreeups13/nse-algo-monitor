import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.0", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history_v5.json"

def load_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_trades(trades):
    with open(TRADES_FILE, "w") as f: json.dump(trades, f)

# --- MARKET CALENDAR ---
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
        return False, "🔴 MARKET CLOSED"
    if now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour >= 15:
        return False, "🔴 MARKET CLOSED"
    return True, "🟢 MARKET LIVE"

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    capital = st.number_input("Capital (₹)", 1000, 1000000, 50000)
    target_pct = st.slider("Target %", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss %", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    full_list = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Clear All Trades"):
        st.session_state.active_trades = {}
        save_trades({})
        st.rerun()

# --- DATA ENGINE ---
def get_live_data():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        # threads=False is MANDATORY here to fix your error
        data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False, threads=False)
        
        for symbol in SYMBOLS:
            tk = f"{symbol}.NS"
            if tk not in data or data[tk].empty: continue
            df = data[tk].dropna()
            if len(df) < 15: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            # Trend Logic
            y = df['Close'].tail(10).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            
            # Volume Logic
            vol_surge = df['Volume'].iloc[-1] > (df['Volume'].rolling(10).mean().iloc[-1] * 1.2)

            trade = st.session_state.active_trades.get(symbol)
            status = "WAITING"
            
            if trade:
                status = "IN TRADE"
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_trades(st.session_state.active_trades)
            elif vol_surge:
                # Candle Color Check
                if cmp > c_open and slope > 0:
                    t_type, status = "BUY", "🔥 BUY"
                elif cmp < c_open and slope < 0:
                    t_type, status = "SELL", "❄️ SELL"
                else: t_type = None

                if t_type:
                    entry = cmp
                    target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                    sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                    st.session_state.active_trades[symbol] = {
                        'entry': entry, 'target': target, 'sl': sl, 
                        'type': t_type, 'time': get_ist().strftime("%H:%M")
                    }
                    save_trades(st.session_state.active_trades)

            results.append({
                "Stock": symbol, "Qty": int(capital // cmp), "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Status": status, "InTrade": 1 if trade else 0,
                "ROC": abs(((cmp - df['Close'].iloc[-5])/df['Close'].iloc[-5])*100)
            })
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- RENDER ---
ist_now = get_ist()
open_status, status_txt = is_market_open()

st.markdown(f"### 🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_txt}")
table_placeholder = st.empty()

df_raw = get_live_data()

if not df_raw.empty:
    df_final = df_raw.sort_values(by=["InTrade", "ROC"], ascending=False).drop(columns=["InTrade", "ROC"])

    def apply_style(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Status'] == "IN TRADE":
                is_buy = row['Target'] > row['Entry']
                # Row Highlight (Pastel)
                row_color = '#e6fffa' if is_buy else '#fff5f5'
                styles.loc[i, :] = f'background-color: {row_color}; color: black'
                # Solid CMP Cell Highlight
                cmp_color = '#68d391' if is_buy else '#fc8181'
                styles.loc[i, 'CMP'] = f'background-color: {cmp_color}; color: white; font-weight: bold'
        return styles

    st_df = df_final.style.apply(apply_style, axis=None).format({
        "CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"
    })
    
    with table_placeholder.container():
        st.dataframe(st_df, use_container_width=True, hide_index=True)

# Safety Sleep to avoid thread crashing
time.sleep(120 if open_status else 300)
st.rerun()
