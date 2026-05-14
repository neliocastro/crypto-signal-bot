"""
Implementa a Estratégia MACD + EMA200 (estratégia 3.3).
Retorna Signal com Entry, SL, TP1, TP2 e confiança 0-10.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd
from . import config
from .indicators import get_latest_values

@dataclass
class Signal:
    symbol: str
    timestamp: str
    side: str            # "LONG" ou "SHORT"
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    confidence: int      # 0 a 10
    rr_ratio: float
    rsi: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

def evaluate(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    """
    Avalia o DataFrame enriquecido e retorna Signal ou None.

    LONG:
      - close > ema200
      - cruzamento MACD para cima (macd_diff_prev <= 0 e macd_diff > 0)
      - RSI entre 40 e 70
    SHORT:
      - close < ema200
      - cruzamento MACD para baixo
      - RSI entre 30 e 60

    SL: 1.5 * ATR  |  TP1: R:R 1:1  |  TP2: R:R 1:2
    """
    if df is None or df.empty or len(df) < 200:
        return None

    v = get_latest_values(df)
    if not v:
        return None

    required = ["close", "ema200", "macd_diff", "macd_diff_prev", "atr", "rsi"]
    if any(v.get(k) is None for k in required):
        return None

    close          = v["close"]
    ema50          = v.get("ema50")
    ema200         = v["ema200"]
    macd_diff      = v["macd_diff"]
    macd_diff_prev = v["macd_diff_prev"]
    atr            = v["atr"]
    rsi            = v["rsi"]

    sl_mult  = getattr(config, "ATR_SL_MULT", 1.5)
    tp1_mult = getattr(config, "TP1_RR", 1.0)
    tp2_mult = getattr(config, "TP2_RR", 2.0)

    side: Optional[str] = None
    score = 0
    reasons = []

    long_ok  = close > ema200 and macd_diff_prev <= 0 < macd_diff and 40 <= rsi <= 70
    short_ok = close < ema200 and macd_diff_prev >= 0 > macd_diff and 30 <= rsi <= 60

    if long_ok:
        side = "LONG"
        score = 6  # base
        reasons.append("Preço acima da EMA200")
        reasons.append("Cruzamento MACD de alta")
        reasons.append(f"RSI saudável ({rsi:.1f})")
        if ema50 and close > ema50:
            score += 2
            reasons.append("Preço acima da EMA50")
        if abs(macd_diff) > abs(macd_diff_prev):
            score += 2
            reasons.append("Momentum MACD acelerando")
    elif short_ok:
        side = "SHORT"
        score = 6
        reasons.append("Preço abaixo da EMA200")
        reasons.append("Cruzamento MACD de baixa")
        reasons.append(f"RSI saudável ({rsi:.1f})")
        if ema50 and close < ema50:
            score += 2
            reasons.append("Preço abaixo da EMA50")
        if abs(macd_diff) > abs(macd_diff_prev):
            score += 2
            reasons.append("Momentum MACD acelerando")

    if side is None:
        return None

    entry = close
    if side == "LONG":
        stop_loss = entry - sl_mult * atr
        risk = entry - stop_loss
        tp1 = entry + tp1_mult * risk
        tp2 = entry + tp2_mult * risk
    else:
        stop_loss = entry + sl_mult * atr
        risk = stop_loss - entry
        tp1 = entry - tp1_mult * risk
        tp2 = entry - tp2_mult * risk

    if risk <= 0:
        return None

    rr = round(tp2_mult, 2)

    ts = v.get("timestamp")
    ts_str = str(ts) if ts is not None else ""

    return Signal(
        symbol=symbol,
        timestamp=ts_str,
        side=side,
        entry=round(entry, 6),
        stop_loss=round(stop_loss, 6),
        take_profit_1=round(tp1, 6),
        take_profit_2=round(tp2, 6),
        confidence=min(score, 10),
        rr_ratio=rr,
        rsi=round(rsi, 2),
        reason=" | ".join(reasons),
    )
