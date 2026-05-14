"""
Indicadores técnicos.
Função pública exigida pelo main.py: add_indicators(df) -> df
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

def _bbands(s: pd.Series, n: int = 20, k: float = 2.0):
    mid = _sma(s, n)
    std = s.rolling(n).std()
    return mid + k * std, mid, mid - k * std

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame com colunas ['timestamp','open','high','low','close','volume']
    e devolve o mesmo DF com colunas de indicadores adicionadas.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    c = df["close"]

    # Tendência
    df["ema9"]   = _ema(c, 9)
    df["ema21"]  = _ema(c, 21)
    df["ema50"]  = _ema(c, 50)
    df["ema200"] = _ema(c, 200)
    df["sma20"]  = _sma(c, 20)

    # Momentum
    df["rsi14"] = _rsi(c, 14)
    macd, sig, hist = _macd(c)
    df["macd"]        = macd
    df["macd_signal"] = sig
    df["macd_hist"]   = hist

    # Volatilidade
    df["atr14"] = _atr(df, 14)
    up, mid, lo = _bbands(c, 20, 2.0)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = up, mid, lo

    # Volume
    df["vol_sma20"] = _sma(df["volume"], 20)
    df["vol_ratio"] = df["volume"] / df["vol_sma20"]

    # Variação
    df["pct_change"] = c.pct_change() * 100

    return df

# ---- aliases defensivos (caso outro módulo importe nomes diferentes) ----
enrich = add_indicators
compute_indicators = add_indicators
calculate_indicators = add_indicators
