import json
import os
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# --- CONFIGURATION ---
st.set_page_config(
    page_title="NSE Pro Monitor v5.3 (VWAP + ATR + Model Fit)",
    layout="wide",
    page_icon="⚡",
)

TRADES_FILE = "trade_history_dual_v53.json"


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
        json.dump(trades, f)


# --- MARKET CALENDAR 2026 ---
NSE_HOLIDAYS = {
    date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28),
    date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25),
}


def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def is_market_open(now_ist):
    if now_ist.weekday() >= 5 or now_ist.date() in NSE_HOLIDAYS:
        return False, "🔴 MARKET CLOSED (WEEKEND/HOLIDAY)"
    start_time = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    end_time = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    if start_time <= now_ist <= end_time:
        return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"


def compute_intraday_vwap(df: pd.DataFrame) -> pd.Series:
    """Computes cumulative VWAP per trading session."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    tp_vol = typical_price * df["Volume"]
    session_date = df.index.date
    cum_tp_vol = tp_vol.groupby(session_date).cumsum()
    cum_vol = df["Volume"].groupby(session_date).cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol


def classify_model_fit(vol_ratio: float, vwap_aligned: bool, trend_aligned: bool, roc_abs: float) -> str:
    """Maps current bar dynamics to the closest low-latency intraday archetype."""
    if vol_ratio >= 1.8 and roc_abs >= 1.2 and vwap_aligned:
        return "1. Zero-Lag Breakout"
    if vwap_aligned and trend_aligned:
        return "2. VWAP + Trend/Kalman"
    return "5. Adaptive / LRC"


if "dual_trades" not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Execution Settings")
    capital = st.number_input("Capital (₹)", min_value=1000, value=5000, step=1000)
    target_pct = st.slider("Target (%)", 0.3, 5.0, 1.2, step=0.1) / 100.0
    sl_atr_mult = st.slider("Stop Loss ATR Multiplier", 0.5, 3.0, 1.5, step=0.1)
    min_atr_target_ratio = st.slider("Min (ATR% / Target%) Room", 0.2, 2.0, 0.5, step=0.1)
    require_vwap_alignment = st.checkbox("Require VWAP Alignment for New Entry", value=True)

    st.markdown("---")
    st.subheader("⚡ Core Entry Controls")
    vol_multiplier = st.slider("Min Volume Surge vs MA(20)", 1.0, 3.0, 1.5, step=0.05)
    filter_min_price = st.number_input("Min Stock Price (₹)", min_value=0.0, value=30.0, step=10.0)
    filter_max_price = st.number_input("Max Stock Price (₹)", min_value=0.0, value=2000.0, step=100.0)

    st.markdown("**📈 ROC Velocity Filter (%)**")
    filter_roc_min = st.number_input("ROC Min", value=0.80, step=0.05)
    filter_roc_max = st.number_input("ROC Max", value=6.00, step=0.05)

    filter_status = st.selectbox("Status Filter", ["All", "In Trade", "Target Hit", "SL Hit", "Waiting"])

    st.markdown("---")
    full_list = (
        "KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,"
        "MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,"
        "ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,"
        "BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,"
        "SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,"
        "HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,"
        "ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,"
        "NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,"
        "TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,"
        "PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,"
        "AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,"
        "ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,"
        "MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,"
        "LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,"
        "THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,"
        "ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,"
        "KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,"
        "BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,"
        "SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,"
        "MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,"
        "COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,"
        "LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,"
        "ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,"
        "MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,"
        "CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,"
        "SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,"
        "ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,"
        "UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"
    )
    user_input = st.text_area("Watchlist", full_list, height=110)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

    if st.button("🗑️ Reset All Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE):
            os.remove(TRADES_FILE)
        st.rerun()

# --- HEADER ---
ist_now = get_ist()
open_status, status_text = is_market_open(ist_now)

try:
    indices = yf.download(["^NSEI", "^BSESN"], period="2d", interval="5m", progress=False)
    if not indices.empty and "Close" in indices.columns:
        n_series = indices["Close"]["^NSEI"].dropna()
        s_series = indices["Close"]["^BSESN"].dropna()
        n_curr, n_prev = float(n_series.iloc[-1]), float(n_series.iloc[0])
        s_curr, s_prev = float(s_series.iloc[-1]), float(s_series.iloc[0])
        n_chg = ((n_curr - n_prev) / n_prev) * 100.0
        s_chg = ((s_curr - s_prev) / s_prev) * 100.0
        st.markdown(
            f"### NIFTY 50: **{n_curr:,.2f}** ({'🟢' if n_chg >= 0 else '🔴'} {n_chg:+.2f}%) | "
            f"SENSEX: **{s_curr:,.2f}** ({'🟢' if s_chg >= 0 else '🔴'} {s_chg:+.2f}%)"
        )
    else:
        st.markdown("### Indices: `Data Temporarily Unavailable`")
except Exception:
    st.markdown("### Indices: `Connecting...`")

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")


def process_core_flex_strategy(data: pd.DataFrame, is_reversed: bool = False) -> pd.DataFrame:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return pd.DataFrame()

    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    level0 = set(data.columns.get_level_values(0))

    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in level0:
            continue

        try:
            df = data[t_str].dropna(subset=["Close", "Open", "High", "Low", "Volume"])
            if len(df) < 30:
                continue

            cmp = float(df["Close"].iloc[-1])
            c_open = float(df["Open"].iloc[-1])
            qty = int(capital // cmp) if cmp > 0 else 0

            if cmp < filter_min_price or cmp > filter_max_price:
                continue

            # ATR & Target Feasibility
            high, low, close = df["High"], df["Low"], df["Close"]
            prev_close = close.shift(1)
            tr = np.maximum(
                (high - low),
                np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
            )
            atr = float(tr.rolling(14).mean().iloc[-1])
            atr_pct = (atr / cmp) * 100.0 if cmp > 0 else 0.0
            target_feasible = (atr_pct / (target_pct * 100.0)) >= min_atr_target_ratio if target_pct > 0 else True

            # Intraday VWAP
            vwap_series = compute_intraday_vwap(df)
            vwap_val = float(vwap_series.iloc[-1]) if not np.isnan(vwap_series.iloc[-1]) else cmp

            # Volume Surge vs MA(20)
            vol_avg = float(df["Volume"].rolling(20).mean().iloc[-1])
            vol_ratio = float(df["Volume"].iloc[-1] / vol_avg) if vol_avg > 0 else 0.0
            vol_surge = vol_ratio >= vol_multiplier

            # ROC Velocity (10-bar window)
            p10 = float(df["Close"].iloc[-11]) if len(df) >= 11 else float(df["Close"].iloc[0])
            roc_val = ((cmp - p10) / p10) * 100.0 if p10 > 0 else 0.0
            roc_abs = abs(roc_val)

            if not (filter_roc_min <= roc_abs <= filter_roc_max):
                continue

            # Confirmation Nodes
            flex_score = 0
            sigs = []

            ema9 = float(df["Close"].ewm(span=9).mean().iloc[-1])
            ema21 = float(df["Close"].ewm(span=21).mean().iloc[-1])
            ema50 = float(df["Close"].ewm(span=50).mean().iloc[-1]) if len(df) >= 50 else ema21

            trend_aligned = (not is_reversed and cmp > ema9 > ema21 > ema50) or (
                is_reversed and cmp < ema9 < ema21 < ema50
            )
            if trend_aligned:
                flex_score += 2
                sigs.append("✓EMA Stack")

            if vol_surge:
                flex_score += 1
                sigs.append(f"⚡Vol {vol_ratio:.1f}x")

            y = df["Close"].tail(14).to_numpy()
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            lrc_aligned = (not is_reversed and slope > 0) or (is_reversed and slope < 0)
            if lrc_aligned:
                flex_score += 1
                sigs.append("LRC:UP" if slope > 0 else "LRC:DOWN")

            # Proposed trade direction
            if not is_reversed:
                proposed_side = "BUY" if cmp > c_open else "SELL"
            else:
                proposed_side = "SELL" if cmp > c_open else "BUY"

            vwap_aligned = (proposed_side == "BUY" and cmp >= vwap_val) or (
                proposed_side == "SELL" and cmp <= vwap_val
            )
            if vwap_aligned:
                sigs.append("✓VWAP")
            else:
                sigs.append("⚠Off-VWAP")

            model_fit = classify_model_fit(vol_ratio, vwap_aligned, trend_aligned, roc_abs)
            confidence_label = "⭐" * flex_score if flex_score > 0 else "⚪ Low"

            # Trade State Monitoring
            trade = st.session_state.dual_trades[strategy_key].get(symbol)
            status = "WAITING"
            e_time = ist_now.strftime("%H:%M")
            t_type = trade.get("type") if trade else None

            can_enter = (
                qty >= 1
                and target_feasible
                and vol_surge
                and trend_aligned
                and (vwap_aligned or not require_vwap_alignment)
            )

            if trade:
                status = "IN TRADE"
                e_time = trade.get("time", e_time)
                if trade["type"] == "BUY":
                    if cmp >= trade["target"]:
                        status = "🎯 TARGET HIT"
                    elif cmp <= trade["sl"]:
                        status = "🛑 SL HIT"
                elif trade["type"] == "SELL":
                    if cmp <= trade["target"]:
                        status = "🎯 TARGET HIT"
                    elif cmp >= trade["sl"]:
                        status = "🛑 SL HIT"
            elif can_enter:
                t_type = proposed_side
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = (entry - (sl_atr_mult * atr)) if t_type == "BUY" else (entry + (sl_atr_mult * atr))

                st.session_state.dual_trades[strategy_key][symbol] = {
                    "entry": entry,
                    "target": target,
                    "sl": sl,
                    "type": t_type,
                    "time": e_time,
                    "score": flex_score,
                }
                save_persistent_trades(st.session_state.dual_trades)
                status = "IN TRADE"
                trade = st.session_state.dual_trades[strategy_key][symbol]

            if filter_status != "All":
                if filter_status == "In Trade" and "IN TRADE" not in status:
                    continue
                if filter_status == "Target Hit" and "TARGET HIT" not in status:
                    continue
                if filter_status == "SL Hit" and "SL HIT" not in status:
                    continue
                if filter_status == "Waiting" and status != "WAITING":
                    continue

            decision_note = (
                "ENTER"
                if trade
                else ("SKIP (No Qty)" if qty < 1 else ("SKIP (Low ATR)" if not target_feasible else "WATCH"))
            )

            results.append({
                "Stock": f"⚡ {symbol}",
                "Decision": decision_note,
                "Model Fit": model_fit,
                "Trade": f"{'🟢' if t_type == 'BUY' else '🔴'} {t_type}" if t_type else "⏳ Ready",
                "Qty": qty,
                "CMP": cmp,
                "VWAP": vwap_val,
                "ATR%": atr_pct,
                "Entry": trade["entry"] if trade else 0.0,
                "SL": trade["sl"] if trade else 0.0,
                "Target": trade["target"] if trade else 0.0,
                "Confidence": confidence_label,
                "Signal Details": " | ".join(sigs),
                "Status": status,
                "Time": e_time,
                "InTrade": 1 if trade else 0,
                "ROC_Val": roc_abs,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()
    return (
        pd.DataFrame(results)
        .sort_values(by=["InTrade", "ROC_Val"], ascending=False)
        .drop(columns=["InTrade", "ROC_Val"])
    )


# --- EXECUTION FETCH ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    raw_market_data = yf.download(
        tickers, period="2d", interval="5m", group_by="ticker", auto_adjust=True, progress=False
    )
except Exception:
    raw_market_data = pd.DataFrame()


def apply_dynamic_styles(df):
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        if "IN TRADE" in str(row["Status"]) or "HIT" in str(row["Status"]):
            row_bg = "#c6f6d5" if "BUY" in str(row["Trade"]) else "#fed7d7"
            styles.loc[i, :] = f"background-color: {row_bg}; color: black; font-weight: 500"
            is_buy = "BUY" in str(row["Trade"])
            cmp_bg = (
                "#1a8a44"
                if (is_buy and row["CMP"] >= row["Entry"]) or (not is_buy and row["CMP"] <= row["Entry"])
                else "#c53030"
            )
            styles.loc[i, "CMP"] = f"background-color: {cmp_bg}; color: white; font-weight: bold"
    return styles


columns_show = [
    "Stock", "Decision", "Model Fit", "Trade", "Entry", "CMP", "VWAP",
    "ATR%", "Confidence", "Signal Details", "SL", "Target", "Status", "Time", "Qty",
]

df_reg = process_core_flex_strategy(raw_market_data, is_reversed=False) if not raw_market_data.empty else pd.DataFrame()
df_rev = process_core_flex_strategy(raw_market_data, is_reversed=True) if not raw_market_data.empty else pd.DataFrame()

# --- DISPLAY INTERFACE ---
st.markdown("---")
st.header("🪟 Active Trade Window")

active_reg = df_reg[df_reg["Status"].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_reg.empty else pd.DataFrame()
active_rev = df_rev[df_rev["Status"].str.contains("IN TRADE|HIT", regex=True, na=False)] if not df_rev.empty else pd.DataFrame()

fmt_active = {"CMP": "{:.2f}", "VWAP": "{:.2f}", "ATR%": "{:.2f}%", "Entry": "{:.2f}", "Target": "{:.2f}", "SL": "{:.2f}"}
fmt_scan = {
    "CMP": "{:.2f}",
    "VWAP": "{:.2f}",
    "ATR%": "{:.2f}%",
    "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
    "Target": lambda x: f"{x:.2f}" if x > 0 else "-",
    "SL": lambda x: f"{x:.2f}" if x > 0 else "-",
}

if not active_reg.empty or not active_rev.empty:
    comb = pd.concat([active_reg, active_rev], ignore_index=True).drop_duplicates(subset=["Stock"])
    st.dataframe(
        comb.style.apply(apply_dynamic_styles, axis=None).format(fmt_active),
        use_container_width=True,
        hide_index=True,
        column_order=columns_show,
    )
else:
    st.info("No active open positions currently.")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Regular Monitor")
    if not df_reg.empty:
        st.dataframe(
            df_reg.style.apply(apply_dynamic_styles, axis=None).format(fmt_scan),
            use_container_width=True,
            hide_index=True,
            column_order=columns_show,
        )
    else:
        st.caption("No tickers match standard filters right now.")

with col2:
    st.subheader("🔄 Reversed Monitor")
    if not df_rev.empty:
        st.dataframe(
            df_rev.style.apply(apply_dynamic_styles, axis=None).format(fmt_scan),
            use_container_width=True,
            hide_index=True,
            column_order=columns_show,
        )
    else:
        st.caption("No tickers match reversal filters right now.")

time.sleep(60 if open_status else 300)
st.rerun()
