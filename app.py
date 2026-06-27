#G9.09.06.26_SUPERSONIC_COMBAT_RADAR_FINAL
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import time
import json
import os

# --- SYSTEM INITIALIZATION ---
st.set_page_config(page_title="AESA Supersonic Terminal HUD v5.5", layout="wide", page_icon="🚀")

MISSILE_BAY_FILE = "supersonic_missile_bay.json"

def load_supersonic_bay():
    if os.path.exists(MISSILE_BAY_FILE):
        try:
            with open(MISSILE_BAY_FILE, "r") as f: return json.load(f)
        except: return {"ACTIVE_LOCKS": {}}
    return {"ACTIVE_LOCKS": {}}

def save_supersonic_bay(data):
    with open(MISSILE_BAY_FILE, "w") as f: json.dump(data, f)

# --- TACTICAL CLOCK & CALENDAR ---
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
    if start_time <= now <= end_time: return True, "🚀 ACTIVE HOMING REGIME (LIVE)"
    return False, "📡 RADAR STANDBY (OUT OF OPERATIONS)"

if 'supersonic_bay' not in st.session_state:
    st.session_state.supersonic_bay = load_supersonic_bay()

if 'combat_stats' not in st.session_state:
    st.session_state.combat_stats = {"Kills": 0, "Ejections": 0}

# --- AVIONICS FLIGHT PANEL (SIDEBAR) ---
with st.sidebar:
    st.header("🕹️ Flight Guidance Control")
    combat_capital = st.number_input("Payload Weight Allocation (₹)", min_value=1000, value=50000, step=5000)
    
    st.markdown("---")
    st.subheader("🎯 Active Radar Homing Scale")
    atr_target_mult = st.slider("Target Multiplier (ATR x)", 1.5, 5.0, 3.0, step=0.1)
    atr_sl_mult = st.slider("Ejection Multiplier (ATR x)", 0.5, 2.5, 1.0, step=0.1)
    
    st.markdown("---")
    st.subheader("📡 Filter Configurations")
    min_roc = st.number_input("Min Velocity (ROC %)", value=0.75, step=0.05, format="%.2f")
    min_adx = st.slider("Min Propulsion Engine (ADX)", 10, 50, 22)
    
    st.markdown("---")
    raw_watchlist = "UPL, COALINDIA, POWERGRID, ITC, NCC, TATASTEEL, WIPRO, ONGC, HDFCLIFE, HINDALCO, BPCL, ADANIPOWER, BIOCON, IRFC, JSWENERGY, RELIANCE, INFY, IOC, ADANIPORTS, TATAPOWER"
    user_input = st.text_area("Target Coordinate Grid Vector List", raw_watchlist)
    SYMBOLS = [s.strip().upper() for s in user_input.split(",") if s.strip()]
    
    if st.button("🚨 PURGE BAY & FLASH SYSTEM MEMORY"):
        st.session_state.supersonic_bay = {"ACTIVE_LOCKS": {}}
        st.session_state.combat_stats = {"Kills": 0, "Ejections": 0}
        if os.path.exists(MISSILE_BAY_FILE): os.remove(MISSILE_BAY_FILE)
        st.rerun()

# --- HEADER STATISTICS BANNER ---
ist_now = get_ist()
radar_active, radar_status_text = query_radar_status()

m_col1, m_col2, m_col3 = st.columns(3)
with m_col1: st.metric(label="Active System Guidance", value=radar_status_text)
with m_col2: st.metric(label="🎯 Impact Matrix (Kills)", value=f"{st.session_state.combat_stats['Kills']} Hits")
with m_col3: st.metric(label="🚨 Tactical Ejections (Losses)", value=f"{st.session_state.combat_stats['Ejections']} Aborts")

# --- CORE GUIDANCE CALCULATIONS ENGINE ---
def process_supersonic_radar(data):
    scanned_vectors = []
    active_locks = st.session_state.supersonic_bay["ACTIVE_LOCKS"]
    
    for symbol in SYMBOLS:
        t_str = f"{symbol}.NS"
        if t_str not in data or data[t_str].empty: continue
        df = data[t_str].dropna()
        if len(df) < 25: continue

        cmp = float(df['Close'].iloc[-1])
        c_open = float(df['Open'].iloc[-1])
        
        # 1. Volatility Flight Envelope (ATR 14 Computation)
        high_arr, low_arr, close_arr = df['High'].values, df['Low'].values, df['Close'].values
        prev_close_arr = df['Close'].shift(1).values
        tr = np.nanmax(np.vstack([high_arr - low_arr, np.abs(high_arr - prev_close_arr), np.abs(low_arr - prev_close_arr)]), axis=0)
        df['ATR'] = pd.Series(tr).rolling(14).mean().values
        atr_val = float(df['ATR'].iloc[-1])
        
        if atr_val <= 0: continue

        # 2. Tracking Velocity Engine (ROC)
        p5 = df['Close'].iloc[-6]
        roc_val = ((cmp - p5) / p5) * 100
        thermal_spike = df['Volume'].iloc[-1] > (df['Volume'].rolling(10).mean().iloc[-1] * 1.3)

        # 3. Macro Flight Trajectory (Linear Regression)
        y = df['Close'].tail(14).values
        slope, _ = np.polyfit(np.arange(len(y)), y, 1)
        trajectory = "CLIMBING" if slope > 0 else "DIVING"
        
        # 4. ADX Propulsion Core
        up_move = high_arr - df['High'].shift(1).values
        down_move = df['Low'].shift(1).values - low_arr
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr_s = pd.Series(tr).rolling(14).sum().values
        p_di = 100 * (pd.Series(plus_dm).rolling(14).sum().values / np.where(tr_s == 0, 1e-9, tr_s))
        m_di = 100 * (pd.Series(minus_dm).rolling(14).sum().values / np.where(tr_s == 0, 1e-9, tr_s))
        adx = float(pd.Series(100 * (np.abs(p_di - m_di) / np.where((p_di + m_di) == 0, 1e-9, (p_di + m_di)))).rolling(14).mean().values[-1])

        # --- TERMINAL HOMING FIRE CONTROLLER ---
        is_locked = symbol in active_locks
        guidance_state = "HOLDING PATTERN"
        fire_protocol = None
        progress_pct = 0.0
        
        if is_locked:
            lock_data = active_locks[symbol]
            fire_protocol = lock_data['protocol']
            entry_price = lock_data['intercept_alt']
            target_price = lock_data['kill_zone']
            current_sl = lock_data['adaptive_ejection']
            
            # Compute Mid-Flight Progress
            total_path = abs(target_price - entry_price)
            distance_covered = (cmp - entry_price) if fire_protocol == "INTERCEPT" else (entry_price - cmp)
            progress_pct = max(0.0, (distance_covered / total_path) * 100) if total_path > 0 else 0.0
            
            # Supersonic Auto-Correction (Terminal Homing Clamp at 70% Progress)
            if progress_pct >= 70.0 and not lock_data.get('terminal_lock_activated', False):
                # Pull SL past entry to lock in variation gains
                if fire_protocol == "INTERCEPT":
                    current_sl = entry_price + (atr_val * 0.2)
                else:
                    current_sl = entry_price - (atr_val * 0.2)
                st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]['adaptive_ejection'] = current_sl
                st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]['terminal_lock_activated'] = True
                save_supersonic_bay(st.session_state.supersonic_bay)

            guidance_state = "🎯 TERMINAL LOCK" if lock_data.get('terminal_lock_activated', False) else "🚀 MID-COURSE GUIDANCE"

            # Terminal Boundary Intercept Validations
            if fire_protocol == "INTERCEPT":
                if cmp >= target_price:
                    st.session_state.combat_stats["Kills"] += 1
                    del st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]
                    st.toast(f"💥 IMPACT! Vector {symbol} intercepted pinpoint targets.", icon="🎯")
                    save_supersonic_bay(st.session_state.supersonic_bay)
                    continue
                elif cmp <= current_sl:
                    st.session_state.combat_stats["Ejections"] += 1
                    del st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]
                    st.toast(f"🔥 ABORT! Missile ejected cleanly on {symbol} structural variation.", icon="🚨")
                    save_supersonic_bay(st.session_state.supersonic_bay)
                    continue
            elif fire_protocol == "BOMBER":
                if cmp <= target_price:
                    st.session_state.combat_stats["Kills"] += 1
                    del st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]
                    st.toast(f"💥 IMPACT! Short trajectory Vector {symbol} completely neutralized.", icon="🎯")
                    save_supersonic_bay(st.session_state.supersonic_bay)
                    continue
                elif cmp >= current_sl:
                    st.session_state.combat_stats["Ejections"] += 1
                    del st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol]
                    st.toast(f"🔥 ABORT! Reverse defensive flares triggered on Vector {symbol}.", icon="🚨")
                    save_supersonic_bay(st.session_state.supersonic_bay)
                    continue
        else:
            # SENSORS RADAR SIGNALS TRIGGER MATCH
            if thermal_spike and adx >= min_adx and abs(roc_val) >= min_roc:
                if cmp > c_open and trajectory == "CLIMBING":
                    fire_protocol = "INTERCEPT"
                    guidance_state = "⚠️ LOCK ACQUIRED"
                elif cmp < c_open and trajectory == "DIVING":
                    fire_protocol = "BOMBER"
                    guidance_state = "⚠️ LOCK ACQUIRED"

            if fire_protocol:
                payload_qty = int(combat_capital // cmp)
                kill_zone = cmp + (atr_val * atr_target_mult) if fire_protocol == "INTERCEPT" else cmp - (atr_val * atr_target_mult)
                adaptive_ejection = cmp - (atr_val * atr_sl_mult) if fire_protocol == "INTERCEPT" else cmp + (atr_val * atr_sl_mult)
                
                st.session_state.supersonic_bay["ACTIVE_LOCKS"][symbol] = {
                    'intercept_alt': cmp, 'kill_zone': kill_zone, 'adaptive_ejection': adaptive_ejection,
                    'protocol': fire_protocol, 'payload': payload_qty, 'lock_time': ist_now.strftime("%H:%M:%S"),
                    'terminal_lock_activated': False
                }
                save_supersonic_bay(st.session_state.supersonic_bay)
                st.toast(f"🚀 BRAHMOS LAUNCHED: Homing sequence configured on {symbol}!", icon="🦅")
                is_locked = True
                guidance_state = "🚀 MID-COURSE GUIDANCE"

        scanned_vectors.append({
            "Target Vector": ("⚡ " if is_locked else "📡 ") + symbol,
            "Guidance State": guidance_state,
            "Payload": active_locks[symbol]['payload'] if is_locked else int(combat_capital // cmp),
            "Last Alt (CMP)": cmp,
            "Intercept Alt": active_locks[symbol]['intercept_alt'] if is_locked else 0.0,
            "Adaptive Ejection (SL)": active_locks[symbol]['adaptive_ejection'] if is_locked else 0.0,
            "Kill Zone (Target)": active_locks[symbol]['kill_zone'] if is_locked else 0.0,
            "Airspace Noise (ATR)": atr_val,
            "Velocity (ROC)": f"{roc_val:+.2f}%",
            "Progress": f"{progress_pct:.1f}%" if is_locked else "-",
            "Protocol": fire_protocol if fire_protocol else "SCANNING",
            "InFlight": 1 if is_locked else 0
        })

    if not scanned_vectors: return pd.DataFrame()
    return pd.DataFrame(scanned_vectors).sort_values(by=["InFlight", "Airspace Noise (ATR)"], ascending=False)

# --- EXECUTE LIVE SWEEP DATA FEED ---
tickers = [f"{s}.NS" for s in SYMBOLS]
try:
    airspace_feed = yf.download(tickers, period='5d', interval='5m', group_by='ticker', auto_adjust=True, progress=False)
except:
    airspace_feed = {}

df_radar = process_supersonic_radar(airspace_feed) if not isinstance(airspace_feed, dict) and not airspace_feed.empty else pd.DataFrame()

# --- DISPLAY UI BAY INTERFACES ---
def render_hud_glowing_matrix(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for idx, row in df.iterrows():
        if "MID-COURSE" in str(row['Guidance State']):
            styles.loc[idx, :] = 'background-color: #12223a; color: #cbd5e1; font-weight: 500;'
        elif "TERMINAL LOCK" in str(row['Guidance State']):
            bg = '#062d1a' if row['Protocol'] == 'INTERCEPT' else '#451010'
            styles.loc[idx, :] = f'background-color: {bg}; color: #ffffff; font-weight: bold; border: 1px solid #38bdf8;'
    return styles

st.markdown("---")
st.header("🪟 ACTIVE MISSILE TRACKING BAY (LOCKED COORDINATES)")

if not df_radar.empty:
    active_tracking = df_radar[df_radar['InFlight'] == 1].drop(columns=["InFlight", "Protocol"])
    if not active_tracking.empty:
        st.dataframe(
            active_tracking.style.apply(render_hud_glowing_matrix, axis=None).format({
                "Last Alt (CMP)": "₹{:.2f}", "Intercept Alt": "₹{:.2f}", "Adaptive Ejection (SL)": "₹{:.2f}", "Kill Zone (Target)": "₹{:.2f}", "Airspace Noise (ATR)": "{:.2f}"
            }), use_container_width=True, hide_index=True
        )
    else:
        st.info("No active threats locked inside the weapon systems. Radar grid is sweeping clear airspace coordinates.")
else:
    st.info("Tactical avionics arrays disconnected or target coordinate grid unmapped.")

st.markdown("---")
st.subheader("📡 MAIN AIRSPACE VECTORS (COMPLETE SCANNING GRID)")
if not df_radar.empty:
    full_grid = df_radar.drop(columns=["InFlight", "Protocol"])
    st.dataframe(
        full_grid.style.format({
            "Last Alt (CMP)": "₹{:.2f}", 
            "Intercept Alt": lambda x: f"₹{x:.2f}" if x > 0 else "-",
            "Adaptive Ejection (SL)": lambda x: f"₹{x:.2f}" if x > 0 else "-", 
            "Kill Zone (Target)": lambda x: f"₹{x:.2f}" if x > 0 else "-",
            "Airspace Noise (ATR)": "{:.2f}"
        }), use_container_width=True, hide_index=True
    )

# --- AUTO REBOOT REFRESH TRACKING TACTIC ---
time.sleep(60 if radar_active else 300)
st.rerun()
