"""
Calcula indicadores técnicos sobre o DataFrame OHLCV.
Usa a biblioteca `ta` (pura Python, compatível com Python 3.11+).
"""
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe DataFrame OHLCV (colunas: timestamp, open, high, low, close, volume)
    e devolve o mesmo DataFrame enriquecido com colunas de indicadores.
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # EMAs
    df["ema9"]   = EMAIndicator(close=df["close"], window=9).ema_indicator()
    df["ema21"]  = EMAIndicator(close=df["close"], window=21).ema_indicator()
    df["ema50"]  = EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["ema200"] = EMAIndicator(close=df["close"], window=200).ema_indicator()

    # RSI
    df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()

    # MACD (12, 26, 9)
    macd = MACD(close=df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"]   = macd.macd_diff()           # histograma
    df["macd_diff_prev"] = df["macd_diff"].shift(1)

    # ATR (para stop loss dinâmico)
    df["atr"] = AverageTrueRange(
        high=df["high"], low=df["low"], close=df["close"], window=14
    ).average_true_range()

    return df

def get_latest_values(df: pd.DataFrame) -> dict:
    """Retorna a última linha como dict, ou {} se vazio."""
    if df is None or df.empty:
        return {}
    last = df.iloc[-1]
    out = {}
    for col in last.index:
        val = last[col]
        if pd.isna(val):
            out[col] = None
        else:
            out[col] = float(val) if col != "timestamp" else val
    return out
