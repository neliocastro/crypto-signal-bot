"""
Busca candles OHLCV de qualquer exchange suportada pelo ccxt.
"""
import ccxt
import pandas as pd
from . import config

def get_exchange():
    """Instancia a exchange configurada. Modo público, sem credenciais."""
    exchange_class = getattr(ccxt, config.EXCHANGE_ID)
    exchange = exchange_class({
        "enableRateLimit": True,
        "timeout": 30000,
    })
    return exchange

def fetch_ohlcv(symbol: str, timeframe: str = None, limit: int = None) -> pd.DataFrame:
    """
    Retorna DataFrame com colunas: timestamp, open, high, low, close, volume.
    O último candle pode estar em formação; o pipeline ignora ele.
    """
    timeframe = timeframe or config.TIMEFRAME
    limit = limit or config.CANDLES_LIMIT

    exchange = get_exchange()
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df