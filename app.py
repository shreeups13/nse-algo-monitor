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
        data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            df = data[ticker_str].dropna()
            
            if df.empty or len(df) < 5: continue
            
            # Original Volume Logic
            df['Vol_Avg'] = df['Volume'].rolling(10).mean()
            last = df.iloc[-1]
            cmp = float(last['Close'])
            vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)
            
            # Trade Exit Check
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                hit_target = (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'SELL' and cmp <= t['target'])
                hit_sl = (t['type'] == 'BUY' and cmp <= t['sl']) or (t['type'] == 'SELL' and cmp >= t['sl'])
                
                if hit_target or hit_sl:
                    del st.session_state.active_trades[symbol]

            # Signal Detection (Entry)
            status = "WAITING"
            if symbol not in st.session_state.active_trades and vol_surge:
                if last['Close'] > last['Open']:
                    status = "🔥 BUY"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1+target_pct), 
                        'sl': cmp*(1-sl_pct), 'type': 'BUY', 'time': ist_now.strftime("%H:%M")
                    }
                elif last['Close'] < last['Open']:
                    status = "❄️ SELL"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1-target_pct), 
                        'sl': cmp*(1+sl_pct), 'type': 'SELL', 'time': ist_now.strftime("%H:%M")
                    }

            trade_info = st.session_state.active_trades.get(symbol)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else 0,
                "Target": round(trade_info['target'], 2) if trade_info else 0,
                "SL": round(trade_info['sl'], 2) if trade_info else "-",
                "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M")
            })
            
        return pd.DataFrame(results)
    except Exception:
        return pd.DataFrame()

# --- EXECUTION & STYLING ---
df_final = update_dashboard()

if not df_final.empty:
    with table_placeholder.container():
        def style_logic(row):
            styles = [''] * len(row)
            
            # Check if row is in a trade or triggered
            if row['Status'] != "WAITING":
                cmp_val = row['CMP']
                entry_val = row['Entry']
                target_val = row['Target']

                # 1. CMP Column Logic (Index 1)
                if cmp_val >= entry_val:
                    styles[1] = 'background-color: #90ee90; color: black;' # Green
                else:
                    styles[1] = 'background-color: #ffcccb; color: black;' # Red

                # 2. Remaining Columns Logic (Stock, Status, Entry, Target, SL, Time)
                if target_val > entry_val:
                    row_color = 'background-color: #d4edda; color: black;' # Light Green (Buy Logic)
                elif target_val < entry_val:
                    row_color = 'background-color: #f8d7da; color: black;' # Light Red (Sell Logic)
                else:
                    row_color = ''

                # Apply row_color to all columns EXCEPT CMP (index 1)
                for i in range(len(row)):
                    if i != 1:
                        styles[i] = row_color
            
            return styles

        # Display formatting
        display_df = df_final.copy()
        display_df['Entry'] = display_df['Entry'].replace(0, "-")
        display_df['Target'] = display_df['Target'].replace(0, "-")

        st.dataframe(
            display_df.style.apply(style_logic, axis=1), 
            use_container_width=True, 
            hide_index=True
        )

# --- REFRESH ---
st.write(f"🔄 Last Sync: {ist_now.strftime('%H:%M:%S')}. Auto-refresh in 120s...")
time.sleep(120)
st.rerun()
