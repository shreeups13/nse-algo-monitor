import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v4.7", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history_final.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f: json.dump(trades, f)

# --- MARKET CALENDAR 2026 ---
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
    start_time, end_time = now.replace(hour=9, minute=15, second=0), now.replace(hour=15, minute=30, second=0)
    if start_time <= now <= end_time: return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED"

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=50000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🛠️ Indicators")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_roc = st.checkbox("ROC (5)", value=True)
    use_lrc = st.checkbox("LRC Trend", value=True)
    
    st.markdown("---")
    full_list = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.active_trades = {}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    # Single-threaded download for indices to save resources
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False, threads=False)['Close']
    n_curr, n_prev = indices["^NSEI"].dropna().iloc[-1], indices["^NSEI"].dropna().iloc[0]
    n_chg = ((n_curr - n_prev) / n_prev) * 100
    st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | {status_text}")
except:
    st.markdown(f"### Indices: `Connecting...` | {status_text}")

table_placeholder = st.empty()

# --- LOGIC ---
def get_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        # CRITICAL FIX: threads=False prevents "RuntimeError: can't start new thread"
        data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False, threads=False)
        for symbol in SYMBOLS:
            t_str = f"{symbol}.NS"
            if t_str not in data or data[t_str].empty: continue
            df = data[t_str].dropna()
            if len(df) < 20: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            sigs = []
            prob_score = 0
            
            p5 = df['Close'].iloc[-6]
            roc_val = ((cmp - p5) / p5) * 100
            if abs(roc_val) > 0.5: prob_score += 1
            if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
            
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
            if vol_surge: prob_score += 1

            y = df['Close'].tail(14).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            if use_lrc: sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
            
            trade = st.session_state.active_trades.get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            
            if trade:
                status = "IN TRADE"
                e_time = trade.get('time', e_time)
                # Exit Logic
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)
            elif vol_surge:
                # Candle Logic: BUY on Green, SELL on Red
                if cmp > c_open and lrc_dir == "UP":
                    t_type, status = "BUY", "🔥 BUY"
                elif cmp < c_open and lrc_dir == "DOWN":
                    t_type, status = "SELL", "❄️ SELL"
                else: t_type = None

                if t_type:
                    entry = cmp
                    target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                    sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                    st.session_state.active_trades[symbol] = {'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 'time': e_time}
                    save_persistent_trades(st.session_state.active_trades)

            results.append({
                "Stock": symbol, "Qty": int(capital // cmp), "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Status": status, "Signal": " | ".join(sigs), 
                "Time": e_time, "InTrade": 1 if trade else 0, "ROC_Val": abs(roc_val)
            })
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- RENDER ---
df_raw = get_dashboard()

if not df_raw.empty:
    df_sorted = df_raw.sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    
    def apply_styles(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Status'] == "IN TRADE":
                is_buy = row['Target'] > row['Entry']
                # Medium-Light Row Highlight
                row_bg = '#e6fffa' if is_buy else '#fff5f5'
                styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
                # Even Medium CMP Highlight
                cmp_bg = '#68d391' if is_buy else '#fc8181'
                styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold; border-radius: 2px'
        return styles

    styled_view = df_sorted.style.apply(apply_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
        "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
    })

    with table_placeholder.container():
        st.dataframe(styled_view, use_container_width=True, hide_index=True)
else:
    st.info("🔄 Reconnecting to Market API...")

time.sleep(60 if open_status else 300)
st.rerun()
