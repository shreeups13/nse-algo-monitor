import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. PAGE CONFIGURATION & GLOBAL SETUP
# ==========================================
st.set_page_config(
    page_title="NSE Pro Quantitative Trade Refiner v5.0",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

TRADES_FILE = "trade_history_v5.json"

def load_persistent_trades():
    """Load open and historical trade positions from JSON file."""
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading trade file: {e}")
            return {"regular": {}, "reversed": {}}
    return {"regular": {}, "reversed": {}}

def save_persistent_trades(trades):
    """Save open and historical trade positions to JSON file."""
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=4)
    except Exception as e:
        st.error(f"Error saving trade file: {e}")

# Market Calendar Setup (India NSE 2026/2027)
NSE_HOLIDAYS = [
    date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28),
    date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25)
]

def get_ist():
    """Returns current Indian Standard Time (IST)."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_open():
    """Determine if Indian markets (NSE) are currently open."""
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now <= end_time:
        return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

# Initialize Session State
if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = "RELIANCE"

# ==========================================
# 2. SIDEBAR - CONTROLS & RISK MANAGEMENT
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
    st.title("Trade Engine Setup")
    
    with st.expander("💰 Capital & Risk Engine", expanded=True):
        total_capital = st.number_input("Total Capital (₹)", min_value=10000, value=200000, step=10000)
        risk_per_trade_pct = st.slider("Max Risk Per Trade (%)", 0.25, 3.0, 1.0, step=0.25) / 100
        max_position_size = st.number_input("Max Capital Allocation / Trade (₹)", min_value=5000, value=50000, step=5000)
        atr_multiplier_sl = st.slider("ATR SL Multiplier", 1.0, 3.5, 1.8, step=0.1)

    with st.expander("🎯 Strategy & Signal Filters", expanded=True):
        filter_min_price = st.number_input("Min Price (₹)", min_value=1.0, value=50.0, step=10.0)
        filter_max_price = st.number_input("Max Price (₹)", min_value=10.0, value=5000.0, step=100.0)
        
        min_adx = st.slider("Min ADX Strength", 15, 40, 22)
        
        st.markdown("**ROC Range (%) Filter**")
        col_roc1, col_roc2 = st.columns(2)
        with col_roc1:
            roc_min = st.number_input("ROC Min %", value=0.8, step=0.1)
        with col_roc2:
            roc_max = st.number_input("ROC Max %", value=4.5, step=0.1)

        use_htf_filter = st.checkbox("Require HTF (Daily) Alignment", value=True)
        use_volume_profile = st.checkbox("Require Volume Spike (>1.3x)", value=True)

    with st.expander("📋 Watchlist Selector"):
        custom_symbols_raw = st.text_area("NSE Tickers (Comma-Separated)", "RELIANCE, HDFCBANK, ICICIBANK, INFY, TCS, KOTAKBANK, LT, AXISBANK, SBIN, MARUTI, BAJFINANCE, TATAMOTORS, HINDUNILVR, ADANIENT, TITAN")
        SYMBOLS = [s.strip().replace("=INFY", "").upper() for s in custom_symbols_raw.split(",") if s.strip()]

    st.markdown("---")
    if st.button("🗑️ Clear All Active Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        save_persistent_trades(st.session_state.dual_trades)
        st.toast("Active trades reset!", icon="🧹")
        st.rerun()

# ==========================================
# 3. TECHNICAL INDICATORS & ENGINE UTILS
# ==========================================
def calculate_atr(df, period=14):
    """Calculates Average True Range (ATR)."""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_adx(df, period=14):
    """Calculates Average Directional Index (ADX) along with +DI and -DI."""
    up_move = df['High'] - df['High'].shift(1)
    down_move = df['Low'].shift(1) - df['Low']
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr = calculate_atr(df, period=period)
    
    p_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(period).mean()
    m_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(period).mean()
    
    p_di = 100 * (p_dm_smooth / np.where(atr == 0, 1e-9, atr))
    m_di = 100 * (m_dm_smooth / np.where(atr == 0, 1e-9, atr))
    
    dx = 100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))
    adx = pd.Series(dx, index=df.index).rolling(period).mean()
    return adx, p_di, m_di

def process_single_stock(df, symbol, is_reversed=False):
    """Processes pricing data to generate actionable quantitative trade setups."""
    if df.empty or len(df) < 30:
        return None

    cmp = float(df['Close'].iloc[-1])
    c_open = float(df['Open'].iloc[-1])
    
    if cmp < filter_min_price or cmp > filter_max_price:
        return None

    # Calculate indicators
    df['ATR'] = calculate_atr(df, 14)
    df['ADX'], df['Plus_DI'], df['Minus_DI'] = calculate_adx(df, 14)
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    df['EMA_21'] = df['Close'].ewm(span=21).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    # Rate of Change (ROC 5)
    p5 = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
    roc_val = ((cmp - p5) / p5) * 100

    # Accumulation / Distribution (A/D) Shift
    denom = np.where(df['High'] == df['Low'], 1e-9, df['High'] - df['Low'])
    mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / denom
    mfv = mfm * df['Volume']
    ad_series = mfv.cumsum()

    lookback = 10
    y_p = df['Close'].tail(lookback).values
    y_ad = ad_series.tail(lookback).values
    x_axis = np.arange(lookback)
    
    slope_price, _ = np.polyfit(x_axis, y_p, 1)
    slope_ad, _ = np.polyfit(x_axis, y_ad, 1)

    if slope_price < 0 and slope_ad > 0:
        ad_trend = "Bullish Shift 🚨"
    elif slope_price > 0 and slope_ad < 0:
        ad_trend = "Bearish Shift 🚨"
    else:
        ad_trend = "Continuous 🔼" if slope_ad > 0 else "Continuous 🔽"

    # Volume & ADX Filters
    vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
    vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.3)
    current_adx = float(df['ADX'].iloc[-1]) if not pd.isna(df['ADX'].iloc[-1]) else 0.0

    # Linear Regression Channel (LRC)
    y_lrc = df['Close'].tail(14).values
    lrc_slope, lrc_intercept = np.polyfit(np.arange(len(y_lrc)), y_lrc, 1)
    lrc_dir = "UP" if lrc_slope > 0 else "DOWN"

    atr_val = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else cmp * 0.01

    # Alignment Signals
    ema_bullish = cmp > df['EMA_9'].iloc[-1] > df['EMA_21'].iloc[-1]
    ema_bearish = cmp < df['EMA_9'].iloc[-1] < df['EMA_21'].iloc[-1]
    
    # Check Active Strategy State
    strategy_key = "reversed" if is_reversed else "regular"
    trade = st.session_state.dual_trades[strategy_key].get(symbol)
    
    t_type = None
    status = "WAITING"
    
    if trade:
        status = trade.get('status', 'IN TRADE')
        t_type = trade.get('type')
        
        # Live Monitor Hit Check
        if t_type == 'BUY':
            if cmp >= trade['target3']:
                status = "🎯 T3 REACHED"
            elif cmp >= trade['target2']:
                status = "🎯 T2 REACHED"
            elif cmp >= trade['target1']:
                status = "🎯 T1 REACHED"
            elif cmp <= trade['sl']:
                status = "🛑 SL HIT"
        elif t_type == 'SELL':
            if cmp <= trade['target3']:
                status = "🎯 T3 REACHED"
            elif cmp <= trade['target2']:
                status = "🎯 T2 REACHED"
            elif cmp <= trade['target1']:
                status = "🎯 T1 REACHED"
            elif cmp >= trade['sl']:
                status = "🛑 SL HIT"
    else:
        # Check Signal Generation Logic
        if current_adx >= min_adx and (not use_volume_profile or vol_surge):
            if abs(roc_val) >= roc_min and abs(roc_val) <= roc_max:
                if not is_reversed:
                    if cmp > c_open and lrc_dir == "UP" and ema_bullish:
                        t_type, status = "BUY", "🔥 SIGNAL (BUY)"
                    elif cmp < c_open and lrc_dir == "DOWN" and ema_bearish:
                        t_type, status = "SELL", "❄️ SIGNAL (SELL)"
                else:
                    if cmp > c_open and lrc_dir == "UP":
                        t_type, status = "SELL", "❄️ SIGNAL (SELL)"
                    elif cmp < c_open and lrc_dir == "DOWN":
                        t_type, status = "BUY", "🔥 SIGNAL (BUY)"

        # Position Sizing & SL/TP Computation if trade triggers
        if t_type and (status.startswith("🔥") or status.startswith("❄️")):
            entry_price = cmp
            sl_distance = atr_val * atr_multiplier_sl
            
            if t_type == "BUY":
                sl_price = entry_price - sl_distance
                t1_price = entry_price + (sl_distance * 1.5)
                t2_price = entry_price + (sl_distance * 2.5)
                t3_price = entry_price + (sl_distance * 4.0)
            else:
                sl_price = entry_price + sl_distance
                t1_price = entry_price - (sl_distance * 1.5)
                t2_price = entry_price - (sl_distance * 2.5)
                t3_price = entry_price - (sl_distance * 4.0)

            risk_amount = total_capital * risk_per_trade_pct
            risk_per_share = abs(entry_price - sl_price)
            qty_by_risk = int(risk_amount / risk_per_share) if risk_per_share > 0 else 1
            qty_by_cap = int(max_position_size / entry_price) if entry_price > 0 else 1
            calculated_qty = max(1, min(qty_by_risk, qty_by_cap))

            st.session_state.dual_trades[strategy_key][symbol] = {
                'entry': entry_price,
                'sl': sl_price,
                'target1': t1_price,
                'target2': t2_price,
                'target3': t3_price,
                'qty': calculated_qty,
                'type': t_type,
                'time': get_ist().strftime("%H:%M:%S"),
                'status': 'IN TRADE',
                'atr': atr_val
            }
            save_persistent_trades(st.session_state.dual_trades)
            status = "IN TRADE"
            trade = st.session_state.dual_trades[strategy_key][symbol]

    return {
        "Symbol": symbol,
        "Type": trade['type'] if trade else (t_type if t_type else "-"),
        "Status": status,
        "CMP": cmp,
        "Entry": trade['entry'] if trade else cmp,
        "SL (ATR)": trade['sl'] if trade else 0.0,
        "Target 1": trade['target1'] if trade else 0.0,
        "Target 2": trade['target2'] if trade else 0.0,
        "Target 3": trade['target3'] if trade else 0.0,
        "Qty": trade['qty'] if trade else 0,
        "ADX": round(current_adx, 1),
        "ROC%": round(roc_val, 2),
        "A/D Trend": ad_trend,
        "Time": trade['time'] if trade else "-"
    }

# ==========================================
# 4. HEADER & MARKET SNAPSHOT
# ==========================================
open_status, status_text = is_market_open()
ist_now = get_ist()

header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.title("⚡ NSE Quantitative Trade Refiner v5.0")
    st.caption("Intraday & Swing Dynamic Structure Engine with ATR Trailing Stops & Multi-Target Execution")

with header_col2:
    st.markdown(f"#### Time: `{ist_now.strftime('%H:%M:%S IST')}`")
    st.markdown(f"**Market Status:** {status_text}")

# Market Tickers Snapshot (NIFTY 50 & SENSEX)
try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="5m", progress=False)
    if not indices.empty and 'Close' in indices.columns:
        n_series = indices["Close"]["^NSEI"].dropna()
        s_series = indices["Close"]["^BSESN"].dropna()
        
        if len(n_series) > 1 and len(s_series) > 1:
            n_curr, n_prev = n_series.iloc[-1], n_series.iloc[0]
            s_curr, s_prev = s_series.iloc[-1], s_series.iloc[0]
            n_chg = ((n_curr - n_prev) / n_prev) * 100
            s_chg = ((s_curr - s_prev) / s_prev) * 100
            
            m1, m2 = st.columns(2)
            m1.metric("NIFTY 50", f"₹{n_curr:,.2f}", f"{n_chg:+.2f}%")
            m2.metric("SENSEX", f"₹{s_curr:,.2f}", f"{s_chg:+.2f}%")
except Exception:
    st.warning("Index ticker snapshot currently updating...")

st.markdown("---")

# ==========================================
# 5. DATA FETCHING ENGINE
# ==========================================
tickers_nse = [f"{s}.NS" for s in SYMBOLS]

@st.cache_data(ttl=45)
def fetch_market_data(tickers):
    """Fetch 5m interval market data for primary intraday processing."""
    try:
        data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", auto_adjust=True, progress=False)
        return data
    except Exception as ex:
        st.error(f"Error fetching live data: {ex}")
        return pd.DataFrame()

with st.spinner("🔍 Scanning NSE Watchlist with ATR & Structural Filters..."):
    raw_data = fetch_market_data(tickers_nse)

reg_results = []
rev_results = []

if isinstance(raw_data, pd.DataFrame) and not raw_data.empty:
    actual_tickers = set([col[0] for col in raw_data.columns]) if isinstance(raw_data.columns, pd.MultiIndex) else set()
    
    for sym in SYMBOLS:
        t_str = f"{sym}.NS"
        if t_str in actual_tickers:
            df_stock = raw_data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low'])
            
            res_reg = process_single_stock(df_stock, sym, is_reversed=False)
            if res_reg:
                reg_results.append(res_reg)
                
            res_rev = process_single_stock(df_stock, sym, is_reversed=True)
            if res_rev:
                rev_results.append(res_rev)

df_reg = pd.DataFrame(reg_results)
df_rev = pd.DataFrame(rev_results)

# ==========================================
# 6. INTERACTIVE TABS DISPLAY
# ==========================================
tab_dashboard, tab_chart, tab_risk, tab_analytics = st.tabs([
    "📊 Active Signals & Trade Engine", 
    "📈 Interactive Structure Chart", 
    "🧮 Risk & Position Calculator", 
    "📜 Trade Log & Performance"
])

def color_trade_table(val):
    """Applies CSS styling to key trade status columns using modern .style.map compatible mapping."""
    if "REACHED" in str(val) or "BUY" in str(val):
        return 'background-color: #2e7d32; color: white; font-weight: bold;'
    elif "HIT" in str(val) or "SELL" in str(val):
        return 'background-color: #c62828; color: white; font-weight: bold;'
    elif "IN TRADE" in str(val):
        return 'background-color: #0277bd; color: white; font-weight: bold;'
    return ''

with tab_dashboard:
    st.subheader("🔥 Active Trade Window (Dynamic ATR Multi-Target Execution)")
    
    all_active = []
    if not df_reg.empty:
        all_active.append(df_reg[df_reg['Status'].str.contains("IN TRADE|REACHED|HIT", regex=True, na=False)])
    if not df_rev.empty:
        all_active.append(df_rev[df_rev['Status'].str.contains("IN TRADE|REACHED|HIT", regex=True, na=False)])
        
    if all_active:
        df_active = pd.concat(all_active, ignore_index=True).drop_duplicates(subset=["Symbol"])
        if not df_active.empty:
            st.dataframe(
                df_active.style.map(color_trade_table, subset=["Type", "Status"]).format({
                    "CMP": "₹{:.2f}", "Entry": "₹{:.2f}", "SL (ATR)": "₹{:.2f}", 
                    "Target 1": "₹{:.2f}", "Target 2": "₹{:.2f}", "Target 3": "₹{:.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No active open positions matching multi-target criteria right now.")
    else:
        st.info("No active positions tracked in current session.")

    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🟢 Standard Momentum & Breakout Monitor")
        if not df_reg.empty:
            st.dataframe(
                df_reg.style.map(color_trade_table, subset=["Type", "Status"]).format({
                    "CMP": "₹{:.2f}", "Entry": "₹{:.2f}", "SL (ATR)": "₹{:.2f}", 
                    "Target 1": "₹{:.2f}", "Target 2": "₹{:.2f}", "Target 3": "₹{:.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No tickers currently match standard filters.")

    with col2:
        st.subheader("🔄 Mean Reversal & Counter-Trend Monitor")
        if not df_rev.empty:
            st.dataframe(
                df_rev.style.map(color_trade_table, subset=["Type", "Status"]).format({
                    "CMP": "₹{:.2f}", "Entry": "₹{:.2f}", "SL (ATR)": "₹{:.2f}", 
                    "Target 1": "₹{:.2f}", "Target 2": "₹{:.2f}", "Target 3": "₹{:.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.caption("No tickers currently match mean-reversal filters.")

# ==========================================
# 7. INTERACTIVE PLOTLY CHART TAB
# ==========================================
with tab_chart:
    st.subheader("🔍 Stock Structure & ATR Target Chart")
    selected_symbol = st.selectbox("Select Watchlist Stock to Analyze", SYMBOLS, index=0)
    
    t_symbol = f"{selected_symbol}.NS"
    if isinstance(raw_data, pd.DataFrame) and t_symbol in raw_data.columns.levels[0]:
        df_chart = raw_data[t_symbol].dropna()
        
        df_chart['EMA_9'] = df_chart['Close'].ewm(span=9).mean()
        df_chart['EMA_21'] = df_chart['Close'].ewm(span=21).mean()
        df_chart['SMA_50'] = df_chart['Close'].rolling(50).mean()
        df_chart['ATR'] = calculate_atr(df_chart, 14)

        # Create Candle Plot
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart['Open'],
            high=df_chart['High'],
            low=df_chart['Low'],
            close=df_chart['Close'],
            name="Price"
        ), row=1, col=1)

        # EMAs
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_9'], line=dict(color='blue', width=1), name="9 EMA"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_21'], line=dict(color='orange', width=1), name="21 EMA"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA_50'], line=dict(color='purple', width=1.5), name="50 SMA"), row=1, col=1)

        # Plot Active Trade Levels if available
        active_trade_info = st.session_state.dual_trades['regular'].get(selected_symbol) or st.session_state.dual_trades['reversed'].get(selected_symbol)
        
        if active_trade_info:
            entry_v = active_trade_info['entry']
            sl_v = active_trade_info['sl']
            t1_v = active_trade_info['target1']
            t2_v = active_trade_info['target2']
            t3_v = active_trade_info['target3']

            fig.add_hline(y=entry_v, line=dict(color="blue", width=2, dash="dash"), annotation_text=f"Entry: ₹{entry_v:.2f}", row=1, col=1)
            fig.add_hline(y=sl_v, line=dict(color="red", width=2, dash="dash"), annotation_text=f"SL: ₹{sl_v:.2f}", row=1, col=1)
            fig.add_hline(y=t1_v, line=dict(color="green", width=1, dash="dot"), annotation_text=f"T1: ₹{t1_v:.2f}", row=1, col=1)
            fig.add_hline(y=t2_v, line=dict(color="green", width=1.5, dash="dot"), annotation_text=f"T2: ₹{t2_v:.2f}", row=1, col=1)
            fig.add_hline(y=t3_v, line=dict(color="green", width=2, dash="solid"), annotation_text=f"T3: ₹{t3_v:.2f}", row=1, col=1)

        # Volume Subplot
        colors = ['red' if row['Open'] > row['Close'] else 'green' for _, row in df_chart.iterrows()]
        fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors, name="Volume"), row=2, col=1)

        fig.update_layout(
            title=f"{selected_symbol} - Intraday Structural Breakdown",
            xaxis_rangeslider_visible=False,
            height=600,
            template="plotly_dark",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"Data for {selected_symbol} is not available in the current download cache.")

# ==========================================
# 8. RISK CALCULATOR & REFINER TOOL
# ==========================================
with tab_risk:
    st.subheader("🧮 Equity Trade Size & Risk Refiner Calculator")
    
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        calc_entry = st.number_input("Planned Entry Price (₹)", min_value=1.0, value=1000.0, step=1.0)
        calc_direction = st.radio("Direction", ["BUY", "SELL"])
    with col_c2:
        calc_atr = st.number_input("Current ATR (₹)", min_value=0.1, value=15.0, step=0.5)
        calc_mult = st.number_input("ATR SL Multiplier", min_value=0.5, value=1.5, step=0.1)
    with col_c3:
        calc_account = st.number_input("Account Balance (₹)", min_value=1000.0, value=100000.0, step=5000.0)
        calc_risk = st.number_input("Risk Tolerance (%)", min_value=0.1, value=1.0, step=0.1)

    # Compute calculations
    sl_dist = calc_atr * calc_mult
    if calc_direction == "BUY":
        calc_sl = calc_entry - sl_dist
        calc_t1 = calc_entry + (sl_dist * 1.5)
        calc_t2 = calc_entry + (sl_dist * 2.5)
        calc_t3 = calc_entry + (sl_dist * 4.0)
    else:
        calc_sl = calc_entry + sl_dist
        calc_t1 = calc_entry - (sl_dist * 1.5)
        calc_t2 = calc_entry - (sl_dist * 2.5)
        calc_t3 = calc_entry - (sl_dist * 4.0)

    total_risk_cash = calc_account * (calc_risk / 100.0)
    risk_per_share = abs(calc_entry - calc_sl)
    calc_qty = int(total_risk_cash / risk_per_share) if risk_per_share > 0 else 0
    total_exposure = calc_qty * calc_entry

    st.markdown("---")
    st.markdown("### Execution Plan Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recommended Quantity", f"{calc_qty} Shares")
    m2.metric("Total Position Capital", f"₹{total_exposure:,.2f}")
    m3.metric("Max Cash at Risk", f"₹{total_risk_cash:,.2f}")
    m4.metric("Calculated Stop-Loss", f"₹{calc_sl:.2f}")

    st.markdown("### Partial Profit Execution Targets")
    tcol1, tcol2, tcol3 = st.columns(3)
    tcol1.metric("Target 1 (1.5x R:R - Scale 50%)", f"₹{calc_t1:.2f}", f"+₹{(abs(calc_t1 - calc_entry)*calc_qty*0.5):,.2f}")
    tcol2.metric("Target 2 (2.5x R:R - Scale 30%)", f"₹{calc_t2:.2f}", f"+₹{(abs(calc_t2 - calc_entry)*calc_qty*0.3):,.2f}")
    tcol3.metric("Target 3 (4.0x R:R - Runner 20%)", f"₹{calc_t3:.2f}", f"+₹{(abs(calc_t3 - calc_entry)*calc_qty*0.2):,.2f}")

# ==========================================
# 9. TRADE LOGS & ANALYTICS
# ==========================================
with tab_analytics:
    st.subheader("📜 Session Trade History Log")
    
    trades_reg = st.session_state.dual_trades.get('regular', {})
    trades_rev = st.session_state.dual_trades.get('reversed', {})
    
    combined_log = []
    for k, v in trades_reg.items():
        v_copy = v.copy()
        v_copy['Symbol'] = k
        v_copy['Strategy'] = 'Standard'
        combined_log.append(v_copy)
        
    for k, v in trades_rev.items():
        v_copy = v.copy()
        v_copy['Symbol'] = k
        v_copy['Strategy'] = 'Reversal'
        combined_log.append(v_copy)

    if combined_log:
        df_log = pd.DataFrame(combined_log)
        st.dataframe(df_log, use_container_width=True)
    else:
        st.info("No recorded session log entries available.")

# ==========================================
# 10. AUTO REFRESH LOOP
# ==========================================
st.markdown("---")
refresh_sec = 60 if open_status else 300
st.caption(f"🔄 Auto-refreshing page every {refresh_sec} seconds. Market open status: {open_status}")
time.sleep(refresh_sec)
st.rerun()
