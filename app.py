import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.0 (Smart Trading Engine)", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history_dual.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"regular": {}, "reversed": {}}
    return {"regular": {}, "reversed": {}}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=4)

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
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now <= end_time:
        return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

# --- INITIALIZE STATE FOR BOTH STRATEGIES ---
if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Execution Settings")
    capital = st.number_input("Capital per Trade (₹)", min_value=1000, value=5000, step=1000)
    risk_pct = st.slider("Risk Per Trade (%)", 0.2, 3.0, 0.75) / 100
    atr_mult = st.slider("ATR SL Multiplier", 0.5, 3.0, 1.5, step=0.1)
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0, format="%.2f")
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=3000.0, step=100.0, format="%.2f")
    
    st.markdown("**📈 Positive ROC Range (%)**")
    filter_pos_roc_min = st.number_input("Pos ROC Min", value=1.00, step=0.01, format="%.2f")
    filter_pos_roc_max = st.number_input("Pos ROC Max", value=5.00, step=0.01, format="%.2f")
    
    st.markdown("**📉 Negative ROC Range (%)**")
    filter_neg_roc_min = st.number_input("Neg ROC Min (e.g. -5.0)", value=-5.00, step=0.01, format="%.2f")
    filter_neg_roc_max = st.number_input("Neg ROC Max (e.g. -1.0)", value=-1.00, step=0.01, format="%.2f")
    
    filter_trade_type = st.selectbox("Trade Type Filter", ["All", "S.Buy Only", "S.Sell Only", "S.Buy & S.Sell", "Blank Only"])
    filter_status = st.selectbox("Status Filter", ["All", "Buy", "Sell", "Buy & Sell", "In Trade", "Waiting"])
    
    st.markdown("---")
    st.subheader("🛠️ Technical Indicators")
    use_ma20 = st.checkbox("MA (20)", value=True)
    use_ema9 = st.checkbox("EMA (9)", value=True)
    use_sma50 = st.checkbox("SMA (50)", value=True)
    use_roc = st.checkbox("ROC (5)", value=True)
    use_lrc = st.checkbox("LRC Trend", value=True)
    
    st.markdown("---")
    full_list = "KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,ETERNAL,AXISBANK,TATASTEEL,LT,ADANIGREEN,CUPID,IDEA,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,WELCORP,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,SAIL,HEROMOTOCO,HCLTECH,ITC,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,FEDERALBNK,SUNTV,HAL,DIXON,PAYTM,NTPC,COALINDIA,DRREDDY,TITAN,HINDCOPPER,PFC,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,PERSISTENT,NAUKRI,RECLTD,MPHASIS,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,BOSCHLTD,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,HINDPETRO,CUMMINSIND,ABCAPITAL,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,INDUSINDBK,NATIONALUM,MUTHOOTFIN,TATAPOWER,BLUESTARCO,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,UNIONBANK,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,RVNL,GAIL,MANKIND,CAMS,TATAELXSI,IRFC,EXIDEIND,JINDALSTEL,COCHINSHIP,BIOCON,DABUR,SIEMENS,JSWENERGY,ESCORTS,SRF,GODREJPROP,NHPC,TATACHEM,COLPAL,IRCTC,JUBLFOOD,BALKRISIND,VOLTAS,KIMS,CYIENT,IREDA,SUPREMEIND,JSL,DELHIVERY,SBICARD,PETRONET,NBCC,MRF,BEML,CONCOR,IEX,IGL,TATACOMM,DEEPAKNTR,MGL,BERGEPAINT,ACC,BLS,UBL,AMBAAL"
    user_input = st.text_area("Watchlist (Comma Separated)", full_list, height=120)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset Persistent Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE):
            os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER (INDICES) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="5m", progress=False)
    if not indices.empty and 'Close' in indices.columns:
        n_series = indices["Close"]["^NSEI"].dropna()
        s_series = indices["Close"]["^BSESN"].dropna()
        
        if len(n_series) >= 2 and len(s_series) >= 2:
            n_curr, n_prev = n_series.iloc[-1], n_series.iloc[0]
            s_curr, s_prev = s_series.iloc[-1], s_series.iloc[0]
            
            n_chg = ((n_curr - n_prev) / n_prev) * 100
            s_chg = ((s_curr - s_prev) / s_prev) * 100
            st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])")
        else:
            st.markdown("### Indices: `Syncing live ticks...`")
    else:
        st.markdown("### Indices: `Data Temporarily Unavailable`")
except Exception:
    st.markdown("### Indices: `Connecting...`")

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")

# --- STRATEGY CORE ---
def process_strategy(data, is_reversed=False):
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return pd.DataFrame()
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    actual_present_tickers = set([col[0] for col in data.columns])
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in actual_present_tickers:
            continue
        
        try:
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low'])
            if len(df) < 25:
                continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            # --- PRICE FILTER ---
            if cmp < filter_min_price or cmp > filter_max_price:
                continue

            sigs = []
            prob_score = 0
            
            highs, lows, closes, volumes = df['High'], df['Low'], df['Close'], df['Volume']
            
            # --- ATR CALCULATION (14-period) ---
            prev_close = closes.shift(1)
            tr1 = highs - lows
            tr2 = (highs - prev_close).abs()
            tr3 = (lows - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            if np.isnan(atr_val) or atr_val == 0:
                atr_val = cmp * 0.005 # Fallback to 0.5% buffer

            # --- A/D SHIFT TREND DETECTOR ---
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

            # --- ROC ---
            p5 = closes.iloc[-6] if len(closes) >= 6 else closes.iloc[0]
            roc_val = ((cmp - p5) / p5) * 100
            if abs(roc_val) > 0.5:
                prob_score += 1
            if use_roc:
                sigs.append(f"ROC:{roc_val:+.2f}%")
            
            flag = "🟢 " if 1.0 <= abs(roc_val) <= 5.0 else "🔴 "
            
            # --- VOLUME SURGE ---
            vol_avg = volumes.rolling(10).mean().iloc[-1]
            vol_surge = volumes.iloc[-1] > (vol_avg * 1.2)
            if vol_surge:
                prob_score += 1

            # --- LRC TREND ---
            y = closes.tail(14).values
            slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            if use_lrc:
                sigs.append(f"LRC:{'↑' if slope > 0 else '↓'}")
            
            avg_price = np.mean(y)
            lrc2 = (slope * (len(y) - 1)) + intercept
            
            trade_flag = "🟢 " if (lrc2 < avg_price if is_reversed else lrc2 > avg_price) else "🔴 "
            
            # --- ADX CALCULATION ---
            up_move = highs - highs.shift(1)
            down_move = lows.shift(1) - lows
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            
            window = 14
            if len(df) >= window + 2:
                tr_s = tr.rolling(window).sum()
                p_dm_s = pd.Series(plus_dm, index=df.index).rolling(window).sum()
                m_dm_s = pd.Series(minus_dm, index=df.index).rolling(window).sum()
                
                p_di = 100 * (p_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
                m_di = 100 * (m_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
                
                adx_series = 100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))
                current_adx = float(adx_series.rolling(window).mean().iloc[-1])
            else:
                current_adx = 0.0
                
            qty_flag = "🟢 " if current_adx > 20 else "🔴 "
            
            # --- MOVING AVERAGES ---
            ma_up = cmp > closes.rolling(20).mean().iloc[-1]
            if use_ma20:
                sigs.append("↑MA" if ma_up else "↓MA")
            
            ema_up = cmp > closes.ewm(span=9).mean().iloc[-1]
            if use_ema9:
                sigs.append("↑EMA" if ema_up else "↓EMA")
            
            if use_sma50:
                sma50_up = len(df) > 50 and cmp > closes.rolling(50).mean().iloc[-1]
                sigs.append("↑SMA50" if sma50_up else "↓SMA50")

            trade = st.session_state.dual_trades[strategy_key].get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            t_type = trade.get('type') if trade else None
            
            # --- DYNAMIC ATR STOP LOSS & TARGET ENGINE ---
            sl_dist = atr_val * atr_mult
            
            if trade:
                status = "IN TRADE"
                e_time = trade.get('time', e_time)
                p_text = trade.get('prob_text', "MED")
                
                # Check target/SL hits dynamically
                if trade['type'] == 'BUY':
                    if cmp >= trade['target']:
                        status = "🎯 TARGET HIT"
                    elif cmp <= trade['sl']:
                        status = "🛑 SL HIT"
                elif trade['type'] == 'SELL':
                    if cmp <= trade['target']:
                        status = "🎯 TARGET HIT"
                    elif cmp >= trade['sl']:
                        status = "🛑 SL HIT"

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
                    
                    if t_type == "BUY":
                        sl = entry - sl_dist
                        target1 = entry + (sl_dist * 1.5)
                        target2 = entry + (sl_dist * 2.5)
                        target3 = entry + (sl_dist * 4.0)
                    else:
                        sl = entry + sl_dist
                        target1 = entry - (sl_dist * 1.5)
                        target2 = entry - (sl_dist * 2.5)
                        target3 = entry - (sl_dist * 4.0)
                    
                    st.session_state.dual_trades[strategy_key][symbol] = {
                        'entry': entry, 'target': target1, 'target2': target2, 'target3': target3,
                        'sl': sl, 'type': t_type, 'time': e_time, 'prob_text': p_text
                    }
                    save_persistent_trades(st.session_state.dual_trades)
            else:
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"

            # --- TRADE CONDITION LABELS ---
            if not is_reversed:
                if p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up:
                    trade_cond = "S.Buy"
                elif p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up:
                    trade_cond = "S.Sell"
                else:
                    trade_cond = "-"
            else:
                if p_text == "HIGH" and roc_val < 0 and lrc_dir == "DOWN" and not ma_up and not ema_up:
                    trade_cond = "S.Buy"
                elif p_text == "HIGH" and roc_val > 0 and lrc_dir == "UP" and ma_up and ema_up:
                    trade_cond = "S.Sell"
                else:
                    trade_cond = "-"

            # --- ROC RANGE FILTERS ---
            if roc_val >= 0:
                if not (filter_pos_roc_min <= roc_val <= filter_pos_roc_max):
                    continue
            else:
                if not (filter_neg_roc_min <= roc_val <= filter_neg_roc_max):
                    continue

            if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy": continue
            if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell": continue
            if filter_trade_type == "S.Buy & S.Sell" and trade_cond not in ["S.Buy", "S.Sell"]: continue
            if filter_trade_type == "Blank Only" and trade_cond != "-": continue

            # --- STATUS FILTERS ---
            if filter_status == "Buy" and "BUY" not in status: continue
            if filter_status == "Sell" and "SELL" not in status: continue
            if filter_status == "Buy & Sell" and ("BUY" not in status and "SELL" not in status): continue
            if filter_status == "In Trade" and "IN TRADE" not in status and "HIT" not in status: continue
            if filter_status == "Waiting" and status != "WAITING": continue

            # Dynamic Quantity calculation based on risk amount
            per_share_risk = abs(cmp - (trade['sl'] if trade else (cmp - sl_dist)))
            calculated_qty = int((capital * risk_pct) / (per_share_risk if per_share_risk > 0 else 1))
            final_qty = max(1, min(calculated_qty, int(capital // cmp)))

            results.append({
                "Stock": flag + symbol, 
                "Trade": trade_flag + trade_cond, 
                "Qty": f"{qty_flag}{final_qty}", 
                "CMP": cmp, 
                "Entry": trade['entry'] if trade else 0.0, 
                "SL": trade['sl'] if trade else (cmp - sl_dist if t_type != "SELL" else cmp + sl_dist),
                "Tgt 1": trade['target'] if trade else (cmp + sl_dist*1.5 if t_type != "SELL" else cmp - sl_dist*1.5), 
                "Tgt 2": trade.get('target2', 0.0) if trade else (cmp + sl_dist*2.5 if t_type != "SELL" else cmp - sl_dist*2.5),
                "A/D Shift": trend_status, 
                "Signal": " | ".join(sigs), 
                "Status": status, 
                "Prob": p_text, 
                "Time": e_time, 
                "InTrade": 1 if trade else 0, 
                "ROC_Val": abs(roc_val), 
                "TradeType": t_type
            })
        except Exception:
            continue
            
    if not results:
        return pd.DataFrame()
    
    df_out = pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    return df_out[["Stock", "Trade", "Qty", "CMP", "Signal", "Entry", "SL", "Tgt 1", "Tgt 2", "A/D Shift", "Status", "Prob", "Time", "TradeType"]]

# --- DATA FETCHING ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except Exception:
    raw_market_data = pd.DataFrame()

# --- TABLE STYLES ---
def apply_dynamic_styles(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        if "IN TRADE" in str(row['Status']) or "HIT" in str(row['Status']):
            row_bg = '#d1fae5' if row['TradeType'] == 'BUY' else '#fee2e2'
            styles.loc[i, :] = f'background-color: {row_bg}; color: #111827; font-weight: 500'
            
            is_buy = row['TradeType'] == 'BUY' or (isinstance(row['Trade'], str) and "Buy" in row['Trade'])
            if is_buy:
                cmp_bg = '#15803d' if row['CMP'] >= row['Entry'] else '#b91c1c'
            else:
                cmp_bg = '#15803d' if row['CMP'] <= row['Entry'] else '#b91c1c'
            styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
    return styles

columns_to_show = ["Stock", "Trade", "Qty", "CMP", "Signal", "Entry", "SL", "Tgt 1", "Tgt 2", "A/D Shift", "Status", "Prob", "Time"]

df_reg = process_strategy(raw_market_data, is_reversed=False) if isinstance(raw_market_data, pd.DataFrame) and not raw_market_data.empty else pd.DataFrame()
df_rev = process_strategy(raw_market_data, is_reversed=True) if isinstance(raw_market_data, pd.DataFrame) and not raw_market_data.empty else pd.DataFrame()

# --- TRADE WINDOW ---
st.markdown("---")
st.header("🪟 1) ACTIVE TRADES MONITOR")

active_reg = df_reg[df_reg['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[df_rev['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_rev.empty else pd.DataFrame()

if not active_reg.empty or not active_rev.empty:
    combined_trades = pd.concat([active_reg, active_rev], ignore_index=True)
    combined_trades = combined_trades.drop_duplicates(subset=["Stock"], keep="first")
    
    view_trade_window = combined_trades.style.apply(apply_dynamic_styles, axis=None).format({
        "CMP": "{:.2f}", "Entry": "{:.2f}", "SL": "{:.2f}", "Tgt 1": "{:.2f}", "Tgt 2": "{:.2f}"
    })
    st.dataframe(view_trade_window, use_container_width=True, hide_index=True, column_order=columns_to_show)
else:
    st.info("No active trades present right now.")

# --- DUAL MONITORS ---
st.markdown("---")
col_reg, col_rev = st.columns(2)

with col_reg:
    st.subheader("📊 2) REGULAR TREND MONITOR")
    if not df_reg.empty:
        view_reg = df_reg.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}", 
            "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
            "SL": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Tgt 1": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Tgt 2": lambda x: f"{x:.2f}" if x > 0 else "-"
        })
        st.dataframe(view_reg, use_container_width=True, hide_index=True, column_order=columns_to_show)
    else:
        st.caption("No tickers match standard strategy filters.")

with col_rev:
    st.subheader("🔄 3) REVERSAL TREND MONITOR")
    if not df_rev.empty:
        view_rev = df_rev.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}", 
            "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
            "SL": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Tgt 1": lambda x: f"{x:.2f}" if x > 0 else "-",
            "Tgt 2": lambda x: f"{x:.2f}" if x > 0 else "-"
        })
        st.dataframe(view_rev, use_container_width=True, hide_index=True, column_order=columns_to_show)
    else:
        st.caption("No tickers match reversal strategy filters.")

# --- AUTO REFRESH ---
time.sleep(60 if open_status else 300)
st.rerun()
