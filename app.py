# #NSE Pro Monitor v5.1 - Core + Flex Momentum Engine
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.1 (Core+Flex)", layout="wide", page_icon="⚡")

TRADES_FILE = "trade_history_dual_v51.json"

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

if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Execution Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("⚡ Core Entry Controls")
    vol_multiplier = st.slider("Min Volume Surge vs MA(10)", 1.0, 2.5, 1.15, step=0.05)
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0)
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=1000.0, step=100.0)
    
    st.markdown("**📈 ROC Velocity Filter (%)**")
    filter_roc_min = st.number_input("ROC Min", value=0.50, step=0.01)
    filter_roc_max = st.number_input("ROC Max", value=5.00, step=0.01)
    
    filter_status = st.selectbox("Status Filter", ["All", "In Trade", "Target Hit", "SL Hit", "Waiting"])
    
    st.markdown("---")
    full_list = "KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER ---
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

# --- CORE STRATEGY CALCULATIONS ---
def process_core_flex_strategy(data, is_reversed=False):
    if data.empty or not isinstance(data.columns, pd.MultiIndex): return pd.DataFrame()
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    actual_present_tickers = set([col[0] for col in data.columns])
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in actual_present_tickers: continue
        
        try:
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
            if len(df) < 25: continue

            cmp = float(df['Close'].iloc[-1])
            c_open = float(df['Open'].iloc[-1])
            
            if cmp < filter_min_price or cmp > filter_max_price: continue

            # --- CORE TRIGGER (PRICE ACTION + VOLUME EXPANSION) ---
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] >= (vol_avg * vol_multiplier)
            
            p5 = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
            roc_val = ((cmp - p5) / p5) * 100
            
            if not (filter_roc_min <= abs(roc_val) <= filter_roc_max): continue

            # --- FLEX CONFIRMATION NODES (CALCULATE WEIGHTED SCORE) ---
            flex_score = 0
            sigs = []

            # Flex Node 1: Moving Average Trend Alignment
            ema9 = df['Close'].ewm(span=9).mean().iloc[-1]
            ema21 = df['Close'].ewm(span=21).mean().iloc[-1]
            if (not is_reversed and cmp > ema9 > ema21) or (is_reversed and cmp < ema9 < ema21):
                flex_score += 1
                sigs.append("✓EMA Alignment")

            # Flex Node 2: Trend Strength (ADX)
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
                sigs.append(f"ADX:{adx:.1f}")

            # Flex Node 3: Volume Surge Magnitude
            if vol_surge:
                flex_score += 1
                sigs.append(f"⚡Vol({df['Volume'].iloc[-1] / vol_avg:.1f}x)")

            # Flex Node 4: Linear Regression Channel (LRC Slope)
            y = df['Close'].tail(14).values
            slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            if (not is_reversed and slope > 0) or (is_reversed and slope < 0):
                flex_score += 1
                sigs.append(f"LRC:{lrc_dir}")

            confidence_label = "⭐" * flex_score if flex_score > 0 else "⚪ Low"

            # --- TRADE STATE MONITORING ---
            trade = st.session_state.dual_trades[strategy_key].get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            t_type = trade.get('type') if trade else None

            if trade:
                status = "IN TRADE"
                e_time = trade.get('time', e_time)
                if trade['type'] == 'BUY':
                    if cmp >= trade['target']: status = "🎯 TARGET HIT"
                    elif cmp <= trade['sl']: status = "🛑 SL HIT"
                elif trade['type'] == 'SELL':
                    if cmp <= trade['target']: status = "🎯 TARGET HIT"
                    elif cmp >= trade['sl']: status = "🛑 SL HIT"
            elif vol_surge: # Core entry condition met
                if not is_reversed:
                    t_type = "BUY" if cmp > c_open else "SELL"
                else:
                    t_type = "SELL" if cmp > c_open else "BUY"
                
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                
                st.session_state.dual_trades[strategy_key][symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': e_time, 'score': flex_score
                }
                save_persistent_trades(st.session_state.dual_trades)

            if filter_status != "All":
                if filter_status == "In Trade" and "IN TRADE" not in status: continue
                if filter_status == "Target Hit" and "TARGET HIT" not in status: continue
                if filter_status == "SL Hit" and "SL HIT" not in status: continue
                if filter_status == "Waiting" and status != "WAITING": continue

            results.append({
                "Stock": f"⚡ {symbol}", "Trade": f"{'🟢' if t_type=='BUY' else '🔴'} {t_type}" if t_type else "⏳ Ready",
                "Qty": int(capital // cmp), "CMP": cmp, "Entry": trade['entry'] if trade else 0.0,
                "SL": trade['sl'] if trade else 0.0, "Target": trade['target'] if trade else 0.0,
                "Confidence": confidence_label, "Signal Details": " | ".join(sigs) if sigs else "Core Trigger Only",
                "Status": status, "Time": e_time, "InTrade": 1 if trade else 0, "ROC_Val": abs(roc_val)
            })
        except Exception:
            continue
            
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])

# --- EXECUTION FETCH ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except Exception:
    raw_market_data = pd.DataFrame()

def apply_dynamic_styles(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        if "IN TRADE" in str(row['Status']) or "HIT" in str(row['Status']):
            row_bg = '#c6f6d5' if "BUY" in str(row['Trade']) else '#fed7d7'
            styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
            is_buy = "BUY" in str(row['Trade'])
            cmp_bg = '#1a8a44' if (is_buy and row['CMP'] >= row['Entry']) or (not is_buy and row['CMP'] <= row['Entry']) else '#c53030'
            styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
    return styles

columns_show = ["Stock", "Trade", "Qty", "Entry","CMP", "Confidence", "Signal Details", "SL", "Target", "Status", "Time"]

df_reg = process_core_flex_strategy(raw_market_data, is_reversed=False) if not raw_market_data.empty else pd.DataFrame()
df_rev = process_core_flex_strategy(raw_market_data, is_reversed=True) if not raw_market_data.empty else pd.DataFrame()

# --- DISPLAY INTERFACE ---
st.markdown("---")
st.header("🪟 Active Trade Window")

active_reg = df_reg[df_reg['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[df_rev['Status'].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_rev.empty else pd.DataFrame()

if not active_reg.empty or not active_rev.empty:
    comb = pd.concat([active_reg, active_rev], ignore_index=True).drop_duplicates(subset=["Stock"])
    st.dataframe(comb.style.apply(apply_dynamic_styles, axis=None).format({"CMP": "{:.2f}", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"}), use_container_width=True, hide_index=True, column_order=columns_show)
else:
    st.info("No active open positions currently.")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Regular Monitor")
    if not df_reg.empty:
        st.dataframe(df_reg.style.apply(apply_dynamic_styles, axis=None).format({"CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-", "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"}), use_container_width=True, hide_index=True, column_order=columns_show)
    else:
        st.caption("No tickers match standard filters right now.")

with col2:
    st.subheader("🔄 Reversed Monitor")
    if not df_rev.empty:
        st.dataframe(df_rev.style.apply(apply_dynamic_styles, axis=None).format({"CMP": "{:.2f}", "Entry": lambda x: f"{x:.2f}" if x > 0 else "-", "Target": lambda x: f"{x:.2f}" if x > 0 else "-", "SL": lambda x: f"{x:.2f}" if x > 0 else "-"}), use_container_width=True, hide_index=True, column_order=columns_show)
    else:
        st.caption("No tickers match reversal filters right now.")

time.sleep(60 if open_status else 300)
st.rerun()
