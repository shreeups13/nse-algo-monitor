import pandas as pd
import streamlit as st
import yfinance as yf

WATCHLIST = [
    "KOTAKBANK", "HDFCBANK", "RELIANCE", "BSE", "ICICIBANK", "TARIL", "M&M", "INFY",
    "BAJAJ-AUTO", "POLICYBZR", "MARUTI", "ADANIENSOL", "BHARTIARTL", "AXISBANK",
    "TATASTEEL", "LT", "ADANIGREEN", "APOLLOHOSP", "TCS", "SBIN", "ADANIPOWER", "MCX",
    "COFORGE", "ULTRACEMCO", "ADANIENT", "JIOFIN", "EICHERMOT", "SBILIFE", "HINDALCO",
    "BAJFINANCE", "BHEL", "FORTIS", "SHRIRAMFIN", "DIVISLAB", "MAXHEALTH", "TVSMOTOR",
    "HEROMOTOCO", "HCLTECH", "ITC", "KALYANKJIL", "SUNPHARMA", "DLF", "GRASIM", "TECHM",
    "CGPOWER", "BAJAJFINSV", "BEL", "JSWSTEEL", "ADANIPORTS", "POLYCAB", "HYUNDAI",
    "MOTHERSON", "INDUSTOWER", "VBL", "HAL", "DIXON", "SWIGGY", "COALINDIA", "DRREDDY",
    "TITAN", "PFC", "ASHOKLEY", "WIPRO", "INDIGO", "ONGC", "ZYDUSLIFE", "INDHOTEL",
    "POWERGRID", "SONACOMS", "CHOLAFIN", "PERSISTENT", "NAUKRI", "RECLTD", "MPHASIS",
    "HDFCAMC", "VEDL", "NYKAA", "DMART", "LODHA", "AUBANK", "HINDUNILVR", "ASIANPAINT",
    "TRENT", "LICI", "GLENMARK", "BOSCHLTD", "BHARATFORG", "HDFCLIFE", "NESTLEIND",
    "HAVELLS", "BANKBARODA", "SUZLON", "PRESTIGE", "OFSS", "HINDPETRO", "WAAREEENER",
    "IDFCFIRSTB", "BANDHANBNK", "LTM", "CUMMINSIND", "LTF", "ANGELONE", "AUROPHARMA",
    "HINDZINC", "TATACONSUM", "BRITANNIA", "TORNTPHARM", "BPCL", "YESBANK", "LUPIN",
    "CANBK", "CDSL", "ABB", "IOC", "MFSL", "MOTILALOFS", "INDUSINDBK", "NATIONALUM",
    "ALKEM", "MUTHOOTFIN", "TATAPOWER", "AMBUJACEM", "MARICO", "MAZDOCK", "UNITDSPR",
    "SHREECEM", "UPL", "NMDC", "PIDILITIND", "PNB", "CIPLA", "GAIL", "REDINGTON",
    "TIINDIA", "LALPATHLAB", "PHOENIXLTD", "MANKIND", "CAMS", "TATAELXSI", "BDL",
    "ZEEL", "OIL", "IRFC", "M&MFIN", "KPITTECH", "EXIDEIND", "THERMAX", "JINDALSTEL",
    "GLAND", "COCHINSHIP", "BIOCON", "DABUR", "CROMPTON", "SIEMENS", "SAMMAANCAP",
    "JSWENERGY", "ESCORTS", "UNOMINDA", "GESHIP", "AMBER", "NCC", "SRF", "TEJASNET",
    "EMAMILTD", "HONASA", "NAM-INDIA", "GODREJPROP", "KAJARIACER", "NHPC", "NAVINFLUOR",
    "TATACHEM", "COLPAL", "KFINTECH", "GODREJCP", "IRCTC", "JUBLFOOD", "INOXWIND",
    "BALKRISIND", "VOLTAS", "STARHEALTH", "CYIENT", "GRANULES", "IPCALAB", "PIRAMALFIN",
    "NATCOPHARM", "IREDA", "SUPREMEIND", "JSL", "CASTROLIND", "DELHIVERY", "SBICARD",
    "BALRAMCHIN", "INDIANB", "HUDCO", "SHYAMMETL", "OBEROIRLTY", "MEDANTA", "PETRONET",
    "NBCC", "CARBORUNIV", "ATGL", "BAJAJHFL", "TATATECH", "NH", "ELECON", "MRF",
    "BAJAJHLDNG", "COROMANDEL", "ASTRAL", "SCI", "BEML", "CONCOR", "PVRINOX",
    "SUMICHEM", "IEX", "POONAWALLA", "IGL", "MINDACORP", "AAVAS", "LTFOODS",
    "ENDURANCE", "TITAGARH", "CANFINHOME", "DEEPAKFERT", "NIACL", "PCBL", "APOLLOTYRE",
    "PIIND", "HONAUT", "ABSLAMC", "LINDEINDIA", "AJANTPHARM", "PARADEEP", "LTTS",
    "ELGIEQUIP", "SJVN", "TRITURBINE", "CESC", "DEEPAKNTR", "MGL", "KEC", "TATACOMM",
    "GICRE", "EIDPARRY", "AARTIIND", "RAILTEL", "JBMA", "USHAMART", "HOMEFIRST",
    "GLAXO", "CONCORDBIO", "TORNTPOWER", "NTPCGREEN", "SYNGENE", "ABBOTINDIA",
    "CHAMBLFERT", "BRIGADE", "BERGEPAINT", "ACC", "SUNDARMFIN", "UBL", "SCHAEFFLER",
    "JKTYRE", "BHARTIHEXA", "CEATLTD", "KPIL", "JUBLINGREA", "GILLETTE", "CRISIL",
    "ASAHIINDIA", "TIMKEN", "VTL", "ATUL", "DALBHARAT", "AIAENG", "KPRMILL",
    "GODREJIND", "SOBHA", "INDIAMART", "CIEINDIA", "UCOBANK", "IOB", "BATAINDIA",
    "ZYDUSWELL", "FACT", "RAMCOCEM", "TRIDENT", "UTIAMC", "EIHOTEL", "DOMS", "ITI",
]

st.set_page_config(page_title="NSE Watchlist Mover Scanner", page_icon="📈", layout="wide")


@st.cache_data(ttl=120, show_spinner=False)
def fetch_watchlist_movers(tickers: tuple[str, ...], rvol_lookback: int = 5) -> pd.DataFrame:
    nse_symbols = [f"{t.strip()}.NS" for t in tickers]

    data = yf.download(
        tickers=nse_symbols,
        period=f"{max(rvol_lookback + 5, 10)}d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    rows = []
    for raw_ticker, nse_sym in zip(tickers, nse_symbols):
        try:
            df = data[nse_sym].dropna(subset=["Close", "Volume"])
            if len(df) < 2:
                continue

            prev_close = float(df["Close"].iloc[-2])
            last_close = float(df["Close"].iloc[-1])
            last_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else prev_close
            last_high = float(df["High"].iloc[-1]) if "High" in df.columns else last_close
            last_low = float(df["Low"].iloc[-1]) if "Low" in df.columns else last_close
            last_vol = float(df["Volume"].iloc[-1])

            avg_vol = float(df["Volume"].iloc[-(rvol_lookback + 1):-1].mean())
            rvol = round(last_vol / avg_vol, 2) if avg_vol > 0 else 0.0
            chg_pct = round(((last_close - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
            range_pct = round(((last_high - last_low) / last_low) * 100, 2) if last_low > 0 else 0.0

            rows.append({
                "ticker": raw_ticker,
                "ltp": round(last_close, 2),
                "chg_pct": chg_pct,
                "rvol": rvol,
                "volume_lakhs": round(last_vol / 1e5, 2),
                "range_pct": range_pct,
                "open": round(last_open, 2),
                "high": round(last_high, 2),
                "low": round(last_low, 2),
            })
        except Exception:
            continue

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(by="chg_pct", ascending=False).reset_index(drop=True)


def render_table(df: pd.DataFrame, key_suffix: str) -> None:
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=f"tbl_{key_suffix}",
        column_config={
            "ticker": st.column_config.TextColumn("Symbol", width="small"),
            "ltp": st.column_config.NumberColumn("LTP (₹)", format="₹%.2f"),
            "chg_pct": st.column_config.NumberColumn("Change %", format="%.2f%%"),
            "rvol": st.column_config.ProgressColumn(
                "RVOL",
                format="%.2fx",
                min_value=0.0,
                max_value=max(5.0, float(df["rvol"].max()) if not df.empty else 5.0),
            ),
            "volume_lakhs": st.column_config.NumberColumn("Vol (Lakhs)", format="%.2f"),
            "range_pct": st.column_config.NumberColumn("Day Range %", format="%.2f%%"),
            "open": st.column_config.NumberColumn("Open (₹)", format="₹%.2f"),
            "high": st.column_config.NumberColumn("High (₹)", format="₹%.2f"),
            "low": st.column_config.NumberColumn("Low (₹)", format="₹%.2f"),
        },
    )


st.title("NSE Watchlist Mover Scanner")
st.caption("Intraday % change, relative volume (RVOL), and range scan across your custom NSE ticker list.")

with st.sidebar:
    st.header("Scan Filters")
    rvol_lookback = st.slider("RVOL Lookback (Days)", min_value=3, max_value=20, value=5)
    min_abs_move = st.slider("Min |Change %|", min_value=0.0, max_value=10.0, value=2.0, step=0.25)
    min_rvol = st.slider("Min RVOL", min_value=0.0, max_value=10.0, value=1.5, step=0.25)
    min_vol_lakhs = st.number_input("Min Volume (Lakhs)", min_value=0.0, value=5.0, step=5.0)
    search_ticker = st.text_input("Filter Symbol", placeholder="e.g. MCX, INFY, IREDA").strip().upper()

    if st.button("Refresh Data", type="primary", use_container_width=True):
        fetch_watchlist_movers.clear()

with st.spinner("Scanning NSE watchlist via Yahoo Finance..."):
    df_all = fetch_watchlist_movers(tuple(WATCHLIST), rvol_lookback=rvol_lookback)

if df_all.empty:
    st.warning("No market data returned right now. Try clicking Refresh Data or check Yahoo Finance connectivity.")
    st.stop()

filtered = df_all[
    (df_all["chg_pct"].abs() >= min_abs_move)
    & (df_all["rvol"] >= min_rvol)
    & (df_all["volume_lakhs"] >= min_vol_lakhs)
]
if search_ticker:
    filtered = filtered[filtered["ticker"].str.contains(search_ticker, na=False)]

top_gainer = df_all.iloc[0]
top_loser = df_all.iloc[-1]
high_rvol_count = int((df_all["rvol"] >= min_rvol).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Scanned Stocks", len(df_all))
c2.metric("Top Gainer", top_gainer["ticker"], f"{top_gainer['chg_pct']:+.2f}%")
c3.metric("Top Loser", top_loser["ticker"], f"{top_loser['chg_pct']:+.2f}%")
c4.metric(f"RVOL >= {min_rvol:.2f}x", high_rvol_count)

tab_bull, tab_bear, tab_rvol, tab_all = st.tabs([
    "Bullish Movers",
    "Bearish Movers",
    "High RVOL + Move",
    "All Filtered",
])

with tab_bull:
    bull_df = filtered[filtered["chg_pct"] > 0].sort_values(by="chg_pct", ascending=False)
    render_table(bull_df, "bull")

with tab_bear:
    bear_df = filtered[filtered["chg_pct"] < 0].sort_values(by="chg_pct", ascending=True)
    render_table(bear_df, "bear")

with tab_rvol:
    rvol_df = filtered.sort_values(by="rvol", ascending=False)
    render_table(rvol_df, "rvol")

with tab_all:
    render_table(filtered, "all")
    st.download_button(
        label="Download Filtered CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="nse_watchlist_movers.csv",
        mime="text/csv",
    )
