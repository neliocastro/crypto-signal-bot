"""
Calcula todos os indicadores técnicos sobre um DataFrame OHLCV.
"""
import pandas as pd
import pandas_ta as ta
from . import config

def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona colunas de indicadores ao DataFrame.
    """
    ind = config.INDICATORS

    # EMAs
    df["ema9"]   = ta.ema(df["close"], length=ind["ema_curto"])
    df["ema21"]  = ta.ema(df["close"], length=ind["ema_medio"])
    df["ema50"]  = ta.ema(df["close"], length=ind["ema_longo"])
    df["ema200"] = ta.ema(df["close"], length=ind["ema_tendencia"])

    # RSI
    df["rsi"] = ta.rsi(df["close"], length=ind["rsi_periodo"])

    # MACD
    macd = ta.macd(
        df["close"],
        fast=ind["macd_fast"],
        slow=ind["macd_slow"],
        signal=ind["macd_signal"],
    )
    df["macd"]      = macd[f"MACD_{ind['macd_fast']}_{ind['macd_slow']}_{ind['macd_signal']}"]
    df["macd_sig"]  = macd[f"MACDs_{ind['macd_fast']}_{ind['macd_slow']}_{ind['macd_signal']}"]
    df["macd_hist"] = macd[f"MACDh_{ind['macd_fast']}_{ind['macd_slow']}_{ind['macd_signal']}"]

    # ATR (para cálculo de Stop Loss)
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=ind["atr_periodo"])

    # Volume médio (20 períodos) para confirmação
    df["vol_ma20"] = df["volume"].rolling(20).mean()

    return df.dropna()