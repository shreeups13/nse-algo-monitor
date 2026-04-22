import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

# --- PERSISTENT SESSION STATE ---
# Note: If the Streamlit tab is closed or server restarts, this resets.
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
    
    if st.button("Clear Trade History"):
        st.session_state.active_trades = {}
        st.rerun()

# --- HEADER ---
ist_now = get_ist()
st.title("📈 Persistent Signal Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')}")

table_placeholder = st.empty()

# --- DATA FETCHING & LOGIC ---
def update_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    
    try:
        # Use a small period to keep it fast
        data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            ticker_str = f"{symbol}.NS"
            if ticker_str not in data: continue
            
            df = data[ticker_str].dropna()
            if df.empty or len(df) < 10: continue
            
            # Simplified Signal Logic (EMA Cross for better visibility)
            df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
            
            last = df.iloc[-1]
            cmp = float(last['Close'])
            
            # 1. Exit Logic (Check if Target/SL hit for stocks in session)
            if symbol in st.session_state.active_trades:
                t = st.session_state.active_trades[symbol]
                hit_target = (t['type'] == 'BUY' and cmp >= t['target']) or (t['type'] == 'SELL' and cmp <= t['target'])
                hit_sl = (t['type'] == 'BUY' and cmp <= t['sl']) or (t['type'] == 'SELL' and cmp >= t['sl'])
                
                if hit_target or hit_sl:
                    del st.session_state.active_trades[symbol]

            # 2. Entry Logic (Only if not already in a trade)
            status = "WAITING"
            if symbol not in st.session_state.active_trades:
                if last['EMA_9'] > last['EMA_21']:
                    status = "BUY"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1+target_pct), 'sl': cmp*(1-sl_pct), 
                        'type': 'BUY', 'time': ist_now.strftime("%H:%M")
                    }
                elif last['EMA_9'] < last['EMA_21']:
                    status = "SELL"
                    st.session_state.active_trades[symbol] = {
                        'entry': cmp, 'target': cmp*(1-target_pct), 'sl': cmp*(1+sl_pct), 
                        'type': 'SELL', 'time': ist_now.strftime("%H:%M")
                    }

            # 3. Build Result Row
            trade_info = st.session_state.active_trades.get(symbol)
            results.append({
                "Stock": symbol,
                "CMP": round(cmp, 2),
                "Status": "IN TRADE" if trade_info else status,
                "Entry": round(trade_info['entry'], 2) if trade_info else "-",
                "Target": round(trade_info['target'], 2) if trade_info else "-",
                "SL": round(trade_info['sl'], 2) if trade_info else "-",
                "Type": trade_info['type'] if trade_info else status, # Hidden helper for coloring
                "Time": trade_info['time'] if trade_info else ist_now.strftime("%H:%M")
            })
            
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- EXECUTION & STYLING ---
df_final = update_dashboard()

if not df_final.empty:
    with table_placeholder.container():
        def style_rows(row):
            # Default style
            styles = [''] * len(row)
            
            # Color the "Stock" name (Index 0)
            if row['Type'] == 'BUY' or row['Status'] == 'BUY':
                styles[0] = 'color: #00ff00; font-weight: bold;' # Bright Green
            elif row['Type'] == 'SELL' or row['Status'] == 'SELL':
                styles[0] = 'color: #ff4b4b; font-weight: bold;' # Bright Red
            
            # Optional: Color the background of the Status cell
            if row['Status'] == "IN TRADE":
                styles[2] = 'background-color: #3d3d3d;' 
                
            return styles

        # Display dataframe excluding the helper 'Type' column
        display_df = df_final.drop(columns=['Type'])
        st.dataframe(
            df_final.style.apply(style_rows, axis=1), 
            use_container_width=True, 
            hide_index=True
        )

# --- AUTO-REFRESH ---
st.write(f"🔄 Last Update: {ist_now.strftime('%H:%M:%S')}. Next scan in 120s...")
time.sleep(120)
st.rerun()
