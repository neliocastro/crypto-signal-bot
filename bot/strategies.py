"""
Implementa a Estratégia MACD + EMA200 (sua estratégia 3.3).
Retorna sinal qualificado com Entry, SL, TP1, TP2 e nível de confiança.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd
from . import config

@dataclass
class Signal:
    symbol: str
    side: str            # "BUY" ou "SELL"
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rr_tp1: float
    confidence: int      # 1-10
    risk_level: str      # Baixo / Médio / Alto
    rationale: str
    timestamp: str       # ISO do candle de gatilho
    extras: dict         # indicadores no momento

def _macd_crossed_up(prev, curr) -> bool:
    return prev["macd"] <= prev["macd_sig"] and curr["macd"] > curr["macd_sig"]

def _macd_crossed_down(prev, curr) -> bool:
    return prev["macd"] >= prev["macd_sig"] and curr["macd"] < curr["macd_sig"]

def _risk_level(stop_pct: float) -> str:
    if stop_pct < 2:
        return "Baixo"
    if stop_pct <= 5:
        return "Médio"
    return "Alto"

def evaluate(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    """
    Avalia o ÚLTIMO candle FECHADO (df.iloc[-2]) contra o anterior (df.iloc[-3]).
    Ignoramos df.iloc[-1] porque pode estar em formação.
    """
    if len(df) < 3:
        return None

    curr = df.iloc[-2]
    prev = df.iloc[-3]

    price       = curr["close"]
    ema200      = curr["ema200"]
    rsi         = curr["rsi"]
    macd_val    = curr["macd"]
    macd_sig    = curr["macd_sig"]
    atr         = curr["atr"]
    vol         = curr["volume"]
    vol_ma      = curr["vol_ma20"]

    p = config.PROFILE
    sl_dist = p["atr_multiplier_sl"] * atr

    # =========== SINAL DE COMPRA ===========
    if _macd_crossed_up(prev, curr) and price > ema200:
        confidence = 5
        reasons = ["Cruzamento MACD de alta", "Preço acima da EMA200"]

        # Confluência: cruzamento abaixo da linha zero (entrada mais cedo na reversão)
        if macd_val < 0:
            confidence += 1
            reasons.append("Cross abaixo da linha zero (early entry)")

        # RSI saudável (40-65)
        if 40 <= rsi <= 65:
            confidence += 1
            reasons.append(f"RSI saudável ({rsi:.1f})")
        elif rsi > 70:
            confidence -= 1
            reasons.append(f"RSI sobrecomprado ({rsi:.1f})")

        # Alinhamento das EMAs
        if curr["ema9"] > curr["ema21"] > curr["ema50"]:
            confidence += 1
            reasons.append("EMAs 9>21>50 alinhadas")

        # Volume acima da média
        if vol_ma and vol > vol_ma:
            confidence += 1
            reasons.append("Volume acima da média 20")

        confidence = max(1, min(10, confidence))

        entry = price
        stop  = entry - sl_dist
        tp1   = entry + p["tp1_rr"] * sl_dist
        tp2   = entry + p["tp2_rr"] * sl_dist
        stop_pct = (sl_dist / entry) * 100

        if confidence < p["confianca_minima"]:
            return None

        return Signal(
            symbol=symbol,
            side="BUY",
            entry=round(entry, 6),
            stop_loss=round(stop, 6),
            take_profit_1=round(tp1, 6),
            take_profit_2=round(tp2, 6),
            rr_tp1=p["tp1_rr"],
            confidence=confidence,
            risk_level=_risk_level(stop_pct),
            rationale=" | ".join(reasons),
            timestamp=str(curr.name),
            extras={
                "rsi": round(rsi, 2),
                "macd": round(macd_val, 6),
                "macd_signal": round(macd_sig, 6),
                "ema200": round(ema200, 6),
                "stop_pct": round(stop_pct, 2),
            },
        )

    # =========== SINAL DE VENDA ===========
    if _macd_crossed_down(prev, curr) and price < ema200:
        confidence = 5
        reasons = ["Cruzamento MACD de baixa", "Preço abaixo da EMA200"]

        if macd_val > 0:
            confidence += 1
            reasons.append("Cross acima da linha zero (early entry)")

        if 35 <= rsi <= 60:
            confidence += 1
            reasons.append(f"RSI saudável ({rsi:.1f})")
        elif rsi < 30:
            confidence -= 1
            reasons.append(f"RSI sobrevendido ({rsi:.1f})")

        if curr["ema9"] < curr["ema21"] < curr["ema50"]:
            confidence += 1
            reasons.append("EMAs 9<21<50 alinhadas")

        if vol_ma and vol > vol_ma:
            confidence += 1
            reasons.append("Volume acima da média 20")

        confidence = max(1, min(10, confidence))

        entry = price
        stop  = entry + sl_dist
        tp1   = entry - p["tp1_rr"] * sl_dist
        tp2   = entry - p["tp2_rr"] * sl_dist
        stop_pct = (sl_dist / entry) * 100

        if confidence < p["confianca_minima"]:
            return None

        return Signal(
            symbol=symbol,
            side="SELL",
            entry=round(entry, 6),
            stop_loss=round(stop, 6),
            take_profit_1=round(tp1, 6),
            take_profit_2=round(tp2, 6),
            rr_tp1=p["tp1_rr"],
            confidence=confidence,
            risk_level=_risk_level(stop_pct),
            rationale=" | ".join(reasons),
            timestamp=str(curr.name),
            extras={
                "rsi": round(rsi, 2),
                "macd": round(macd_val, 6),
                "macd_signal": round(macd_sig, 6),
                "ema200": round(ema200, 6),
                "stop_pct": round(stop_pct, 2),
            },
        )

    return None
