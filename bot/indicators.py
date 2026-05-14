"""
Cálculo de indicadores técnicos usando a biblioteca 'ta'.
"""
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe um DataFrame OHLCV e adiciona colunas de indicadores:
    rsi, ema50, ema200, macd, macd_signal, macd_diff, atr, bb_high, bb_low, bb_mid
    """
    if df is None or df.empty or len(df) < 200:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]

    # RSI 14
    df["rsi"] = RSIIndicator(close=close, window=14).rsi()

    # EMAs
    df["ema50"] = EMAIndicator(close=close, window=50).ema_indicator()
    df["ema200"] = EMAIndicator(close=close, window=200).ema_indicator()

    # MACD (12, 26, 9)
    macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd_obj.macd()
    df["macd_signal"] = macd_obj.macd_signal()
    df["macd_diff"] = macd_obj.macd_diff()

    # ATR 14 (para stop loss)
    df["atr"] = AverageTrueRange(
        high=high, low=low, close=close, window=14
    ).average_true_range()

    # Bollinger Bands (20, 2)
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()

    return df

def get_latest_values(df: pd.DataFrame) -> dict:
    """
    Retorna os valores mais recentes dos indicadores como dicionário.
    """
    if df is None or df.empty:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    return {
        "close": float(last["close"]),
        "rsi": float(last["rsi"]) if pd.notna(last["rsi"]) else None,
        "ema50": float(last["ema50"]) if pd.notna(last["ema50"]) else None,
        "ema200": float(last["ema200"]) if pd.notna(last["ema200"]) else None,
        "macd": float(last["macd"]) if pd.notna(last["macd"]) else None,
        "macd_signal": float(last["macd_signal"]) if pd.notna(last["macd_signal"]) else None,
        "macd_diff": float(last["macd_diff"]) if pd.notna(last["macd_diff"]) else None,
        "macd_diff_prev": float(prev["macd_diff"]) if pd.notna(prev["macd_diff"]) else None,
        "atr": float(last["atr"]) if pd.notna(last["atr"]) else None,
        "bb_high": float(last["bb_high"]) if pd.notna(last["bb_high"]) else None,
        "bb_low": float(last["bb_low"]) if pd.notna(last["bb_low"]) else None,
        "bb_mid": float(last["bb_mid"]) if pd.notna(last["bb_mid"]) else None,
    }

# Alias para compatibilidade com main.py
enrich = add_indicators
