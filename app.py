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

# NSE Holidays 2026
nse_holidays = ["2026-01-26", "2026-03-06", "2026-03-25", "2026-05-01", "2026-12-25"]
is_weekend = current_day in ['Saturday', 'Sunday']
is_holiday = current_date in nse_holidays
is_time_open = (ist_now.hour == 9 and ist_now.minute >= 15) or (10 <= ist_now.hour < 15) or (ist_now.hour == 15 and ist_now.minute <= 30)

if is_weekend: market_status = "🔴 MARKET CLOSED (WEEKEND)"
elif is_holiday: market_status = "🔴 MARKET CLOSED (HOLIDAY)"
elif not is_time_open: market_status = "🔴 MARKET CLOSED (AFTER HOURS)"
else: market_status = "🟢 MARKET OPEN"

st.title("📈 1% Strategy Live Monitor")
st.subheader(f"Current IST: {ist_now.strftime('%H:%M:%S')} | {market_status}")
st.info("🔊 *Tap screen once* to enable sound alerts for Buy/Sell signals.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    target_pct = st.sidebar.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.sidebar.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    user_input = st.sidebar.text_area("Stocks", "RELIANCE, TCS, ZOMATO, INFY, ITC, WIPRO")
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

# --- STRATEGY LOGIC ---
def get_analysis(symbol, t_pct, s_pct):
    try:
        df = yf.download(f"{symbol}.NS", period='1mo', interval='5m', auto_adjust=True, multi_level_index=False, progress=False)
        if df.empty or len(df) < 30: return None

        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['Vol_Avg'] = df['Volume'].rolling(10).mean()

        last = df.iloc[-2]; cmp = last['Close']
        rsi_ok = 40 < last['RSI'] < 70
        vol_surge = last['Volume'] > (last['Vol_Avg'] * 1.2)

        # Status Logic
        status = "WAITING"
        if (last['Close'] > last['Open']) and (last['Close'] > last['EMA20']) and rsi_ok and vol_surge:
            status = "🔥 STRONG BUY"
        elif (last['Close'] < last['Open']) and (last['Close'] < last['EMA20']) and rsi_ok and vol_surge:
            status = "❄️ STRONG SELL"

        # Win Prob (Mini-Backtest)
        df['Sig'] = (df['Close'] > df['EMA20']) if "BUY" in status else (df['Close'] < df['EMA20'])
        trades = []
        signals = df.index[df['Sig']]
        for idx in signals[-20:]:
            entry = df.loc[idx, 'Close']
            future = df.loc[idx:].head(12)
            res = 0
            for _, row in future.iterrows():
                if "BUY" in status:
                    if row['High'] >= entry * (1 + t_pct): res = 1; break
                    if row['Low'] <= entry * (1 - s_pct): res = -1; break
                else:
                    if row['Low'] <= entry * (1 - t_pct): res = 1; break
                    if row['High'] >= entry * (1 + s_pct): res = -1; break
            trades.append(res)
        win_prob = (trades.count(1) / len(trades) * 100) if trades else 0

        # Dynamic Target/SL based on Signal Type
        target_val = round(cmp*(1+t_pct),2) if "BUY" in status else round(cmp*(1-t_pct),2)
        sl_val = round(cmp*(1-s_pct),2) if "BUY" in status else round(cmp*(1+s_pct),2)

        return {
            "Stock": symbol, 
            "CMP": round(cmp, 2), 
            "Status": status, 
            "Target": target_val, 
            "StopLoss": sl_val, 
            "Win Prob": f"{win_prob:.1f}%",
            "RSI": round(last['RSI'], 1),
            "Time (IST)": get_ist().strftime("%H:%M:%S")
        }
    except: return None

# --- DASHBOARD RUN ---
placeholder = st.empty()
while True:
    with placeholder.container():
        results = []
        for stock in SYMBOLS:
            analysis = get_analysis(stock, target_pct, sl_pct)
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
        
        time.sleep(300); st.rerun()
