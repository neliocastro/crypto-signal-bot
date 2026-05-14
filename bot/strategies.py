"""
Avalia o DataFrame enriquecido e retorna um Signal (ou None).
Função pública obrigatória: evaluate(symbol, df) -> Signal | None.
"""
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd

@dataclass
class Signal:
    symbol: str
    side: str                      # "LONG" ou "SHORT"
    entry: float
    stop: float
    targets: List[float] = field(default_factory=list)
    confidence: int = 0            # 0..10
    reasons: List[str] = field(default_factory=list)
    timeframe: str = "1h"
    timestamp: str = ""            # ISO do candle que disparou

# ---------- regras auxiliares ----------
def _trend_up(row) -> bool:
    return row["ema21"] > row["ema50"] > row["ema200"]

def _trend_down(row) -> bool:
    return row["ema21"] < row["ema50"] < row["ema200"]

def _cross_up(prev, curr, a: str, b: str) -> bool:
    return prev[a] <= prev[b] and curr[a] > curr[b]

def _cross_down(prev, curr, a: str, b: str) -> bool:
    return prev[a] >= prev[b] and curr[a] < curr[b]

# ---------- API pública ----------
def evaluate(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    """
    Retorna Signal se houver setup válido, caso contrário None.
    Estratégia: confluência de tendência (EMAs) + RSI + cruzamento MACD + volume.
    """
    if df is None or len(df) < 210:   # precisa de histórico p/ EMA200
        return None

    # usamos a penúltima vela (fechada). a última pode estar em formação.
    curr = df.iloc[-2]
    prev = df.iloc[-3]

    reasons_long: List[str] = []
    reasons_short: List[str] = []

    # --- viés LONG ---
    if _trend_up(curr):
        reasons_long.append("Tendência de alta (EMA21>50>200)")
    if 40 <= curr["rsi14"] <= 65:
        reasons_long.append(f"RSI saudável ({curr['rsi14']:.1f})")
    if _cross_up(prev, curr, "macd", "macd_signal"):
        reasons_long.append("MACD cruzou p/ cima")
    if curr["vol_ratio"] and curr["vol_ratio"] > 1.2:
        reasons_long.append(f"Volume {curr['vol_ratio']:.2f}x média")
    if curr["close"] > curr["ema21"] and prev["close"] <= prev["ema21"]:
        reasons_long.append("Rompimento da EMA21")

    # --- viés SHORT ---
    if _trend_down(curr):
        reasons_short.append("Tendência de baixa (EMA21<50<200)")
    if 35 <= curr["rsi14"] <= 60:
        reasons_short.append(f"RSI em zona de venda ({curr['rsi14']:.1f})")
    if _cross_down(prev, curr, "macd", "macd_signal"):
        reasons_short.append("MACD cruzou p/ baixo")
    if curr["vol_ratio"] and curr["vol_ratio"] > 1.2:
        reasons_short.append(f"Volume {curr['vol_ratio']:.2f}x média")
    if curr["close"] < curr["ema21"] and prev["close"] >= prev["ema21"]:
        reasons_short.append("Perdeu a EMA21")

    score_long = len(reasons_long)
    score_short = len(reasons_short)

    # exige pelo menos 3 confluências
    if max(score_long, score_short) < 3:
        return None

    side = "LONG" if score_long >= score_short else "SHORT"
    reasons = reasons_long if side == "LONG" else reasons_short
    score = score_long if side == "LONG" else score_short

    entry = float(curr["close"])
    atr = float(curr["atr14"]) if not pd.isna(curr["atr14"]) else entry * 0.01

    if side == "LONG":
        stop = entry - 1.5 * atr
        targets = [entry + 1.0 * atr, entry + 2.0 * atr, entry + 3.5 * atr]
    else:
        stop = entry + 1.5 * atr
        targets = [entry - 1.0 * atr, entry - 2.0 * atr, entry - 3.5 * atr]

    # confiança 0..10 (cada confluência ~2 pontos, teto 10)
    confidence = min(10, score * 2)

    ts = curr["timestamp"]
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    else:
        ts = str(ts)

    return Signal(
        symbol=symbol,
        side=side,
        entry=round(entry, 6),
        stop=round(stop, 6),
        targets=[round(t, 6) for t in targets],
        confidence=confidence,
        reasons=reasons,
        timeframe="1h",
        timestamp=ts,
    )
