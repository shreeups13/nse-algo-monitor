#G9.12.06.26_STOCK_CENTRIC_FINAL_TRADE_WINDOW
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- INITIALIZATION & CONFIG ---
st.set_page_config(page_title="NSE Pro Monitor v9.0 (Stock Centric)", layout="wide", page_icon="🚀")

TRADES_FILE = "trade_history_uniform.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {"regular": {}, "reversed": {}}
    return {"regular": {}, "reversed": {}}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f: json.dump(trades, f)

if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

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

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Parameter Matrix")
    capital = st.number_input("Capital per Trade (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")  
    filter_roc_gt = st.number_input("ROC Greater Than (>) %", value=1.00, step=0.01, format="%.2f")
    filter_roc_lt = st.number_input("ROC Less Than (<) %", value=1.00, step=0.01, format="%.2f")
    
    st.markdown("---")
    st.subheader("🛠️ Technical Overlays")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_roc = st.checkbox("ROC (5)", value=True)
    use_lrc = st.checkbox("LRC Trend", value=True)
    
    st.markdown("---")
    full_list = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist Matrix", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Active Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- DISPLAY CLOCK ---
ist_now = get_ist()
open_status, status_text = is_market_open()
st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")
st.markdown("---")

# --- CORE MATH STRATEGY ENGINE ---
def process_stock_centric_engine(data):
    results = []
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in data or data[t_str].empty: continue
        df = data[t_str].dropna()
        if len(df) < 20: continue

        cmp = float(df['Close'].iloc[-1])
        c_open = float(df['Open'].iloc[-1])
        
        sigs = []
        prob_score = 0
        
        # 1. ROC (5) Block
        p5 = df['Close'].iloc[-6]
        roc_val = ((cmp - p5) / p5) * 100
        if abs(roc_val) > 0.5: prob_score += 1
        if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
        
        # 2. Volume Surge Logic
        vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
        vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
        if vol_surge: prob_score += 1

        # 3. Linear Regression Channel (LRC)
        y = df['Close'].tail(14).values
        slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
        lrc_dir = "UP" if slope > 0 else "DOWN"
        if use_lrc: sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
        
        avg_price = np.mean(y)
        lrc2 = (slope * (len(y) - 1)) + intercept
        
        # 4. ADX Trend Intensity
        high, low, close = df['High'].values, df['Low'].values, df['Close'].values
        prev_high, prev_low, prev_close = df['High'].shift(1).values, df['Low'].shift(1).values, df['Close'].shift(1).values
        tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
        plus_dm = np.where(((high - prev_high) > (prev_low - low)) & ((high - prev_high) > 0), high - prev_high, 0.0)
        minus_dm = np.where(((prev_low - low) > (high - prev_high)) & ((prev_low - low) > 0), prev_low - low, 0.0)
        
        if len(df) >= 16:
            tr_s = pd.Series(tr).rolling(14).sum().values
            p_di = 100 * (pd.Series(plus_dm).rolling(14).sum().values / np.where(tr_s == 0, 1e-9, tr_s))
            m_di = 100 * (pd.Series(minus_dm).rolling(14).sum().values / np.where(tr_s == 0, 1e-9, tr_s))
            current_adx = float(pd.Series(100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))).rolling(14).mean().values[-1])
        else:
            current_adx = 0.0
            
        # 5. Overlays Moving Averages
        ma_up = cmp > df['Close'].rolling(20).mean().iloc[-1]
        if use_ma20: sigs.append("↑MA" if ma_up else "↓MA")
        ema_up = cmp > df['Close'].ewm(span=9).mean().iloc[-1]
        if use_ema9: sigs.append("↑EMA" if ema_up else "↓EMA")

        # 6. Evaluate Strategy Type Based Entirely On Stock Metrics Instead of Index Matrix
        # If LRC endpoint is above average price, look for breakout momentum. Else look for mean reversion exhaustion.
        is_reversed = False if (lrc2 > avg_price) else True
        strategy_key = "reversed" if is_reversed else "regular"
        strat_display = "REVERSION 🔄" if is_reversed else "TREND 📊"

        # Check for existing open positions
        trade = st.session_state.dual_trades[strategy_key].get(symbol)
        status, t_type = "WAITING", None
        e_time = ist_now.strftime("%H:%M")
        
        if trade:
            status = "IN TRADE"
            e_time = trade.get('time', e_time)
            p_text = trade.get('prob_text', "MED")
            t_type = trade['type']
            if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
               (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                del st.session_state.dual_trades[strategy_key][symbol]
                save_persistent_trades(st.session_state.dual_trades)
                trade = None
                status = "WAITING"
        
        if not trade and vol_surge:
            if not is_reversed: 
                if cmp > c_open and lrc_dir == "UP": t_type, status = "BUY", "🔥 BUY"
                elif cmp < c_open and lrc_dir == "DOWN": t_type, status = "SELL", "❄️ SELL"
            else: 
                if cmp > c_open and lrc_dir == "UP": t_type, status = "SELL", "❄️ SELL"
                elif cmp < c_open and lrc_dir == "DOWN": t_type, status = "BUY", "🔥 BUY"

            if t_type:
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                
                st.session_state.dual_trades[strategy_key][symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': e_time, 'prob_text': p_text, 'strategy': strategy_key.upper()
                }
                save_persistent_trades(st.session_state.dual_trades)
                trade = st.session_state.dual_trades[strategy_key][symbol]
        else:
            p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"

        if not is_reversed:
            trade_cond = "S.Buy" if (p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up) else "S.Sell" if (p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up) else "-"
        else:
            trade_cond = "S.Buy" if (p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up) else "S.Sell" if (p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up) else "-"

        # Custom user sidebar filters
        if roc_val >= 0 and roc_val < filter_roc_gt: continue
        if roc_val < 0 and roc_val > -filter_roc_lt: continue

        results.append({
            "Stock": ("🟢 " if 1.0 <= abs(roc_val) <= 5.0 else "🔴 ") + symbol,
            "Strategy Mode": strat_display,
            "Trade": ("🟢 " if "Buy" in trade_cond or (trade and trade['type'] == 'BUY') else "🔴 " if "Sell" in trade_cond or (trade and trade['type'] == 'SELL') else "⚪ ") + trade_cond,
            "Qty": f"{'🟢 ' if current_adx > 20 else '🔴 '}{int(capital // cmp)}", 
            "CMP": cmp, 
            "Entry": trade['entry'] if trade else 0.0, 
            "SL": trade['sl'] if trade else 0.0,
            "Target": trade['target'] if trade else 0.0, 
            "Signal": " | ".join(sigs), 
            "Status": status, 
            "Prob": p_text, 
            "Time": e_time, 
            "InTrade": 1 if trade else 0, 
            "ROC_Val": abs(roc_val),
            "TradeType": t_type
        })
    return results

# --- DATA STREAM CONSUMPTION LINK ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='7d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except:
    raw_market_data = {}

# --- RENDER UNIFIED FINAL STOCK WINDOW ---
st.success("🎯 **Stock-Centric Analysis Mode Active.** Tickers are processed independently of broad market trend rules to catch independent movers.")
st.subheader("🚀 Final Trade Window (Aligned Stock Actions)")

columns_to_show = ["Stock", "Strategy Mode", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "Signal", "Status", "Prob", "Time"]

compiled_trades = []
if not isinstance(raw_market_data, dict) and not raw_market_data.empty:
    compiled_trades = process_stock_centric_engine(raw_market_data)

if compiled_trades:
    df_final = pd.DataFrame(compiled_trades)
    
    # Keep active positions perfectly locked to the top row layout
    df_final = df_final.sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    
    def apply_dynamic_styles(df):
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Status'] == "IN TRADE":
                row_bg = '#c6f6d5' if row['TradeType'] == 'BUY' else '#fed7d7'
                styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
                
                if row['TradeType'] == 'BUY':
                    cmp_bg = '#1a8a44' if row['CMP'] >= row['Entry'] else '#c53030'
                else:
                    cmp_bg = '#1a8a44' if row['CMP'] <= row['Entry'] else '#c53030'
                styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
        return styles

    view_final = df_final.style.apply(apply_dynamic_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
        "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
    })
    
    st.dataframe(view_final, use_container_width=True, hide_index=True, column_order=columns_to_show)
else:
    st.caption("No tickers passing structural parameter criteria. Monitoring raw data streams...")

# --- AUTOMATED REFRESH LOOP ---
time.sleep(60 if open_status else 300)
st.rerun()
