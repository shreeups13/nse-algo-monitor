from datetime import date, datetime, timedelta
import json
import os
import time
import numpy as np
import pandas as pd
import streamlit as st

# --- CONFIGURATION ---
st.set_page_config(
    page_title="NSE Pro Monitor v5.0 (Trade Refinement Engine)",
    layout="wide",
    page_icon="📈",
)

TRADES_FILE = "trade_history_dual_refined.json"


def load_persistent_trades():
  if os.path.exists(TRADES_FILE):
    try:
      with open(TRADES_FILE, 'r') as f:
        return json.load(f)
    except:
      return {'regular': {}, 'reversed': {}}
  return {'regular': {}, 'reversed': {}}


def save_persistent_trades(trades):
  with open(TRADES_FILE, 'w') as f:
    json.dump(trades, f)


# --- MARKET CALENDAR 2026 ---
NSE_HOLIDAYS = [
    date(2026, 1, 26),
    date(2026, 3, 3),
    date(2026, 3, 26),
    date(2026, 3, 31),
    date(2026, 4, 3),
    date(2026, 4, 14),
    date(2026, 5, 1),
    date(2026, 5, 28),
    date(2026, 6, 26),
    date(2026, 9, 14),
    date(2026, 10, 2),
    date(2026, 10, 20),
    date(2026, 11, 10),
    date(2026, 11, 24),
    date(2026, 12, 25),
]


def get_ist():
  return datetime.now() + timedelta(hours=5, minutes=30)


def is_market_open():
  now = get_ist()
  if now.weekday() >= 5 or now.date() in NSE_HOLIDAYS:
    return False, '🔴 MARKET CLOSED (WEEKEND/HOLIDAY)'
  start_time, end_time = now.replace(hour=9, minute=15, second=0), now.replace(
      hour=15, minute=30, second=0
  )
  if start_time <= now <= end_time:
    return True, '🟢 MARKET LIVE'
  return False, '🔴 MARKET CLOSED (OUT OF HOURS)'


# --- INITIALIZE STATE FOR BOTH STRATEGIES ---
if 'dual_trades' not in st.session_state:
  st.session_state.dual_trades = load_persistent_trades()

# --- SIDEBAR ---
with st.sidebar:
  st.header('⚙️ General Settings & Risk')
  capital = st.number_input('Capital (₹)', min_value=1000, value=50000, step=5000)

  st.markdown('---')
  st.subheader('🎯 Custom Filters')
  filter_min_price = st.number_input(
      'Min Stock Price (₹)', min_value=0.0, value=30.0, step=10.0, format='%.2f'
  )
  filter_max_price = st.number_input(
      'Max Stock Price (₹)',
      min_value=0.0,
      value=5000.0,
      step=100.0,
      format='%.2f',
  )

  st.markdown('**📈 Positive ROC Range (%) [10-Period]**')
  filter_pos_roc_min = st.number_input(
      'Pos ROC Min', value=1.36, step=0.05, format='%.2f'
  )
  filter_pos_roc_max = st.number_input(
      'Pos ROC Max', value=10.0, step=0.1, format='%.2f'
  )

  st.markdown('**📉 Negative ROC Range (%) [10-Period]**')
  filter_neg_roc_min = st.number_input(
      'Neg ROC Min', value=-10.0, step=0.1, format='%.2f'
  )
  filter_neg_roc_max = st.number_input(
      'Neg ROC Max', value=-1.36, step=0.05, format='%.2f'
  )

  filter_trade_type = st.selectbox(
      'Trade Type Filter',
      ['All', 'S.Buy Only', 'S.Sell Only', 'S.Buy & S.Sell', 'Blank Only'],
  )
  filter_status = st.selectbox(
      'Status Filter',
      ['All', 'Buy', 'Sell', 'Buy & Sell', 'In Trade', 'Waiting'],
  )

  st.markdown('---')
  st.subheader('🛠️ Refinement Filters')
  use_htf_ema = st.checkbox(
      'HTF Trend Filter (Price > 50 & 200 EMA)', value=True
  )
  use_atr_volatility = st.checkbox(
      'Volatility Filter (ATR14 > 30d Avg)', value=True
  )
  use_demand_zone = st.checkbox(
      'Demand Zone Equilibrium Pullback (15m)', value=True
  )

  st.markdown('---')
  full_list = (
      'KOTAKBANK,HDFCBANK,RELIANCE,BSE,ICICIBANK,TARIL,M&M,INFY,BAJAJ-AUTO,'
      'POLICYBZR,MARUTI,ADANIENSOL,BHARTIARTL,ETERNAL,AXISBANK,TATASTEEL,LT,'
      'ADANIGREEN,CUPID,IDEA,APOLLOHOSP,TCS,SBIN,ADANIPOWER,MCX,COFORGE,'
      'ULTRACEMCO,WELCORP,ADANIENT,JIOFIN,ATHERENERG,EICHERMOT,SBILIFE,HINDALCO,'
      'ENRIN,HFCL,BAJFINANCE,WELSPUNLIV,BHEL,FORTIS,SHRIRAMFIN,STLTECH,DIVISLAB,'
      'MAXHEALTH,TVSMOTOR,SAIL,POWERINDIA,RITES,HEROMOTOCO,TDPOWERSYS,HCLTECH,'
      'TMPV,ITC,KALYANKJIL,SUNPHARMA,DLF,GRASIM,TECHM,CGPOWER,BAJAJFINSV,'
      'SOLARINDS,BEL,JSWSTEEL,AZAD,ADANIPORTS,POLYCAB,HYUNDAI,MOTHERSON,'
      'INDUSTOWER,VBL,FEDERALBNK,SUNTV,LEMONTREE,LENSKART,APLAPOLLO,HAL,NETWEB,'
      'GVT&D,DIXON,SWIGGY,SYRMA,KAYNES,GROWW,PAYTM,NTPC,COALINDIA,DRREDDY,TITAN,'
      'HINDCOPPER,PFC,ASHOKLEY,LICHSGFIN,TMCV,WIPRO,INDIGO,ONGC,ZYDUSLIFE,'
      'INDHOTEL,LAURUSLABS,VAML,POWERGRID,SONACOMS,IFCI,CHOLAFIN,PERSISTENT,'
      'NAUKRI,RECLTD,MPHASIS,HDFCAMC,VEDL,NYKAA,CHENNPETRO,DMART,LODHA,AUBANK,'
      'ENGINERSIN,HINDUNILVR,APARINDS,ASIANPAINT,MANAPPURAM,PINELABS,TRENT,IRCON,'
      'LICI,IDBI,GLENMARK,MTARTECH,RBLBANK,BOSCHLTD,BHARATFORG,HDFCLIFE,'
      'NESTLEIND,MRPL,HAVELLS,BANKBARODA,SUZLON,PRESTIGE,OFSS,OLAELEC,'
      'HINDPETRO,FORCEMOT,WAAREEENER,IDFCFIRSTB,BANDHANBNK,SANSERA,LTM,'
      'CUMMINSIND,LTF,ABCAPITAL,ANGELONE,RADICO,SCHNEIDER,AUROPHARMA,LLOYDSME,'
      'HINDZINC,TATACONSUM,BRITANNIA,TORNTPHARM,BPCL,YESBANK,LUPIN,JKCEMENT,'
      'CANBK,CDSL,ABB,WOCKPHARMA,KIRLOSENG,IOC,MFSL,MOTILALOFS,INDUSINDBK,'
      'NATIONALUM,PATANJALI,ALKEM,MUTHOOTFIN,NEULANDLAB,TATAPOWER,PAGEIND,'
      'AEGISLOG,GMRAIRPORT,NUVAMA,KEI,BLUESTARCO,AMBUJACEM,MARICO,MEESHO,'
      'MAZDOCK,INOXINDIA,UNITDSPR,UNIONBANK,DATAPATTNS,SHREECEM,UPL,NMDC,'
      'PIDILITIND,PNB,360ONE,CIPLA,RVNL,GRAPHITE,ACUTAAS,GRSE,PFOCUS,PNBHOUSING,'
      'JSWINFRA,VMM,GAIL,REDINGTON,TIINDIA,PREMIERENE,CUB,LALPATHLAB,HBLENGINE,'
      'ASTERDM,PHOENIXLTD,MANKIND,IIFL,CAMS,TATAELXSI,BDL,KARURVYSYA,ZEEL,OIL,'
      'IRFC,M&MFIN,KPITTECH,EXIDEIND,THERMAX,LGEINDIA,RRKABEL,HSCL,JINDALSTEL,'
      'GLAND,COCHINSHIP,BIOCON,DABUR,CROMPTON,SIEMENS,WHIRLPOOL,SAMMAANCAP,'
      'ONESOURCE,JSWENERGY,BELRISE,SAILIFE,ANANTRAJ,ESCORTS,UNOMINDA,GESHIP,'
      'CARTRADE,AMBER,NCC,FINCABLES,SRF,TEGA,TEJASNET,VOGL,EMAMILTD,SHRIPISTON,'
      'HONASA,NAM-INDIA,ZENSARTECH,GODREJPROP,KAJARIACER,TATACAP,NHPC,'
      'NAVINFLUOR,MAHABANK,TATACHEM,ABDL,VISL,COLPAL,PWL,KFINTECH,PPLPHARMA,'
      'GODREJCP,CGCL,IRCTC,JUBLFOOD,OLECTRA,INOXWIND,BALKRISIND,VOLTAS,'
      'FLUOROCHEM,STARHEALTH,JYOTICNC,KIMS,GMDCLTD,CYIENT,GRANULES,IPCALAB,'
      'AETHER,JPPOWER,PIRAMALFIN,VEDPOWER,ANANDRATHI,RKFORGE,BBOX,NATCOPHARM,'
      'IREDA,JINDALSAW,URBANCO,ACE,CLEANMAX,SUPREMEIND,JSL,CASTROLIND,RPOWER,'
      'J&KBANK,BANKINDIA,DELHIVERY,ANTHEM,SBICARD,CMPDI,BALRAMCHIN,MSUMI,'
      'INDIANB,TBOTEK,AEGISVOPAK,HUDCO,JWL,SHYAMMETL,SAGILITY,OBEROIRLTY,'
      'MEDANTA,PGEL,GODFRYPHLP,PRIVISCL,GABRIEL,PETRONET,NBCC,ABREL,'
      'CARBORUNIV,ACMESOLAR,ATGL,BAJAJHFL,TATATECH,CPPLUS,NH,ELECON,GPIL,MRF,'
      'EMMVEE,CREDITACC,BAJAJHLDNG,BSOFT,CCL,COROMANDEL,GRAVITA,NLCINDIA,'
      'CAPLIPOINT,ASTRAL,ZENTEC,SCI,BEML,CONCOR,PVRINOX,ARE&M,FIRSTCRY,ITCHOTELS,'
      'SUMICHEM,NUVOCO,THANGAMAYL,CRAFTSMAN,APTUS,AWL,ZFCVINDIA,TENNIND,IEX,'
      'POONAWALLA,IGL,MINDACORP,KSB,AAVAS,LTFOODS,ENDURANCE,CHOLAHLDNG,PTCIL,'
      'CHOICEIN,COHANCE,TITAGARH,TTML,CANFINHOME,DEEPAKFERT,NIACL,NSLNISP,PCBL,'
      'APOLLOTYRE,PIIND,RAINBOW,HONAUT,FIVESTAR,AADHARHFC,ABSLAMC,HDBFS,'
      'LINDEINDIA,AJANTPHARM,VIJAYA,PARADEEP,IKS,ANURAS,AFFLE,CEMPRO,LTTS,'
      'ELGIEQUIP,SJVN,RUBICON,TRITURBINE,CLEAN,JMFINANCIL,CESC,DEEPAKNTR,MGL,KEC,'
      'TATACOMM,GICRE,AVANTIFEED,EIDPARRY,KIRLOSBROS,AARTIIND,JAINREC,RAILTEL,'
      'JBMA,JSWCEMENT,USHAMART,HOMEFIRST,GLAXO,FRACTAL,SWANCORP,CONCORDBIO,'
      'ECLERX,TORNTPOWER,NTPCGREEN,SYNGENE,NAVA,ABBOTINDIA,IRB,HEGAM,'
      'CHAMBLFERT,BRIGADE,BERGEPAINT,ACC,TATAINVEST,BLS,SUNDARMFIN,UBL,'
      'SCHAEFFLER,JKTYRE,SIGNATURE,INTELLECT,FSL,RHIM,BHARTIHEXA,CEATLTD,'
      'TECHNOE,BHARATCOAL,KPIL,JUBLINGREA,GILLETTE,POLYMED,CRISIL,CENTRALBK,'
      'ASAHIINDIA,TIMKEN,VTL,EMCURE,ATUL,DEVYANI,DALBHARAT,HEXT,AIIL,AIAENG,'
      'KPRMILL,GODREJIND,SOBHA,AFCONS,SARDAEN,INDIAMART,CIEINDIA,UCOBANK,IOB,'
      'BATAINDIA,IGIL,ZYDUSWELL,FACT,INDIACEM,RAMCOCEM,CANHLIFE,TRIDENT,UTIAMC,'
      'MMTC,EIHOTEL,DOMS,ITI,GALLANTT'
  )
  user_input = st.text_area('Watchlist Tickers', full_list, height=120)
  SYMBOLS = [s.strip().upper() for s in user_input.split(',') if s.strip()]

  if st.button('🗑️ Reset All Trades'):
    st.session_state.dual_trades = {'regular': {}, 'reversed': {}}
    if os.path.exists(TRADES_FILE):
      os.remove(TRADES_FILE)
    st.rerun()

# --- HEADER (INDICES) ---
ist_now = get_ist()
open_status, status_text = is_market_open()

try:
  indices = yf.download(
      ['^NSEI', '^BSESN'], period='2d', interval='5m', progress=False
  )
  if not indices.empty and 'Close' in indices.columns:
    n_series = indices['Close']['^NSEI'].dropna()
    s_series = indices['Close']['^BSESN'].dropna()

    n_curr, n_prev = n_series.iloc[-1], n_series.iloc[0]
    s_curr, s_prev = s_series.iloc[-1], s_series.iloc[0]

    n_chg = ((n_curr - n_prev) / n_prev) * 100
    s_chg = ((s_curr - s_prev) / s_prev) * 100
    st.markdown(
        f"### NIFTY 50: **{n_curr:,.2f}** ({':green' if n_chg>=0 else ':red'}[{n_chg:+.2f}%]) | SENSEX: **{s_curr:,.2f}** ({':green' if s_chg>=0 else ':red'}[{s_chg:+.2f}%])"
    )
  else:
    st.markdown('### Indices: `Data Temporarily Unavailable`')
except Exception:
  st.markdown('### Indices: `Connecting...`')

st.subheader(f"🕰️ IST: {ist_now.strftime('%H:%M:%S')} | {status_text}")


# --- CALCULATION LOGIC CORE WITH TRADE REFINEMENT RULE SET ---
def process_strategy_refined(
    data_daily, data_intraday, is_reversed=False
):
  if data_intraday.empty or not isinstance(
      data_intraday.columns, pd.MultiIndex
  ):
    return pd.DataFrame()
  results = []
  strategy_key = 'reversed' if is_reversed else 'regular'

  actual_present_tickers = set([col[0] for col in data_intraday.columns])

  for symbol in SYMBOLS:
    t_str = f'{symbol}.NS'
    if t_str not in actual_present_tickers:
      continue

    try:
      df_i = data_intraday[t_str].dropna(
          subset=['Close', 'Open', 'High', 'Low', 'Volume']
      )
      if len(df_i) < 30:
        continue

      cmp = float(df_i['Close'].iloc[-1])

      # --- 1. PRICE FILTER ---
      if cmp < filter_min_price or cmp > filter_max_price:
        continue

      # --- 2. HTF FILTER (Daily) ---
      htf_passed = True
      if use_htf_ema and symbol in data_daily.columns.levels[0]:
        df_d = data_daily[symbol].dropna(subset=['Close'])
        if len(df_d) >= 200:
          d_close = df_d['Close']
          ema_50 = d_close.ewm(span=50, adjust=False).mean().iloc[-1]
          ema_200 = d_close.ewm(span=200, adjust=False).mean().iloc[-1]
          if not (d_close.iloc[-1] > ema_50 and d_close.iloc[-1] > ema_200):
            htf_passed = False

      # --- 3. VOLATILITY FILTER (ATR 14 vs 30-day Avg) ---
      vol_passed = True
      if use_atr_volatility and symbol in data_daily.columns.levels[0]:
        df_d = data_daily[symbol].dropna(subset=['High', 'Low', 'Close'])
        if len(df_d) >= 45:
          h, l, c = df_d['High'], df_d['Low'], df_d['Close']
          tr_d = np.maximum(
              h - l, np.maximum(abs(h - c.shift(1)), abs(l - c.shift(1)))
          )
          atr_14 = tr_d.rolling(14).mean()
          avg_atr_30 = atr_14.rolling(30).mean()
          if atr_14.iloc[-1] <= avg_atr_30.iloc[-1]:
            vol_passed = False

      # --- 4. MOMENTUM (ROC 10-period) ---
      closes = df_i['Close']
      p10 = closes.iloc[-11] if len(closes) >= 11 else closes.iloc[0]
      roc_val = ((cmp - p10) / p10) * 100

      if roc_val >= 0:
        if not (filter_pos_roc_min <= roc_val <= filter_pos_roc_max):
          continue
      else:
        if not (filter_neg_roc_min <= roc_val <= filter_neg_roc_max):
          continue

      # --- 5. DEMAND ZONE & ATR STOP LOSS REFINEMENT ---
      highs, lows, volumes = df_i['High'], df_i['Low'], df_i['Volume']
      zone_low = lows.tail(20).min()

      # Intraday 15m ATR for buffer
      tr_i = np.maximum(
          highs - lows,
          np.maximum(
              abs(highs - closes.shift(1)), abs(lows - closes.shift(1))
          ),
      )
      atr_15m = pd.Series(tr_i, index=df_i.index).rolling(14).mean().iloc[-1]
      trigger_high = highs.iloc[-2]

      # Entry & Invalidation Rules
      entry_price = trigger_high + (0.0005 * cmp)  # 0.05% CMP offset
      stop_loss = zone_low - (0.5 * atr_15m)  # Volatility buffer

      risk_per_share = entry_price - stop_loss
      if risk_per_share <= 0:
        risk_per_share = cmp * 0.005  # fallback safeguard

      target_1 = entry_price + (2.0 * risk_per_share)
      target_2 = entry_price + (3.5 * risk_per_share)

      # Prob Score & Signals
      prob_score = 3 if (htf_passed and vol_passed) else 1
      p_text = 'HIGH' if prob_score >= 3 else 'MED'
      flag = '🟢 ' if 1.0 <= abs(roc_val) <= 5.0 else '🔴 '

      # Trade conditions
      if not is_reversed:
        trade_cond = (
            'S.Buy'
            if (roc_val > 0 and htf_passed)
            else ('S.Sell' if (roc_val < 0 and not htf_passed) else '-')
        )
      else:
        trade_cond = (
            'S.Buy'
            if (roc_val < 0 and not htf_passed)
            else ('S.Sell' if (roc_val > 0 and htf_passed) else '-')
        )

      trade = st.session_state.dual_trades[strategy_key].get(symbol)
      status = 'WAITING'
      e_time = ist_now.strftime('%H:%M')
      t_type = trade.get('type') if trade else ('BUY' if roc_val > 0 else 'SELL')

      if trade:
        status = 'IN TRADE'
        e_time = trade.get('time', e_time)
        if t_type == 'BUY':
          if cmp >= trade['target']:
            status = '🎯 TARGET HIT'
          elif cmp <= trade['sl']:
            status = '🛑 SL HIT'
        else:
          if cmp <= trade['target']:
            status = '🎯 TARGET HIT'
          elif cmp >= trade['sl']:
            status = '🛑 SL HIT'
      else:
        # Register new trade setup
        st.session_state.dual_trades[strategy_key][symbol] = {
            'entry': round(entry_price, 2),
            'target': round(target_1, 2),
            'sl': round(stop_loss, 2),
            'type': t_type,
            'time': e_time,
            'prob_text': p_text,
        }
        save_persistent_trades(st.session_state.dual_trades)
        trade = st.session_state.dual_trades[strategy_key][symbol]

      # Filters check
      if (
          filter_trade_type == 'S.Buy Only'
          and trade_cond != 'S.Buy'
          and trade_cond != '-'
      ):
        continue
      if (
          filter_trade_type == 'S.Sell Only'
          and trade_cond != 'S.Sell'
          and trade_cond != '-'
      ):
        continue

      results.append({
          'Stock': flag + symbol,
          'Trade': '🟢 ' + trade_cond,
          'Qty': f"🟢 {int(capital // cmp)}",
          'CMP': cmp,
          'Entry': trade['entry'],
          'SL': trade['sl'],
          'Target': trade['target'],
          'A/D Trend': (
              '🚨 Bullish Shift' if roc_val > 0 else '🚨 Bearish Shift'
          ),
          'Signal': f'ROC:{roc_val:+.2f}% | ATR:{atr_15m:.2f}',
          'Status': status,
          'Prob': p_text,
          'Time': e_time,
          'InTrade': 1 if trade else 0,
          'ROC_Val': abs(roc_val),
          'TradeType': t_type,
      })
    except Exception:
      continue

  if not results:
    return pd.DataFrame()
  df_out = (
      pd.DataFrame(results)
      .sort_values(by=['InTrade', 'ROC_Val'], ascending=False)
      .drop(columns=['InTrade', 'ROC_Val'])
  )
  return df_out[[
      'Stock',
      'Trade',
      'Qty',
      'CMP',
      'Entry',
      'SL',
      'Target',
      'A/D Trend',
      'Signal',
      'Status',
      'Prob',
      'Time',
      'TradeType',
  ]]


# --- EXECUTE FETCH ---
tickers = [f'{s}.NS' for s in SYMBOLS]
try:
  raw_intraday = yf.download(
      tickers,
      period='2d',
      interval='5m',
      group_by='ticker',
      auto_adjust=True,
      progress=False,
  )
  raw_daily = yf.download(
      tickers,
      period='1y',
      interval='1d',
      group_by='ticker',
      auto_adjust=True,
      progress=False,
  )
except Exception:
  raw_intraday, raw_daily = pd.DataFrame(), pd.DataFrame()


# --- STYLING ---
def apply_dynamic_styles(df):
  styles = pd.DataFrame('', index=df.index, columns=df.columns)
  for i, row in df.iterrows():
    if 'IN TRADE' in str(row['Status']) or 'HIT' in str(row['Status']):
      row_bg = '#c6f6d5' if row['TradeType'] == 'BUY' else '#fed7d7'
      styles.loc[i, :] = (
          f'background-color: {row_bg}; color: black; font-weight: 500'
      )
      is_buy = row['TradeType'] == 'BUY'
      cmp_bg = (
          '#1a8a44'
          if (is_buy and row['CMP'] >= row['Entry'])
          or (not is_buy and row['CMP'] <= row['Entry'])
          else '#c53030'
      )
      styles.loc[i, 'CMP'] = (
          f'background-color: {cmp_bg}; color: white; font-weight: bold'
      )
  return styles


columns_to_show = [
    'Stock',
    'Trade',
    'Qty',
    'CMP',
    'Signal',
    'Entry',
    'SL',
    'Target',
    'A/D Trend',
    'Status',
    'Prob',
    'Time',
]

df_reg = (
    process_strategy_refined(raw_daily, raw_intraday, is_reversed=False)
    if not raw_intraday.empty
    else pd.DataFrame()
)
df_rev = (
    process_strategy_refined(raw_daily, raw_intraday, is_reversed=True)
    if not raw_intraday.empty
    else pd.DataFrame()
)

# --- 🪟 TRADE WINDOW ---
st.markdown('---')
st.header('🪟 1) REFINED TRADE WINDOW')

active_reg = (
    df_reg[df_reg['Status'].str.contains('IN TRADE|HIT', regex=True, na=False)]
    if not df_reg.empty
    else pd.DataFrame()
)
active_rev = (
    df_rev[df_rev['Status'].str.contains('IN TRADE|HIT', regex=True, na=False)]
    if not df_rev.empty
    else pd.DataFrame()
)

if not active_reg.empty or not active_rev.empty:
  combined_trades = pd.concat([active_reg, active_rev], ignore_index=True)
  combined_trades = combined_trades.drop_duplicates(
      subset=['Stock'], keep='first'
  )

  view_trade_window = combined_trades.style.apply(
      apply_dynamic_styles, axis=None
  ).format({'CMP': '{:.2f}', 'Entry': '{:.2f}', 'Target': '{:.2f}', 'SL': '{:.2f}'})
  st.dataframe(
      view_trade_window,
      use_container_width=True,
      hide_index=True,
      column_order=columns_to_show,
  )
else:
  st.info('No active open positions match refined conditions.')

# --- RENDER MONITORS ---
st.markdown('---')
col_reg, col_rev = st.columns(2)

with col_reg:
  st.subheader('📊 2) REGULAR REFINED MONITOR')
  if not df_reg.empty:
    view_reg = df_reg.style.apply(apply_dynamic_styles, axis=None).format({
        'CMP': '{:.2f}',
        'Entry': lambda x: f'{x:.2f}' if x > 0 else '-',
        'Target': lambda x: f'{x:.2f}' if x > 0 else '-',
        'SL': lambda x: f'{x:.2f}' if x > 0 else '-',
    })
    st.dataframe(
        view_reg,
        use_container_width=True,
        hide_index=True,
        column_order=columns_to_show,
    )
  else:
    st.caption('No tickers match refined standard filters.')

with col_rev:
  st.subheader('🔄 3) REVERSED REFINED MONITOR')
  if not df_rev.empty:
    view_rev = df_rev.style.apply(apply_dynamic_styles, axis=None).format({
        'CMP': '{:.2f}',
        'Entry': lambda x: f'{x:.2f}' if x > 0 else '-',
        'Target': lambda x: f'{x:.2f}' if x > 0 else '-',
        'SL': lambda x: f'{x:.2f}' if x > 0 else '-',
    })
    st.dataframe(
        view_rev,
        use_container_width=True,
        hide_index=True,
        column_order=columns_to_show,
    )
  else:
    st.caption('No tickers match reversal refined filters.')

# --- REFRESH CONTROL ---
time.sleep(60 if open_status else 300)
st.rerun()
