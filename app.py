import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 1. CORE ALGORITHMIC ENGINE
# ==========================================


class TradeRefinementEngine:

  def __init__(
      self,
      df_daily: pd.DataFrame,
      df_intraday: pd.DataFrame,
      roc_threshold: float = 1.36,
  ):
    self.df_d = df_daily.copy()
    self.df_i = df_intraday.copy()
    self.roc_threshold = roc_threshold

  def compute_htf_filters((self) -> dict:
    """Evaluates Trend, Volatility, and Momentum filters on the Daily timeframe."""
    close = self.df_d["Close"]
    high = self.df_d["High"]
    low = self.df_d["Low"]

    # Trend Filter: Price > 50 EMA and 200 EMA
    ema_50 = close.ewm(span=50, adjust=False).mean()
    ema_200 = close.ewm(span=200, adjust=False).mean()
    self.df_d["EMA_50"] = ema_50
    self.df_d["EMA_200"] = ema_200

    is_uptrend = (close.iloc[-1] > ema_50.iloc[-1]) and (
        close.iloc[-1] > ema_200.iloc[-1]
    )

    # Volatility Filter: 14-period ATR > Average 30-day ATR
    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))),
    )
    atr_14 = tr.rolling(window=14).mean()
    avg_atr_30 = atr_14.rolling(window=30).mean()
    self.df_d["ATR_14"] = atr_14
    self.df_d["Avg_ATR_30"] = avg_atr_30

    volatility_expanded = atr_14.iloc[-1] > avg_atr_30.iloc[-1]

    # Momentum Filter: 10-period ROC > ROC Threshold
    roc_10 = ((close - close.shift(10)) / close.shift(10)) * 100
    self.df_d["ROC_10"] = roc_10
    momentum_valid = roc_10.iloc[-1] > self.roc_threshold

    passed_all = is_uptrend and volatility_expanded and momentum_valid

    return {
        "trend_valid": is_uptrend,
        "volatility_expanded": volatility_expanded,
        "momentum_valid": momentum_valid,
        "htf_bias_approved": passed_all,
        "current_roc": roc_10.iloc[-1],
        "current_atr": atr_14.iloc[-1],
        "ema_50": ema_50.iloc[-1],
        "ema_200": ema_200.iloc[-1],
    }

  def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))),
    )
    return tr.rolling(window=period).mean()

  def identify_demand_zone_and_setup(self, lookback_bars: int = 20) -> dict:
    recent_df = self.df_i.tail(lookback_bars)

    zone_low = recent_df["Low"].min()
    atr_15m = self.calculate_atr(self.df_i, period=14).iloc[-1]
    cmp = self.df_i["Close"].iloc[-1]
    trigger_high = self.df_i["High"].iloc[-2]

    # Entry: Trigger High + 0.05% CMP offset
    entry_price = trigger_high + (0.0005 * cmp)

    # Invalidation Stop Loss: Zone Low - 0.5 * ATR(15m)
    stop_loss = zone_low - (0.5 * atr_15m)

    risk_per_share = entry_price - stop_loss
    target_1 = entry_price + (2.0 * risk_per_share)
    target_2 = entry_price + (3.5 * risk_per_share)

    return {
        "cmp": cmp,
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "risk_per_share": round(risk_per_share, 2),
        "target_1_50_pct": round(target_1, 2),
        "target_2_remaining": round(target_2, 2),
        "atr_15m": round(atr_15m, 2),
        "zone_low": zone_low,
    }


# ==========================================
# 2. MOCK DATA GENERATOR
# ==========================================


@st.cache_data
def generate_market_data():
  np.random.seed(42)
  dates_d = pd.date_range(end=pd.Timestamp.today(), periods=250, freq="B")
  df_daily = pd.DataFrame(
      {
          "Open": np.linspace(100, 150, 250) + np.random.normal(0, 1, 250),
          "High": np.linspace(102, 153, 250) + np.random.normal(0, 1, 250),
          "Low": np.linspace(98, 148, 250) + np.random.normal(0, 1, 250),
          "Close": np.linspace(101, 151, 250) + np.random.normal(0, 1, 250),
          "Volume": np.random.randint(100000, 500000, 250),
      },
      index=dates_d,
  )

  dates_i = pd.date_range(end=pd.Timestamp.today(), periods=100, freq="15min")
  df_intraday = pd.DataFrame(
      {
          "Open": np.linspace(145, 151, 100) + np.random.normal(0, 0.2, 100),
          "High": np.linspace(146, 152, 100) + np.random.normal(0, 0.2, 100),
          "Low": np.linspace(144, 150, 100) + np.random.normal(0, 0.2, 100),
          "Close": np.linspace(145, 151, 100) + np.random.normal(0, 0.2, 100),
          "Volume": np.random.randint(10000, 50000, 100),
      },
      index=dates_i,
  )

  return df_daily, df_intraday


# ==========================================
# 3. STREAMLIT APPLICATION INTERFACE
# ==========================================

st.set_page_config(
    page_title="Trade Execution Engine", page_icon="⚡", layout="wide"
)

st.title("⚡ Structural Trade Refinement & Execution Engine")
st.markdown(
    "Automated quantitative setup evaluation based on HTF trend alignment,"
    " intraday demand zones, and ATR volatility buffers."
)

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Parameters & Controls")

ticker = st.sidebar.textbox("Ticker Symbol", value="NSE:RELIANCE")
capital = st.sidebar.number_input(
    "Total Capital (₹)", value=500000, step=25000
)
risk_pct = st.sidebar.slider(
    "Max Risk Per Trade (%)", min_value=0.5, max_value=3.0, value=1.0, step=0.1
)
roc_threshold = st.sidebar.slider(
    "Daily ROC Threshold (%)",
    min_value=0.5,
    max_value=3.0,
    value=1.36,
    step=0.05,
)
lookback_bars = st.sidebar.slider(
    "Intraday Zone Lookback Bars", min_value=10, max_value=50, value=20
)

# Load Data & Process Engine
df_daily, df_intraday = generate_market_data()
engine = TradeRefinementEngine(
    df_daily, df_intraday, roc_threshold=roc_threshold
)
htf_status = engine.compute_htf_filters()
params = engine.identify_demand_zone_and_setup(lookback_bars=lookback_bars)

# --- ALERT / SYSTEM STATUS BANNER ---
st.subheader("1. Trade Signal Status")

if htf_status["htf_bias_approved"]:
  st.success(
      f"🟢 **TRADE APPROVED FOR {ticker}**: All Higher Timeframe (HTF)"
      " filters validated. Entry parameters unlocked."
  )
else:
  reasons = []
  if not htf_status["trend_valid"]:
    reasons.append("Price below 50/200 EMA")
  if not htf_status["volatility_expanded"]:
    reasons.append("ATR(14) < 30-Day Avg ATR")
  if not htf_status["momentum_valid"]:
    reasons.append(f"ROC(10) <= {roc_threshold}%")

  st.error(
      f"🔴 **TRADE REJECTED FOR {ticker}**: Failed HTF Criteria ->"
      f" {', '.join(reasons)}"
  )

# --- HTF FILTER CHECKPOINTS ---
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
  status_icon = "✅ PASS" if htf_status["trend_valid"] else "❌ FAIL"
  st.metric(
      label="Trend Alignment (50/200 EMA)",
      value=f"{params['cmp']:.2f} CMP",
      delta=status_icon,
  )

with col_f2:
  status_icon = "✅ PASS" if htf_status["volatility_expanded"] else "❌ FAIL"
  st.metric(
      label="Volatility Expansion (ATR 14 vs 30d)",
      value=f"{htf_status['current_atr']:.2f}",
      delta=status_icon,
  )

with col_f3:
  status_icon = "✅ PASS" if htf_status["momentum_valid"] else "❌ FAIL"
  st.metric(
      label="Momentum Filter (ROC 10)",
      value=f"{htf_status['current_roc']:.2f}%",
      delta=f"Target > {roc_threshold}%",
  )

st.markdown("---")

# --- EXECUTION PARAMETERS & POSITION SIZING ---
st.subheader("2. Precise Execution Levels & Sizing")

# Calculation of Position Sizing based on Capital & Risk
max_loss_amount = capital * (risk_pct / 100.0)
position_size = int(max_loss_amount / params["risk_per_share"])
total_position_value = position_size * params["entry_price"]

col_e1, col_e2, col_e3, col_e4, col_e5 = st.columns(5)
col_e1.metric(
    label="Limit Entry Price",
    value=f"₹{params['entry_price']}",
    delta="+0.05% CMP Offset",
)
col_e2.metric(
    label="Stop Loss (Invalidation)",
    value=f"₹{params['stop_loss']}",
    delta=f"-0.5*ATR ({params['risk_per_share']}/sh)",
    delta_color="inverse",
)
col_e3.metric(
    label="Target 1 (50% Qty - 1:2 R:R)",
    value=f"₹{params['target_1_50_pct']}",
    delta="Move SL to BE",
)
col_e4.metric(
    label="Target 2 (50% Qty - 1:3.5 R:R)",
    value=f"₹{params['target_2_remaining']}",
    delta="Runner Target",
)
col_e5.metric(
    label="Max Position Qty",
    value=f"{position_size} Shares",
    delta=f"₹{total_position_value:,.0f} Total Val",
)

st.markdown("---")

# --- INTERACTIVE CHARTS ---
st.subheader("3. Technical Visualization")

tab1, tab2 = st.tabs(
    ["Intraday Setup & Order Levels (15m)", "Daily HTF Structure & Moving Averages"]
)

with tab1:
  fig_i = make_subplots(
      rows=2,
      cols=1,
      shared_xaxes=True,
      vertical_spacing=0.05,
      row_heights=[0.7, 0.3],
  )

  # Intraday Candlestick Chart
  fig_i.add_trace(
      go.Candlestick(
          x=df_intraday.index,
          open=df_intraday["Open"],
          high=df_intraday["High"],
          low=df_intraday["Low"],
          close=df_intraday["Close"],
          name="15m OHLC",
      ),
      row=1,
      col=1,
  )

  # Execution Lines
  fig_i.add_hline(
      y=params["entry_price"],
      line_dash="dash",
      line_color="blue",
      annotation_text="ENTRY LIMIT",
      row=1,
      col=1,
  )
  fig_i.add_hline(
      y=params["stop_loss"],
      line_dash="dash",
      line_color="red",
      annotation_text="STOP LOSS",
      row=1,
      col=1,
  )
  fig_i.add_hline(
      y=params["target_1_50_pct"],
      line_dash="dash",
      line_color="green",
      annotation_text="T1 (1:2 R:R)",
      row=1,
      col=1,
  )
  fig_i.add_hline(
      y=params["target_2_remaining"],
      line_dash="dash",
      line_color="darkgreen",
      annotation_text="T2 (1:3.5 R:R)",
      row=1,
      col=1,
  )

  # Intraday Volume
  fig_i.add_trace(
      go.Bar(
          x=df_intraday.index,
          y=df_intraday["Volume"],
          name="Volume",
          marker_color="lightblue",
      ),
      row=2,
      col=1,
  )

  fig_i.update_layout(
      height=500, xaxis_rangeslider_visible=False, template="plotly_white"
  )
  st.plotly_chart(fig_i, use_container_width=True)

with tab2:
  fig_d = make_subplots(
      rows=2,
      cols=1,
      shared_xaxes=True,
      vertical_spacing=0.05,
      row_heights=[0.7, 0.3],
  )

  # Daily Candlestick Chart
  fig_d.add_trace(
      go.Candlestick(
          x=df_daily.index,
          open=df_daily["Open"],
          high=df_daily["High"],
          low=df_daily["Low"],
          close=df_daily["Close"],
          name="Daily OHLC",
      ),
      row=1,
      col=1,
  )

  # EMAs
  fig_d.add_trace(
      go.Scatter(
          x=df_daily.index,
          y=engine.df_d["EMA_50"],
          line=dict(color="orange", width=1.5),
          name="50 EMA",
      ),
      row=1,
      col=1,
  )
  fig_d.add_trace(
      go.Scatter(
          x=df_daily.index,
          y=engine.df_d["EMA_200"],
          line=dict(color="purple", width=1.5),
          name="200 EMA",
      ),
      row=1,
      col=1,
  )

  # ROC Subplot
  fig_d.add_trace(
      go.Scatter(
          x=df_daily.index,
          y=engine.df_d["ROC_10"],
          line=dict(color="blue", width=1.5),
          name="ROC (10)",
      ),
      row=2,
      col=1,
  )
  fig_d.add_hline(
      y=roc_threshold,
      line_dash="dot",
      line_color="red",
      annotation_text=f"Threshold ({roc_threshold}%)",
      row=2,
      col=1,
  )

  fig_d.update_layout(
      height=500, xaxis_rangeslider_visible=False, template="plotly_white"
  )
  st.plotly_chart(fig_d, use_container_width=True)
