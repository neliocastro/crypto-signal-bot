"""
Busca candles OHLCV com fallback automático entre exchanges.

Ordem de tentativa: gateio (primária) -> binance -> bybit
Se todas falharem, levanta RuntimeError consolidado.

Vantagens:
  - Resiliência se Gate.io estiver instável
  - Detecção indireta de anomalias (se preços divergirem muito, log warning)
  - Mantém ccxt como interface única
"""
import logging
import ccxt
import pandas as pd
from . import config

log = logging.getLogger(__name__)

# Ordem de prioridade para fallback
FALLBACK_EXCHANGES = [config.EXCHANGE_ID, "binance", "bybit"]
# remove duplicatas mantendo ordem
_seen = set()
FALLBACK_EXCHANGES = [x for x in FALLBACK_EXCHANGES if not (x in _seen or _seen.add(x))]


def _build_exchange(exchange_id: str):
    """Instancia uma exchange ccxt em modo público, sem credenciais."""
    exchange_class = getattr(ccxt, exchange_id)
    return exchange_class({
        "enableRateLimit": True,
        "timeout": 30000,
    })


def get_exchange():
    """Mantido para compatibilidade — retorna a exchange primária."""
    return _build_exchange(config.EXCHANGE_ID)


def _fetch_from(exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Tenta buscar OHLCV de uma exchange específica. Pode levantar exceção."""
    exchange = _build_exchange(exchange_id)
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not raw:
        raise RuntimeError(f"{exchange_id} retornou lista vazia")
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def fetch_ohlcv(symbol: str, timeframe: str = None, limit: int = None) -> pd.DataFrame:
    """
    Retorna DataFrame OHLCV tentando exchanges em ordem.
    Levanta RuntimeError se todas falharem.
    """
    timeframe = timeframe or config.TIMEFRAME
    limit = limit or config.CANDLES_LIMIT

    errors = []
    for exch_id in FALLBACK_EXCHANGES:
        try:
            df = _fetch_from(exch_id, symbol, timeframe, limit)
            if exch_id != FALLBACK_EXCHANGES[0]:
                log.warning("[fallback] %s obtido de %s (primária falhou)", symbol, exch_id)
            return df
        except Exception as e:                                       # noqa: BLE001
            err_msg = f"{exch_id}: {type(e).__name__}: {str(e)[:120]}"
            errors.append(err_msg)
            log.warning("[%s] falha em %s -> %s", symbol, exch_id, err_msg)
            continue

    raise RuntimeError(
        f"Todas as exchanges falharam para {symbol} ({timeframe}): " + " | ".join(errors)
    )


# ---------------------------------------------------------------------------
# Fase 2a: suporte multi-timeframe
# ---------------------------------------------------------------------------
# Lista padrão de timeframes usados pela estratégia MTF.
# Pode ser sobrescrita via config.MTF_TIMEFRAMES no futuro.
DEFAULT_MTF_TIMEFRAMES = ("4h", "1h", "15m")

# Quantidade mínima de candles por timeframe (para indicadores como EMA200).
# 4h: 250 candles ≈ 42 dias; 1h: 300 ≈ 12 dias; 15m: 200 ≈ 2 dias
DEFAULT_MTF_LIMITS = {
    "4h":  250,
    "1h":  300,
    "15m": 200,
}


def fetch_multi_tf(
    symbol: str,
    timeframes=None,
    limits: dict = None,
) -> dict:
    """
    Busca OHLCV em múltiplos timeframes para o mesmo ativo.

    Args:
        symbol:     par no formato ccxt (ex: "BTC/USDT")
        timeframes: tupla/lista de timeframes (default: 4h, 1h, 15m)
        limits:     dict {timeframe: int}; usa DEFAULT_MTF_LIMITS se None

    Returns:
        dict { timeframe: pd.DataFrame } — DataFrames OHLCV completos.
        Timeframes que falharem em TODAS as exchanges são omitidos do dict
        (não levanta exceção global — permite fallback parcial na estratégia).

    Nota:
        Cada chamada interna reutiliza fetch_ohlcv(), portanto herda
        automaticamente o fallback gateio -> binance -> bybit.
    """
    timeframes = tuple(timeframes) if timeframes else DEFAULT_MTF_TIMEFRAMES
    limits = limits or DEFAULT_MTF_LIMITS

    result: dict = {}
    for tf in timeframes:
        tf_limit = limits.get(tf, config.CANDLES_LIMIT)
        try:
            result[tf] = fetch_ohlcv(symbol, timeframe=tf, limit=tf_limit)
        except Exception as e:                                       # noqa: BLE001
            log.warning("[multi_tf] %s @ %s falhou em todas as fontes: %s",
                        symbol, tf, str(e)[:120])
            # Não adiciona ao dict; a estratégia decide como reagir
            continue

    return result
