#G9.27.06.26_COMBAT_RADAR_MONITOR
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- SYSTEM INITIALIZATION ---
st.set_page_config(page_title="AESA Combat Trader v5.0", layout="wide", page_icon="⚡")

TRADES_FILE = "combat_missile_bay.json"

def load_missile_bay():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f: return json.load(f)
        except: return {"LOCKED_TARGETS": {}}
    return {"LOCKED_TARGETS": {}}

def save_missile_bay(data):
    with open(TRADES_FILE, "w") as f: json.dump(data, f)

# --- TACTICAL MARKET CLOCK ---
NSE_HOLIDAYS = [
    date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31),
    date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28),
    date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20),
    date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25)
]

def get_ist():
    return datetime.now() + timedelta(hours=5, minutes=30)

def query_radar_status():
    now = get_ist()
    if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
        return False, "📡 RADAR STANDBY (MARKET CLOSED)"
    start_time, end_time = now.replace(hour=9, minute=15, second=0), now.replace(hour=15, minute=30, second=0)
    if start_time <= now <= end_time: return True, "⚡ RADAR ACTIVE (MARKET LIVE)"
    return False, "📡 RADAR STANDBY (OUT OF OPERATIONS)"

if 'missile_bay' not in st.session_state:
    st.session_state.missile_bay = load_missile_bay()

if 'combat_stats' not in st.session_state:
    st.session_state.combat_stats = {"Kills": 0, "Ejections": 0}

# --- FLIGHT CONTROL PANEL (SIDEBAR) ---
with st.sidebar:
    st.header("🕹️ Flight Control Intercept")
    combat_capital = st.number_input("Payload Weight Allocation (₹)", min_value=1000, value=50000, step=5000)
    target_pct = st.slider("Target Yield (%)", 0.5, 5.0, 1.5) / 100
    sl_pct = st.slider("Ejection Range / Stop Loss (%)", 0.2, 3.0, 0.5) / 100
    
    st.markdown("---")
    st.subheader("🎯 Fire Control Avionics")
    min_roc = st.number_input("Min Velocity Threshold (ROC %)", value=0.75, step=0.05, format="%.2f")
    min_adx = st.slider("Min Propulsion Index (ADX Trend Strength)", 10, 50, 22)
    engagement_mode = st.selectbox("Engagement Protocol", ["All Vectors", "Interceptors Only (Buy)", "Bombers Only (Sell)"])
    
    st.markdown("---")
    raw_watchlist = "UPL, COALINDIA, POWERGRID, ITC, NCC, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, BIOCON, IRFC, JSWENERGY, RELIANCE, INFY, IOC, ADANIPORTS, TATAPOWER"
    user_input = st.text_area("Target Vector Coordinate Grid (Watchlist)", raw_watchlist)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🚨 PURGE ALL LOCKS & RESET SYSTEMS"):
        st.session_state.missile_bay = {"LOCKED_TARGETS": {}}
        st.session_state.combat_stats = {"Kills": 0, "Ejections": 0}
        if os.path.exists(TRADES_FILE): os.remove(TRADES_FILE)
        st.rerun()

# --- MISSION HUD BANNER ---
ist_now = get_ist()
radar_active, radar_status_text = query_radar_status()

# Dashboard Performance Metrics
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1: st.metric(label="System Status", value=radar_status_text)
with m_col2: st.metric(label="🎯 Confirmed Kills (Targets Hit)", value=f"{st.session_state.combat_stats['Kills']} Hits")
with m_col3: st.metric(label="🚨 Emergency Ejections (SL Hit)", value=f"{st.session_state.combat_stats['Ejections']} Losses")

# --- RADAR SIGNAL PROCESSING ENGINE ---
def sweep_airspace(data):
    scanned_vectors = []
    locked_targets = st.session_state.missile_bay["LOCKED_TARGETS"]
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in data or data[t_str].empty: continue
        df = data[t_str].dropna()
        if len(df) < 25: continue

        cmp = float(df['Close'].iloc[-1])
        c_open = float(df['Open'].iloc[-1])
        vol_avg = df['Volume'].rolling(10).mean().iloc[-1]
        current_vol = df['Volume'].iloc[-1]
        
        # 1. Radar Velocity (ROC)
        p5 = df['Close'].iloc[-6]
        roc_val = ((cmp - p5) / p5) * 100
        
        # 2. Thermal Signature Spike (Volume Surge)
        thermal_spike = current_vol > (vol_avg * 1.3)

        # 3. Flight Path Vector (Linear Regression Channel)
        y = df['Close'].tail(14).values
        slope, intercept = np.polyfit(np.arange(len(y)), y, 1)
        trajectory = "CLIMBING" if slope > 0 else "DIVING"
        
        # 4. Engine Propulsion Index (ADX Engine)
        high, low, close = df['High'].values, df['Low'].values, df['Close'].values
        prev_high, prev_low, prev_close = df['High'].shift(1).values, df['Low'].shift(1).values, df['Close'].shift(1).values
        tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        window = 14
        if len(df) >= window + 2:
            tr_s = pd.Series(tr).rolling(window).sum().values
            p_dm_s = pd.Series(plus_dm).rolling(window).sum().values
            m_dm_s = pd.Series(minus_dm).rolling(window).sum().values
            p_di = 100 * (p_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
            m_di = 100 * (m_dm_s / np.where(tr_s == 0, 1e-9, tr_s))
            adx = float(pd.Series(100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))).rolling(window).mean().values[-1])
        else:
            adx = 0.0

        # --- SYSTEM FIRE-CONTROL & ACQUISITION ---
        is_locked = symbol in locked_targets
        missile_status = "HOLDING PATTERN"
        fire_protocol = None
        
        if is_locked:
            missile_status = "🚀 MISSILE IN FLIGHT"
            lock_data = locked_targets[symbol]
            fire_protocol = lock_data['protocol']
            
            # Continuous Guidance Tracking Check
            if fire_protocol == "INTERCEPT" and cmp >= lock_data['kill_zone']:
                st.session_state.combat_stats["Kills"] += 1
                del st.session_state.missile_bay["LOCKED_TARGETS"][symbol]
                st.toast(f"🎯 DIRECT HIT! Vector {symbol} destroyed at target checkpoint.", icon="💥")
                save_missile_bay(st.session_state.missile_bay)
                continue
            elif fire_protocol == "INTERCEPT" and cmp <= lock_data['ejection_line']:
                st.session_state.combat_stats["Ejections"] += 1
                del st.session_state.missile_bay["LOCKED_TARGETS"][symbol]
                st.toast(f"🚨 MISSILE DEFLECTED! Emergency Ejection structural damage on {symbol}.", icon="🔥")
                save_missile_bay(st.session_state.missile_bay)
                continue
            elif fire_protocol == "BOMBER" and cmp <= lock_data['kill_zone']:
                st.session_state.combat_stats["Kills"] += 1
                del st.session_state.missile_bay["LOCKED_TARGETS"][symbol]
                st.toast(f"🎯 DIRECT HIT! Short Vector {symbol} neutralized successfully.", icon="💥")
                save_missile_bay(st.session_state.missile_bay)
                continue
            elif fire_protocol == "BOMBER" and cmp >= lock_data['ejection_line']:
                st.session_state.combat_stats["Ejections"] += 1
                del st.session_state.missile_bay["LOCKED_TARGETS"][symbol]
                st.toast(f"🚨 FLARE FLARE! Short Position blew through parameters on {symbol}.", icon="🔥")
                save_missile_bay(st.session_state.missile_bay)
                continue
                
        else:
            # AUTO-ENGAGE FIRE RADAR SIGNALS
            if thermal_spike and adx >= min_adx and abs(roc_val) >= min_roc:
                if cmp > c_open and trajectory == "CLIMBING":
                    fire_protocol = "INTERCEPT"
                    missile_status = "⚠️ LOCK ACQUIRED"
                elif cmp < c_open and trajectory == "DIVING":
                    fire_protocol = "BOMBER"
                    missile_status = "⚠️ LOCK ACQUIRED"

            if fire_protocol:
                payload_qty = int(combat_capital // cmp)
                kill_zone = cmp * (1 + target_pct) if fire_protocol == "INTERCEPT" else cmp * (1 - target_pct)
                ejection_line = cmp * (1 - sl_pct) if fire_protocol == "INTERCEPT" else cmp * (1 + sl_pct)
                
                st.session_state.missile_bay["LOCKED_TARGETS"][symbol] = {
                    'lock_price': cmp, 'kill_zone': kill_zone, 'ejection_line': ejection_line,
                    'protocol': fire_protocol, 'payload_qty': payload_qty, 'lock_time': ist_now.strftime("%H:%M:%S")
                }
                save_missile_bay(st.session_state.missile_bay)
                st.toast(f"🚀 MISSILE LAUNCHED: Locked on Target {symbol}!", icon="🦅")
                is_locked = True
                missile_status = "🚀 MISSILE IN FLIGHT"

        # Apply Dynamic Filter Controls
        if engagement_mode == "Interceptors Only (Buy)" and fire_protocol != "INTERCEPT": continue
        if engagement_mode == "Bombers Only (Sell)" and fire_protocol != "BOMBER": continue

        scanned_vectors.append({
            "Vector": ("⚡ " if is_locked else "📡 ") + symbol,
            "Protocol": "📈 INTERCEPT (BUY)" if fire_protocol == "INTERCEPT" else "📉 BOMBER (SELL)" if fire_protocol == "BOMBER" else "🔍 SCANNING",
            "Payload (Qty)": locked_targets[symbol]['payload_qty'] if is_locked else int(combat_capital // cmp),
            "Current Alt (CMP)": cmp,
            "Lock Radar Alt": locked_targets[symbol]['lock_price'] if is_locked else 0.0,
            "Ejection Line (SL)": locked_targets[symbol]['ejection_line'] if is_locked else 0.0,
            "Kill Zone (Target)": locked_targets[symbol]['kill_zone'] if is_locked else 0.0,
            "System Status": missile_status,
            "Velocity (ROC)": f"{roc_val:+.2f}%",
            "Propulsion (ADX)": f"{adx:.1f}",
            "Time of Lock": locked_targets[symbol]['lock_time'] if is_locked else "-",
            "InFlight": 1 if is_locked else 0
        })

    if not scanned_vectors: return pd.DataFrame()
    return pd.DataFrame(scanned_vectors).sort_values(by=["InFlight", "Velocity (ROC)"], ascending=False)

# --- EXECUTE ACTIVE DATA RADAR ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    airspace_raw_data = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except:
    airspace_raw_data = {}

df_radar = sweep_airspace(airspace_raw_data) if not isinstance(airspace_raw_data, dict) and not airspace_raw_data.empty else pd.DataFrame()

# --- DISPLAY HUDS ---
def highlight_missile_bays(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for idx, row in df.iterrows():
        if "MISSILE IN FLIGHT" in str(row['System Status']):
            bg = '#0f2d1e' if "INTERCEPT" in str(row['Protocol']) else '#3b0f0f'
            styles.loc[idx, :] = f'background-color: {bg}; color: #e0e0e0; font-weight: bold; border: 1px solid neon'
    return styles

st.markdown("---")
st.header("🪟 WEAPONS CONTROL BAY (LOCKED TARGET TRACKER)")

if not df_radar.empty:
    active_locks = df_radar[df_radar['InFlight'] == 1].drop(columns=["InFlight"])
    if not active_locks.empty:
        st.dataframe(
            active_locks.style.apply(highlight_missile_bays, axis=None).format({
                "Current Alt (CMP)": "₹{:.2f}", "Lock Radar Alt": "₹{:.2f}", "Ejection Line (SL)": "₹{:.2f}", "Kill Zone (Target)": "₹{:.2f}"
            }), use_container_width=True, hide_index=True
        )
    else:
        st.info("No hostile targets locked. Radar is actively sweeping coordinates...")
else:
    st.info("No targets loaded inside tracking computer array.")

st.markdown("---")
st.subheader("🖥️ MAIN HEADS-UP DISPLAY (AESA AIRSPACE RADAR)")
if not df_radar.empty:
    full_airspace = df_radar.drop(columns=["InFlight"])
    st.dataframe(
        full_airspace.style.format({
            "Current Alt (CMP)": "₹{:.2f}", 
            "Lock Radar Alt": lambda x: f"₹{x:.2f}" if x > 0 else "-",
            "Ejection Line (SL)": lambda x: f"₹{x:.2f}" if x > 0 else "-", 
            "Kill Zone (Target)": lambda x: f"₹{x:.2f}" if x > 0 else "-"
        }), use_container_width=True, hide_index=True
    )

# --- AVIONICS REFRESH RATE ---
time.sleep(60 if radar_active else 300)
st.rerun()
