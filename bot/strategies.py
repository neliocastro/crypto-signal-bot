"""
Estrategia de geracao de sinais (LONG only).

Funcao publica: evaluate_signal(symbol, df, **extras) -> dict | None

Estrategias implementadas:
  1) Integrada Curto Prazo  -> VWAP + EMAs(9/21/50) + MACD + RSI + pullback
  2) Tendencia MACD         -> EMA200 + MACD crossover abaixo da linha zero

Filtro direcional (transversal): so opera LONG se preco > VWAP.

Aceita chamadas em qualquer ordem/forma para evitar
"got multiple values for argument".
"""
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd

# ---------- helpers ----------
def _xup(p, c, a, b):   return p[a] <= p[b] and c[a] > c[b]

def _is_nan(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)

def _safe(curr, key, default=float("nan")):
    try:
        v = curr[key]
        return v if not _is_nan(v) else default
    except Exception:
        return default

# ---------- parser tolerante ----------
def _parse_args(args, kwargs) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[str], Optional[str]]:
    """Extrai (symbol, df, timeframe, exchange) de qualquer combinacao de args/kwargs."""
    symbol = kwargs.pop("symbol", None)
    df = kwargs.pop("df", None)

    if df is None:
        df = (
            kwargs.pop("dataframe", None)
            or kwargs.pop("data", None)
            or kwargs.pop("candles", None)
            or kwargs.pop("ohlcv", None)
        )
    if symbol is None:
        symbol = (
            kwargs.pop("ticker", None)
            or kwargs.pop("pair", None)
            or kwargs.pop("asset", None)
        )

    for a in args:
        if isinstance(a, pd.DataFrame):
            if df is None:
                df = a
        elif isinstance(a, str):
            if symbol is None:
                symbol = a

    timeframe = kwargs.pop("timeframe", None) or kwargs.pop("tf", None)
    exchange  = kwargs.pop("exchange", None)
    kwargs.clear()
    return symbol, df, timeframe, exchange

# ---------- estrategia 1: Integrada Curto Prazo ----------
def _check_integrada_long(prev, curr) -> Optional[List[str]]:
    """
    LONG se:
      - preco > VWAP
      - EMA9 > EMA21 (na vela atual) E EMA9 cruzou acima da EMA21 OU ja estava
      - EMA9 e EMA21 ambas > EMA50
      - MACD: linha > sinal E (de preferencia) acima de zero
      - RSI entre 40 e 65
      - pullback: preco a <=0.5% da EMA9 OU do VWAP
    """
    price = _safe(curr, "close")
    vwap  = _safe(curr, "vwap")
    ema9  = _safe(curr, "ema9")
    ema21 = _safe(curr, "ema21")
    ema50 = _safe(curr, "ema50")
    rsi   = _safe(curr, "rsi")
    macd  = _safe(curr, "macd")
    macd_s= _safe(curr, "macd_signal")

    reasons: List[str] = []

    # VWAP filter (transversal)
    if _is_nan(vwap) or price <= vwap:
        return None
    reasons.append(f"Preco acima do VWAP ({price:.4f} > {vwap:.4f})")

    # EMA alignment
    if _is_nan(ema9) or _is_nan(ema21) or _is_nan(ema50):
        return None
    if not (ema9 > ema21 > ema50):
        return None
    reasons.append("EMAs alinhadas: EMA9 > EMA21 > EMA50")

    # MACD
    if _is_nan(macd) or _is_nan(macd_s):
        return None
    if macd <= macd_s:
        return None
    if macd > 0:
        reasons.append(f"MACD > sinal e acima de zero ({macd:.4f})")
    else:
        reasons.append(f"MACD > sinal (abaixo de zero, sinal mais fraco)")

    # RSI 40-65
    if _is_nan(rsi) or not (40 <= rsi <= 65):
        return None
    reasons.append(f"RSI saudavel ({rsi:.1f})")

    # Pullback simplificado: preco a <=0.5% da EMA9 OU do VWAP
    dist_ema9 = abs(price - ema9) / price * 100.0 if price else 99
    dist_vwap = abs(price - vwap) / price * 100.0 if price else 99
    if min(dist_ema9, dist_vwap) > 0.5:
        return None
    if dist_ema9 <= dist_vwap:
        reasons.append(f"Pullback na EMA9 ({dist_ema9:.2f}% de distancia)")
    else:
        reasons.append(f"Pullback no VWAP ({dist_vwap:.2f}% de distancia)")

    return reasons

# ---------- estrategia 2: Tendencia MACD ----------
def _check_tendencia_macd_long(prev, curr) -> Optional[List[str]]:
    """
    LONG se:
      - preco > EMA200
      - preco > VWAP (filtro direcional transversal)
      - MACD: linha cruzou acima do sinal NA VELA ATUAL
      - cruzamento ocorreu abaixo da linha zero (ou MACD ainda <0 na vela atual)
    """
    price  = _safe(curr, "close")
    ema200 = _safe(curr, "ema200")
    vwap   = _safe(curr, "vwap")
    macd_c = _safe(curr, "macd")
    sig_c  = _safe(curr, "macd_signal")
    macd_p = _safe(prev, "macd")
    sig_p  = _safe(prev, "macd_signal")

    reasons: List[str] = []

    # VWAP transversal
    if _is_nan(vwap) or price <= vwap:
        return None
    reasons.append(f"Preco acima do VWAP ({price:.4f} > {vwap:.4f})")

    # EMA200
    if _is_nan(ema200) or price <= ema200:
        return None
    reasons.append(f"Preco acima da EMA200 ({price:.4f} > {ema200:.4f})")

    # MACD crossover abaixo de zero
    if any(_is_nan(x) for x in [macd_c, sig_c, macd_p, sig_p]):
        return None
    crossed_up = (macd_p <= sig_p) and (macd_c > sig_c)
    if not crossed_up:
        return None
    # ideal: cruzamento abaixo de zero -> verifica se MACD atual ainda <=0
    if macd_c > 0:
        # tolerancia: aceita se a linha de sinal anterior estava <=0
        if sig_p > 0:
            return None
    reasons.append(f"MACD cruzou acima do sinal (linha={macd_c:.4f})")
    if macd_c <= 0:
        reasons.append("Cruzamento ocorreu abaixo da linha zero (setup classico)")

    return reasons

# ---------- funcao principal ----------
def evaluate_signal(*args, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Avalia 1 ativo nas 2 estrategias (LONG only). Retorna dict com sinal ou None.

    Dict retornado:
      {
        "symbol", "side": "LONG",
        "strategy": "Integrada Curto Prazo" | "Tendencia MACD" | "Integrada + MACD",
        "entry", "stop",
        "tp2", "tp3", "targets": [tp2, tp3],
        "risk_reward", "order_type",
        "timeframe", "exchange",
        "confidence" (0-10), "reasons" (list[str]),
        "timestamp"
      }
    """
    symbol, df, timeframe, exchange = _parse_args(list(args), dict(kwargs))

    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 210:
        return None
    if not symbol:
        symbol = "UNKNOWN"

    # vela fechada (penultima) e a anterior para detectar cruzamentos
    curr = df.iloc[-2]
    prev = df.iloc[-3]

    # Executa as 2 estrategias
    r1 = _check_integrada_long(prev, curr)
    r2 = _check_tendencia_macd_long(prev, curr)

    if not r1 and not r2:
        return None

    # Confluencia: as 2 estrategias dispararam (decisao Q)
    if r1 and r2:
        strategy_name = "Integrada + MACD"
        reasons = ["[Confluencia das 2 estrategias]"] + r1 + ["---"] + r2
        confidence = 10
    elif r1:
        strategy_name = "Integrada Curto Prazo"
        reasons = r1
        confidence = 8
    else:
        strategy_name = "Tendencia MACD"
        reasons = r2
        confidence = 7

    # ---------- TP/SL via ATR (2 TPs apenas: R:R 1:2 e 1:3) ----------
    entry = float(curr["close"])
    atr_v = float(curr["atr"]) if not _is_nan(curr["atr"]) else entry * 0.01

    stop = entry - 1.5 * atr_v
    tp2  = entry + 3.0 * atr_v   # R:R 1:2
    tp3  = entry + 4.5 * atr_v   # R:R 1:3

    risk   = abs(entry - stop)
    reward = abs(tp2 - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    # ---------- order_type por distancia da EMA21 ----------
    ema21_v = float(curr["ema21"]) if not _is_nan(curr["ema21"]) else entry
    dist_pct = (abs(entry - ema21_v) / entry * 100.0) if entry else 0.0
    if dist_pct <= 0.3:
        order_type = "Limit"
    elif dist_pct <= 1.0:
        order_type = "Market"
    else:
        order_type = "Stop-Limit"

    ts = curr["timestamp"] if "timestamp" in df.columns else df.index[-2]
    ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    return {
        "symbol":      symbol,
        "side":        "LONG",
        "strategy":    strategy_name,
        "entry":       round(entry, 6),
        "stop":        round(stop, 6),
        "tp2":         round(tp2, 6),
        "tp3":         round(tp3, 6),
        "targets":     [round(tp2, 6), round(tp3, 6)],
        "risk_reward": risk_reward,
        "order_type":  order_type,
        "timeframe":   timeframe,
        "exchange":    exchange,
        "confidence":  confidence,
        "reasons":     reasons,
        "timestamp":   ts,
    }

# aliases defensivos (mantem compat com codigo antigo)
evaluate_signals = evaluate_signal
evaluate = evaluate_signal
