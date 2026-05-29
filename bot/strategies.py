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
def _parse_args(args, kwargs):
    """Extrai (symbol, df, timeframe, exchange, df_4h, df_15m) de qualquer combinacao."""
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
    # Fase 2b.2: dataframes multi-TF (opcionais)
    df_4h  = kwargs.pop("df_4h", None)
    df_15m = kwargs.pop("df_15m", None)
    kwargs.clear()
    return symbol, df, timeframe, exchange, df_4h, df_15m

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
def _check_aggressive_macd(df: pd.DataFrame, symbol: str, timeframe: str, exchange: str) -> Optional[Dict[str, Any]]:
    """
    Fase A: gatilho MACD-only (perfil agressivo).

    Entrada (validada por backtest 90d em LINK & HYPE):
      - MACD line cruzou ACIMA do signal na vela fechada
      - preco > EMA200 (filtro de tendencia minimo)
      - 40 <= RSI <= 70

    Saida no mesmo formato de evaluate_signal (compativel com telegram_sender).
    Confidence fixado em 5 (perfil agressivo).
    """
    try:
        curr = df.iloc[-2]
        prev = df.iloc[-3]
    except Exception:
        return None

    try:
        macd_prev   = float(prev["macd"])
        signal_prev = float(prev["macd_signal"])
        macd_curr   = float(curr["macd"])
        signal_curr = float(curr["macd_signal"])
        close_curr  = float(curr["close"])
        ema200_curr = float(curr["ema200"])
        rsi_curr    = float(curr["rsi"])
        atr_curr    = float(curr.get("atr", float("nan")))
        ema21_v     = float(curr["ema21"]) if not _is_nan(curr.get("ema21", float("nan"))) else close_curr
    except (KeyError, ValueError, TypeError):
        return None

    if any(_is_nan(v) for v in (macd_prev, signal_prev, macd_curr, signal_curr,
                                  close_curr, ema200_curr, rsi_curr, atr_curr)):
        return None
    if atr_curr <= 0:
        return None

    crossed_above = (macd_prev <= signal_prev) and (macd_curr > signal_curr)
    above_ema200  = close_curr > ema200_curr
    rsi_ok        = 40.0 <= rsi_curr <= 70.0

    if not (crossed_above and above_ema200 and rsi_ok):
        return None

    entry = close_curr
    stop  = entry - 1.5 * atr_curr
    tp1   = entry + 1.5 * atr_curr   # R:R 1:1 (saida parcial)
    tp2   = entry + 3.0 * atr_curr   # R:R 1:2
    tp3   = entry + 4.5 * atr_curr   # R:R 1:3
    risk   = abs(entry - stop)
    reward = abs(tp2 - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else None

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
        "symbol":       symbol,
        "side":         "LONG",
        "strategy":     "MACD-only (Agressivo)",
        "entry":        round(entry, 8),
        "stop":         round(stop, 8),
        "tp1":          round(tp1, 8),
        "tp2":          round(tp2, 8),
        "tp3":          round(tp3, 8),
        "targets":      [round(tp1, 8), round(tp2, 8), round(tp3, 8)],
        "risk_reward":  risk_reward,
        "order_type":   order_type,
        "timeframe":    timeframe or "1h",
        "exchange":     exchange or "",
        "confidence":   5,
        "reasons":      [
            "[Perfil AGRESSIVO]",
            "MACD cruzou acima do sinal (vela fechada)",
            f"Preco > EMA200 ({close_curr:.2f} > {ema200_curr:.2f})",
            f"RSI saudavel ({rsi_curr:.1f})",
        ],
        "timestamp":    ts,
        "profile":      "agressivo",
    }


# ---------- estrategia D: Breakout / Trend-following (HYPE) ----------
def _check_breakout_trend(df: pd.DataFrame, symbol: str, timeframe: str, exchange: str,
                          lookback: int = 30, atr_mult: float = 2.5,
                          shadow: bool = False) -> Optional[Dict[str, Any]]:
    """
    Estrategia BREAKOUT + TREND-FOLLOWING (LONG only).

    Validada por teste de robustez (2026-05-28) em HYPE/USDT:
      lb=30 atr=2.5 -> PF 2.55, +67% em ~150d, MDD -16.9%.
      Robusto a parametros (9/9 configs PF>1.3); 2/3 janelas lucrativas.
      Risco conhecido: retorno concentrado em 2-3 trades grandes.

    Entrada (vela fechada):
      - EMA9 > EMA21 > EMA50            (tendencia empilhada de alta)
      - close rompe a maxima das ultimas `lookback` velas anteriores
      - RSI > 50                        (momentum, sem teto -> deixa correr)
    Saida: stop inicial = entry - atr_mult*ATR (largo). Usar TRAILING STOP
      manual; alvos R:R 1:2 e 1:3 sao apenas informativos (deixa correr).
    """
    try:
        curr = df.iloc[-2]
    except Exception:
        return None
    try:
        close_c = float(curr["close"])
        ema9_c  = float(curr["ema9"])
        ema21_c = float(curr["ema21"])
        ema50_c = float(curr["ema50"])
        rsi_c   = float(curr["rsi"])
        atr_c   = float(curr.get("atr", float("nan")))
    except (KeyError, ValueError, TypeError):
        return None
    if any(_is_nan(v) for v in (close_c, ema9_c, ema21_c, ema50_c, rsi_c, atr_c)):
        return None
    if atr_c <= 0:
        return None

    # maxima das `lookback` velas ANTERIORES a vela de sinal (sem lookahead)
    try:
        hh = float(df["high"].astype(float).rolling(int(lookback)).max().shift(1).iloc[-2])
    except Exception:
        return None
    if _is_nan(hh):
        return None

    stacked  = ema9_c > ema21_c > ema50_c
    breakout = close_c > hh
    momentum = rsi_c > 50.0
    if not (stacked and breakout and momentum):
        return None

    entry = close_c
    stop  = entry - atr_mult * atr_c
    tp1   = entry + (1.0 * atr_mult) * atr_c   # R:R 1:1 (informativo)
    tp2   = entry + (2.0 * atr_mult) * atr_c   # R:R 1:2 (informativo)
    tp3   = entry + (3.0 * atr_mult) * atr_c   # R:R 1:3 (informativo)
    risk   = abs(entry - stop)
    reward = abs(tp2 - entry)
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    dist_pct = (abs(entry - ema21_c) / entry * 100.0) if entry else 0.0
    if dist_pct <= 0.3:
        order_type = "Limit"
    elif dist_pct <= 1.0:
        order_type = "Market"
    else:
        order_type = "Stop-Limit"

    ts = curr["timestamp"] if "timestamp" in df.columns else df.index[-2]
    ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    tag = "[SHADOW] " if shadow else ""
    reasons = [
        f"{tag}[Perfil TENDENCIA / Breakout]",
        "EMA9 > EMA21 > EMA50 (tendencia empilhada)",
        f"Rompeu maxima das ultimas {lookback} velas ({close_c:.4f} > {hh:.4f})",
        f"RSI com momentum ({rsi_c:.1f} > 50)",
        f"Stop largo {atr_mult}xATR; usar TRAILING STOP (deixa o lucro correr)",
    ]
    if shadow:
        reasons.append("MODO OBSERVACAO: shadow 2-4 semanas antes de operar valendo")

    return {
        "symbol":        symbol,
        "side":          "LONG",
        "strategy":      "Breakout/Tendencia (HYPE)" + (" [SHADOW]" if shadow else ""),
        "entry":         round(entry, 8),
        "stop":          round(stop, 8),
        "tp1":           round(tp1, 8),
        "tp2":           round(tp2, 8),
        "tp3":           round(tp3, 8),
        "targets":       [round(tp1, 8), round(tp2, 8), round(tp3, 8)],
        "risk_reward":   risk_reward,
        "order_type":    order_type,
        "timeframe":     timeframe or "1h",
        "exchange":      exchange or "",
        "confidence":    6,
        "reasons":       reasons,
        "timestamp":     ts,
        "profile":       "tendencia",
        "shadow":        bool(shadow),
        "trailing_stop": True,
    }


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
    symbol, df, timeframe, exchange, df_4h, df_15m = _parse_args(list(args), dict(kwargs))

    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 210:
        return None
    if not symbol:
        symbol = "UNKNOWN"

    # Fase D: fast-path BREAKOUT / TREND-FOLLOWING (ex.: HYPE).
    # Ativo dedicado: se BREAKOUT_ENABLED e o simbolo esta em BREAKOUT_SYMBOLS,
    # usa SO o breakout (nao cai para o caminho normal). Falha segura via except.
    try:
        from .config import BREAKOUT_ENABLED, BREAKOUT_SYMBOLS, BREAKOUT_SHADOW_MODE
        if BREAKOUT_ENABLED and symbol in (BREAKOUT_SYMBOLS or {}):
            _bp = BREAKOUT_SYMBOLS[symbol]
            return _check_breakout_trend(
                df, symbol, timeframe, exchange,
                lookback=int(_bp.get("lookback", 30)),
                atr_mult=float(_bp.get("atr_mult", 2.5)),
                shadow=bool(BREAKOUT_SHADOW_MODE),
            )
    except Exception:
        pass  # degradacao segura

    # Fase A: fast-path do perfil agressivo (MACD-only).
    # Se ACTIVE_PROFILE == "agressivo" e o ativo esta na whitelist,
    # usa apenas o gatilho MACD cross above. NAO faz fallback para o
    # caminho normal (modo agressivo e exclusivo). Falha silenciosa em
    # qualquer Exception -> cai para o caminho normal.
    try:
        from .config import RISK_PROFILES, ACTIVE_PROFILE
        _profile = RISK_PROFILES.get(ACTIVE_PROFILE) or RISK_PROFILES.get("balanceado", {})
        if _profile.get("macd_cross_enough"):
            _approved = _profile.get("approved_symbols") or []
            if symbol in _approved:
                return _check_aggressive_macd(df, symbol, timeframe, exchange)
    except Exception:
        pass  # degradacao segura: cai para o caminho normal

    # vela fechada (penultima) e a anterior para detectar cruzamentos
    curr = df.iloc[-2]
    prev = df.iloc[-3]

    # Executa as 2 estrategias
    r1 = _check_integrada_long(prev, curr)
    r2 = _check_tendencia_macd_long(prev, curr)

    if not r1 and not r2:
        return None

    # ---------- Fase 2b.2: gating Multi-TimeFrame ----------
    mtf_reasons: List[str] = []
    mtf_bonus = 0
    trend_4h = _check_trend_4h(df_4h)
    pullback_15m = _check_pullback_15m(df_15m)

    # 4h: se for explicitamente False -> bloqueia LONG (downtrend macro)
    if trend_4h is False:
        return None
    if trend_4h is True:
        mtf_reasons.append("Tendencia 4h confirmada (EMA50>EMA200, preco>EMA200)")
        mtf_bonus += 1

    # 15m: bonus de timing se houver pullback proximo a EMA9
    if pullback_15m is True:
        mtf_reasons.append("Pullback 15m proximo a EMA9 (timing preciso)")
        mtf_bonus += 1

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

    # Fase 2b.2: anexa contexto MTF
    if mtf_reasons:
        reasons = reasons + ["--- MTF ---"] + mtf_reasons
    confidence = min(10, confidence + mtf_bonus)

    # ---------- TP/SL via ATR (2 TPs apenas: R:R 1:2 e 1:3) ----------
    entry = float(curr["close"])
    atr_v = float(curr["atr"]) if not _is_nan(curr["atr"]) else entry * 0.01

    stop = entry - 1.5 * atr_v
    tp1  = entry + 1.5 * atr_v   # R:R 1:1 (saida parcial)
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
        "tp1":         round(tp1, 6),
        "tp2":         round(tp2, 6),
        "tp3":         round(tp3, 6),
        "targets":     [round(tp1, 6), round(tp2, 6), round(tp3, 6)],
        "risk_reward": risk_reward,
        "order_type":  order_type,
        "timeframe":   timeframe,
        "exchange":    exchange,
        "confidence":  confidence,
        "reasons":     reasons,
        "timestamp":   ts,
    }

# ---------- Fase 2b: helpers Multi-TimeFrame (aditivo, ainda nao plugado) ----------
def _check_trend_4h(df_4h: Optional[pd.DataFrame]) -> Optional[bool]:
    """
    Filtro de tendencia maior no 4h.
    Retorna:
      True  -> tendencia de alta confirmada (EMA50 > EMA200 e preco > EMA200)
      False -> tendencia de baixa (nao operar LONG no 1h)
      None  -> dados insuficientes (estrategia deve decidir o fallback)
    """
    if df_4h is None or not isinstance(df_4h, pd.DataFrame) or len(df_4h) < 210:
        return None
    try:
        last = df_4h.iloc[-2]   # vela fechada
        price  = _safe(last, "close")
        ema50  = _safe(last, "ema50")
        ema200 = _safe(last, "ema200")
        if _is_nan(price) or _is_nan(ema50) or _is_nan(ema200):
            return None
        return bool(price > ema200 and ema50 > ema200)
    except Exception:
        return None


def _check_pullback_15m(df_15m: Optional[pd.DataFrame],
                        max_dist_pct: float = 0.4) -> Optional[bool]:
    """
    Timing fino no 15m: detecta pullback recente proximo a EMA9.

    Retorna:
      True  -> ha pullback (preco a <= max_dist_pct% da EMA9 na vela fechada)
      False -> nao ha pullback
      None  -> dados insuficientes
    """
    if df_15m is None or not isinstance(df_15m, pd.DataFrame) or len(df_15m) < 30:
        return None
    try:
        last = df_15m.iloc[-2]
        price = _safe(last, "close")
        ema9  = _safe(last, "ema9")
        if _is_nan(price) or _is_nan(ema9) or price <= 0:
            return None
        dist_pct = abs(price - ema9) / price * 100.0
        return bool(dist_pct <= max_dist_pct)
    except Exception:
        return None


# aliases defensivos (mantem compat com codigo antigo)
evaluate_signals = evaluate_signal
evaluate = evaluate_signal
