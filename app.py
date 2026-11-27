import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="NSE Price-Movement Scanner", layout="wide")

st.title("⚡ NSE Pure Price-Movement Scanner")
st.markdown(
    "**BUY** when `Current Price > Previous Candle Open` + Volume Spike; "
    "**SELL** when `Current Price < Previous Candle Open` + Volume Spike."
)

RAW_STOCKS = """KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"""

# Sidebar Controls
st.sidebar.header("⚡ Movement Parameters")
auto_refresh = st.sidebar.toggle("Auto-Refresh Every 1 Min", value=True)
refresh_sec = 60

interval = st.sidebar.selectbox("Candle Interval", ["5m", "15m", "1m"], index=0)
period_map = {"1m": "2d", "5m": "5d", "15m": "10d"}
prev_bars_req = st.sidebar.slider(
    "Beat Last N Candle Opens",
    min_value=1,
    max_value=4,
    value=1,
    help="1 = Current price > previous candle's Open (or < for SELL). 2+ = must beat last N candles' Opens.",
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

@st.cache_data(ttl=55)
def scan_movement(symbols, tf, n_prev_opens, vol_thresh, atr_k):
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
            if len(df) < max(20, n_prev_opens + 2):
                continue

            df["ATR"] = calc_atr(df, 14)
            df["Vol_Avg"] = df["Volume"].rolling(20).mean()
            df["Vol_Ratio"] = df["Volume"] / df["Vol_Avg"].replace(0, np.nan)
            df["Candle_Pct"] = ((df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)) * 100

            last = df.iloc[-1]
            prev_opens = df["Open"].iloc[-(n_prev_opens + 1):-1]

            price = float(last["Close"])
            prev_open = float(df["Open"].iloc[-2])
            atr = float(last["ATR"]) if pd.notna(last["ATR"]) else price * 0.005
            vol_r = float(last["Vol_Ratio"]) if pd.notna(last["Vol_Ratio"]) else 0.0
            c_pct = float(last["Candle_Pct"])

            above_prev_opens = bool((price > prev_opens).all())
            below_prev_opens = bool((price < prev_opens).all())

            action = "WAIT"
            stop_loss = np.nan
            target = np.nan

            if above_prev_opens and vol_r >= vol_thresh:
                action = "BUY (LONG)"
                stop_loss = round(min(prev_open, price - atr * atr_k), 2)
                target = round(price + atr * atr_k * 1.5, 2)
            elif below_prev_opens and vol_r >= vol_thresh:
                action = "SELL (SHORT / EXIT)"
                stop_loss = round(max(prev_open, price + atr * atr_k), 2)
                target = round(price - atr * atr_k * 1.5, 2)
            elif abs(c_pct) >= 0.8 and vol_r >= vol_thresh:
                action = "SPIKE WATCH"

            if action != "WAIT":
                rows.append({
                    "Symbol": ticker.replace(".NS", ""),
                    "Action": action,
                    "LTP (₹)": round(price, 2),
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
    scan_movement.clear()

ist_now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
with col_ts:
    status_mode = "Auto-refreshing every 60s" if auto_refresh else "Manual mode"
    st.caption(
        f"🕒 **Last Scan Timestamp:** `{ist_now}` | **Interval:** `{interval}` | "
        f"**Beat Last N Opens:** `{prev_bars_req}` | **Mode:** `{status_mode}`"
    )

with st.spinner(f"Scanning {interval} candles across watchlist..."):
    out = scan_movement(stock_input.split(","), interval, prev_bars_req, vol_mult, atr_mult)

if out.empty:
    st.info(f"No active movement signals match your criteria as of {ist_now}.")
else:
    longs = out[out["Action"] == "BUY (LONG)"].sort_values(by="Vol Spike (x)", ascending=False)
    shorts = out[out["Action"] == "SELL (SHORT / EXIT)"].sort_values(by="Vol Spike (x)", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Buy Setups", len(longs))
    c2.metric("🔴 Sell / Short Setups", len(shorts))
    c3.metric("⚡ Total Active Alerts", len(out))

    st.subheader("🟢 BUY Setups (Price > Previous Open)")
    st.dataframe(longs, use_container_width=True, hide_index=True)

    st.subheader("🔴 SELL / SHORT Setups (Price < Previous Open)")
    st.dataframe(shorts, use_container_width=True, hide_index=True)

    st.subheader("📋 All Active Signals & Spikes")
    st.dataframe(out, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()
