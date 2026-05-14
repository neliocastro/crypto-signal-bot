"""
Cálculo de indicadores técnicos sobre o DataFrame OHLCV.
Função pública obrigatória: enrich(df) -> df enriquecido.
"""
import numpy as np
import pandas as pd

# ---------- helpers ----------
def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()

def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()

def _bollinger(series: pd.Series, length: int = 20, mult: float = 2.0):
    mid = _sma(series, length)
    std = series.rolling(length).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower

# ---------- API pública ----------
def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame com colunas ['timestamp','open','high','low','close','volume']
    e devolve o mesmo DF com indicadores adicionados.
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # garante ordenação por tempo
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    close = df["close"]

    # médias móveis
    df["ema9"]   = _ema(close, 9)
    df["ema21"]  = _ema(close, 21)
    df["ema50"]  = _ema(close, 50)
    df["ema200"] = _ema(close, 200)
    df["sma20"]  = _sma(close, 20)

    # momentum
    df["rsi14"] = _rsi(close, 14)
    macd_line, signal_line, hist = _macd(close)
    df["macd"]        = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"]   = hist

    # volatilidade
    df["atr14"] = _atr(df, 14)
    up, mid, low = _bollinger(close, 20, 2.0)
    df["bb_upper"] = up
    df["bb_mid"]   = mid
    df["bb_lower"] = low

    # volume
    df["vol_sma20"] = _sma(df["volume"], 20)
    df["vol_ratio"] = df["volume"] / df["vol_sma20"]

    # variação percentual
    df["pct_change"] = close.pct_change() * 100

    return df
