import numpy as np
import pandas as pd


class TradeRefinementEngine:

  def __init__(self, df_daily: pd.DataFrame, df_intraday: pd.DataFrame):
    """Initializes the engine with Daily and Intraday (15m/5m) OHLCV data.

    Expected columns: ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    self.df_d = df_daily.copy()
    self.df_i = df_intraday.copy()

  def compute_htf_filters(self) -> dict:
    """Evaluates Trend, Volatility, and Momentum filters on the Daily timeframe."""
    close = self.df_d['Close']
    high = self.df_d['High']
    low = self.df_d['Low']

    # 1. Trend Filter: Price > 50 EMA and 200 EMA
    ema_50 = close.ewm(span=50, adjust=False).mean()
    ema_200 = close.ewm(span=200, adjust=False).mean()

    is_uptrend = (close.iloc[-1] > ema_50.iloc[-1]) and (
        close.iloc[-1] > ema_200.iloc[-1]
    )

    # 2. Volatility Filter: 14-period ATR > Average 30-day ATR
    tr = np.maximum(
        high - low,
        np.maximum(
            abs(high - close.shift(1)), abs(low - close.shift(1))
        ),
    )
    atr_14 = tr.rolling(window=14).mean()
    avg_atr_30 = atr_14.rolling(window=30).mean()
    volatility_expanded = atr_14.iloc[-1] > avg_atr_30.iloc[-1]

    # 3. Relative Strength / Momentum: 10-period ROC > 1.36%
    roc_10 = ((close - close.shift(10)) / close.shift(10)) * 100
    momentum_valid = roc_10.iloc[-1] > 1.36

    passed_all = is_uptrend and volatility_expanded and momentum_valid

    return {
        'trend_valid': is_uptrend,
        'volatility_expanded': volatility_expanded,
        'momentum_valid': momentum_valid,
        'htf_bias_approved': passed_all,
        'current_roc': roc_10.iloc[-1],
        'current_atr': atr_14.iloc[-1],
    }

  def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Average True Range for a given dataframe."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))),
    )
    return tr.rolling(window=period).mean()

  def identify_demand_zone_and_setup(self, lookback_bars: int = 20) -> dict:
    """Identifies the most recent demand zone and calculates exact Entry, Stop Loss, and Targets."""
    recent_df = self.df_i.tail(lookback_bars)

    # Find local swing low acting as the Demand Zone / Order Block baseline
    zone_low = recent_df['Low'].min()
    zone_high = recent_df['Low'] + (
        recent_df['High'] - recent_df['Low']
    ).mean()  # Approximation of zone equilibrium top

    # Intraday ATR (15m) for buffer calculation
    atr_15m = self.calculate_atr(self.df_i, period=14).iloc[-1]
    cmp = self.df_i['Close'].iloc[-1]

    # Trigger candle high estimation (using last completed candle)
    trigger_high = self.df_i['High'].iloc[-2]

    # 1. Point of Entry (Limit Order Price)
    entry_price = trigger_high + (0.0005 * cmp)

    # 2. Point of Invalidation (Stop Loss = Demand Zone Low - 0.5 * ATR_15m)
    stop_loss = zone_low - (0.5 * atr_15m)

    # Risk per share
    risk_per_share = entry_price - stop_loss

    # 3. Target Calculations (1:2 and 1:3.5 R:R)
    target_1 = entry_price + (2.0 * risk_per_share)
    target_2 = entry_price + (3.5 * risk_per_share)

    return {
        'cmp': cmp,
        'entry_price': round(entry_price, 2),
        'stop_loss': round(stop_loss, 2),
        'risk_per_share': round(risk_per_share, 2),
        'target_1_50_pct': round(target_1, 2),
        'target_2_remaining': round(target_2, 2),
        'atr_15m': round(atr_15m, 2),
    }

  def evaluate_trade_execution(self) -> dict:
    """Runs full pipeline and returns structured execution plan."""
    htf_status = self.compute_htf_filters()

    if not htf_status['htf_bias_approved']:
      return {
          'status': 'REJECTED',
          'reason': 'HTF Market Filters Failed (Trend, Volatility, or Momentum)',
          'filters': htf_status,
      }

    trade_levels = self.identify_demand_zone_and_setup()

    return {
        'status': 'APPROVED',
        'filters': htf_status,
        'execution_parameters': trade_levels,
    }


# ==========================================
# Example Usage:
# ==========================================
if __name__ == '__main__':
  # Mocking sample OHLCV data frames for testing
  np.random.seed(42)
  dates_d = pd.date_range(end=pd.Timestamp.today(), periods=250, freq='B')
  df_daily_mock = pd.DataFrame({
      'Open': np.linspace(100, 150, 250) + np.random.normal(0, 1, 250),
      'High': np.linspace(102, 153, 250) + np.random.normal(0, 1, 250),
      'Low': np.linspace(98, 148, 250) + np.random.normal(0, 1, 250),
      'Close': np.linspace(101, 151, 250) + np.random.normal(0, 1, 250),
      'Volume': np.random.randint(100000, 500000, 250),
  }, index=dates_d)

  dates_i = pd.date_range(end=pd.Timestamp.today(), periods=100, freq='15min')
  df_intraday_mock = pd.DataFrame({
      'Open': np.linspace(145, 151, 100) + np.random.normal(0, 0.2, 100),
      'High': np.linspace(146, 152, 100) + np.random.normal(0, 0.2, 100),
      'Low': np.linspace(144, 150, 100) + np.random.normal(0, 0.2, 100),
      'Close': np.linspace(145, 151, 100) + np.random.normal(0, 0.2, 100),
      'Volume': np.random.randint(10000, 50000, 100),
  }, index=dates_i)

  engine = TradeRefinementEngine(df_daily_mock, df_intraday_mock)
  result = engine.evaluate_trade_execution()

  import pprint
  pprint.pprint(result)
