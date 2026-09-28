#NSE pro V5.1 28.09.26
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor v5.1 (Early Breakout Edition)", layout="wide", page_icon="📈")

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
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save trades: {e}")

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
    start_time = now.replace(hour=9, minute=15, second=0)
    end_time = now.replace(hour=15, minute=30, second=0)
    if start_time <= now <= end_time:
        return True, "🟢 MARKET LIVE"
    return False, "🔴 MARKET CLOSED (OUT OF HOURS)"

# --- INITIALIZE STATE ---
if 'dual_trades' not in st.session_state:
    st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ General Settings")
    capital = st.number_input("Capital per Trade (₹)", min_value=1000, value=70000, step=1000)
    use_atr_risk = st.checkbox("Use Dynamic ATR Risk", value=True)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.5) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 3.0, 0.6) / 100
    
    st.markdown("---")
    st.subheader("⚡ Early Breakout (Whirlpool Scanner)")
    enable_early_breakout = st.checkbox("Enable Early Squeeze Detection", value=True)
    roc_period = st.number_input("ROC Period", value=9, step=1)
    min_vol_spike = st.slider("Min Volume Spike Multiplier", 1.5, 4.0, 2.0, step=0.1)
    
    st.markdown("---")
    st.subheader("🎯 Custom Filters")
    filter_roc_gt = st.number_input("ROC Greater Than (>) %", value=1.00, step=0.01, format="%.2f")
    filter_roc_lt = st.number_input("ROC Less Than (<) %", value=1.00, step=0.01, format="%.2f")
    
    filter_trade_type = st.selectbox("Trade Type Filter", ["All", "S.Buy Only", "S.Sell Only", "S.Buy & S.Sell", "Blank Only"])
    filter_status = st.selectbox("Status Filter", ["All", "Buy", "Sell", "Buy & Sell", "In Trade", "Waiting"])
    
    st.markdown("---")
    full_list = "WHIRLPOOL,AASTHA,ABCAPITAL,ACMESOLAR,ADANIPOWER,ADSL,AEQUS,AGIIL,AHCL,ALGOQUANT,AMBUJACEM,ANANTRAJ,ANGELONE,APOLLO,APTUS,ARDEE,ARCIL,ARFIN,ARTEMISMED,AVANTEL,AWL,AYE,BAJAJHFL,BALRAMCHIN,BANDHANBNK,BANKBARODA,BANKINDIA,BEL,BELRISE,BHEL,BIOCON,BODALCHEM,BOROLTD,BPCL,CANBK,CAPILLARY,CASTROLIND,CENTRALBK,CESC,COALINDIA,CMPDI,COMSYN,CONFIPET,CORDELIA,CROMPTON,CUB,CUBEXTUB,CUPID,DALMIASUG,DCMSRIND,DCW,DEEPA,DELTACORP,DELHIVERY,DEVYANI,DHAMPURSUG,DLF,DWARKESH,EDELWEISS,EIEL,EMAMILTD,EMBDL,EMIL,EMMVEE,ENGINERSIN,EPL,EQUITASBNK,ETERNAL,EXCELSOFT,EXIDEIND,FCL,FEDDERSHOL,FEDERALBNK,FILATEX,FIRSTCRY,GAIL,GLASSWALL,GKSL,GOLD1,GOLDBEES,GOLDIETF,GRAUWEIL,GMRP&UI,GMRAIRPORT,GNFC,GREAVESCOT,GROWW,HDFCBSE500,HDFCGOLD,HDFCLIFE,HDFCSILVER,HDFCSML250,HEGAM,HEROMOTORS,HIMATSEIDE,HINDCOPPER,HINDPETRO,HINDZINC,HORIZONIND,HSCL,HTEL,ICICIPRULI,IDBI,IDFCFIRSTB,IFCI,IEX,INDGN,INDIAGLYCO,INDOTHAI,INDUSTOWER,INOXWIND,IOB,IOLCP,IOC,IRCON,IREDA,IRFC,ITCHOTELS,ITC,ITBEES,J&KBANK,JAMNAAUTO,JAYBARMARU,JAYNECOIND,JINDALSAW,JINDWORLD,JNPR,JSFB,JSWCEMENT,JSWINFRA,JSWENERGY,JTLIND,JMFINANCIL,KALYANKJIL,KAPSTON,KARAMTARA,KARURVYSYA,KISSHT,KMSUGAR,KOTAKBANK,KPIGREEN,KPITTECH,KWIL,LALITHAA,LCCPROJECT,LEAPIND,LENSKART,LEMONTREE,LICHSGFIN,LICI,LIQUIDCASE,LCL,LLOYDSENGG,LLOYDSENT,LTF,LUMINO,MAHABANK,MANAPPURAM,MANINFRA,MANALIPETC,MARKSANS,MARINE,MARSONS,MASPTOP50,MAWANASUG,M&MFIN,MEESHO,MOL,MONQ50,MOREPENLAB,MOTHERSON,MPIMANIPAL,MRPL,MSUMI,MUKANDLTD,NATIONALUM,NAZARA,NBCC,NCC,NEXT50IETF,NHPC,NIACL,NIFTYBEES,NIVABUPA,NMDC,NOCIL,NSLNISP,NTPC,NTPCGREEN,NYKAA,ONEPOINT,ONGC,OLAELEC,PAISALO,PARACABLES,PARADEEP,PARAGMILK,PATANJALI,PENIND,PFOCUS,PINELABS,PNB,PNCINFRA,POONAWALLA,POWERGRID,PPLPHARMA,PRANAV,PRIORITY,PROTEAN,PROZONER,PVP,PWL,QUADFUTURE,QUESS,RATNAVEER,RBA,RECLTD,REDINGTON,RENTOMOJO,REMSONSIND,RESPONIND,RIR,RBLBANK,ROLEXRINGS,RVNL,SAGILITY,SAIL,SAMMAANCAP,SAMBHV,SBC,SDBL,SETFGOLD,SHADOWFAX,SHANTIGOLD,SHAREINDIA,SHIPROCKET,SHOPERSTOP,SHRINGARMS,SILVERBEES,SILVERIETF,SJVN,SKYWAYS,SSWL,SPARC,STARHEALTH,STEELCAS,STLNETWORK,SOUTHBANK,SUZLON,SWIGGY,SUNFLAG,TATACAP,TATACHEM,TATAPOWER,TATASTEEL,TEXRAIL,TFCILTD,TEMBO,TEMPSENS,TECHNOCRAF,TGVSL,TI,TIMETECHNO,TMCV,TNPETRO,TRIVENI,TURTLEMINT,TTML,UGARSUGAR,UNIONBANK,UNITEDPOLY,UPL,URBANCO,UTTAMSUGAR,VAML,VASCONEQ,VBL,VEDL,VEDPOWER,VIDYAWIRES,VIKRAN,VIYASH,VISL,VMM,VOGL,WEBELSOLAR,WELSPUNLIV,WIPRO,ZEEL,ZENSARTECH"
    user_input = st.text_area("Watchlist", full_list)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🗑️ Reset All Trades"):
        st.session_state.dual_trades = {"regular": {}, "reversed": {}}
        if os.path.exists(TRADES_FILE):
            os.remove(TRADES_FILE)
        st.rerun()

# --- MARKET DATA FETCHING ---
ist_now = get_ist()
open_status, status_text = is_market_open()

@st.cache_data(ttl=30)
def fetch_market_data(tickers):
    if not tickers:
        return pd.DataFrame()
    return yf.download(tickers, period='2d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)

# --- DETECT EARLY BREAKOUT PATTERN ---
def check_early_breakout(df, roc_p=9, vol_thresh=2.0):
    if len(df) < 25:
        return False, 0.0, "NORMAL"
    
    close = df['Close']
    volume = df['Volume']
    
    # 1. Calculate Custom ROC(9)
    p_prev = close.shift(roc_p)
    roc_series = ((close - p_prev) / p_prev) * 100
    current_roc = float(roc_series.iloc[-1])
    prev_roc = float(roc_series.iloc[-2])
    
    # 2. ROC Acceleration Spike (Detecting rapid curve up)
    roc_diff = current_roc - prev_roc
    
    # 3. Bollinger Band Breakout Signal
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_bb = sma20 + (2.0 * std20)
    lower_bb = sma20 - (2.0 * std20)
    
    bandwidth = (upper_bb - lower_bb) / sma20
    is_bb_squeeze = float(bandwidth.iloc[-2]) < float(bandwidth.rolling(20).mean().iloc[-1])
    
    cmp = float(close.iloc[-1])
    vol_avg = float(volume.rolling(20).mean().iloc[-1])
    curr_vol = float(volume.iloc[-1])
    
    vol_surge = curr_vol >= (vol_avg * vol_thresh)
    
    # Early Bullish Breakout Condition
    is_bullish_early = (cmp > upper_bb.iloc[-1]) and (roc_diff > 1.2) and vol_surge and (current_roc > 1.0)
    # Early Bearish Breakdown Condition
    is_bearish_early = (cmp < lower_bb.iloc[-1]) and (roc_diff < -1.2) and vol_surge and (current_roc < -1.0)
    
    if is_bullish_early:
        return True, current_roc, "🚀 EARLY BREAKOUT (BUY)"
    elif is_bearish_early:
        return True, current_roc, "📉 EARLY BREAKDOWN (SELL)"
    
    return False, current_roc, "NORMAL"

# --- CALCULATION LOGIC CORE ---
def process_strategy(data, is_reversed=False):
    if data.empty:
        return pd.DataFrame()
    results = []
    strategy_key = "reversed" if is_reversed else "regular"
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        
        if isinstance(data.columns, pd.MultiIndex):
            if t_str not in data.columns.levels[0]:
                continue
            df = data[t_str].dropna(subset=['Close', 'Open', 'High', 'Low'])
        else:
            df = data.dropna(subset=['Close', 'Open', 'High', 'Low'])

        if len(df) < 30:
            continue

        cmp = float(df['Close'].iloc[-1])
        c_open = float(df['Open'].iloc[-1])
        curr_high = float(df['High'].iloc[-1])
        curr_low = float(df['Low'].iloc[-1])
        
        sigs = []
        prob_score = 0
        
        # Check Early Squeeze Breakout Condition
        early_found, roc9_val, early_label = check_early_breakout(df, roc_p=roc_period, vol_thresh=min_vol_spike)
        
        if enable_early_breakout and early_found:
            sigs.append(f"⚡ROC(9):{roc9_val:+.2f}%")
            prob_score += 2

        # Standard Indicators
        vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
        vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.3)
        
        # ATR Calculation
        tr = np.maximum(df['High'] - df['Low'], np.maximum(np.abs(df['High'] - df['Close'].shift(1)), np.abs(df['Low'] - df['Close'].shift(1))))
        current_atr = float(pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().iloc[-1])

        trade = st.session_state.dual_trades[strategy_key].get(symbol)
        status = "WAITING"
        e_time = ist_now.strftime("%H:%M")
        t_type = trade.get('type') if trade else None
        
        if trade:
            status = "IN TRADE"
            e_time = trade.get('time', e_time)
            p_text = trade.get('prob_text', "MED")
            
            hit_target = (trade['type'] == 'BUY' and curr_high >= trade['target']) or \
                         (trade['type'] == 'SELL' and curr_low <= trade['target'])
            hit_sl = (trade['type'] == 'BUY' and curr_low <= trade['sl']) or \
                     (trade['type'] == 'SELL' and curr_high >= trade['sl'])
            
            if hit_target or hit_sl:
                del st.session_state.dual_trades[strategy_key][symbol]
                save_persistent_trades(st.session_state.dual_trades)
                
        elif (vol_surge or early_found):
            if "BUY" in early_label:
                t_type, status = ("BUY", "🚀 EARLY BUY") if not is_reversed else ("SELL", "❄️ SELL")
                prob_score += 2
            elif "SELL" in early_label:
                t_type, status = ("SELL", "📉 EARLY SELL") if not is_reversed else ("BUY", "🔥 BUY")
                prob_score += 2
            elif cmp > c_open:
                t_type, status = ("BUY", "🔥 BUY") if not is_reversed else ("SELL", "❄️ SELL")
            elif cmp < c_open:
                t_type, status = ("SELL", "❄️ SELL") if not is_reversed else ("BUY", "🔥 BUY")

            if t_type:
                p_text = "HIGH" if prob_score >= 2 else "MED"
                entry = cmp
                
                if use_atr_risk and current_atr > 0:
                    target = entry + (2.0 * current_atr) if t_type == "BUY" else entry - (2.0 * current_atr)
                    sl = entry - (0.8 * current_atr) if t_type == "BUY" else entry + (0.8 * current_atr)
                else:
                    target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                    sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                
                st.session_state.dual_trades[strategy_key][symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': e_time, 'prob_text': p_text
                }
                save_persistent_trades(st.session_state.dual_trades)
        else:
            p_text = "LOW" if prob_score <= 1 else "MED"

        trade_cond = "S.Buy" if ("BUY" in status or "EARLY BUY" in status) else "S.Sell" if ("SELL" in status or "EARLY SELL" in status) else "-"

        # Filter Application
        if filter_trade_type == "S.Buy Only" and trade_cond != "S.Buy":
            continue
        if filter_trade_type == "S.Sell Only" and trade_cond != "S.Sell":
            continue

        results.append({
            "Stock": ("⚡ " if early_found else "🟢 ") + symbol, 
            "Trade": trade_cond, 
            "Qty": int(capital // cmp), 
            "CMP": cmp, 
            "Entry": trade['entry'] if trade else 0.0, 
            "SL": trade['sl'] if trade else 0.0,
            "Target": trade['target'] if trade else 0.0, 
            "A/D Trend": early_label if early_found else "Continuous", 
            "Signal": " | ".join(sigs) if sigs else "Standard", 
            "Status": status, 
            "Prob": p_text, 
            "Time": e_time, 
            "TradeType": t_type
        })

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)

# --- EXECUTE DISPLAY ---
tickers = [f"{s}.NS" for s in SYMBOLS]
raw_market_data = fetch_market_data(tickers)

df_reg = process_strategy(raw_market_data, is_reversed=False)

st.header("⚡ EARLY BREAKOUT & STANDARD MONITOR")
if not df_reg.empty:
    st.dataframe(df_reg, use_container_width=True, hide_index=True)
else:
    st.caption("No early breakout patterns detected in watchlist.")

time.sleep(60 if open_status else 300)
st.rerun()
