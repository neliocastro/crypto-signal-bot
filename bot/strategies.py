"""
Estrategia de geracao de sinais (LONG only).

Funcao publica: evaluate_signal(symbol, df, **extras) -> dict | None

Estrategias ATIVAS (2026-08-24 - limpeza de codigo morto):
  1) Breakout / Tendencia   -> fast-path por simbolo (BREAKOUT_SYMBOLS, ex.: HYPE)
  2) Acumulo (RSI sobrevenda) -> fast-path por simbolo (ACCUMULATION_SYMBOLS, ex.: PAXG)

Fora destes fast-paths, evaluate_signal retorna None: o ativo opera
EXCLUSIVAMENTE pelo trilho Mare Alta D1 (bot/mare_alta.py), que tem scan
proprio e nao passa por aqui.

REMOVIDO em 2026-08-24 (commit de limpeza) - eram codigo morto:
  - _check_aggressive_macd  (MACD-only "agressivo"): rodava em todo scan para
    6 ativos e o resultado era 100% descartado pelo INTRADAY_EXEC_ALLOWLIST
    do main.py. Nunca gerou Telegram nem ordem.
  - _check_integrada_long / _check_tendencia_macd_long e a fusao
    "Integrada + MACD (Confluencia)": inalcancaveis desde que o perfil
    agressivo passou a interceptar todos os ativos com `return`.
Historico completo em docs/limpeza_estrategias_2026-08-24.md.
Rollback: `git revert` do commit de limpeza.

Aceita chamadas em qualquer ordem/forma para evitar
"got multiple values for argument".
"""
from typing import Optional, Dict, Any, List
import pandas as pd

# ---------- helpers ----------
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


# ---------- estrategia: Acumulo por sobrevenda (RSI) ----------
def _check_accumulation(df_tf, symbol: str, exchange: str,
                        timeframe: str = "4h",
                        rsi_threshold: float = 30.0,
                        rsi_extreme: float = 20.0,
                        cooldown_hours: float = 24.0,
                        state_file: str = "state/accumulation_signals.json"
                        ) -> Optional[Dict[str, Any]]:
    """
    Estrategia de ACUMULO por sobrevenda (BUY only, sem stop nem alvo de venda).

    Dispara quando o RSI CRUZA para baixo do `rsi_threshold` (entrada na zona de
    sobrevenda) no timeframe definido. Um cooldown evita spam enquanto o RSI fica
    preso abaixo do threshold. Pensado p/ ouro digital (PAXG): DCA inteligente.
    Sem stop e sem take-profit -> e acumulo (hold), nao trade.
    """
    if df_tf is None or not isinstance(df_tf, pd.DataFrame) or len(df_tf) < 3:
        return None
    try:
        curr = df_tf.iloc[-2]   # ultima vela FECHADA
        prev = df_tf.iloc[-3]
        rsi_curr = float(curr["rsi"])
        rsi_prev = float(prev["rsi"])
        price    = float(curr["close"])
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    if any(_is_nan(v) for v in (rsi_curr, rsi_prev, price)):
        return None

    # gatilho: cruzou para BAIXO do threshold (entrada na zona)
    crossed_down = (rsi_prev >= rsi_threshold) and (rsi_curr < rsi_threshold)
    if not crossed_down:
        return None

    # cooldown anti-spam (persistido em state_file; o workflow commita state/)
    import json, os as _os
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    _state = {}
    try:
        if _os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as fh:
                _state = json.load(fh) or {}
        last_iso = _state.get(symbol)
        if last_iso:
            last_dt = datetime.fromisoformat(last_iso)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if now - last_dt < timedelta(hours=float(cooldown_hours)):
                return None  # ainda em cooldown -> nao reenvia
    except Exception:
        _state = {}  # estado corrompido -> trata como sem cooldown

    extreme = rsi_curr < float(rsi_extreme)

    # grava o disparo (best-effort; nunca quebra o scan)
    try:
        _dir = _os.path.dirname(state_file)
        if _dir:
            _os.makedirs(_dir, exist_ok=True)
        _state[symbol] = now.isoformat()
        with open(state_file, "w", encoding="utf-8") as fh:
            json.dump(_state, fh, indent=2)
    except Exception:
        pass

    ts = curr["timestamp"] if "timestamp" in df_tf.columns else df_tf.index[-2]
    ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    reasons = [
        f"RSI {timeframe} caiu para {rsi_curr:.1f} (< {rsi_threshold:.0f}) - sobrevenda",
        "Reserva de valor (ouro digital): acumular na fraqueza",
        "Sem stop/alvo de venda - estrategia de DCA (hold)",
    ]
    if extreme:
        reasons.insert(1, f"Sobrevenda EXTREMA (RSI < {rsi_extreme:.0f}) - oportunidade rara")

    return {
        "symbol":      symbol,
        "side":        "BUY",
        "signal_type": "accumulation",
        "strategy":    "Acúmulo (RSI sobrevenda)",
        "entry":       round(price, 6),
        "rsi":         round(rsi_curr, 2),
        "timeframe":   timeframe,
        "extreme":     extreme,
        "exchange":    exchange,
        "confidence":  9 if extreme else 7,
        "reasons":     reasons,
        "timestamp":   ts,
    }


# ---------- estrategia: Breakout / Trend-following ----------
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
    tp1   = entry + (2.0 * atr_mult) * atr_c   # R:R 1:2 (informativo)
    tp2   = entry + (3.0 * atr_mult) * atr_c   # R:R 1:3 (informativo)
    risk   = abs(entry - stop)
    reward = abs(tp1 - entry)
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
        "strategy":      "Breakout / Tendência" + (" [SHADOW]" if shadow else ""),
        "entry":         round(entry, 8),
        "stop":          round(stop, 8),
        "tp1":           round(tp1, 8),
        "tp2":           round(tp2, 8),
        "targets":       [round(tp1, 8), round(tp2, 8)],
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
    Avalia 1 ativo nos fast-paths ATIVOS. Retorna dict com sinal ou None.

    Roteamento (unico caminho existente apos a limpeza de 2026-08-24):
      symbol em BREAKOUT_SYMBOLS     -> _check_breakout_trend
      symbol em ACCUMULATION_SYMBOLS -> _check_accumulation
      qualquer outro                 -> None (opera so via Mare Alta D1)

    df_4h / df_15m continuam sendo aceitos: o main.py os usa para o
    diagnostico MTF no Telegram (_check_trend_4h / _check_pullback_15m) e o
    fast-path de acumulo consome o df_4h.
    """
    symbol, df, timeframe, exchange, df_4h, df_15m = _parse_args(list(args), dict(kwargs))

    if df is None or not isinstance(df, pd.DataFrame) or len(df) < 210:
        return None
    if not symbol:
        symbol = "UNKNOWN"

    # Fast-path BREAKOUT / TREND-FOLLOWING (ex.: HYPE).
    # Ativo dedicado: se BREAKOUT_ENABLED e o simbolo esta em BREAKOUT_SYMBOLS,
    # usa SO o breakout. Falha segura via except.
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

    # Fast-path ACUMULACAO (ex.: PAXG - ouro digital).
    # Ativo dedicado: RSI sobrevendido (cruza p/ baixo) no TF definido ->
    # sinal de COMPRA p/ acumulo (sem stop/alvo). Usa o df do TF (4h via MTF).
    try:
        from .config import ACCUMULATION_ENABLED, ACCUMULATION_SYMBOLS
        if ACCUMULATION_ENABLED and symbol in (ACCUMULATION_SYMBOLS or {}):
            _ap = ACCUMULATION_SYMBOLS[symbol]
            _acc_tf = _ap.get("timeframe", "4h")
            _df_acc = df_4h if _acc_tf == "4h" else df
            try:
                from .config import ACCUMULATION_STATE_FILE as _acc_state
            except Exception:
                _acc_state = "state/accumulation_signals.json"
            return _check_accumulation(
                _df_acc, symbol, exchange,
                timeframe=_acc_tf,
                rsi_threshold=float(_ap.get("rsi_threshold", 30.0)),
                rsi_extreme=float(_ap.get("rsi_extreme", 20.0)),
                cooldown_hours=float(_ap.get("cooldown_hours", 24.0)),
                state_file=_acc_state,
            )
    except Exception:
        pass  # degradacao segura

    # Sem fast-path para este ativo: nao ha caminho legado.
    # BTC/SOL/TRX/BNB operam exclusivamente pelo Mare Alta D1.
    return None


# ---------- Fase 2b: helpers Multi-TimeFrame (usados pelo main.py no diag) ----------
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
