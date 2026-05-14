"""
Implementa a Estratégia MACD + EMA200 (estratégia 3.3).
Retorna sinal qualificado com Entry, SL, TP1, TP2 e nível de confiança.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd
from . import config
from .indicators import get_latest_values

@dataclass
class Signal:
    symbol: str
    timeframe: str
    side: str            # "LONG" ou "SHORT"
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    confidence: str      # "ALTA", "MÉDIA", "BAIXA"
    rr_ratio: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

def _confidence_level(score: int) -> str:
    if score >= 4:
        return "ALTA"
    if score == 3:
        return "MÉDIA"
    return "BAIXA"

def evaluate(df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[Signal]:
    """
    Avalia o DataFrame enriquecido com indicadores e retorna um Signal
    se houver setup válido, ou None caso contrário.

    Regras (estratégia MACD + EMA200):
      LONG:
        - close > ema200 (tendência de alta)
        - cruzamento do MACD para cima (macd_diff_prev <= 0 e macd_diff > 0)
        - RSI entre 40 e 70 (evita sobrecompra extrema)
      SHORT:
        - close < ema200 (tendência de baixa)
        - cruzamento do MACD para baixo (macd_diff_prev >= 0 e macd_diff < 0)
        - RSI entre 30 e 60 (evita sobrevenda extrema)

    Stop Loss: 1.5 * ATR
    TP1: 1 * (entry - SL)  → R:R 1:1
    TP2: 2 * (entry - SL)  → R:R 1:2
    """
    if df is None or df.empty or len(df) < 200:
        return None

    v = get_latest_values(df)
    if not v:
        return None

    required = ["close", "ema200", "macd_diff", "macd_diff_prev", "atr", "rsi"]
    if any(v.get(k) is None for k in required):
        return None

    close = v["close"]
    ema50 = v.get("ema50")
    ema200 = v["ema200"]
    macd_diff = v["macd_diff"]
    macd_diff_prev = v["macd_diff_prev"]
    atr = v["atr"]
    rsi = v["rsi"]

    # Multiplicadores (com fallback caso não estejam no config)
    sl_mult = getattr(config, "ATR_SL_MULT", 1.5)
    tp1_mult = getattr(config, "TP1_RR", 1.0)
    tp2_mult = getattr(config, "TP2_RR", 2.0)

    side: Optional[str] = None
    score = 0
    reasons = []

    # ---- LONG ----
    long_trend = close > ema200
    long_cross = macd_diff_prev <= 0 < macd_diff
    long_rsi_ok = 40 <= rsi <= 70

    # ---- SHORT ----
    short_trend = close < ema200
    short_cross = macd_diff_prev >= 0 > macd_diff
    short_rsi_ok = 30 <= rsi <= 60

    if long_trend and long_cross and long_rsi_ok:
        side = "LONG"
        score = 3
        reasons.append("Preço acima da EMA200 (tendência de alta)")
        reasons.append("Cruzamento de alta do MACD")
        reasons.append(f"RSI saudável ({rsi:.1f})")
        if ema50 and close > ema50:
            score += 1
            reasons.append("Preço acima da EMA50")
        if macd_diff > 0 and macd_diff_prev < 0 and abs(macd_diff) > abs(macd_diff_prev):
            score += 1
            reasons.append("Momentum forte do MACD")

    elif short_trend and short_cross and short_rsi_ok:
        side = "SHORT"
        score = 3
        reasons.append("Preço abaixo da EMA200 (tendência de baixa)")
        reasons.append("Cruzamento de baixa do MACD")
        reasons.append(f"RSI saudável ({rsi:.1f})")
        if ema50 and close < ema50:
            score += 1
            reasons.append("Preço abaixo da EMA50")
        if macd_diff < 0 and macd_diff_prev > 0 and abs(macd_diff) > abs(macd_diff_prev):
            score += 1
            reasons.append("Momentum forte do MACD")

    if side is None:
        return None

    # Cálculo de Entry / SL / TPs
    entry = close
    if side == "LONG":
        stop_loss = entry - sl_mult * atr
        risk = entry - stop_loss
        tp1 = entry + tp1_mult * risk
        tp2 = entry + tp2_mult * risk
    else:  # SHORT
        stop_loss = entry + sl_mult * atr
        risk = stop_loss - entry
        tp1 = entry - tp1_mult * risk
        tp2 = entry - tp2_mult * risk

    if risk <= 0:
        return None

    rr = round((tp2 - entry) / risk if side == "LONG" else (entry - tp2) / risk, 2)

    return Signal(
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        entry=round(entry, 6),
        stop_loss=round(stop_loss, 6),
        take_profit_1=round(tp1, 6),
        take_profit_2=round(tp2, 6),
        confidence=_confidence_level(score),
        rr_ratio=rr,
        reason=" | ".join(reasons),
    )
