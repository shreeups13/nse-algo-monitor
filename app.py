import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os
import plotly.graph_objects as go

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.0 (Smart Trade Engine)", layout="wide", page_icon="📈")

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
    capital = st.number_input("Capital (₹)", min_value=1000, value=30000, step=5000)
    target_pct = st.slider("Target 1 (%)", 0.5, 5.0, 1.5) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.75) / 100
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0, format="%.2f")
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=2000.0, step=100.0, format="%.2f")
    
    st.markdown("**📈 Positive ROC Range (%)**")
    filter_pos_roc_min = st.number_input("Pos ROC Min", value=1.00, step=0.01, format="%.2f")
    filter_pos_roc_max = st.number_input("Pos ROC Max", value=5.00, step=0.01, format="%.2f")
    
    st.markdown("**📉 Negative ROC Range (%)**")
    filter_neg_roc_min = st.number_input("Neg ROC Min", value=-5.00, step=0.01, format="%.2f")
    filter_neg_roc_max = st.number_input("Neg ROC Max", value=-1.00, step=0.01, format="%.2f")
    
    filter_trade_type = st.selectbox("Trade Type Filter", ["All", "S.Buy Only", "S.Sell Only", "S.Buy & S.Sell", "Blank Only"])
    filter_status = st.selectbox("Status Filter", ["All", "Buy", "Sell", "Buy & Sell", "In Trade", "Waiting"])
    
    st.markdown("---")
    st.subheader("🛠️ Indicators")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_sma50 = st.checkbox("SMA (50)", value=False)
    use_roc = st.checkbox("ROC (5)", value=True)
    use_lrc = st.checkbox("LRC Trend", value=True)
    
    st.markdown("---")
    full_list = "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN,BHARTIARTL,ITC,KOTAKBANK,LT,AXISBANK,HINDUNILVR,ASIANPAINT,MARUTI,SUNPHARMA,TITAN,BAJFINANCE,ULTRACEMCO,WIPRO,NTPC,POWERGRID,M&M,TATASTEEL,ADANIENT,ONGC,COALINDIA,GRASIM,HCLTECH,JSWSTEEL,BAJAJFINSV"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER (INDICES) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="5m", progress=False)
    if not indices.empty and 'Close' in indices.columns:
        n_series = indices["Close"]["^NSEI"].dropna()
        s_series = indices["Close"]["^BSESN"].dropna()
        
        n_curr, n_prev = n_series.iloc[-1], n_series.iloc[0]
        s_curr, s_prev = s_series.iloc[-1], s_series.iloc[0]
        
        n_chg = ((n_curr - n_prev) / n_prev) * 100
        s_chg = ((s_curr - s_prev) / s_prev) * 100
        st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])")
    else:
        st.markdown("### Indices: `Data Temporarily Unavailable`")
except Exception:
    st.markdown("### Indices: `Connecting...`")

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")

# --- CALCULATION LOGIC CORE ---
def process_strategy(data, is_reversed=False):
    if data.empty or not isinstance(data.columns, pd.MultiIndex): return pd.DataFrame()
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    actual_present_tickers = set([col[0] for col in data.columns])
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in actual_present_tickers: continue
        
        try:
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low'])
            if len(df) < 25: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            if cmp < filter_min_price or cmp > filter_max_price:
                continue

            sigs = []
            prob_score = 0
            
            highs = df['High']
            lows = df['Low']
            closes = df['Close']
            volumes = df['Volume']
            
            denom = np.where(highs == lows, 1e-9, highs - lows)
            mfm = ((closes - lows) - (highs - closes)) / denom
            mfv = mfm * volumes
            ad_series = mfv.cumsum()
            
            lookback = 10
            y_p = closes.tail(lookback).values
            y_ad = ad_series.tail(lookback).values
            x_axis = np.arange(lookback)
            
            slope_price, _ = np.polyfit(x_axis, y_p, 1)
            slope_ad, _ = np.polyfit(x_axis, y_ad, 1)
            
            if slope_price < 0 and slope_ad > 0:
                trend_status = "🚨 Bullish Shift"
                prob_score += 1
            elif slope_price > 0 and slope_ad < 0:
                trend_status = "🚨 Bearish Shift"
                prob_score += 1
            else:
                trend_status = "🔼 Continuous" if slope_ad > 0 else "🔽 Continuous"

            p5 = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
            roc_val = ((cmp - p5) / p5) * 100
            if abs(roc_val) > 0.5: prob_score += 1
            if use_roc: sigs.append(f"ROC:{roc_val:+.2f}%")
            
            flag = "🟢 " if 1.0 <= abs(roc_val) <= 5.0 else "🔴 "
            
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)
            if vol_surge: prob_score += 1

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
            
            high, low, close = df['High'], df['Low'], df['Close']
            prev_high, prev_low, prev_close = high.shift(1), low.shift(1), close.shift(1)
            
            v_1 = (high - low).values
            v_2 = np.abs(high - prev_close).values
            v_3 = np.abs(low - prev_close).values
            
            tr = np.nanmax(np.column_stack([v_1, v_2, v_3]), axis=1)
            tr_series = pd.Series(tr, index=df.index)
            
            up_move = high - prev_high
            down_move = prev_low - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            
            window = 14
            if len(df) >= window + 2:
                tr_s = tr_series.rolling(window).sum()
                p_dm_s = pd.Series(plus_dm, index=df.index).rolling(window).sum()
                m_dm_s = pd.Series(minus_dm, index=df.index).rolling(window).sum()
                
                p_di = 100 * (p_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
                m_di = 100 * (m_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
                
                adx_series = 100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))
                current_adx = float(adx_series.rolling(window).mean().iloc[-1])
            else:
                current_adx = 0.0
                
            qty_flag = "🟢 " if current_adx > 20 else "🔴 "
            
            ma_up = cmp > df['Close'].rolling(20).mean().iloc[-1]
            if use_ma20: sigs.append("↑MA" if ma_up else "↓MA")
            
            ema_up = cmp > df['Close'].ewm(span=9).mean().iloc[-1]
            if use_ema9: sigs.append("↑EMA" if ema_up else "↓EMA")
            
            if use_sma50: sigs.append("↑SMA50" if len(df)>50 and cmp > df['Close'].rolling(50).mean().iloc[-1] else "•SMA")

            trade = st.session_state.dual_trades[strategy_key].get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            t_type = trade.get('type') if trade else None
            
            if trade:
                status = "IN TRADE"
                e_time = trade.get('time', e_time)
                p_text = trade.get('prob_text', "MED")
                
                if trade['type'] == 'BUY':
                    if cmp >= trade['target']: status = "🎯 TARGET HIT"
                    elif cmp <= trade['sl']: status = "🛑 SL HIT"
                elif trade['type'] == 'SELL':
                    if cmp <= trade['target']: status = "🎯 TARGET HIT"
                    elif cmp >= trade['sl']: status = "🛑 SL HIT"

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

            if not is_reversed:
                if p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Buy"
                elif p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Sell"
                else: trade_cond = "-"
            else:
                if p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up: trade_cond = "S.Buy"
                elif p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up: trade_cond = "S.Sell"
                else: trade_cond = "-"

            if roc_val >= 0:
                if not (filter_pos_roc_min <= roc_val <= filter_pos_roc_max): continue
            else:
                if not (filter_neg_roc_min <= roc_val <= filter_neg_roc_max): continue

            if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy": continue
            if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell": continue
            if filter_trade_type == "S.Buy & S.Sell" and trade_cond not in ["S.Buy", "S.Sell"]: continue
            if filter_trade_type == "Blank Only" and trade_cond != "-": continue

            if filter_status == "Buy" and "BUY" not in status: continue
            if filter_status == "Sell" and "SELL" not in status: continue
            if filter_status == "Buy & Sell" and ("BUY" not in status and "SELL" not in status): continue
            if filter_status == "In Trade" and "IN TRADE" not in status and "HIT" not in status: continue
            if filter_status == "Waiting" and status != "WAITING": continue

            results.append({
                "Stock": flag + symbol, "Trade": trade_flag + trade_cond, "Qty": f"{qty_flag}{int(capital // cmp)}", 
                "CMP": cmp, "Entry": trade['entry'] if trade else 0.0, "SL": trade['sl'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0, "A/D Trend": trend_status, "Signal": " | ".join(sigs), "Status": status, 
                "Prob": p_text, "Time": e_time, "InTrade": 1 if trade else 0, "ROC_Val": abs(roc_val), "TradeType": t_type, "RawSymbol": symbol
            })
        except Exception:
            continue
            
    if not results: return pd.DataFrame()
    df_out = pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    return df_out[["Stock", "Trade", "Qty", "CMP", "Entry", "SL", "Target", "A/D Trend", "Signal", "Status", "Prob", "Time", "TradeType", "RawSymbol"]]

# --- EXECUTE FETCH ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except Exception:
    raw_market_data = pd.DataFrame()

# --- FIXED DYNAMIC STYLES (Pandas .style.map instead of applymap) ---
def apply_dynamic_styles(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        if "IN TRADE" in str(row['Status']) or "HIT" in str(row['Status']):
            row_bg = '#c6f6d5' if row['TradeType'] == 'BUY' else '#fed7d7'
            styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
            
            is_buy = row['TradeType'] == 'BUY' or (isinstance(row['Trade'], str) and "Buy" in row['Trade'])
            if is_buy:
                cmp_bg = '#1a8a44' if row['CMP'] >= row['Entry'] else '#c53030'
            else:
                cmp_bg = '#1a8a44' if row['CMP'] <= row['Entry'] else '#c53030'
            styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
    return styles

columns_to_show = ["Stock", "Trade", "Qty", "CMP", "Signal", "Entry", "SL", "Target", "A/D Trend", "Status", "Prob", "Time"]

df_reg = process_strategy(raw_market_data, is_reversed=False) if isinstance(raw_market_data, pd.DataFrame) and not raw_market_data.empty else pd.DataFrame()
df_rev = process_strategy(raw_market_data, is_reversed=True) if isinstance(raw_market_data, pd.DataFrame) and not raw_market_data.empty else pd.DataFrame()

# --- 🪟 TRADE WINDOW ---
st.markdown("---")
st.header("🪟 1) ACTIVE TRADE WINDOW")

active_reg = df_reg[df_reg['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[df_rev['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_rev.empty else pd.DataFrame()

if not active_reg.empty or not active_rev.empty:
    combined_trades = pd.concat([active_reg, active_rev], ignore_index=True)
    combined_trades = combined_trades.drop_duplicates(subset=["Stock"], keep="first")
    
    view_trade_window = combined_trades.style.apply(apply_dynamic_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"
    })
    st.dataframe(view_trade_window, use_container_width=True, hide_index=True, column_order=columns_to_show)
else:
    st.info("No active open positions match conditions.")

# --- RENDER PANELS ---
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

# --- 📈 INTERACTIVE CHART & TRADE DEEP DIVE ---
st.markdown("---")
st.header("📈 4) Interactive Stock Chart & Trade Setup")
selected_stock = st.selectbox("Select stock to inspect setup:", SYMBOLS)

if selected_stock:
    try:
        stock_df = yf.download(f"{selected_stock}.NS", period="5d", interval="5m", progress=False)
        if not stock_df.empty:
            # Flatten multi-index if returned by yfinance
            if isinstance(stock_df.columns, pd.MultiIndex):
                stock_df.columns = stock_df.columns.get_level_values(0)
            
            fig = go.Figure(data=[go.Candlestick(
                x=stock_df.index,
                open=stock_df['Open'],
                high=stock_df['High'],
                low=stock_df['Low'],
                close=stock_df['Close'],
                name="Price"
            )])
            
            # Check if active trade exists for this stock
            reg_trade = st.session_state.dual_trades["regular"].get(selected_stock)
            if reg_trade:
                fig.add_hline(y=reg_trade['entry'], line_dash="dash", line_color="blue", annotation_text=f"Entry: ₹{reg_trade['entry']:.2f}")
                fig.add_hline(y=reg_trade['target'], line_dash="dash", line_color="green", annotation_text=f"Target: ₹{reg_trade['target']:.2f}")
                fig.add_hline(y=reg_trade['sl'], line_dash="dash", line_color="red", annotation_text=f"SL: ₹{reg_trade['sl']:.2f}")

            fig.update_layout(title=f"{selected_stock} - 5m Intraday Chart", xaxis_title="Time", yaxis_title="Price (INR)", template="plotly_dark", height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Chart data currently unavailable for this ticker.")
    except Exception as e:
        st.error(f"Error loading chart: {e}")

# --- REFRESH CONTROL ---
time.sleep(60 if open_status else 300)
st.rerun()
