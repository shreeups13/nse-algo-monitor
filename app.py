import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import streamlit.components.v1 as components

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide")

# --- SOUND & POPUP COMPONENT ---
def trigger_alert(stock_name, price, signal_type):
    js_code = f"""
    <script>
    var audio = new Audio('https://google.com');
    audio.play();
    alert("🚨 {signal_type} ALERT: {stock_name} at {price}");
    </script>
    """
    components.html(js_code, height=0)

# --- INDIA TIME & MARKET LOGIC ---
def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

ist_now = get_ist()
current_day = ist_now.strftime('%A')
current_date = ist_now.strftime('%Y-%m-%d')

# Official NSE Holidays 2026
nse_holidays = ["2026-01-26", "2026-03-06", "2026-03-25", "2026-04-10", "2026-05-01", "2026-12-25"]
is_weekend = current_day in ['Saturday', 'Sunday']
is_holiday = current_date in nse_holidays
is_time_open = (9 <= ist_now.hour <= 15) # Simplified for checking logic

if is_weekend: market_status = "🔴 MARKET CLOSED (WEEKEND)"
elif is_holiday: market_status = "🔴 MARKET CLOSED (HOLIDAY)"
elif not (9 <= ist_now.hour <= 15): market_status = "🔴 MARKET CLOSED (AFTER HOURS)"
else: market_status = "🟢 MARKET OPEN"

# --- UI HEADER ---
st.title("📈 1% Strategy Live Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')} | {market_status}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.sidebar.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.sidebar.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.header("Manage Stocks")
    default_list = "PFC, SJVN, MOTHERSON, VEDL, WIPRO, UPL, IRFC, BEL, BPCL, INFY, NMDC, ENGINERSIN, MUTHOOTFIN, IOC, PNB, NCC, TRIVENI, FINCABLES, ADANIPORTS, TATAPOWER, POWERGRID, HDFCLIFE, CGPOWER, DELTACORP, JWL"
    user_input = st.text_area("Symbols", default_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

# --- CACHE-BUSTING ANALYSIS LOGIC ---
@st.cache_data(ttl=60) # Only cache for 1 minute as a safety net
def get_analysis(symbol, t_pct, s_pct, refresh_trigger):
    ticker = f"{symbol}.NS"
    try:
        # Use Ticker object and history to bypass high-level download cache
        t = yf.Ticker(ticker)
        # Fetching 1mo history for indicators and probability
        df_hist = t.history(period='1mo', interval='5m', auto_adjust=True)
        
        if df_hist.empty or len(df_hist) < 30: return None

        # Calculate Indicators
        df_hist['EMA20'] = df_hist['Close'].ewm(span=20, adjust=False).mean()
        delta = df_hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df_hist['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df_hist['Vol_Avg'] = df_hist['Volume'].rolling(10).mean()

        last = df_hist.iloc[-1] # The absolute latest available bar
        cmp = last['Close']
        
        # Signal Detection
        rsi_ok = 40 < last['RSI'] < 70
        vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)
        
        status = "WAITING"
        if (last['Close'] > last['Open']) and (last['Close'] > last['EMA20']) and rsi_ok and vol_surge:
            status = "🔥 STRONG BUY"
        elif (last['Close'] < last['Open']) and (last['Close'] < last['EMA20']) and rsi_ok and vol_surge:
            status = "❄️ STRONG SELL"

        # Win Prob (4-hour window backtest)
        df_hist['Sig'] = (df_hist['Close'] > df_hist['EMA20']) if "BUY" in status or status == "WAITING" else (df_hist['Close'] < df_hist['EMA20'])
        trades = []
        sig_indices = df_hist.index[df_hist['Sig']]
        for idx in sig_indices[-20:]:
            entry = df_hist.loc[idx, 'Close']
            future = df_hist.loc[idx:].head(48)
            res = 0
            for _, row in future.iterrows():
                if "BUY" in status or status == "WAITING":
                    if row['High'] >= entry * (1 + t_pct): res = 1; break
                    if row['Low'] <= entry * (1 - s_pct): res = -1; break
                else:
                    if row['Low'] <= entry * (1 - t_pct): res = 1; break
                    if row['High'] >= entry * (1 + s_pct): res = -1; break
            if res != 0: trades.append(res)
        
        win_prob = (trades.count(1) / len(trades) * 100) if len(trades) > 0 else 0.0

        return {
            "Stock": symbol, "CMP": round(cmp, 2), "Status": status,
            "Target": round(cmp*(1+t_pct),2) if "BUY" in status else round(cmp*(1-t_pct),2),
            "StopLoss": round(cmp*(1-s_pct),2) if "BUY" in status else round(cmp*(1+s_pct),2),
            "Win Prob": f"{win_prob:.1f}%", "RSI": round(last['RSI'], 1),
            "Time (IST)": get_ist().strftime("%H:%M:%S")
        }
    except: return None

# --- DASHBOARD UI ---
placeholder = st.empty()

# We use a session state variable to force a rerun and bypass cache
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()

while True:
    with placeholder.container():
        results = []
        # We pass st.session_state.last_update as a parameter to get_analysis to break the cache
        for stock in SYMBOLS:
            analysis = get_analysis(stock, target_pct, sl_pct, st.session_state.last_update)
            if analysis:
                results.append(analysis)
                if "STRONG" in analysis['Status']:
                    trigger_alert(analysis['Stock'], analysis['CMP'], analysis['Status'])
        
        if results:
            df_res = pd.DataFrame(results)
            def highlight(val):
                if val == "🔥 STRONG BUY": return 'background-color: #90ee90; color: black; font-weight: bold'
                if val == "❄️ STRONG SELL": return 'background-color: #ffcccb; color: black; font-weight: bold'
                return ''
            
            st.dataframe(df_res.style.map(highlight, subset=['Status']), use_container_width=True, hide_index=True)
        
        # Freshness Timer
        for i in range(300, 0, -1):
            st.write(f"🔄 Next live price refresh in: **{i}** seconds")
            time.sleep(1)
            st.empty() # Clears the timer text so it doesn't stack
            
        # Update session state to force a fresh cache-busted call on next loop
        st.session_state.last_update = time.time()
        st.rerun()
