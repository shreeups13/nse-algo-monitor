import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.2", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history_v52.json"

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
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS: return False
    # 9:15 AM to 3:30 PM
    start = now.replace(hour=9, minute=15, second=0)
    end = now.replace(hour=15, minute=30, second=0)
    return start <= now <= end

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    capital = st.number_input("Capital (₹)", 1000, 1000000, 50000)
    target_p = st.slider("Target %", 0.5, 5.0, 1.0) / 100
    sl_p = st.slider("Stop Loss %", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    full_list = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist", full_list, height=150)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.active_trades = {}
        save_trades({})
        st.rerun()

# --- FRAGMENTED LIVE DASHBOARD ---
@st.fragment(run_every=60)
def live_monitor():
    now = get_ist()
    status_label = "🟢 MARKET OPEN" if is_market_open() else "🔴 MARKET CLOSED"
    st.subheader(f"🕰️ IST: {now.strftime('%H:%M:%S')} | {status_label}")
    
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        # threads=False prevents the 'can't start new thread' crash
        data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False, threads=False)
        
        results = []
        for s in SYMBOLS:
            tk = f"{s}.NS"
            if tk not in data or data[tk].empty: continue
            df = data[tk].dropna()
            if len(df) < 10: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            # Simple Trend Logic
            y = df['Close'].tail(10).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)

            trade = st.session_state.active_trades.get(s)
            status = "WAITING"
            
            if trade:
                status = "IN TRADE"
                # Exit Check
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[s]
                    save_trades(st.session_state.active_trades)
            elif vol_surge:
                if cmp > c_open and slope > 0:
                    t_type, status = "BUY", "🔥 BUY"
                elif cmp < c_open and slope < 0:
                    t_type, status = "SELL", "❄️ SELL"
                else: t_type = None

                if t_type:
                    entry = cmp
                    target = entry * (1 + target_p) if t_type == "BUY" else entry * (1 - target_p)
                    sl = entry * (1 - sl_p) if t_type == "BUY" else entry * (1 + sl_p)
                    st.session_state.active_trades[s] = {
                        'entry': entry, 'target': target, 'sl': sl, 
                        'type': t_type, 'time': now.strftime("%H:%M")
                    }
                    save_trades(st.session_state.active_trades)

            results.append({
                "Stock": s, "CMP": cmp, "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0, "SL": trade['sl'] if trade else 0.0,
                "Status": status, "InTrade": 1 if trade else 0, 
                "Momentum": abs(((cmp - df['Close'].iloc[-5])/df['Close'].iloc[-5])*100)
            })
        
        if results:
            df_final = pd.DataFrame(results).sort_values(by=["InTrade", "Momentum"], ascending=False).drop(columns=["InTrade", "Momentum"])

            # CUSTOM STYLING (Matches Screenshot)
            def color_rows(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for i, row in df.iterrows():
                    if row['Status'] == "IN TRADE":
                        is_buy = row['Target'] > row['Entry']
                        # Pastel Row Background
                        bg = '#c6f6d5' if is_buy else '#fed7d7'
                        styles.loc[i, :] = f'background-color: {bg}; color: black'
                        # Solid Bright CMP Block
                        cmp_bg = '#48bb78' if is_buy else '#f56565'
                        styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
                return styles

            st.dataframe(
                df_final.style.apply(color_rows, axis=None).format({
                    "CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"
                }), 
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("No data available for selected stocks.")
            
    except Exception as e:
        st.error(f"System Re-syncing... (Detail: {e})")

# --- APP START ---
st.title("📈 NSE Pro Monitor")
live_monitor()
