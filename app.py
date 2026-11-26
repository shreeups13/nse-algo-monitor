# NSE Pro Monitor v6.0 - Adaptive Best-Fit Model & Target Engine
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v6.0 (Best-Fit Engine)", layout="wide", page_icon="⚡")

TRADES_FILE = "trade_history_bestfit_v60.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                data = json.load(f)
                if "active" in data:
                    return data
        except Exception:
            pass
    return {"active": {}}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

# --- MARKET CALENDAR 2026 (Updated with Jan 15 Election Holiday) ---
NSE_HOLIDAYS = [
    date(2026, 1, 15), date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26),
    date(2026, 3, 31), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1),
    date(2026, 5, 28), date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2),
    date(2026, 10, 20), date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25)
]

def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_open():
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now <= end_time:
        return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

if 'bestfit_trades' not in st.session_state:
    st.session_state.bestfit_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Execution & Risk Settings")
    capital = st.number_input("Capital per Trade (₹)", min_value=1000, value=5000, step=1000)
    base_target_pct = st.slider("Baseline Target Floor (%)", 0.5, 5.0, 1.2, step=0.1) / 100
    rr_t1 = st.slider("Target 1 R:R Multiplier (Auto-BE)", 1.5, 3.0, 2.0, step=0.1)
    rr_t2 = st.slider("Target 2 R:R Multiplier (Final)", 2.5, 5.0, 3.5, step=0.1)
    sl_atr_mult = st.slider("Structural SL Buffer (ATR Mult)", 0.5, 2.5, 1.0, step=0.1)
    
    st.markdown("---")
    st.subheader("🧠 Best-Fit Model Thresholds")
    vol_multiplier = st.slider("Min Volume Surge vs MA(20)", 1.0, 3.0, 1.5, step=0.05)
    min_r2_trend = st.slider("Trend Model Min R² Linearity", 0.30, 0.85, 0.55, step=0.05)
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0)
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=2000.0, step=100.0)
    
    st.markdown("**📈 ROC Velocity Filter (%)**")
    filter_roc_min = st.number_input("ROC Min", value=0.80, step=0.05)
    filter_roc_max = st.number_input("ROC Max", value=6.00, step=0.05)
    
    filter_model = st.selectbox("Model Filter", ["All Models", "Trend Breakout", "Demand BOS", "Mean Reversion"])
    filter_status = st.selectbox("Status Filter", ["All", "In Trade", "T1 Hit (BE)", "Target Hit", "SL Hit", "Waiting"])
    
    st.markdown("---")
    full_list = "KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.bestfit_trades = {"active": {}}
        if os.path.exists(TRADES_FILE):
            os.remove(TRADES_FILE)
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

# --- BEST-FIT MODEL & TARGET ANALYZER ---
def evaluate_stock_best_fit(df):
    """
    Analyzes a stock's 5m + resampled 15m/1H structure to select the optimal model,
    structural Stop Loss, and multi-tier Targets (T1 & T2).
    """
    cmp = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    curr_open = float(df['Open'].iloc[-1])
    curr_high = float(df['High'].iloc[-1])
    curr_low = float(df['Low'].iloc[-1])

    # 1. Volatility & ATR Expansion Check (14-bar ATR vs 30-bar Mean ATR)
    high, low, close = df['High'], df['Low'], df['Close']
    tr = np.maximum((high - low), np.maximum(np.abs(high - close.shift(1)), np.abs(low - close.shift(1))))
    atr_series = tr.rolling(14).mean()
    atr_14 = float(atr_series.iloc[-1])
    atr_30_avg = float(atr_series.rolling(30).mean().iloc[-1]) if len(df) >= 45 else atr_14
    vol_expanding = atr_14 > atr_30_avg

    # 2. Volume Surge
    vol_avg = float(df['Volume'].rolling(20).mean().iloc[-1])
    vol_ratio = float(df['Volume'].iloc[-1] / vol_avg) if vol_avg > 0 else 0.0
    vol_surge = vol_ratio >= vol_multiplier

    # 3. ROC Velocity (10-bar)
    p10 = float(df['Close'].iloc[-11]) if len(df) >= 11 else float(df['Close'].iloc[0])
    roc_val = ((cmp - p10) / p10) * 100

    # 4. EMA Stack (5m + 15m Resampled Structural Trend)
    ema9 = float(close.ewm(span=9).mean().iloc[-1])
    ema21 = float(close.ewm(span=21).mean().iloc[-1])
    ema50 = float(close.ewm(span=50).mean().iloc[-1]) if len(df) >= 50 else ema21
    
    # 15-min resampled 20 EMA for trailing exit
    df_15m = df.resample('15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    ema20_15m = float(df_15m['Close'].ewm(span=20).mean().iloc[-1]) if len(df_15m) >= 5 else ema21

    # 5. Linear Regression Slope & R-Squared (Trend Linearity Fit)
    window = min(20, len(df))
    y = close.tail(window).values
    x = np.arange(window)
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # 6. Structural Swing High / Low & Order Block Equilibrium (last 24 bars = 2 hours)
    lookback = df.iloc[-25:-1]
    swing_low = float(lookback['Low'].min())
    swing_high = float(lookback['High'].max())
    
    # Demand Zone Equilibrium (bottom 35% of range -> top 50% of demand zone)
    zone_span = swing_high - swing_low
    demand_top = swing_low + (0.35 * zone_span)
    demand_eq = swing_low + (0.175 * zone_span)
    supply_bottom = swing_high - (0.35 * zone_span)
    supply_eq = swing_high - (0.175 * zone_span)

    # Micro Break of Structure (BOS) on 5m
    bull_bos = (cmp > prev_close) and (cmp > curr_open) and (float(df['Low'].iloc[-2]) <= demand_top)
    bear_bos = (cmp < prev_close) and (cmp < curr_open) and (float(df['High'].iloc[-2]) >= supply_bottom)

    # 7. Bollinger Band / VWAP Extension for Mean Reversion Fit
    sma20 = float(close.rolling(20).mean().iloc[-1])
    std20 = float(close.rolling(20).std().iloc[-1])
    z_score = (cmp - sma20) / std20 if std20 > 0 else 0.0

    # --- BEST-FIT MODEL CLASSIFICATION ---
    model_name = "Unassigned"
    direction = None
    fit_score = 0
    rationale = []

    bull_stack = cmp > ema9 > ema21 > ema50
    bear_stack = cmp < ema9 < ema21 < ema50

    # Model A: Trend Breakout (High R² linearity + EMA Stack + Vol Surge)
    if r_squared >= min_r2_trend and (bull_stack or bear_stack) and vol_surge:
        model_name = "Trend Breakout"
        direction = "BUY" if bull_stack else "SELL"
        fit_score = min(5, int(round(r_squared * 3)) + (1 if vol_expanding else 0) + 1)
        rationale.append(f"R²:{r_squared:.2f}")
        rationale.append(f"Vol:{vol_ratio:.1f}x")
        if vol_expanding:
            rationale.append("ATR↑")

    # Model B: Demand/Supply BOS (Pullback into Equilibrium + Micro BOS + HTF Bias)
    elif (bull_bos and cmp > ema50) or (bear_bos and cmp < ema50):
        model_name = "Demand BOS"
        direction = "BUY" if bull_bos else "SELL"
        fit_score = 4 if vol_surge else 3
        rationale.append("Zone EQ Pullback")
        rationale.append("5m BOS")
        if vol_surge:
            rationale.append(f"Vol:{vol_ratio:.1f}x")

    # Model C: Mean Reversion (Low R² chop/exhaustion + Z-Score > 2.1 extension)
    elif r_squared < 0.40 and abs(z_score) >= 2.1 and vol_surge:
        model_name = "Mean Reversion"
        direction = "SELL" if z_score > 0 else "BUY"
        fit_score = 3 if abs(z_score) >= 2.5 else 2
        rationale.append(f"Z:{z_score:+.1f}σ")
        rationale.append(f"R²:{r_squared:.2f} (Chop)")

    # --- DYNAMIC TARGET & STOP LOSS CALCULATION ---
    if direction == "BUY":
        # Structural SL below Demand Zone Low or Swing Low minus ATR buffer
        struct_sl = min(swing_low, curr_low) - (sl_atr_mult * atr_14 * 0.5)
        # Cap maximum risk to 1.5 * ATR to prevent overly wide stops
        sl = max(struct_sl, cmp - (1.5 * atr_14))
        risk = max(cmp - sl, cmp * 0.003)  # Minimum 0.3% risk floor
        
        # Target 1: Max of Baseline Floor or 1:2 R:R
        t1_rr = cmp + (risk * rr_t1)
        t1_floor = cmp * (1 + base_target_pct)
        t1 = max(t1_rr, t1_floor)
        
        # Target 2: Blend of 1:3.5 R:R and Prior Structural Swing High
        t2_rr = cmp + (risk * rr_t2)
        t2 = max(t2_rr, swing_high) if swing_high > t1 else t2_rr
        
        expected_hit_prob = min(92, int(52 + (fit_score * 6) + (5 if vol_expanding else 0) + (4 if r_squared > 0.6 else 0)))

    elif direction == "SELL":
        struct_sl = max(swing_high, curr_high) + (sl_atr_mult * atr_14 * 0.5)
        sl = min(struct_sl, cmp + (1.5 * atr_14))
        risk = max(sl - cmp, cmp * 0.003)
        
        t1_rr = cmp - (risk * rr_t1)
        t1_floor = cmp * (1 - base_target_pct)
        t1 = min(t1_rr, t1_floor)
        
        t2_rr = cmp - (risk * rr_t2)
        t2 = min(t2_rr, swing_low) if swing_low < t1 else t2_rr
        
        expected_hit_prob = min(92, int(52 + (fit_score * 6) + (5 if vol_expanding else 0) + (4 if r_squared > 0.6 else 0)))
    else:
        sl, t1, t2, expected_hit_prob = 0.0, 0.0, 0.0, 0

    return {
        "cmp": cmp,
        "roc_val": roc_val,
        "model": model_name,
        "direction": direction,
        "fit_score": fit_score,
        "hit_prob": expected_hit_prob,
        "sl": sl,
        "t1": t1,
        "t2": t2,
        "ema20_15m": ema20_15m,
        "r2": r_squared,
        "rationale": " | ".join(rationale) if rationale else "Scanning Structure"
    }

# --- MAIN STRATEGY ENGINE ---
def process_best_fit_engine(data):
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return pd.DataFrame()
    
    results = []
    actual_present_tickers = set([col[0] for col in data.columns])
    state_changed = False

    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in actual_present_tickers:
            continue

        try:
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low', 'Volume'])
            if len(df) < 35:
                continue

            analysis = evaluate_stock_best_fit(df)
            cmp = analysis["cmp"]
            roc_val = analysis["roc_val"]

            if cmp < filter_min_price or cmp > filter_max_price:
                continue

            existing_trade = st.session_state.bestfit_trades["active"].get(symbol)
            
            # Allow existing active trades even if ROC cools down; filter new entries by ROC
            if not existing_trade and not (filter_roc_min <= abs(roc_val) <= filter_roc_max):
                continue

            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")

            if existing_trade:
                t_type = existing_trade["type"]
                entry = existing_trade["entry"]
                sl = existing_trade["sl"]
                t1 = existing_trade["t1"]
                t2 = existing_trade["t2"]
                model_used = existing_trade["model"]
                fit_score = existing_trade["fit_score"]
                hit_prob = existing_trade["hit_prob"]
                rationale = existing_trade["rationale"]
                e_time = existing_trade.get("time", e_time)
                t1_reached = existing_trade.get("t1_reached", False)

                if t_type == "BUY":
                    if cmp >= t2:
                        status = "🏆 T2 TARGET HIT"
                    elif cmp <= sl:
                        status = "🛑 SL HIT" if not t1_reached else "🛡️ BE EXIT"
                    else:
                        if cmp >= t1 and not t1_reached:
                            # Auto-move SL to Break-Even upon T1 hit
                            sl = entry
                            existing_trade["sl"] = sl
                            existing_trade["t1_reached"] = True
                            t1_reached = True
                            state_changed = True
                        # Trail SL along 15m 20-EMA once T1 is hit
                        if t1_reached and analysis["ema20_15m"] > sl:
                            sl = analysis["ema20_15m"]
                            existing_trade["sl"] = sl
                            state_changed = True
                        status = "🎯 T1 HIT (BE)" if t1_reached else "IN TRADE"

                elif t_type == "SELL":
                    if cmp <= t2:
                        status = "🏆 T2 TARGET HIT"
                    elif cmp >= sl:
                        status = "🛑 SL HIT" if not t1_reached else "🛡️ BE EXIT"
                    else:
                        if cmp <= t1 and not t1_reached:
                            sl = entry
                            existing_trade["sl"] = sl
                            existing_trade["t1_reached"] = True
                            t1_reached = True
                            state_changed = True
                        if t1_reached and analysis["ema20_15m"] < sl:
                            sl = analysis["ema20_15m"]
                            existing_trade["sl"] = sl
                            state_changed = True
                        status = "🎯 T1 HIT (BE)" if t1_reached else "IN TRADE"

            else:
                model_used = analysis["model"]
                t_type = analysis["direction"]
                fit_score = analysis["fit_score"]
                hit_prob = analysis["hit_prob"]
                rationale = analysis["rationale"]
                entry, sl, t1, t2 = 0.0, analysis["sl"], analysis["t1"], analysis["t2"]

                # Execute Auto-Entry if Best-Fit Model confirms high-probability setup (score >= 3)
                if t_type in ("BUY", "SELL") and fit_score >= 3:
                    entry = cmp
                    status = "IN TRADE"
                    st.session_state.bestfit_trades["active"][symbol] = {
                        "type": t_type,
                        "model": model_used,
                        "entry": entry,
                        "sl": sl,
                        "t1": t1,
                        "t2": t2,
                        "fit_score": fit_score,
                        "hit_prob": hit_prob,
                        "rationale": rationale,
                        "time": e_time,
                        "t1_reached": False
                    }
                    state_changed = True

            # Apply Sidebar Filters
            if filter_model != "All Models" and model_used != filter_model:
                continue
            if filter_status != "All":
                if filter_status == "In Trade" and status != "IN TRADE": continue
                if filter_status == "T1 Hit (BE)" and "T1 HIT" not in status: continue
                if filter_status == "Target Hit" and "TARGET HIT" not in status: continue
                if filter_status == "SL Hit" and "SL HIT" not in status: continue
                if filter_status == "Waiting" and status != "WAITING": continue

            t1_pct = ((abs(t1 - (entry if entry > 0 else cmp)) / (entry if entry > 0 else cmp)) * 100) if t1 > 0 else 0.0

            results.append({
                "Stock": f"⚡ {symbol}",
                "Best-Fit Model": model_used,
                "Trade": f"{'🟢' if t_type=='BUY' else '🔴'} {t_type}" if t_type else "⏳ Scan",
                "Fit Score": "⭐" * fit_score if fit_score > 0 else "⚪",
                "Hit Prob": f"{hit_prob}%" if hit_prob > 0 else "-",
                "Entry": entry,
                "CMP": cmp,
                "SL (Trail)": sl,
                "T1 (BE)": t1,
                "T2 (Max)": t2,
                "T1 Gain%": f"+{t1_pct:.2f}%" if t1_pct > 0 else "-",
                "Model Metrics": rationale,
                "Status": status,
                "Time": e_time,
                "Qty": int(capital // cmp) if cmp > 0 else 0,
                "SortRank": 2 if "IN TRADE" in status or "T1 HIT" in status else (1 if "HIT" in status else 0),
                "ProbVal": hit_prob
            })
        except Exception:
            continue

    if state_changed:
        save_persistent_trades(st.session_state.bestfit_trades)

    if not results:
        return pd.DataFrame()
    return (
        pd.DataFrame(results)
        .sort_values(by=["SortRank", "ProbVal"], ascending=False)
        .drop(columns=["SortRank", "ProbVal"])
    )

# --- EXECUTION FETCH ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except Exception:
    raw_market_data = pd.DataFrame()

def apply_dynamic_styles(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        st_val = str(row['Status'])
        if any(k in st_val for k in ["IN TRADE", "T1 HIT", "TARGET HIT", "SL HIT", "BE EXIT"]):
            row_bg = '#c6f6d5' if "BUY" in str(row['Trade']) else '#fed7d7'
            styles.loc[i, :] = f'background-color: {row_bg}; color: black; font-weight: 500'
            is_buy = "BUY" in str(row['Trade'])
            cmp_bg = '#1a8a44' if (is_buy and row['CMP'] >= row['Entry']) or (not is_buy and row['CMP'] <= row['Entry']) else '#c53030'
            styles.loc[i, 'CMP'] = f'background-color: {cmp_bg}; color: white; font-weight: bold'
    return styles

columns_show = [
    "Stock", "Best-Fit Model", "Trade", "Fit Score", "Hit Prob",
    "Entry", "CMP", "SL (Trail)", "T1 (BE)", "T2 (Max)", "T1 Gain%",
    "Model Metrics", "Status", "Time", "Qty"
]

df_master = process_best_fit_engine(raw_market_data) if not raw_market_data.empty else pd.DataFrame()

# --- DISPLAY INTERFACE ---
st.markdown("---")
st.header("🪟 Active Best-Fit Executions")

if not df_master.empty:
    active_df = df_master[df_master['Status'].str.contains("IN TRADE|HIT|EXIT", regex=True, na=False)]
    if not active_df.empty:
        st.dataframe(
            active_df.style.apply(apply_dynamic_styles, axis=None).format({
                "CMP": "{:.2f}", "Entry": "{:.2f}", "SL (Trail)": "{:.2f}",
                "T1 (BE)": "{:.2f}", "T2 (Max)": "{:.2f}"
            }),
            use_container_width=True, hide_index=True, column_order=columns_show
        )
    else:
        st.info("No active open positions currently. Engine is scanning for Best-Fit setups.")

    st.markdown("---")
    st.subheader("📊 Watchlist Best-Fit Model Matrix & Projected Targets")
    st.dataframe(
        df_master.style.apply(apply_dynamic_styles, axis=None).format({
            "CMP": "{:.2f}",
            "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
            "SL (Trail)": lambda x: f"{x:.2f}" if x > 0 else "-",
            "T1 (BE)": lambda x: f"{x:.2f}" if x > 0 else "-",
            "T2 (Max)": lambda x: f"{x:.2f}" if x > 0 else "-"
        }),
        use_container_width=True, hide_index=True, column_order=columns_show
    )
else:
    st.warning("No stocks matched the current Best-Fit velocity and price filters.")

time.sleep(60 if open_status else 300)
st.rerun()
