"""
Estratégia de geração de sinais.
Função pública: evaluate_signal(symbol, df) -> dict | None
"""
from typing import Optional, Dict, Any, List
import pandas as pd

def _trend_up(r):   return r["ema21"] > r["ema50"] > r["ema200"]
def _trend_down(r): return r["ema21"] < r["ema50"] < r["ema200"]
def _xup(p, c, a, b):   return p[a] <= p[b] and c[a] > c[b]
def _xdown(p, c, a, b): return p[a] >= p[b] and c[a] < c[b]

def evaluate_signal(symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Avalia um ativo. Retorna dict com o sinal ou None se não houver setup.

    Dict retornado:
      {
        "symbol", "side" ("LONG"/"SHORT"),
        "entry", "stop", "tp1", "tp2", "tp3",
        "confidence" (0-10), "reasons" (list[str]),
        "timestamp"
      }
    """
    if df is None or len(df) < 210:
        return None

    # vela fechada (penúltima) e a anterior para detectar cruzamentos
    curr = df.iloc[-2]
    prev = df.iloc[-3]

    long_reasons:  List[str] = []
    short_reasons: List[str] = []

    # ---- LONG ----
    if _trend_up(curr):
        long_reasons.append("Tendência de alta (EMA21>50>200)")
    if 40 <= curr["rsi"] <= 65:
        long_reasons.append(f"RSI saudável ({curr['rsi']:.1f})")
    if _xup(prev, curr, "macd", "macd_signal"):
        long_reasons.append("MACD cruzou para cima")
    if pd.notna(curr["vol_ratio"]) and curr["vol_ratio"] > 1.2:
        long_reasons.append(f"Volume {curr['vol_ratio']:.2f}x da média")
    if curr["close"] > curr["ema21"] and prev["close"] <= prev["ema21"]:
        long_reasons.append("Rompimento da EMA21")

    # ---- SHORT ----
    if _trend_down(curr):
        short_reasons.append("Tendência de baixa (EMA21<50<200)")
    if 35 <= curr["rsi"] <= 60:
        short_reasons.append(f"RSI fraco ({curr['rsi']:.1f})")
    if _xdown(prev, curr, "macd", "macd_signal"):
        short_reasons.append("MACD cruzou para baixo")
    if pd.notna(curr["vol_ratio"]) and curr["vol_ratio"] > 1.2:
        short_reasons.append(f"Volume {curr['vol_ratio']:.2f}x da média")
    if curr["close"] < curr["ema21"] and prev["close"] >= prev["ema21"]:
        short_reasons.append("Perdeu a EMA21")

    sl, ss = len(long_reasons), len(short_reasons)
    if max(sl, ss) < 3:           # exige pelo menos 3 confirmações
        return None

    side = "LONG" if sl >= ss else "SHORT"
    reasons = long_reasons if side == "LONG" else short_reasons
    score = sl if side == "LONG" else ss
    confidence = min(10, score * 2)   # 3→6, 4→8, 5→10

    entry = float(curr["close"])
    atr = float(curr["atr"]) if pd.notna(curr["atr"]) else entry * 0.01

    if side == "LONG":
        stop = entry - 1.5 * atr
        tp1, tp2, tp3 = entry + 1.0 * atr, entry + 2.0 * atr, entry + 3.5 * atr
    else:
        stop = entry + 1.5 * atr
        tp1, tp2, tp3 = entry - 1.0 * atr, entry - 2.0 * atr, entry - 3.5 * atr

    ts = curr["timestamp"] if "timestamp" in df.columns else df.index[-2]
    ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    return {
        "symbol": symbol,
        "side": side,
        "entry": round(entry, 6),
        "stop":  round(stop, 6),
        "tp1":   round(tp1, 6),
        "tp2":   round(tp2, 6),
        "tp3":   round(tp3, 6),
        "confidence": confidence,
        "reasons": reasons,
        "timestamp": ts,
    }

# aliases defensivos (não atrapalham)
evaluate_signals = evaluate_signal
evaluate = evaluate_signal
