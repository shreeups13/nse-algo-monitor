#G9.09.06.26_SUPERSONIC_TERMINAL_GUIDANCE
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- SUPERSONIC GUIDANCE COMPUTATION ---
def apply_terminal_guidance(df, base_capital=50000):
    """
    Implements Proportional Navigation using Average True Range (ATR) 
    to dynamically adjust for target variation and market noise.
    """
    if len(df) < 20:
        return pd.DataFrame()
        
    df = df.copy()
    
    # 1. Calculate True Range & ATR (Missile Tracking Envelope)
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    prev_close = df['Close'].shift(1).values
    
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
    df['ATR'] = pd.Series(tr).rolling(14).mean().values
    
    # Baseline CMP and Indicators
    cmp = float(df['Close'].iloc[-1])
    atr_val = float(df['ATR'].iloc[-1])
    
    # 2. Dynamic Weapon Calibration (No rigid percentages)
    # Target and SL adapt dynamically to the stock's volatility variance
    atr_multiplier_target = 3.0  # Seek 3x the standard noise variance
    atr_multiplier_sl = 1.0      # Eject if asset breaches 1x standard deviation
    
    simulated_entry = cmp
    dynamic_target = simulated_entry + (atr_val * atr_multiplier_target)
    dynamic_sl = simulated_entry - (atr_val * atr_multiplier_sl)
    
    # 3. Vector Mid-Flight Auto-Correction Logic (Terminal Trailing)
    current_progress_pct = ((cmp - simulated_entry) / (dynamic_target - simulated_entry)) if dynamic_target != simulated_entry else 0
    
    if current_progress_pct >= 0.70:
        # Missile is within terminal homing distance -> Clamp Ejection Line to lock profit/break-even
        adjusted_sl = simulated_entry + (atr_val * 0.2) 
        guidance_state = "🎯 TERMINAL HOMING LOCK (SL Dragged Forward)"
    else:
        adjusted_sl = dynamic_sl
        guidance_state = "🚀 MID-COURSE GUIDANCE ACTIVE"
        
    return {
        "CMP": cmp,
        "ATR_Variance": atr_val,
        "Dynamic_Target": dynamic_target,
        "Adjusted_Ejection_Line": adjusted_sl,
        "Guidance_System": guidance_state
    }
