"""
Estratégias de sinais.
Exporta vários nomes (aliases) para casar com qualquer import do main.py:
  generate_signals, evaluate_signals, check_signals, evaluate, analyze, run
"""
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd

@dataclass
class Signal:
    symbol: str
    side: str                       # "LONG" / "SHORT"
    entry: float
    stop: float
    targets: List[float] = field(default_factory=list)
    confidence: int = 0             # 0..10
    reasons: List[str] = field(default_factory=list)
    timeframe: str = "1h"
    timestamp: str = ""

# ---------- helpers ----------
def _trend_up(r):   return r["ema21"] > r["ema50"] > r["ema200"]
def _trend_down(r): return r["ema21"] < r["ema50"] < r["ema200"]
def _xup(p, c, a, b):   return p[a] <= p[b] and c[a] > c[b]
def _xdown(p, c, a, b): return p[a] >= p[b] and c[a] < c[b]

# ---------- núcleo ----------
def _evaluate_one(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    if df is None or len(df) < 210:
        return None

    curr = df.iloc[-2]   # vela fechada
    prev = df.iloc[-3]

    long_r:  List[str] = []
    short_r: List[str] = []

    # LONG
    if _trend_up(curr):
        long_r.append("Tendência de alta (EMA21>50>200)")
    if 40 <= curr["rsi14"] <= 65:
        long_r.append(f"RSI saudável ({curr['rsi14']:.1f})")
    if _xup(prev, curr, "macd", "macd_signal"):
        long_r.append("MACD cruzou p/ cima")
    if pd.notna(curr["vol_ratio"]) and curr["vol_ratio"] > 1.2:
        long_r.append(f"Volume {curr['vol_ratio']:.2f}x")
    if curr["close"] > curr["ema21"] and prev["close"] <= prev["ema21"]:
        long_r.append("Rompimento da EMA21")

    # SHORT
    if _trend_down(curr):
        short_r.append("Tendência de baixa (EMA21<50<200)")
    if 35 <= curr["rsi14"] <= 60:
        short_r.append(f"RSI fraco ({curr['rsi14']:.1f})")
    if _xdown(prev, curr, "macd", "macd_signal"):
        short_r.append("MACD cruzou p/ baixo")
    if pd.notna(curr["vol_ratio"]) and curr["vol_ratio"] > 1.2:
        short_r.append(f"Volume {curr['vol_ratio']:.2f}x")
    if curr["close"] < curr["ema21"] and prev["close"] >= prev["ema21"]:
        short_r.append("Perdeu a EMA21")

    sl, ss = len(long_r), len(short_r)
    if max(sl, ss) < 3:
        return None

    side = "LONG" if sl >= ss else "SHORT"
    reasons = long_r if side == "LONG" else short_r
    score = sl if side == "LONG" else ss

    entry = float(curr["close"])
    atr = float(curr["atr14"]) if pd.notna(curr["atr14"]) else entry * 0.01

    if side == "LONG":
        stop = entry - 1.5 * atr
        targets = [entry + 1.0 * atr, entry + 2.0 * atr, entry + 3.5 * atr]
    else:
        stop = entry + 1.5 * atr
        targets = [entry - 1.0 * atr, entry - 2.0 * atr, entry - 3.5 * atr]

    ts = curr["timestamp"]
    ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    return Signal(
        symbol=symbol,
        side=side,
        entry=round(entry, 6),
        stop=round(stop, 6),
        targets=[round(t, 6) for t in targets],
        confidence=min(10, score * 2),
        reasons=reasons,
        timeframe="1h",
        timestamp=ts,
    )

# ---------- API pública (vários nomes p/ casar com o main.py) ----------
def evaluate(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    """Avalia 1 ativo. Retorna Signal ou None."""
    return _evaluate_one(symbol, df)

def generate_signals(data) -> List[Signal]:
    """
    Aceita:
      - dict {symbol: df}
      - list[tuple(symbol, df)]
    Retorna lista de Signals (sem None).
    """
    out: List[Signal] = []
    if isinstance(data, dict):
        items = data.items()
    else:
        items = data
    for symbol, df in items:
        s = _evaluate_one(symbol, df)
        if s is not None:
            out.append(s)
    return out

# aliases — qualquer nome que o main.py use vai funcionar
evaluate_signals = generate_signals
check_signals    = generate_signals
analyze          = generate_signals
run              = generate_signals
