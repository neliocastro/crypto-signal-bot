"""
Estratégia 3.3: MACD + EMA200 (Trend-Following com Confirmação de Momentum).
Retorna sinal qualificado com Entry, SL, TP1, TP2 e nível de confiança.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd

@dataclass
class Signal:
    symbol: str
    timeframe: str
    side: str           # "LONG" ou "SHORT"
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    confidence: str     # "ALTA", "MÉDIA", "BAIXA"
    rationale: str

    def to_dict(self):
        return asdict(self)

def _calc_levels(side: str, entry: float, atr: float):
    """
    Stop = 1.5 ATR | TP1 = 1R (1.5 ATR) | TP2 = 2R (3.0 ATR)
    """
    sl_dist = 1.5 * atr
    if side == "LONG":
        sl = entry - sl_dist
        tp1 = entry + sl_dist          # R:R 1:1
        tp2 = entry + (2 * sl_dist)    # R:R 1:2
    else:  # SHORT
        sl = entry + sl_dist
        tp1 = entry - sl_dist
        tp2 = entry - (2 * sl_dist)
    return round(sl, 6), round(tp1, 6), round(tp2, 6)

def _confidence_score(rsi: float, macd_diff: float, macd_diff_prev: float,
                      side: str) -> str:
    """
    ALTA  → MACD diff acelerando + RSI em zona favorável (não extremo)
    MÉDIA → MACD apenas cruzou
    BAIXA → sinal marginal
    """
    accelerating = abs(macd_diff) > abs(macd_diff_prev)

    if side == "LONG":
        rsi_ok = 50 <= rsi <= 70
    else:
        rsi_ok = 30 <= rsi <= 50

    if accelerating and rsi_ok:
        return "ALTA"
    if accelerating or rsi_ok:
        return "MÉDIA"
    return "BAIXA"

def evaluate_macd_ema200(df: pd.DataFrame, symbol: str, timeframe: str
                        ) -> Optional[Signal]:
    """
    Regras da Estratégia 3.3:

    LONG:
      - Preço acima da EMA200 (tendência de alta)
      - Cruzamento MACD para cima (macd > signal AGORA, macd <= signal antes)
      - RSI entre 50 e 70 (momentum saudável, sem sobrecompra)

    SHORT:
      - Preço abaixo da EMA200 (tendência de baixa)
      - Cruzamento MACD para baixo (macd < signal AGORA, macd >= signal antes)
      - RSI entre 30 e 50

    Retorna Signal ou None.
    """
    if df is None or len(df) < 210:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Verifica se indicadores estão preenchidos
    needed = ["close", "ema200", "macd", "macd_signal", "macd_diff", "rsi", "atr"]
    for col in needed:
        if col not in df.columns or pd.isna(last[col]) or pd.isna(prev[col]):
            return None

    close = float(last["close"])
    ema200 = float(last["ema200"])
    rsi = float(last["rsi"])
    atr = float(last["atr"])

    macd_now = float(last["macd"])
    sig_now = float(last["macd_signal"])
    macd_prev = float(prev["macd"])
    sig_prev = float(prev["macd_signal"])
    macd_diff = float(last["macd_diff"])
    macd_diff_prev = float(prev["macd_diff"])

    cross_up = (macd_prev <= sig_prev) and (macd_now > sig_now)
    cross_down = (macd_prev >= sig_prev) and (macd_now < sig_now)

    side = None
    rationale = ""

    if close > ema200 and cross_up and 50 <= rsi <= 70:
        side = "LONG"
        rationale = (
            f"Preço {close:.4f} acima da EMA200 ({ema200:.4f}). "
            f"MACD cruzou para cima. RSI={rsi:.1f} (zona saudável)."
        )
    elif close < ema200 and cross_down and 30 <= rsi <= 50:
        side = "SHORT"
        rationale = (
            f"Preço {close:.4f} abaixo da EMA200 ({ema200:.4f}). "
            f"MACD cruzou para baixo. RSI={rsi:.1f} (zona saudável)."
        )
    else:
        return None

    sl, tp1, tp2 = _calc_levels(side, close, atr)
    conf = _confidence_score(rsi, macd_diff, macd_diff_prev, side)

    return Signal(
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        entry=round(close, 6),
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        confidence=conf,
        rationale=rationale,
    )

def format_signal_message(sig: Signal) -> str:
    """Formata o sinal como mensagem Telegram (Markdown)."""
    emoji = "🟢" if sig.side == "LONG" else "🔴"
    conf_emoji = {"ALTA": "🔥", "MÉDIA": "⚡", "BAIXA": "💧"}.get(sig.confidence, "")

    return (
        f"{emoji} *{sig.side} {sig.symbol}* ({sig.timeframe})\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Entry:* `{sig.entry}`\n"
        f"🛑 *Stop Loss:* `{sig.stop_loss}`\n"
        f"✅ *TP1:* `{sig.take_profit_1}` (1R)\n"
        f"🎯 *TP2:* `{sig.take_profit_2}` (2R)\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{conf_emoji} *Confiança:* {sig.confidence}\n"
        f"📝 {sig.rationale}"
    )
