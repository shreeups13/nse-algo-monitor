#G7.03.06.26
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
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    start_time, end_time = now.replace(hour=9, minute=15, second=0), now.replace(hour=15, minute=30, second=0)
    if start_time <= now <= end_time: return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")
    filter_roc_gt = st.number_input("ROC Greater Than (>) %", value=1.00, step=0.01, format="%.2f")
    filter_roc_lt = st.number_input("ROC Less Than (<) %", value=1.00, step=0.01, format="%.2f")
    
    filter_trade_type = st.selectbox("Trade Type Filter", ["All", "S.Buy Only", "S.Sell Only", "S.Buy & S.Sell", "Blank Only"])
    
    st.markdown("---")
    st.subheader("🛠️ Indicators")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_sma50 = st.checkbox("SMA (50)", value=False)
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

# --- HEADER (INDICES) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)['Close']
    n_curr, n_prev = indices["^NSEI"].dropna().iloc[-1], indices["^NSEI"].dropna().iloc[0]
    s_curr, s_prev = indices["^BSESN"].dropna().iloc[-1], indices["^BSESN"].dropna().iloc[0]
    n_chg = ((n_curr - n_prev) / n_prev) * 100
    s_chg = ((s_curr - s_prev) / s_prev) * 100
    st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])")
except:
    st.markdown("### Indices: `Connecting...`")

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")
table_placeholder = st.empty()

# --- LOGIC ---
def get_dashboard():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        data = yf.download(tickers, period='7d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        for symbol in SYMBOLS:
            t_str = f"{symbol}.NS"
            if t_str not in data or data[t_str].empty: continue
            df = data[t_str].dropna()
            if len(df) < 20: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            sigs = []
            prob_score = 0
            
            # Indicators
            p5 = df['Close'].iloc[-6]
            roc_val = ((cmp - p5) / p5) * 100
            if abs(roc_val) > 0.5: prob_score += 1
            if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
            
            # --- EVALUATE FLAG COLOR ---
            if 1.0 <= abs(roc_val) <= 5.0:
                flag = "🔵 "
            else:
                flag = "🔴 "
            
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
            if vol_surge: prob_score += 1

            y = df['Close'].tail(14).values
            x = np.arange(len(y))
            slope, intercept = np.polyfit(x, y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            if use_lrc: sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
            
            # --- LRC 2 AND AVERAGE PRICE CALCULATION FOR UNDERLINE ---
            avg_price = np.mean(y)
            lrc2 = (slope * (len(y) - 1)) + intercept  # End value of the trend fit line
            
            if lrc2 > avg_price:
                underline_color = "#1a8a44" # Green underline
            else:
                underline_color = "#c53030" # Red underline
                
            display_stock_name = f"{flag}<span style='text-decoration: underline; text-decoration-color: {underline_color}; text-decoration-thickness: 2px;'>**{symbol}**</span>"
            
            ma_up = cmp > df['Close'].rolling(20).mean().iloc[-1]
            if use_ma20: sigs.append("↑MA" if ma_up else "↓MA")
            
            ema_up = cmp > df['Close'].ewm(span=9).mean().iloc[-1]
            if use_ema9: sigs.append("↑EMA" if ema_up else "↓EMA")
            
            if use_sma50: sigs.append("↑SMA50" if len(df)>50 and cmp > df['Close'].rolling(50).mean().iloc[-1] else "•SMA")

            trade = st.session_state.active_trades.get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            
            if trade:
                status = "IN TRADE"
                e_time = trade.get('time', e_time)
                p_text = trade.get('prob_text', "MED")
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)
            elif vol_surge:
                if cmp > c_open and lrc_dir == "UP":
                    t_type = "BUY"
                    status = "🔥 BUY"
                    prob_score += 1
                elif cmp < c_open and lrc_dir == "DOWN":
                    t_type = "SELL"
                    status = "❄️ SELL"
                    prob_score += 1
                else:
                    t_type = None

                if t_type:
                    p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"
                    entry = cmp
                    target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                    sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                    
                    st.session_state.active_trades[symbol] = {
                        'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                        'time': e_time, 'prob_text': p_text
                    }
                    save_persistent_trades(st.session_state.active_trades)
            else:
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"

            # Compute "Trade" conditions
            if p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up:
                trade_cond = "S.Buy"
            elif p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up:
                trade_cond = "S.Sell"
            else:
                trade_cond = "-"

            # --- STRICT ROC FILTERS ---
            if roc_val >= 0 and roc_val < filter_roc_gt:
                continue
            if roc_val < 0 and roc_val > -filter_roc_lt:
                continue

            # --- TRADE TYPE SELECTION FILTER ---
            if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy":
                continue
            if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell":
                continue
            if filter_trade_type == "S.Buy & S.Sell" and trade_cond not in ["S.Buy", "S.Sell"]:
                continue
            if filter_trade_type == "Blank Only" and trade_cond != "-":
                continue

            results.append({
                "Stock": display_stock_name, 
                "Trade": trade_cond,
                "Qty": int(capital // cmp), 
                "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "Signal": " | ".join(sigs), 
                "Status": status, 
                "Prob": p_text, 
                "Time": e_time,
                "InTrade": 1 if trade else 0, 
                "ROC_Val": abs(roc_val)
            })
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- RENDER ---
df_raw = get_dashboard()

if not df_raw.empty:
    df_sorted = df_raw.sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    
    target_order = ["Stock", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "Signal", "Status", "Prob", "Time"]
    df_sorted = df_sorted[target_order]
    
    def apply_styles(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Status'] == "IN TRADE":
                row_bg = '#c6f6d5' if row['Target'] > row['Entry'] else '#fed7d7'
                styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
                cmp_bg = '#1a8a44' if row['CMP'] >= row['Entry'] else '#c53030'
                styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
        return styles

    styled_view = df_sorted.style.apply(apply_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
        "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
    })

    with table_placeholder.container():
        # Streamlit requires custom HTML columns to be rendered explicitly via safe_html configuration
        st.dataframe(styled_view, use_container_width=True, hide_index=True)
else:
    st.info("🔄 Processing candle data matching filter parameters...")

time.sleep(60 if open_status else 300)
st.rerun()
