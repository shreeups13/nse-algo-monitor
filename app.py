#G9.11.06.26_UNIFIED_INTELLIGENCE_DASHBOARD
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v6.0 (Unified Intelligence)", layout="wide", page_icon="🤖")

TRADES_FILE = "trade_history_uniform.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {"regular": {}, "reversed": {}}
    return {"regular": {}, "reversed": {}}

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

# --- INITIALIZE STATE ---
if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.header("⚙️ General Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")  
    filter_roc_gt = st.number_input("ROC Greater Than (>) %", value=1.00, step=0.01, format="%.2f")
    filter_roc_lt = st.number_input("ROC Less Than (<) %", value=1.00, step=0.01, format="%.2f")
    filter_trade_type = st.selectbox("Trade Type Filter", ["All", "S.Buy Only", "S.Sell Only", "S.Buy & S.Sell", "Blank Only"])
    
    st.markdown("---")
    st.subheader("🎯 Sensitivity Thresholds")
    trend_threshold = st.number_input("Trend Boundary Threshold (%)", min_value=0.05, max_value=0.50, value=0.15, step=0.01, format="%.2f")
    
    st.markdown("---")
    st.subheader("🛠️ Technical Overlays")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_sma50 = st.checkbox("SMA (50)", value=False)
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

# --- FETCH MARKET INDICES ---
ist_now = get_ist()
open_status, status_text = is_market_open()

n_chg = 0.0
s_chg = 0.0

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)['Close']
    n_curr, n_prev = indices["^NSEI"].dropna().iloc[-1], indices["^NSEI"].dropna().iloc[0]
    s_curr, s_prev = indices["^BSESN"].dropna().iloc[-1], indices["^BSESN"].dropna().iloc[0]
    n_chg = ((n_curr - n_prev) / n_prev) * 100
    s_chg = ((s_curr - s_prev) / s_prev) * 100
    st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])")
except:
    st.markdown("### Indices: `Synchronizing with Exchange...`")

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")
st.markdown("---")

# --- CALCULATION LOGIC ENGINE ---
def process_strategy(data, is_reversed=False):
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in data or data[t_str].empty: continue
        df = data[t_str].dropna()
        if len(df) < 20: continue

        cmp = float(df['Close'].iloc[-1])
        c_open = float(df['Open'].iloc[-1])
        
        sigs = []
        prob_score = 0
        p_text = "LOW"
        
        # ROC Calculation Block
        p5 = df['Close'].iloc[-6]
        roc_val = ((cmp - p5) / p5) * 100
        if abs(roc_val) > 0.5: prob_score += 1
        if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
        
        flag = "🟢 " if 1.0 <= abs(roc_val) <= 5.0 else "🔴 "
        
        # Volume Surge Assessment
        vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
        vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
        if vol_surge: prob_score += 1

        # LRC Mathematics
        y = df['Close'].tail(14).values
        slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
        lrc_dir = "UP" if slope > 0 else "DOWN"
        if use_lrc: sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
        
        avg_price = np.mean(y)
        lrc2 = (slope * (len(y) - 1)) + intercept
        
        if is_reversed:
            trade_flag = "🟢 " if lrc2 < avg_price else "🔴 "
        else:
            trade_flag = "🟢 " if lrc2 > avg_price else "🔴 "
        
        # Trend Intensity via ADX
        high, low, close = df['High'].values, df['Low'].values, df['Close'].values
        prev_high, prev_low, prev_close = df['High'].shift(1).values, df['Low'].shift(1).values, df['Close'].shift(1).values
        
        tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
        up_move = high - prev_high
        down_move = prev_low - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        window = 14
        if len(df) >= window + 2:
            tr_s = pd.Series(tr).rolling(window).sum().values
            p_dm_s = pd.Series(plus_dm).rolling(window).sum().values
            m_dm_s = pd.Series(minus_dm).rolling(window).sum().values
            
            p_di = 100 * (p_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
            m_di = 100 * (m_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
            current_adx = float(pd.Series(100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))).rolling(window).mean().values[-1])
        else:
            current_adx = 0.0
            
        qty_flag = "🟢 " if current_adx > 20 else "🔴 "
        
        ma_up = cmp > df['Close'].rolling(20).mean().iloc[-1]
        if use_ma20: sigs.append("↑MA" if ma_up else "↓MA")
        
        ema_up = cmp > df['Close'].ewm(span=9).mean().iloc[-1]
        if use_ema9: sigs.append("↑EMA" if ema_up else "↓EMA")
        
        if use_sma50: sigs.append("↑SMA50" if len(df)>50 and cmp > df['Close'].rolling(50).mean().iloc[-1] else "•SMA")

        # Session Execution Handling
        trade = st.session_state.dual_trades[strategy_key].get(symbol)
        status = "WAITING"
        e_time = ist_now.strftime("%H:%M")
        t_type = trade.get('type') if trade else None
        
        if trade:
            status = "IN TRADE"
            e_time = trade.get('time', e_time)
            p_text = trade.get('prob_text', "MED")
            if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
               (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                del st.session_state.dual_trades[strategy_key][symbol]
                save_persistent_trades(st.session_state.dual_trades)
        elif vol_surge:
            if not is_reversed:
                if cmp > c_open and lrc_dir == "UP":
                    t_type, status = "BUY", "🔥 BUY"
                    prob_score += 1
                elif cmp < c_open and lrc_dir == "DOWN":
                    t_type, status = "SELL", "❄️ SELL"
                    prob_score += 1
            else:
                if cmp > c_open and lrc_dir == "UP":
                    t_type, status = "SELL", "❄️ SELL"
                    prob_score += 1
                elif cmp < c_open and lrc_dir == "DOWN":
                    t_type, status = "BUY", "🔥 BUY"
                    prob_score += 1

            if t_type:
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                
                st.session_state.dual_trades[strategy_key][symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': e_time, 'prob_text': p_text
                }
                save_persistent_trades(st.session_state.dual_trades)
        else:
            p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"

        # Structural Concurrence Matching
        if not is_reversed:
            if p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Buy"
            elif p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Sell"
            else: trade_cond = "-"
        else:
            if p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Buy"
            elif p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Sell"
            else: trade_cond = "-"

        # --- RESTORED DYNAMIC ROW FILTERS ---
        if roc_val >= 0 and roc_val < filter_roc_gt: continue
        if roc_val < 0 and roc_val > -filter_roc_lt: continue

        if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy": continue
        if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell": continue
        if filter_trade_type == "S.Buy & S.Sell" and trade_cond not in ["S.Buy", "S.Sell"]: continue
        if filter_trade_type == "Blank Only" and trade_cond != "-": continue

        results.append({
            "Stock": flag + symbol, "Trade": trade_flag + trade_cond, "Qty": f"{qty_flag}{int(capital // cmp)}", 
            "CMP": cmp, "Entry": trade['entry'] if trade else 0.0, "SL": trade['sl'] if trade else 0.0,
            "Target": trade['target'] if trade else 0.0, "Signal": " | ".join(sigs), "Status": status, 
            "Prob": p_text, "Time": e_time, "InTrade": 1 if trade else 0, "ROC_Val": abs(roc_val), "TradeType": t_type,
            "TradeCondRaw": trade_cond
        })
    
    if not results: return pd.DataFrame()
    df_out = pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    return df_out

# --- DOWNLOAD MARKET TICKERS ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='7d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except:
    raw_market_data = {}

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

columns_to_show = ["Stock", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "Signal", "Status", "Prob", "Time"]

# --- INTELLIGENT REGIME ASSESSMENT BLOCK ---
master_index_change = n_chg if n_chg != 0.0 else s_chg

if master_index_change > trend_threshold:
    env_msg = f"📈 **TREND EXPANSION DOMINANT** ({master_index_change:+.2f}%) — Focus primarily on the Regular Monitor matrix. Directional breakouts are highly supported by the broad index."
    favored = "REGULAR"
elif master_index_change < -trend_threshold:
    env_msg = f"📉 **TREND BREAKDOWN DOMINANT** ({master_index_change:+.2f}%) — Focus primarily on the Regular Monitor matrix. Short momentum setups have clear statistical backing."
    favored = "REGULAR"
else:
    env_msg = f"🔄 **MEAN REVERSION DOMINANT** ({master_index_change:+.2f}%) — Market is locked inside a channel range. Focus primarily on the Reversed Monitor matrix to catch extremes snapping back."
    favored = "REVERSED"

# Display Live Macro-Guidance Status Box at top of screen
st.info(env_msg)

# --- UNIFIED SIDE-BY-SIDE VIEW LAYOUT ---
# Creates 2 equal columns instead of hiding data
col1, col2 = st.columns(2)

with col1:
    title_suffix = " 🔥 [FAVORED REGIME]" if favored == "REGULAR" else ""
    st.subheader(f"📊 1) REGULAR MONITOR (Trends){title_suffix}")
    
    if not isinstance(raw_market_data, dict) and not raw_market_data.empty:
        df_reg = process_strategy(raw_market_data, is_reversed=False)
        if not df_reg.empty:
            # We filter directional alignment but NEVER completely hide the monitor panel
            if master_index_change < -trend_threshold:
                df_reg = df_reg[df_reg['TradeCondRaw'].str.contains("S.Sell|-")]
            elif master_index_change > trend_threshold:
                df_reg = df_reg[df_reg['TradeCondRaw'].str.contains("S.Buy|-")]
                
            view_reg = df_reg.style.apply(apply_dynamic_styles, axis=None).format({
                "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
                "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
            })
            st.dataframe(view_reg, use_container_width=True, hide_index=True, column_order=columns_to_show)
        else:
            st.caption("No trend tickers passing filters currently.")
    else:
        st.info("Awaiting live data streams...")

with col2:
    title_suffix = " 🔥 [FAVORED REGIME]" if favored == "REVERSED" else ""
    st.subheader(f"🔄 2) REVERSED MONITOR (Mean Reversions){title_suffix}")
    
    if not isinstance(raw_market_data, dict) and not raw_market_data.empty:
        df_rev = process_strategy(raw_market_data, is_reversed=True)
        if not df_rev.empty:
            view_rev = df_rev.style.apply(apply_dynamic_styles, axis=None).format({
                "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
                "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
            })
            st.dataframe(view_rev, use_container_width=True, hide_index=True, column_order=columns_to_show)
        else:
            st.caption("No mean-reversion anomalies found inside the ranges.")
    else:
        st.info("Awaiting live data streams...")

# --- AUTOMATED ENGINE REFRESH LOOP ---
time.sleep(60 if open_status else 300)
st.rerun()
