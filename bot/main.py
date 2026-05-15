"""
Crypto Signal Bot — entrypoint.

Pipeline:
  1. Lê configuração (símbolos, timeframe, exchange).
  2. Busca OHLCV de cada símbolo.
  3. Calcula indicadores (EMA200, RSI14, MACD).
  4. Avalia estratégia → gera sinal qualificado (ou None).
  5. Envia ao Telegram:
       - 1 mensagem por sinal qualificado (format_signal)
       - 1 mensagem-resumo com diagnósticos de TODOS os ativos
"""
from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from .config import SYMBOLS, TIMEFRAME, EXCHANGE
from .data_fetcher import fetch_ohlcv
from .indicators import add_indicators          # <- ver nota abaixo
from .strategies import evaluate_signal         # <- ver nota abaixo
from .sentiment import get_fear_greed
from .telegram_sender import (
    send,
    format_signal,
    format_scan_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot.main")

def _safe_last(series) -> float:
    """Último valor de uma série pandas, tolerante a NaN/empty."""
    try:
        return float(series.iloc[-1])
    except Exception:
        return float("nan")

def scan_symbol(symbol: str) -> dict[str, Any]:
    """
    Roda o pipeline para 1 símbolo e devolve um dict de diagnóstico
    + (opcional) o sinal qualificado.

    Estrutura retornada:
        {
          "symbol": "BTC/USDT",
          "price": 67234.12,
          "ema200": 65890.55,
          "rsi": 58.3,
          "macd": 120.5,
          "macd_signal": 95.1,
          "macd_hist": 25.4,
          "signal": <Signal | None>,
          "error": "msg..."   # somente se algo falhou
        }
    """
    diag: dict[str, Any] = {"symbol": symbol, "signal": None}
    try:
        df = fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=300)
        if df is None or df.empty or len(df) < 200:
            diag["error"] = f"OHLCV insuficiente ({0 if df is None else len(df)} candles)"
            return diag

        df = add_indicators(df)  # deve adicionar: ema200, rsi, macd, macd_signal, macd_hist

        # macd_hist_prev: penúltimo valor do histograma (para detectar aceleração)
        macd_hist_prev = float("nan")
        try:
            if "macd_hist" in df.columns and len(df["macd_hist"]) >= 2:
                macd_hist_prev = float(df["macd_hist"].iloc[-2])
        except Exception:
            pass

        diag.update({
            "price":          _safe_last(df["close"]),
            "ema200":         _safe_last(df["ema200"]),
            "rsi":            _safe_last(df["rsi"]),
            "macd":           _safe_last(df["macd"]),
            "macd_signal":    _safe_last(df["macd_signal"]),
            "macd_hist":      _safe_last(df["macd_hist"]),
            "macd_hist_prev": macd_hist_prev,
            "atr":            _safe_last(df["atr"]) if "atr" in df.columns else float("nan"),
            "vol_ratio":      _safe_last(df["vol_ratio"]) if "vol_ratio" in df.columns else float("nan"),
        })

        # Avalia estratégia → Signal ou None
        sig = evaluate_signal(df, symbol=symbol, timeframe=TIMEFRAME)
        diag["signal"] = sig

    except Exception as e:
        log.exception("Falha no scan de %s", symbol)
        diag["error"] = f"{type(e).__name__}: {e}"

    return diag

def main() -> int:
    log.info("🚀 Iniciando scan | symbols=%s | TF=%s | exchange=%s",
             SYMBOLS, TIMEFRAME, EXCHANGE)

    # 1) Sentimento (Fear & Greed)
    try:
        fg = get_fear_greed()  # esperado: {"score": int, "emoji": str, "label": str}
        log.info("Fear & Greed: %s", fg)
    except Exception as e:
        log.warning("Falha ao obter Fear & Greed: %s", e)
        fg = None

    # 2) Scan de todos os ativos
    diagnostics: list[dict[str, Any]] = []
    qualified_signals = []

    for sym in SYMBOLS:
        log.info("🔎 Analisando %s...", sym)
        d = scan_symbol(sym)
        diagnostics.append(d)
        if d.get("signal"):
            qualified_signals.append(d["signal"])

    # 3) Envia sinais qualificados (1 msg cada)
    for sig in qualified_signals:
        try:
            msg = format_signal(sig, fg=fg)
            ok = send(msg)
            log.info("Sinal %s enviado: %s", sig.symbol, ok)
        except Exception:
            log.error("Falha ao enviar sinal %s\n%s", sig, traceback.format_exc())

    # 4) Envia resumo do scan (sempre)
    try:
        fg_score = fg["score"] if isinstance(fg, dict) else 0
        summary = format_scan_summary(
            diagnostics=diagnostics,
            signals_count=len(qualified_signals),
            fg=fg_score,
            timeframe=TIMEFRAME,
            exchange=EXCHANGE,
        )
        send(summary)
        log.info("📨 Resumo enviado (%d ativos, %d sinais).",
                 len(diagnostics), len(qualified_signals))
    except Exception:
        log.error("Falha ao enviar resumo:\n%s", traceback.format_exc())

    log.info("✅ Scan finalizado.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
