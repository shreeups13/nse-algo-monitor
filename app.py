import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# --- APP CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide")

# --- CUSTOM INDIA TIME FUNCTION ---
def get_ist():
    # Streamlit Cloud uses UTC, so we add 5.5 hours for India (IST)
    return datetime.now() + timedelta(hours=5, minutes=30)

# --- MARKET STATUS LOGIC ---
ist_now = get_ist()
current_day = ist_now.strftime('%A')
current_date = ist_now.strftime('%Y-%m-%d')

# Official NSE Holidays 2026 (Update this list annually)
nse_holidays = [
    "2026-01-26", "2026-03-06", "2026-03-25", "2026-04-02", "2026-04-10", 
    "2026-05-01", "2026-10-02", "2026-10-21", "2026-11-10", "2026-12-25"
]

is_weekend = current_day in ['Saturday', 'Sunday']
is_holiday = current_date in nse_holidays
# Market Hours: 9:15 AM to 3:30 PM
is_time_open = (ist_now.hour == 9 and ist_now.minute >= 15) or (10 <= ist_now.hour < 15) or (ist_now.hour == 15 and ist_now.minute <= 30)

if is_weekend:
    market_status = "🔴 MARKET CLOSED (WEEKEND)"
elif is_holiday:
    market_status = "🔴 MARKET CLOSED (NSE HOLIDAY)"
elif not is_time_open:
    market_status = "🔴 MARKET CLOSED (AFTER HOURS)"
else:
    market_status = "🟢 MARKET OPEN"

# --- UI HEADER ---
st.title("📈 1% Strategy Live Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')} | {market_status}")

# --- SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("Strategy Settings")
    target_pct = st.slider("Target Profit (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.header("Manage Stocks")
    default_symbols = "RELIANCE, TCS, ZOMATO, INFY, ITC, WIPRO, TATAPOWER, JSWENERGY, IRFC"
    user_input = st.text_area("Symbols (Comma Separated)", default_symbols)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

# --- ANALYSIS LOGIC ---
def get_analysis(symbol, t_pct, s_pct):
    ticker = f"{symbol}.NS"
    try:
        # Fetch 1 month data for backtesting probability
        df = yf.download(ticker, period='1mo', interval='5m', 
                         auto_adjust=True, multi_level_index=False, progress=False)
        
        if df.empty or len(df) < 30: return None

        # 1. Technical Indicators
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        df['Vol_Avg'] = df['Volume'].rolling(window=10).mean()

        # 2. Live Status (Last COMPLETED candle)
        last = df.iloc[-2]
        cmp = last['Close']
        
        is_bullish = last['Close'] > last['Open']
        above_ema = last['Close'] > last['EMA20']
        rsi_ok = 40 < last['RSI'] < 70
        vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)

        status = "🔥 STRONG BUY" if (is_bullish and above_ema and rsi_ok and vol_surge) else "WAITING"
        
        # 3. Win Prob (Backtest last 30 signals)
        df['Sig'] = (df['Close'] > df['Open']) & (df['Close'] > df['EMA20']) & \
                    (df['RSI'].between(40, 70)) & (df['Volume'] > (df['Vol_Avg'] * 1.2))
        
        trades = []
        signals = df.index[df['Sig']]
        for idx in signals[-30:]:
            entry = df.loc[idx, 'Close']
            future = df.loc[idx:].head(12) # Check next 1 hour
            res = 0
            for _, row in future.iterrows():
                if row['High'] >= entry * (1 + t_pct): res = 1; break
                if row['Low'] <= entry * (1 - s_pct): res = -1; break
            trades.append(res)
        
        win_prob = (trades.count(1) / len(trades) * 100) if trades else 0

        return {
            "Stock": symbol,
            "CMP": round(cmp, 2),
            "Status": status,
            "Target": round(cmp * (1 + t_pct), 2),
            "StopLoss": round(cmp * (1 - s_pct), 2),
            "Win Prob": f"{win_prob:.1f}%",
            "RSI": round(last['RSI'], 1),
            "Time (IST)": get_ist().strftime("%H:%M:%S")
        }
    except:
        return None

# --- DASHBOARD UI ---
placeholder = st.empty()

while True:
    with placeholder.container():
        results = []
        for stock in SYMBOLS:
            analysis = get_analysis(stock, target_pct, sl_pct)
            if analysis: results.append(analysis)
        
        if results:
            df_res = pd.DataFrame(results)
            
            # Styling for Streamlit Cloud compatibility
            def highlight_status(val):
                return 'background-color: #90ee90; color: black; font-weight: bold' if val == "🔥 STRONG BUY" else ''

            st.dataframe(
                df_res.style.map(highlight_status, subset=['Status']),
                use_container_width=True,
                hide_index=True
            )
        
        # Refresh every 5 minutes
        time.sleep(300)
        st.rerun()
