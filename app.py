import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="NSE Pro Monitor", layout="wide", page_icon="📈")

TRADES_FILE = "trade_history.json"

def load_persistent_trades():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_persistent_trades(trades):
    with open(TRADES_FILE, "w") as f: json.dump(trades, f)

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Strategy Settings")
    capital = st.number_input("Trading Capital (₹)", min_value=1000, value=50000)
    target_pct = st.slider("Target (%)", 0.5, 5.0, 1.0) / 100
    sl_pct = st.slider("Stop Loss (%)", 0.2, 2.0, 0.5) / 100
    
    st.markdown("---")
    # ADDED FULL STOCK LIST BELOW
    default_stocks = "UPL, COALINDIA, POWERGRID, ITC, NCC, DELTACORP, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, FINPIPE, CAMPUS, TRIVENI, BIOCON, IRFC, KIOCL, GPIL, JSWENERGY, DELHIVERY, REDINGTON, ADANIGREEN, AVANTIFEED, SJVN, NLCINDIA, STAR, RAILTEL, PETRONET, SUZLON, CENTURYPLY, IGL, PNCINFRA, STARCEMENT, PPLPHARMA, JWL, JINDWORLD, HINDCOPPER, RCF, TTML, VEDL, UNIONBANK, OIL, SAREGAMA, INFY, MUTHOOTFIN, NYKAA, RALLIS, NESTLEIND, KARURVYSYA, RELIANCE, IOC, PCBL, ADANIPORTS, TANLA, GRASIM, ENGINERSIN, FEDERALBNK, TRIDENT, MOTHERSON, AMBUJACEM, FINCABLES, NMDC, TATAPOWER, BBTC, ARVIND, BANDHANBNK, ABCAPITAL, HFCL, PFC, BEL, PNB, CGPOWER, CUB"
    user_input = st.text_area("Watchlist (Comma Separated)", default_stocks)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]

# --- 1. FETCH INDICES ---
ist_now = datetime.now() + timedelta(hours=5, minutes=30)
try:
    idx_raw = yf.download(["^NSEI", "^BSESN"], period="2d", interval="1m", progress=False)['Close']
    n_curr = idx_raw["^NSEI"].dropna().iloc[-1]
    s_curr = idx_raw["^BSESN"].dropna().iloc[-1]
    n_prev = idx_raw["^NSEI"].dropna().iloc[0]
    s_prev = idx_raw["^BSESN"].dropna().iloc[0]
    n_chg = ((n_curr - n_prev) / n_prev) * 100
    s_chg = ((s_curr - s_prev) / s_prev) * 100
    st.markdown(f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])")
except:
    st.markdown("### Indices: `Connecting to NSE...`")

st.subheader(f"IST: {ist_now.strftime('%H:%M:%S')} | 🟢 MARKET LIVE")

# --- 2. DATA FETCHING ---
def get_dashboard_data():
    results = []
    tickers = [f"{s}.NS" for s in SYMBOLS]
    try:
        data = yf.download(tickers, period='7d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
        
        for symbol in SYMBOLS:
            t_str = f"{symbol}.NS"
            if t_str not in data: continue
            df = data[t_str].dropna()
            if len(df) < 20: continue

            cmp = float(df['Close'].iloc[-1])
            
            y = df['Close'].tail(14).values
            slope, _ = np.polyfit(np.arange(len(y)), y, 1)
            lrc_dir = "UP" if slope > 0 else "DOWN"
            roc = ((cmp - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
            vol_surge = df['Volume'].iloc[-1] > (vol_avg * 1.2)

            prob_score = 0
            if vol_surge: prob_score += 1
            if abs(roc) > 0.5: prob_score += 1
            
            trade = st.session_state.active_trades.get(symbol)
            status = "WAITING"
            
            if trade:
                status = "IN TRADE"
                p_text = trade.get('prob_text', "MED")
                if (trade['type'] == 'BUY' and (cmp >= trade['target'] or cmp <= trade['sl'])) or \
                   (trade['type'] == 'SELL' and (cmp <= trade['target'] or cmp >= trade['sl'])):
                    del st.session_state.active_trades[symbol]
                    save_persistent_trades(st.session_state.active_trades)
            elif vol_surge:
                t_type = "BUY" if df['Close'].iloc[-1] > df['Open'].iloc[-1] else "SELL"
                if (t_type == "BUY" and lrc_dir == "UP") or (t_type == "SELL" and lrc_dir == "DOWN"):
                    prob_score += 1
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"
                entry = cmp
                target = entry * (1 + target_pct) if t_type == "BUY" else entry * (1 - target_pct)
                sl = entry * (1 - sl_pct) if t_type == "BUY" else entry * (1 + sl_pct)
                st.session_state.active_trades[symbol] = {
                    'entry': entry, 'target': target, 'sl': sl, 'type': t_type, 
                    'time': ist_now.strftime("%H:%M"), 'prob_text': p_text
                }
                save_persistent_trades(st.session_state.active_trades)
            else:
                p_text = "LOW" if prob_score <= 1 else "MED" if prob_score == 2 else "HIGH"

            results.append({
                "Stock": symbol, "Qty": int(capital // cmp), "CMP": cmp,
                "Entry": trade['entry'] if trade else 0.0,
                "Target": trade['target'] if trade else 0.0,
                "Prob": p_text,
                "SL": trade['sl'] if trade else 0.0,
                "Signal": f"LRC:{'↑' if slope > 0 else '↓'} | ROC:{roc:.2f}%",
                "Status": status, 
                "InTrade": 1 if trade else 0,
                "ROC_Val": abs(roc)
            })
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

# --- 3. RENDER ---
df_raw = get_dashboard_data()

if not df_raw.empty:
    df_sorted = df_raw.sort_values(by=["InTrade", "ROC_Val"], ascending=False).drop(columns=["InTrade", "ROC_Val"])
    
    def apply_cmp_background(df):
        style_df = pd.DataFrame('', index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            if row['Status'] == "IN TRADE" and row['Entry'] > 0:
                # Green background if Profit (CMP >= Entry), Red if Loss (CMP < Entry)
                bg_color = '#22c55e' if row['CMP'] >= row['Entry'] else '#ef4444'
                style_df.loc[i, 'CMP'] = f'background-color: {bg_color}; color: white; font-weight: bold'
        return style_df

    disp_df = df_sorted.copy()
    styled_view = disp_df.style.apply(apply_cmp_background, axis=None).format({
        "CMP": "{:.2f}", 
        "Entry": lambda x: f"{x:.2f}" if x > 0 else "-",
        "Target": lambda x: f"{x:.2f}" if x > 0 else "-",
        "SL": lambda x: f"{x:.2f}" if x > 0 else "-"
    })

    st.dataframe(styled_view, use_container_width=True, hide_index=True)
else:
    st.info("🔄 Synching Data...")

time.sleep(60)
st.rerun()
