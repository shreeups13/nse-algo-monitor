import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="NSE Intraday & Scalping Scanner", layout="wide")

st.title("⚡ NSE Intraday & Scalping Signal Scanner")
st.markdown("Uses **VWAP**, **EMA (9 / 21)**, **RSI (7)**, **ATR (14)**, and **Volume Spike** on intraday candles.")

RAW_STOCKS = """KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,AXISBANK,TATASTEEL,LT,ADANIGREEN,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,ULTRACEMCO,ADANIENT,JIOFIN,EICHERMOT,SBILIFE,HINDALCO,BAJFINANCE,BHEL,FORTIS,SHRIRAMFIN,DIVISLAB,MAXHEALTH,TVSMOTOR,HEROMOTOCO,HCLTECH,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,BEL,JSWSTEEL,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,INDUSTOWER,VBL,HAL,DIXON,SWIGGY,COALINDIA,DRREDDY,TITAN,PFC,ASHOKLEY,WIPRO,INDIGO,ONGC,ZYDUSLIFE,INDHOTEL,POWERGRID,SONACOMS,CHOLAFIN,PERSISTENT,NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,DMART,LODHA,AUBANK,HINDUNILVR,ASIANPAINT,TRENT,LICI,GLENMARK,BOSCHLTD,BHARATFORG,HDFCLIFE,NESTLEIND,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,HINDPETRO,WAAREEENER,IDFCFIRSTB,BANDHANBNK,LTM,CUMMINSIND,LTF,ANGELONE,AUROPHARMA,HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,CANBK,CDSL,ABB,IOC,MFSL,MOTILALOFS,INDUSINDBK,NATIONALUM,ALKEM,MUTHOOTFIN,TATAPOWER,AMBUJACEM,MARICO,MAZDOCK,UNITDSPR,SHREECEM,UPL,NMDC,PIDILITIND,PNB,CIPLA,GAIL,REDINGTON,TIINDIA,LALPATHLAB,PHOENIXLTD,MANKIND,CAMS,TATAELXSI,BDL,ZEEL,OIL,IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,JINDALSTEL,GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,SAMMAANCAP,JSWENERGY,ESCORTS,UNOMINDA,GESHIP,AMBER,NCC,SRF,TEJASNET,EMAMILTD,HONASA,NAM-INDIA,GODREJPROP,KAJARIACER,NHPC,NAVINFLUOR,TATACHEM,COLPAL,KFINTECH,GODREJCP,IRCTC,JUBLFOOD,INOXWIND,BALKRISIND,VOLTAS,STARHEALTH,CYIENT,GRANULES,IPCALAB,PIRAMALFIN,NATCOPHARM,IREDA,SUPREMEIND,JSL,CASTROLIND,DELHIVERY,SBICARD,BALRAMCHIN,INDIANB,HUDCO,SHYAMMETL,OBEROIRLTY,MEDANTA,PETRONET,NBCC,CARBORUNIV,ATGL,BAJAJHFL,TATATECH,NH,ELECON,MRF,BAJAJHLDNG,COROMANDEL,ASTRAL,SCI,BEML,CONCOR,PVRINOX,SUMICHEM,IEX,POONAWALLA,IGL,MINDACORP,AAVAS,LTFOODS,ENDURANCE,TITAGARH,CANFINHOME,DEEPAKFERT,NIACL,PCBL,APOLLOTYRE,PIIND,HONAUT,ABSLAMC,LINDEINDIA,AJANTPHARM,PARADEEP,LTTS,ELGIEQUIP,SJVN,TRITURBINE,CESC,DEEPAKNTR,MGL,KEC,TATACOMM,GICRE,EIDPARRY,AARTIIND,RAILTEL,JBMA,USHAMART,HOMEFIRST,GLAXO,CONCORDBIO,TORNTPOWER,NTPCGREEN,SYNGENE,ABBOTINDIA,CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,SUNDARMFIN,UBL,SCHAEFFLER,JKTYRE,BHARTIHEXA,CEATLTD,KPIL,JUBLINGREA,GILLETTE,CRISIL,ASAHIINDIA,TIMKEN,VTL,ATUL,DALBHARAT,AIAENG,KPRMILL,GODREJIND,SOBHA,INDIAMART,CIEINDIA,UCOBANK,IOB,BATAINDIA,ZYDUSWELL,FACT,RAMCOCEM,TRIDENT,UTIAMC,EIHOTEL,DOMS,ITI"""

# Sidebar Controls
st.sidebar.header("⚡ Intraday Parameters")
auto_refresh = st.sidebar.toggle("Auto-Refresh Every 1 Min", value=True)
refresh_sec = 60

interval = st.sidebar.selectbox("Candle Interval", ["5m", "15m", "1m"], index=0)
period_map = {"1m": "2d", "5m": "5d", "15m": "10d"}
fast_ema = st.sidebar.number_input("Fast EMA", min_value=3, max_value=25, value=9)
slow_ema = st.sidebar.number_input("Slow EMA", min_value=10, max_value=60, value=21)
vol_mult = st.sidebar.slider("Min Volume Spike (x Avg)", min_value=1.0, max_value=4.0, value=1.5, step=0.1)
atr_mult = st.sidebar.slider("ATR Target / Stop Multiplier", min_value=0.5, max_value=3.0, value=1.5, step=0.25)
stock_input = st.sidebar.text_area("Watchlist", value=RAW_STOCKS, height=130)

def calc_rsi(series, period=7):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_vwap(df):
    # Reset VWAP per trading day
    df = df.copy()
    df["Date"] = df.index.date
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    tp_vol = typical_price * df["Volume"]
    cum_tp_vol = tp_vol.groupby(df["Date"]).cumsum()
    cum_vol = df["Volume"].groupby(df["Date"]).cumsum().replace(0, np.nan)
    return cum_tp_vol / cum_vol

def calc_atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

@st.cache_data(ttl=55)  # Refresh cache just under 1 minute for live polling
def scan_intraday(symbols, tf, fast_p, slow_p, vol_thresh, atr_k):
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
            df = data[ticker].dropna(subset=["Close", "Volume"]).copy()
            if len(df) < slow_p + 5:
                continue

            df["EMA_Fast"] = df["Close"].ewm(span=fast_p, adjust=False).mean()
            df["EMA_Slow"] = df["Close"].ewm(span=slow_p, adjust=False).mean()
            df["VWAP"] = calc_vwap(df)
            df["RSI"] = calc_rsi(df["Close"], 7)
            df["ATR"] = calc_atr(df, 14)
            df["Vol_Avg"] = df["Volume"].rolling(20).mean()
            df["Vol_Ratio"] = df["Volume"] / df["Vol_Avg"].replace(0, np.nan)
            df["Candle_Pct"] = ((df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)) * 100

            last = df.iloc[-1]
            prev = df.iloc[-2]

            price = float(last["Close"])
            vwap = float(last["VWAP"])
            ema_f = float(last["EMA_Fast"])
            ema_s = float(last["EMA_Slow"])
            rsi = float(last["RSI"])
            atr = float(last["ATR"]) if pd.notna(last["ATR"]) else price * 0.005
            vol_r = float(last["Vol_Ratio"]) if pd.notna(last["Vol_Ratio"]) else 0.0
            c_pct = float(last["Candle_Pct"])

            # Fresh EMA cross or momentum continuation with volume
            bull_cross = (prev["EMA_Fast"] <= prev["EMA_Slow"]) and (ema_f > ema_s)
            bear_cross = (prev["EMA_Fast"] >= prev["EMA_Slow"]) and (ema_f < ema_s)

            action = "WAIT"
            stop_loss = np.nan
            target = np.nan

            if price > vwap and ema_f > ema_s and vol_r >= vol_thresh and (bull_cross or c_pct > 0.35) and rsi < 78:
                action = "BUY (LONG)"
                stop_loss = round(max(price - atr * atr_k, vwap - atr * 0.5), 2)
                target = round(price + atr * atr_k * 1.5, 2)
            elif price < vwap and ema_f < ema_s and vol_r >= vol_thresh and (bear_cross or c_pct < -0.35) and rsi > 22:
                action = "SELL (SHORT / EXIT)"
                stop_loss = round(min(price + atr * atr_k, vwap + atr * 0.5), 2)
                target = round(price - atr * atr_k * 1.5, 2)
            elif abs(c_pct) >= 0.8 and vol_r >= vol_thresh:
                action = "SPIKE WATCH"

            if action != "WAIT":
                rows.append({
                    "Symbol": ticker.replace(".NS", ""),
                    "Action": action,
                    "LTP (₹)": round(price, 2),
                    "Stop Loss (₹)": stop_loss,
                    "Target (₹)": target,
                    "Candle %": round(c_pct, 2),
                    "Vol Spike (x)": round(vol_r, 2),
                    "VWAP (₹)": round(vwap, 2),
                    "RSI (7)": round(rsi, 1),
                })
        except Exception:
            continue

    return pd.DataFrame(rows)

col_btn, col_ts = st.columns([1, 3])
with col_btn:
    manual_scan = st.button("⚡ Scan Now", type="primary")

if manual_scan:
    scan_intraday.clear()

ist_now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
with col_ts:
    status_mode = "Auto-refreshing every 60s" if auto_refresh else "Manual mode"
    st.caption(f"🕒 **Last Scan Timestamp:** `{ist_now}` | **Interval:** `{interval}` | **Mode:** `{status_mode}`")

with st.spinner(f"Scanning {interval} candles across watchlist..."):
    out = scan_intraday(stock_input.split(","), interval, fast_ema, slow_ema, vol_mult, atr_mult)

if out.empty:
    st.info(f"No active intraday signals match your current volume and momentum thresholds as of {ist_now}.")
else:
    longs = out[out["Action"] == "BUY (LONG)"].sort_values(by="Vol Spike (x)", ascending=False)
    shorts = out[out["Action"] == "SELL (SHORT / EXIT)"].sort_values(by="Vol Spike (x)", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Buy Setups", len(longs))
    c2.metric("🔴 Sell / Short Setups", len(shorts))
    c3.metric("⚡ Total Active Alerts", len(out))

    st.subheader("🟢 Intraday BUY Setups")
    st.dataframe(longs, use_container_width=True, hide_index=True)

    st.subheader("🔴 Intraday SELL / SHORT Setups")
    st.dataframe(shorts, use_container_width=True, hide_index=True)

    st.subheader("📋 All Active Signals & Spikes")
    st.dataframe(out, use_container_width=True, hide_index=True)

if auto_refresh:
    time.sleep(refresh_sec)
    st.rerun()
