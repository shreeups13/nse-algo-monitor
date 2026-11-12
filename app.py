# NSE Pro Monitor v5.2 - Multi-Cycle Core + Flex Momentum Engine
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- PAGE CONFIG & COMPACT CSS ---
st.set_page_config(page_title="NSE Pro Monitor v5.2", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
        /* Maximize screen space & tighten header padding */
        .block-container {
            padding-top: 1.1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        header[data-testid="stHeader"] {
            height: 2.2rem !important;
            background: transparent !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
        }
        .compact-bar {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            background-color: #1e222a;
            color: #f8fafc;
            padding: 8px 16px;
            border-radius: 8px;
            border: 1px solid #2e3440;
            font-size: 0.92rem;
            margin-bottom: 10px;
        }
        .compact-bar span {
            margin-right: 14px;
        }
        h2, h3 {
            margin-top: 0.3rem !important;
            margin-bottom: 0.4rem !important;
            font-size: 1.15rem !important;
        }
    </style>
""", unsafe_allow_html=True)

TRADES_FILE = "trade_history_dual_v52.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                data = json.load(f)
                if "regular" in data and "reversed" in data:
                    return data
        except Exception:
            pass
    return {"regular": {}, "reversed": {}}

def save_persistent_trades(trades):
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f)
    except Exception:
        pass

# --- MARKET CALENDAR 2026 ---
NSE_HOLIDAYS = {
    date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28),
    date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25)
}

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_open():
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 CLOSED (HOLIDAY/WKND)"
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now <= end_time:
        return True, "🟢 LIVE"
    return False, "🔴 CLOSED (AFTER HRS)"

if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Execution Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.2, 5.0, 1.0, step=0.1) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.1, 2.0, 0.5, step=0.1) / 100
    refresh_sec = st.slider("Auto-Refresh (sec)", 15, 120, 30, step=5)
    
    st.markdown("---")
    st.subheader("⚡ Core Entry Controls")
    vol_multiplier = st.slider("Min Volume Surge vs MA(10)", 1.0, 2.5, 1.15, step=0.05)
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0)
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=1000.0, step=100.0)
    
    st.markdown("**📈 ROC Velocity Filter (%)**")
    filter_roc_min = st.number_input("ROC Min", value=0.50, step=0.05)
    filter_roc_max = st.number_input("ROC Max", value=5.00, step=0.10)
    
    filter_status = st.selectbox("Status Filter", ["All", "In Trade", "Target Hit", "SL Hit", "Multi-Cycle (Pos 2+)", "Waiting"])
    
    st.markdown("---")
    full_list = "KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"
    user_input = st.text_area("Watchlist", full_list, height=100)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_b2:
        if st.button("🗑️ Reset Trades", use_container_width=True):
            st.session_state.dual_trades = {"regular": {}, "reversed": {}}
            if os.path.exists(TRADES_FILE):
                os.remove(TRADES_FILE)
            st.rerun()

# --- FAST CACHED DATA ENGINE ---
@st.cache_data(ttl=20, show_spinner=False)
def fetch_indices():
    try:
        idx = yf.download(["^NSEI", "^BSESN"], period="1d", interval="1m", progress=False, threads=True)
        if not idx.empty and 'Close' in idx.columns:
            n_s = idx["Close"]["^NSEI"].dropna()
            s_s = idx["Close"]["^BSESN"].dropna()
            if len(n_s) > 0 and len(s_s) > 0:
                n_curr, n_open = float(n_s.iloc[-1]), float(n_s.iloc[0])
                s_curr, s_open = float(s_s.iloc[-1]), float(s_s.iloc[0])
                return (
                    n_curr, ((n_curr - n_open) / n_open) * 100,
                    s_curr, ((s_curr - s_open) / s_open) * 100
                )
    except Exception:
        pass
    return None

@st.cache_data(ttl=25, show_spinner=False)
def fetch_market_batch(ticker_tuple):
    try:
        return yf.download(
            list(ticker_tuple),
            period="2d",
            interval="5m",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False
        )
    except Exception:
        return pd.DataFrame()

# --- COMPACT TOP STATUS BAR ---
ist_now = get_ist()
open_status, status_text = is_market_open()
idx_data = fetch_indices()

if idx_data:
    n_curr, n_chg, s_curr, s_chg = idx_data
    n_color = "#4ade80" if n_chg >= 0 else "#f87171"
    s_color = "#4ade80" if s_chg >= 0 else "#f87171"
    idx_html = (
        f"<span><b>NIFTY 50:</b> {n_curr:,.2f} <b style='color:{n_color}'>({n_chg:+.2f}%)</b></span>"
        f"<span><b>SENSEX:</b> {s_curr:,.2f} <b style='color:{s_color}'>({s_chg:+.2f}%)</b></span>"
    )
else:
    idx_html = "<span><b>INDICES:</b> Syncing live feed...</span>"

st.markdown(
    f"""
    <div class="compact-bar">
        <div>{idx_html}</div>
        <div>
            <span>🕰️ <b>{ist_now.strftime('%H:%M:%S')} IST</b></span>
            <span><b>{status_text}</b></span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- MULTI-CYCLE CORE + FLEX STRATEGY ENGINE ---
def process_core_flex_strategy(data, is_reversed=False):
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return pd.DataFrame()
    
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    actual_present_tickers = set(col[0] for col in data.columns)
    trades_updated = False
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in actual_present_tickers:
            continue
        
        try:
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
            if len(df) < 25:
                continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            if cmp < filter_min_price or cmp > filter_max_price:
                continue

            # Core Trigger metrics
            vol_avg = float(df['Volume'].rolling(10).mean().iloc[-1])
            curr_vol = float(df['Volume'].iloc[-1])
            vol_surge = curr_vol >= (vol_avg * vol_multiplier) if vol_avg > 0 else False
            
            p5 = float(df['Close'].iloc[-6]) if len(df) >= 6 else float(df['Close'].iloc[0])
            roc_val = ((cmp - p5) / p5) * 100
            
            trade = st.session_state.dual_trades[strategy_key].get(symbol)
            
            # Allow active trades to continue monitoring even if ROC temporarily cools off
            if not trade and not (filter_roc_min <= abs(roc_val) <= filter_roc_max):
                continue

            # --- FLEX CONFIRMATION NODES ---
            flex_score = 0
            sigs = []

            ema9 = float(df['Close'].ewm(span=9).mean().iloc[-1])
            ema21 = float(df['Close'].ewm(span=21).mean().iloc[-1])
            if (not is_reversed and cmp > ema9 > ema21) or (is_reversed and cmp < ema9 < ema21):
                flex_score += 1
                sigs.append("✓EMA")

            high, low, close = df['High'], df['Low'], df['Close']
            prev_close = close.shift(1)
            tr = np.nanmax(np.column_stack([(high - low), np.abs(high - prev_close), np.abs(low - prev_close)]), axis=1)
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            tr_s = pd.Series(tr).rolling(14).sum()
            p_di = 100 * (pd.Series(plus_dm).rolling(14).sum() / np.where(tr_s == 0, 1e-9, tr_s))
            m_di = 100 * (pd.Series(minus_dm).rolling(14).sum() / np.where(tr_s == 0, 1e-9, tr_s))
            adx = float(100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di))).rolling(14).mean().iloc[-1])
            
            if adx > 20.0:
                flex_score += 1
                sigs.append(f"ADX:{adx:.0f}")

            if vol_surge:
                flex_score += 1
                sigs.append(f"⚡Vol({curr_vol / vol_avg:.1f}x)")

            y = df['Close'].tail(14).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            if (not is_reversed and slope > 0) or (is_reversed and slope < 0):
                flex_score += 1
                sigs.append(f"LRC:{'UP' if slope > 0 else 'DN'}")

            confidence_label = "⭐" * flex_score if flex_score > 0 else "⚪ Low"

            # --- MULTI-CYCLE TRADE STATE MACHINE ---
            e_time = ist_now.strftime("%H:%M")
            status = "WAITING"
            t_type = None
            pos_num = 1
            t_hits = 0
            s_hits = 0

            if trade:
                t_hits = trade.get('t_hits', 0)
                s_hits = trade.get('s_hits', 0)
                pos_num = trade.get('pos_num', 1)
                t_type = trade.get('type')
                e_time = trade.get('time', e_time)
                active_state = trade.get('active', True)

                if active_state:
                    hit_event = None
                    if t_type == 'BUY':
                        if cmp >= trade['target']:
                            t_hits += 1
                            hit_event = "TARGET"
                        elif cmp <= trade['sl']:
                            s_hits += 1
                            hit_event = "SL"
                    elif t_type == 'SELL':
                        if cmp <= trade['target']:
                            t_hits += 1
                            hit_event = "TARGET"
                        elif cmp >= trade['sl']:
                            s_hits += 1
                            hit_event = "SL"

                    if hit_event:
                        # Record hit & advance to next position cycle
                        next_pos = pos_num + 1
                        # Re-enter immediately if momentum & volume criteria still hold, else queue next cycle
                        if vol_surge and (filter_roc_min <= abs(roc_val) <= filter_roc_max):
                            new_dir = ("BUY" if cmp > c_open else "SELL") if not is_reversed else ("SELL" if cmp > c_open else "BUY")
                            new_entry = cmp
                            new_target = new_entry * (1 + target_pct) if new_dir == "BUY" else new_entry * (1 - target_pct)
                            new_sl = new_entry * (1 - sl_pct) if new_dir == "BUY" else new_entry * (1 + sl_pct)
                            
                            st.session_state.dual_trades[strategy_key][symbol] = {
                                'entry': new_entry, 'target': new_target, 'sl': new_sl,
                                'type': new_dir, 'time': e_time, 'score': flex_score,
                                't_hits': t_hits, 's_hits': s_hits, 'pos_num': next_pos,
                                'active': True, 'last_event': f"{'🎯T' if hit_event=='TARGET' else '🛑S'}{t_hits if hit_event=='TARGET' else s_hits}"
                            }
                            trade = st.session_state.dual_trades[strategy_key][symbol]
                            t_type = new_dir
                            pos_num = next_pos
                            status = f"T{t_hits} S{s_hits} | 🔄 IN TRADE (Pos #{pos_num})"
                        else:
                            # Mark hit and await next trigger for Position #next_pos
                            st.session_state.dual_trades[strategy_key][symbol].update({
                                't_hits': t_hits, 's_hits': s_hits, 'pos_num': next_pos,
                                'active': False, 'last_event': hit_event
                            })
                            trade = st.session_state.dual_trades[strategy_key][symbol]
                            pos_num = next_pos
                            hit_tag = f"🎯 T{t_hits} HIT" if hit_event == "TARGET" else f"🛑 S{s_hits} HIT"
                            status = f"T{t_hits} S{s_hits} | {hit_tag} → Ready Pos #{pos_num}"
                        trades_updated = True
                    else:
                        status = f"T{t_hits} S{s_hits} | IN TRADE"
                else:
                    # Completed prior cycle; check for fresh trigger for Pos #2, #3, etc.
                    if vol_surge and (filter_roc_min <= abs(roc_val) <= filter_roc_max):
                        new_dir = ("BUY" if cmp > c_open else "SELL") if not is_reversed else ("SELL" if cmp > c_open else "BUY")
                        new_entry = cmp
                        new_target = new_entry * (1 + target_pct) if new_dir == "BUY" else new_entry * (1 - target_pct)
                        new_sl = new_entry * (1 - sl_pct) if new_dir == "BUY" else new_entry * (1 + sl_pct)
                        
                        st.session_state.dual_trades[strategy_key][symbol] = {
                            'entry': new_entry, 'target': new_target, 'sl': new_sl,
                            'type': new_dir, 'time': e_time, 'score': flex_score,
                            't_hits': t_hits, 's_hits': s_hits, 'pos_num': pos_num,
                            'active': True
                        }
                        trade = st.session_state.dual_trades[strategy_key][symbol]
                        t_type = new_dir
                        status = f"T{t_hits} S{s_hits} | IN TRADE (Pos #{pos_num})"
                        trades_updated = True
                    else:
                        last_ev = trade.get('last_event', 'TARGET')
                        hit_tag = f"🎯 T{t_hits} HIT" if last_ev == "TARGET" else f"🛑 S{s_hits} HIT"
                        status = f"T{t_hits} S{s_hits} | {hit_tag} (Next: Pos #{pos_num})"

            elif vol_surge:
                # First cycle entry (Pos #1)
                t_type = ("BUY" if cmp > c_open else "SELL") if not is_reversed else ("SELL" if cmp > c_open else "BUY")
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                
                st.session_state.dual_trades[strategy_key][symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type,
                    'time': e_time, 'score': flex_score, 't_hits': 0, 's_hits': 0,
                    'pos_num': 1, 'active': True
                }
                trade = st.session_state.dual_trades[strategy_key][symbol]
                status = "T0 S0 | IN TRADE"
                trades_updated = True

            # --- SIDEBAR STATUS FILTERING ---
            if filter_status != "All":
                if filter_status == "In Trade" and "IN TRADE" not in status:
                    continue
                if filter_status == "Target Hit" and "T0" in status and "TARGET" not in status:
                    continue
                if filter_status == "SL Hit" and "S0" in status and "SL" not in status:
                    continue
                if filter_status == "Multi-Cycle (Pos 2+)" and pos_num < 2:
                    continue
                if filter_status == "Waiting" and status != "WAITING":
                    continue

            is_active_row = 1 if (trade and trade.get('active', False)) else (0.5 if trade else 0)

            results.append({
                "Stock": f"⚡ {symbol}",
                "Pos #": f"#{pos_num}",
                "T/S": f"T{t_hits} | S{s_hits}",
                "Trade": f"{'🟢' if t_type=='BUY' else '🔴'} {t_type}" if t_type else "⏳ Ready",
                "Qty": int(capital // cmp),
                "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "Confidence": confidence_label,
                "Signal Details": " | ".join(sigs) if sigs else "Core Trigger",
                "Status": status,
                "Time": e_time,
                "SortRank": is_active_row,
                "ROC_Val": abs(roc_val)
            })
        except Exception:
            continue

    if trades_updated:
        save_persistent_trades(st.session_state.dual_trades)

    if not results:
        return pd.DataFrame()
    return (
        pd.DataFrame(results)
        .sort_values(by=["SortRank", "ROC_Val"], ascending=False)
        .drop(columns=["SortRank", "ROC_Val"])
    )

# --- FETCH & PROCESS ---
tickers_tuple = tuple(f"{s}.NS" for s in SYMBOLS)
raw_market_data = fetch_market_batch(tickers_tuple)

def apply_dynamic_styles(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        st_str = str(row['Status'])
        if "IN TRADE" in st_str or "HIT" in st_str:
            is_buy = "BUY" in str(row['Trade'])
            row_bg = '#dcfce7' if is_buy else '#fee2e2'
            styles.loc[i, :] = f'background-color: {row_bg}; color: #111827; font-weight: 500'
            cmp_bg = '#15803d' if (is_buy and row['CMP'] >= row['Entry']) or (not is_buy and row['CMP'] <= row['Entry']) else '#b91c1c'
            styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
            if row['Pos #'] != "#1":
                styles.loc[i, 'Pos #'] = 'background-color: #dbeafe; color: #1e40af; font-weight: bold'
    return styles

columns_show = ["Stock", "Pos #", "T/S", "Trade", "Entry", "CMP", "SL", "Target", "Status", "Confidence", "Signal Details", "Time", "Qty"]

df_reg = process_core_flex_strategy(raw_market_data, is_reversed=False) if not raw_market_data.empty else pd.DataFrame()
df_rev = process_core_flex_strategy(raw_market_data, is_reversed=True) if not raw_market_data.empty else pd.DataFrame()

# --- DISPLAY INTERFACE ---
st.subheader("🪟 Active & Multi-Cycle Trade Window")

active_reg = df_reg[df_reg['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)].copy() if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[df_rev['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)].copy() if not df_rev.empty else pd.DataFrame()

if not active_reg.empty:
    active_reg["Stock"] = active_reg["Stock"] + " (REG)"
if not active_rev.empty:
    active_rev["Stock"] = active_rev["Stock"] + " (REV)"

if not active_reg.empty or not active_rev.empty:
    comb = pd.concat([active_reg, active_rev], ignore_index=True)
    st.dataframe(
        comb.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"
        }),
        use_container_width=True,
        hide_index=True,
        column_order=columns_show,
        height=240
    )
else:
    st.info("No active or completed trade cycles yet.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Regular Monitor")
    if not df_reg.empty:
        st.dataframe(
            df_reg.style.apply(apply_dynamic_styles, axis=None).format({
                "CMP": "{:.2f}",
                "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
                "Target": lambda x: f"{x:.2f}" if x > 0 else "-",
                "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
            }),
            use_container_width=True,
            hide_index=True,
            column_order=columns_show,
            height=460
        )
    else:
        st.caption("No tickers match standard filters right now.")

with col2:
    st.subheader("🔄 Reversed Monitor")
    if not df_rev.empty:
        st.dataframe(
            df_rev.style.apply(apply_dynamic_styles, axis=None).format({
                "CMP": "{:.2f}",
                "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
                "Target": lambda x: f"{x:.2f}" if x > 0 else "-",
                "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
            }),
            use_container_width=True,
            hide_index=True,
            column_order=columns_show,
            height=460
        )
    else:
        st.caption("No tickers match reversal filters right now.")

# --- NON-BLOCKING AUTO-REFRESH ---
time.sleep(refresh_sec if open_status else 180)
st.rerun()
