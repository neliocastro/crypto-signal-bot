"""
Indicadores técnicos.
Função pública: add_indicators(df) -> df
"""
import numpy as np
import pandas as pd

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(s: pd.Series, fast=12, slow=26, signal=9):
    macd = _ema(s, fast) - _ema(s, slow)
    sig = _ema(macd, signal)
    return macd, sig, macd - sig

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def _vwap_daily(df: pd.DataFrame) -> pd.Series:
    """
    VWAP ancorado no fechamento diario em UTC 00:00.
    Reseta a cada novo dia (padrao cripto: Gate.com, TradingView default).

    Usa typical price = (high + low + close) / 3, ponderado pelo volume.
    """
    if "timestamp" not in df.columns or df["volume"].sum() == 0:
        return pd.Series([float("nan")] * len(df), index=df.index)

    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    day_key = ts.dt.strftime("%Y-%m-%d")

    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]

    cum_pv  = pv.groupby(day_key).cumsum()
    cum_vol = df["volume"].groupby(day_key).cumsum()
    vwap = cum_pv / cum_vol.replace(0, np.nan)
    return vwap

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame OHLCV e devolve o mesmo DF com colunas de indicadores.
    Colunas esperadas: open, high, low, close, volume (+ timestamp opcional).
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    c = df["close"]

    # EMAs (nomes alinhados ao config.py: 9, 21, 50, 200)
    df["ema9"]   = _ema(c, 9)
    df["ema21"]  = _ema(c, 21)
    df["ema50"]  = _ema(c, 50)
    df["ema200"] = _ema(c, 200)

    # Momentum
    df["rsi"] = _rsi(c, 14)
    macd, sig, hist = _macd(c, 12, 26, 9)
    df["macd"] = macd
    df["macd_signal"] = sig
    df["macd_hist"]   = hist

    # Volatilidade
    df["atr"] = _atr(df, 14)

    # VWAP Daily (ancorado em UTC 00:00)
    df["vwap"] = _vwap_daily(df)

    # Volume
    df["vol_sma20"] = _sma(df["volume"], 20)
    df["vol_ratio"] = df["volume"] / df["vol_sma20"]

    return df
