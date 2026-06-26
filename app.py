#G9.09.06.26_DUAL_MONITOR_SINGLE_TRADE_WINDOW
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime  # Imported cleanly to protect against object clashes
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v4.7 (Dual Mode)", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history_dual.json"

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

# --- INITIALIZE STATE FOR BOTH STRATEGIES ---
if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ General Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=20000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("📊 Backtest Control Panel")
    backtest_active = st.checkbox("Turn On Historical Backtest Engine", value=False)
    backtest_days = st.slider("Backtest History Period (Days)", min_value=1, max_value=59, value=7)
    
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
    
    if st.button("🗑️ Reset All Trades (Both Layouts)"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
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

# --- INTERNAL SIMULATION ENGINE FOR BACKTEST P&L COLUMN ---
def compute_backtest_pnl_matrix(data, target_p, sl_p):
    pnl_ledger = {"regular": {}, "reversed": {}}
    sq_off = datetime.time(15, 15) # Fixed object reference mismatch
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in data or data[t_str].empty: continue
        df = data[t_str].dropna()
        if len(df) < 20: continue
        
        df_copy = df.copy()
        df_copy['Vol_Avg'] = df_copy['Volume'].rolling(10).mean()
        
        reg_pnl, rev_pnl = 0.0, 0.0
        
        for idx in range(20, len(df_copy)):
            current_candle = df_copy.iloc[idx]
            past_candles = df_copy.iloc[:idx+1]
            trade_datetime = df_copy.index[idx]
            
            if trade_datetime.time() >= sq_off: continue
            if not (current_candle['Volume'] > (current_candle['Vol_Avg'] * 1.2)): continue
            
            cmp, c_open = float(current_candle['Close']), float(current_candle['Open'])
            y = past_candles['Close'].tail(14).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            
            for strategy_mode in ['Regular', 'Reversed']:
                trade_type = None
                if strategy_mode == 'Regular':
                    if cmp > c_open and lrc_dir == "UP": trade_type = "BUY"
                    elif cmp < c_open and lrc_dir == "DOWN": trade_type = "SELL"
                else:
                    if cmp > c_open and lrc_dir == "UP": trade_type = "SELL"
                    elif cmp < c_open and lrc_dir == "DOWN": trade_type = "BUY"
                
                if not trade_type: continue
                qty = int(capital // cmp)
                if qty == 0: continue
                
                target_price = cmp * (1 + target_p) if trade_type == "BUY" else cmp * (1 - target_p)
                sl_price = cmp * (1 - sl_p) if trade_type == "BUY" else cmp * (1 + sl_p)
                exit_price = cmp
                
                for scan_idx in range(idx + 1, len(df_copy)):
                    future_candle = df_copy.iloc[scan_idx]
                    future_time = df_copy.index[scan_idx]
                    
                    if future_time.date() == trade_datetime.date() and future_time.time() >= sq_off:
                        exit_price = float(future_candle['Close']); break
                    if future_time.date() != trade_datetime.date():
                        exit_price = float(df_copy.iloc[scan_idx-1]['Close']); break
                    
                    if trade_type == "BUY":
                        if future_candle['High'] >= target_price: exit_price = target_price; break
                        elif future_candle['Low'] <= sl_price: exit_price = sl_price; break
                    else:
                        if future_candle['Low'] <= target_price: exit_price = target_price; break
                        elif future_candle['High'] >= sl_price: exit_price = sl_price; break
                
                pnl_calc = (exit_price - cmp) * qty if trade_type == "BUY" else (cmp - exit_price) * qty
                if strategy_mode == 'Regular': reg_pnl += pnl_calc
                else: rev_pnl += pnl_calc
                
        pnl_ledger["regular"][symbol] = round(reg_pnl, 2)
        pnl_ledger["reversed"][symbol] = round(rev_pnl, 2)
        
    return pnl_ledger

# --- CALCULATION LOGIC CORE ---
def process_strategy(data, is_reversed=False, historical_ledger=None):
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
        
        # ROC Calculation
        p5 = df['Close'].iloc[-6]
        roc_val = ((cmp - p5) / p5) * 100
        if abs(roc_val) > 0.5: prob_score += 1
        if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
        
        flag = "🟢 " if 1.0 <= abs(roc_val) <= 5.0 else "🔴 "
        
        # Volume Surge Calculation
        vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
        vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
        if vol_surge: prob_score += 1

        # LRC Trend Line Properties
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
        
        # ADX Calculation Block
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

        # Memory Check
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

        # Scoreboard setups
        if not is_reversed:
            if p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Buy"
            elif p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Sell"
            else: trade_cond = "-"
        else:
            if p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Buy"
            elif p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Sell"
            else: trade_cond = "-"

        # --- FILTERS ---
        if roc_val >= 0 and roc_val < filter_roc_gt: continue
        if roc_val < 0 and roc_val > -filter_roc_lt: continue

        if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy": continue
        if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell": continue
        if filter_trade_type == "S.Buy & S.Sell" and trade_cond not in ["S.Buy", "S.Sell"]: continue
        if filter_trade_type == "Blank Only" and trade_cond != "-": continue

        # Attach Backtest metric value based on active configuration
        bt_val = "-"
        if historical_ledger and symbol in historical_ledger[strategy_key]:
            val_stat = historical_ledger[strategy_key][symbol]
            bt_val = f"₹{val_stat:+.2f}" if val_stat != 0.0 else "₹0.00"

        results.append({
            "Stock": flag + symbol, "Trade": trade_flag + trade_cond, "Qty": f"{qty_flag}{int(capital // cmp)}", 
            "CMP": cmp, "Entry": trade['entry'] if trade else 0.0, "SL": trade['sl'] if trade else 0.0,
            "Target": trade['target'] if trade else 0.0, "Signal": " | ".join(sigs), "Status": status, 
            "Prob": p_text, "Time": e_time, "InTrade": 1 if trade else 0, "ROC_Val": abs(roc_val), "TradeType": t_type,
            "Backtest P&L": bt_val
        })
    
    if not results: return pd.DataFrame()
    df_out = pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    return df_out[["Stock", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "Signal", "Status", "Prob", "Time", "TradeType", "Backtest P&L"]]


# --- EXECUTE FETCH ---
tickers = [f"{s}.NS" for s in SYMBOLS]
data_window_period = f"{backtest_days}d" if backtest_active else "7d"

try:
    raw_market_data = yf.download(tickers, period=data_window_period, interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except:
    raw_market_data = {}

# Compute historical context calculations if turned on
active_pnl_ledger = None
if backtest_active and not isinstance(raw_market_data, dict) and not raw_market_data.empty:
    active_pnl_ledger = compute_backtest_pnl_matrix(raw_market_data, target_pct, sl_pct)

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

columns_to_show = ["Stock", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "Signal", "Status", "Prob", "Time", "Backtest P&L"]

# Process datasets
df_reg = process_strategy(raw_market_data, is_reversed=False, historical_ledger=active_pnl_ledger) if not isinstance(raw_market_data, dict) and not raw_market_data.empty else pd.DataFrame()
df_rev = process_strategy(raw_market_data, is_reversed=True, historical_ledger=active_pnl_ledger) if not isinstance(raw_market_data, dict) and not raw_market_data.empty else pd.DataFrame()


# --- 🏢 CHANGED ELEMENT: 1) CONSOLIDATED TRADE WINDOW ---
st.markdown("---")
st.header("🪟 1) TRADE WINDOW")

# Filter active records for Regular & Reversed
active_reg = df_reg[(df_reg['Status'] == "IN TRADE") & ((df_reg['CMP'] > df_reg['Entry']) | (df_reg['CMP'] < df_reg['Entry']))] if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[(df_rev['Status'] == "IN TRADE") & ((df_rev['CMP'] > df_rev['Entry']) | (df_rev['CMP'] < df_rev['Entry']))] if not df_rev.empty else pd.DataFrame()

# Merge matrices to eliminate duplication across displays
if not active_reg.empty or not active_rev.empty:
    combined_trades = pd.concat([active_reg, active_rev], ignore_index=True)
    # Deduplicate keeping standard monitor preference to keep layout clean
    combined_trades = combined_trades.drop_duplicates(subset=["Stock"], keep="first")
    
    view_trade_window = combined_trades.style.apply(apply_dynamic_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"
    })
    st.dataframe(view_trade_window, use_container_width=True, hide_index=True, column_order=columns_to_show)
else:
    st.info("No active open positions match conditions (CMP > Entry or CMP < Entry).")


# --- RENDER SIDE-BY-SIDE PANELS ---
st.markdown("---")
col_reg, col_rev = st.columns(2)

with col_reg:
    st.subheader("📊 2) REGULAR MONITOR")
    if not df_reg.empty:
        view_reg = df_reg.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
        })
        st.dataframe(view_reg, use_container_width=True, hide_index=True, column_order=columns_to_show)
    else:
        st.caption("No tickers match standard filters right now.")

with col_rev:
    st.subheader("🔄 3) REVERSED MONITOR")
    if not df_rev.empty:
        view_rev = df_rev.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
        })
        st.dataframe(view_rev, use_container_width=True, hide_index=True, column_order=columns_to_show)
    else:
        st.caption("No tickers match reversal filters right now.")

# --- REFRESH RATE ---
time.sleep(60 if open_status else 300)
st.rerun()
