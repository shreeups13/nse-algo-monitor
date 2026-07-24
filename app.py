import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# Set Page Config
st.set_page_config(page_title="NSE Pro Monitor v4.9", layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------
# 1. INITIALIZE SESSION STATE
# ----------------------------------------------------
DEFAULT_WATCHLIST = [
    "UPL", "COALINDIA", "POWERGRID", "ITC", "NCC", 
    "DELTACORP", "TATASTEEL", "WIPRO", "ONGC", 
    "HDFCLIFE", "HINDALCO", "BPCL", "ADANIPOWER", "FINPIPE", "CAMPUS"
]

if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()

# ----------------------------------------------------
# 2. ROBUST SCRAPER FUNCTION FOR GAINERS / LOSERS
# ----------------------------------------------------
def fetch_top_symbols(fetch_type="gainers", market="NSE"):
    """
    Fetches Top 30 Gainers or Losers using requests + BeautifulSoup
    Includes custom headers and fallback sources to prevent blocking.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    url_type = "price-gainers" if fetch_type == "gainers" else "price-losers"
    url = f"https://www.moneycontrol.com/india/stockmarket/{url_type}/nse/all/"
    
    extracted_symbols = []
    
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Locate market tables on Moneycontrol
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if cols:
                        link = cols[0].find("a")
                        if link and link.text:
                            # Extract clean symbol string
                            raw_name = link.text.strip()
                            clean_sym = re.sub(r'[^A-Za-z0-9]', '', raw_name).upper()
                            if len(clean_sym) > 1 and clean_sym not in extracted_symbols:
                                extracted_symbols.append(clean_sym)
                                
            if extracted_symbols:
                return extracted_symbols[:30], None
    except Exception as e:
        pass

    # Backup Fallback list if live fetch is blocked by network/proxy
    fallback_gainers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "BAJFINANCE", "LTIM", "AXISBANK", "TATAMOTORS", "MARUTI", "SUNPHARMA", "NTPC", "TITAN"]
    fallback_losers = ["TECHM", "DIVISLAB", "HEROMOTOCO", "EICHERMOT", "CIPLA", "BRITANNIA", "DRREDDY", "ULTRACEMCO", "GRASIM", "BAJAJFINSV"]
    
    fallback_list = fallback_gainers if fetch_type == "gainers" else fallback_losers
    return fallback_list, "Used fallback list due to live connection limits."

# ----------------------------------------------------
# 3. SIDEBAR CONTROLS
# ----------------------------------------------------
st.sidebar.title("🔥 Top 30 Gainers & Losers")
st.sidebar.caption("(Overall Equity Market)")

market_choice = st.sidebar.selectbox("Select Exchange Market", ["NSE", "BSE"])
fetch_mode = st.sidebar.radio("Fetch Type", ["gainers", "losers"], horizontal=True)

# AUTO-ADD BUTTON WITH MERGE LOGIC
if st.sidebar.button("📥 Fetch & Append to Watchlist", use_container_width=True):
    new_symbols, err = fetch_top_symbols(fetch_type=fetch_mode, market=market_choice)
    
    if new_symbols:
        # Merge new symbols into existing list without removing existing ones or adding duplicates
        current_set = set(st.session_state.watchlist)
        added_count = 0
        for sym in new_symbols:
            if sym not in current_set:
                st.session_state.watchlist.append(sym)
                current_set.add(sym)
                added_count += 1
                
        if err:
            st.sidebar.warning(f"Fetched {added_count} new symbols. ({err})")
        else:
            st.sidebar.success(f"Successfully added {added_count} new symbols!")
    else:
        st.sidebar.error("Could not fetch symbols at this moment.")

st.sidebar.markdown("---")
st.sidebar.subheader("Current Watchlist")

# Watchlist Text Area
watchlist_str = ", ".join(st.session_state.watchlist)
updated_text = st.sidebar.text_area(
    "Edit symbols manually (comma-separated):",
    value=watchlist_str,
    height=150
)

# Keep Session State in sync if user types directly into the box
parsed_watchlist = [s.strip().upper() for s in updated_text.split(",") if s.strip()]
st.session_state.watchlist = parsed_watchlist

# Reset Button
if st.sidebar.button("🗑️ Reset Watchlist to Default", use_container_width=True):
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
    st.rerun()

# ----------------------------------------------------
# 4. MAIN DASHBOARD CONTENT
# ----------------------------------------------------
st.title("📈 NSE Pro Monitor (Trend Shift Mode)")

st.info(f"**Active Symbols ({len(st.session_state.watchlist)}):** " + ", ".join(st.session_state.watchlist))

# Sample Data Display
st.subheader("Market Trend Analysis")

data = []
for symbol in st.session_state.watchlist:
    data.append({
        "Symbol": symbol,
        "Exchange": market_choice,
        "Trend": "Bullish Shift 🟢" if hash(symbol) % 2 == 0 else "Bearish Shift 🔴",
        "Entry": round((hash(symbol) % 1000) + 100.50, 2),
        "SL": round((hash(symbol) % 1000) + 95.00, 2)
    })

df = pd.DataFrame(data)
st.dataframe(df, use_container_width=True)
