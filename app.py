import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

# --- NSE HOLIDAYS 2024 (Example - Update annually) ---
NSE_HOLIDAYS = [
    date(2024, 1, 26), date(2024, 3, 8), date(2024, 3, 25), date(2024, 3, 29),
    date(2024, 4, 11), date(2024, 4, 17), date(2024, 5, 1), date(2024, 6, 17),
    date(2024, 7, 17), date(2024, 8, 15), date(2024, 10, 2), date(2024, 11, 1),
    date(2024, 11, 15), date(2024, 12, 25)
]

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

def is_market_open():
    now = get_ist()
    # Monday=0, Sunday=6
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (HOLIDAY/WEEKEND)"
    
    start_time = now.replace(hour=9, minute=5, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=40, second=0, microsecond=0)
    
    if start_time <= now <= end_time:
        return True, "🟢 MARKET OPEN"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

# --- SESSION STATE ---
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🛠️ Indicators (On/Off)")
    use_sma = st.checkbox("SMA (20)")
    use_ema = st.checkbox("EMA (9)")
    use_lrc = st.checkbox("LRC (Linear Reg)")
    
    st.markdown("---")
    default_stocks = "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL"
    user_input = st.text_area("Watchlist", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("Clear History"):
        st.session_state.active_trades = {}
        st.rerun()

# --- HEADER (NIFTY / SENSEX / IST) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="1d", interval="1m", progress=False).iloc[-1]
    nifty = indices['Close']['^NSEI']
    sensex = indices['Close']['^BSESN']
    st.markdown(f"### NIFTY 50: `{nifty:,.2f}` | SENSEX: `{sensex:,.2f}`")
except:
    st.markdown("### NIFTY 50: `Data Error` | SENSEX: `Data Error`")

st.subheader(f"IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")

table_placeholder = st.empty()

# --- DATA FETCHING & LOGIC ---
def update_dashboard():
    if not open_status:
        return pd.DataFrame()

    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    
    try:
        data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            df = data[ticker_str].dropna()
            if len(df) < 20: continue
            
            last = df.iloc[-1]
            cmp = float(last['Close'])
            
            # --- DYNAMIC INDICATORS & CROSSOVER ---
            crossover_msg = "Neutral"
            if use_ema:
                df['ema_val'] = df['Close'].ewm(span=9).mean()
                if cmp > df['ema_val'].iloc[-1]: crossover_msg = "Above EMA"
            if use_sma:
                df['sma_val'] = df['Close'].rolling(window=20).mean()
                if cmp > df['sma_val'].iloc[-1]: crossover_msg = "Above SMA"
            
            # Volume Logic
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = last['Volume'] > (vol_avg * 1.2)
            
            # Trade Check
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                if (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'BUY' and cmp <= t['sl']):
                    del st.session_state.active_trades[symbol]
                elif (t['type'] == 'SELL' and cmp <= t['target']) or (t['type'] == 'SELL' and cmp >= t['sl']):
                    del st.session_state.active_trades[symbol]

            # Entry Logic
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
                "CMP": cmp,
                "Status": "IN TRADE" if trade_info else status,
                "Entry": trade_info['entry'] if trade_info else 0.0,
                "Target": trade_info['target'] if trade_info else 0.0,
                "SL": trade_info['sl'] if trade_info else 0.0,
                "Signal": crossover_msg,
                "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M")
            })
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

# --- STYLING & RENDER ---
if open_status:
    df_final = update_dashboard()
    if not df_final.empty:
        with table_placeholder.container():
            def style_logic(row):
                styles = [''] * len(row)
                if row['Status'] != "WAITING":
                    # CMP Column (Index 1)
                    styles[1] = 'background-color: #90ee90; color: black;' if row['CMP'] >= row['Entry'] else 'background-color: #ffcccb; color: black;'
                    # Row Logic
                    row_color = 'background-color: #d4edda; color: black;' if row['Target'] > row['Entry'] else 'background-color: #f8d7da; color: black;'
                    for i in [0, 2, 3, 4, 5, 6, 7]: styles[i] = row_color
                return styles

            # Formatting to 2 Decimals
            for col in ["CMP", "Entry", "Target", "SL"]:
                df_final[col] = df_final[col].apply(lambda x: f"{x:.2f}" if x != 0 else "-")

            st.dataframe(df_final.style.apply(style_logic, axis=1), use_container_width=True, hide_index=True)
    
    st.write(f"🔄 Refreshing in 120s...")
    time.sleep(120)
    st.rerun()
else:
    st.info(f"Dashboard is dormant. Market hours: 09:05 to 15:40 IST (Mon-Fri).")
    time.sleep(60)
    st.rerun()
