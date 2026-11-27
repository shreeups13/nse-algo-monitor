import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="NSE Opening-Base Movement Scanner", layout="wide")

st.title("⚡ NSE Opening-Base Price-Movement Scanner")
st.markdown(
    "Tracks **rising/falling candle opening bases** (`Open` progression + `LTP` vs. opening base + volume spike) with **no SMA, EMA, or VWAP**."
)

RAW_STOCKS = """KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"""

# Sidebar Controls
st.sidebar.header("⚡ Opening-Base Parameters")
auto_refresh = st.sidebar.toggle("Auto-Refresh Every 1 Min", value=True)
refresh_sec = 60

interval = st.sidebar.selectbox("Candle Interval", ["5m", "15m", "1m"], index=0)
period_map = {"1m": "2d", "5m": "5d", "15m": "10d"}
base_candles = st.sidebar.slider(
    "Opening Base Candles",
    min_value=2,
    max_value=5,
    value=3,
    help="Number of candles used to form the rising/falling Opening Price Base (3 matches your 1-2-3 sketch).",
)
vol_mult = st.sidebar.slider("Min Volume Spike (x Avg)", min_value=1.0, max_value=4.0, value=1.5, step=0.1)
atr_mult = st.sidebar.slider("ATR Target / Stop Multiplier", min_value=0.5, max_value=3.0, value=1.5, step=0.25)
stock_input = st.sidebar.text_area("Watchlist", value=RAW_STOCKS, height=130)

def calc_atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def project_opening_base(opens):
    """Fits a line across the last N candle opens and projects the next base level."""
    y = np.asarray(opens, dtype=float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    projected_base = slope * len(y) + intercept
    return float(projected_base), float(slope)

@st.cache_data(ttl=55)
def scan_opening_base(symbols, tf, n_base, vol_thresh, atr_k):
    tickers = [f"{s.strip()}.NS" for s in symbols if s.strip()]
    data = yf.download(
        tickers,
        period=period_map[tf],
        interval=tf,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    rows = []
    for ticker in tickers:
        try:
            df = data[ticker].dropna(subset=["Open", "Close", "Volume"]).copy()
            if len(df) < max(20, n_base + 2):
                continue

            df["ATR"] = calc_atr(df, 14)
            df["Vol_Avg"] = df["Volume"].rolling(20).mean()
            df["Vol_Ratio"] = df["Volume"] / df["Vol_Avg"].replace(0, np.nan)
            df["Candle_Pct"] = ((df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)) * 100

            last = df.iloc[-1]
            # Prior N completed candle opens (e.g. candles 1, 2, 3 in your sketch)
            base_opens = df["Open"].iloc[-(n_base + 1):-1]
            prev_open = float(df["Open"].iloc[-2])
            curr_open = float(last["Open"])
            price = float(last["Close"])

            base_line, base_slope = project_opening_base(base_opens)
            atr = float(last["ATR"]) if pd.notna(last["ATR"]) else price * 0.005
            vol_r = float(last["Vol_Ratio"]) if pd.notna(last["Vol_Ratio"]) else 0.0
            c_pct = float(last["Candle_Pct"])

            # Rising opens across the base window and current price holding above base
            rising_opens = bool((np.diff(base_opens.values) > 0).all()) and (curr_open >= prev_open)
            falling_opens = bool((np.diff(base_opens.values) < 0).all()) and (curr_open <= prev_open)

            above_base = (price > prev_open) and (price > base_line)
            below_base = (price < prev_open) and (price < base_line)

            action = "WAIT"
            stop_loss = np.nan
            target = np.nan

            if rising_opens and above_base and vol_r >= vol_thresh:
                action = "BUY (LONG)"
                stop_loss = round(min(base_line, price - atr * atr_k), 2)
                target = round(price + atr * atr_k * 1.5, 2)
            elif falling_opens and below_base and vol_r >= vol_thresh:
                action = "SELL (SHORT / EXIT)"
                stop_loss = round(max(base_line, price + atr * atr_k), 2)
                target = round(price - atr * atr_k * 1.5, 2)
            elif abs(c_pct) >= 0.8 and vol_r >= vol_thresh:
                action = "SPIKE WATCH"

            if action != "WAIT":
                rows.append({
                    "Symbol": ticker.replace(".NS", ""),
                    "Action": action,
                    "LTP (₹)": round(price, 2),
                    "Base Line (₹)": round(base_line, 2),
                    "Prev Open (₹)": round(prev_open, 2),
                    "Stop Loss (₹)": stop_loss,
                    "Target (₹)": target,
                    "Candle %": round(c_pct, 2),
                    "Vol Spike (x)": round(vol_r, 2),
                })
        except Exception:
            continue

    return pd.DataFrame(rows)

col_btn, col_ts = st.columns([1, 3])
with col_btn:
    manual_scan = st.button("⚡ Scan Now", type="primary")

if manual_scan:
    scan_opening_base.clear()

ist_now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
with col_ts:
    status_mode = "Auto-refreshing every 60s" if auto_refresh else "Manual mode"
    st.caption(
        f"🕒 **Last Scan Timestamp:** `{ist_now}` | **Interval:** `{interval}` | "
        f"**Base Candles:** `{base_candles}` | **Mode:** `{status_mode}`"
    )

with st.spinner(f"Scanning {interval} candles across watchlist..."):
    out = scan_opening_base(stock_input.split(","), interval, base_candles, vol_mult, atr_mult)

if out.empty:
    st.info(f"No active opening-base signals match your criteria as of {ist_now}.")
else:
    longs = out[out["Action"] == "BUY (LONG)"].sort_values(by="Vol Spike (x)", ascending=False)
    shorts = out[out["Action"] == "SELL (SHORT / EXIT)"].sort_values(by="Vol Spike (x)", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Buy Setups", len(longs))
    c2.metric("🔴 Sell / Short Setups", len(shorts))
    c3.metric("⚡ Total Active Alerts", len(out))

    st.subheader("🟢 BUY Setups (Rising Opening Base + LTP Above Base)")
    st.dataframe(longs, use_container_width=True, hide_index=True)

    st.subheader("🔴 SELL / SHORT Setups (Falling Opening Base + LTP Below Base)")
    st.dataframe(shorts, use_container_width=True, hide_index=True)

    st.subheader("📋 All Active Signals & Spikes")
    st.dataframe(out, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()
