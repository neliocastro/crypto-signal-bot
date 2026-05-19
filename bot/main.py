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
try:
    from .config import MTF_ENABLED                              # Fase 2b.2
except ImportError:
    MTF_ENABLED = False
from .data_fetcher import fetch_ohlcv, fetch_multi_tf            # Fase 2b.2
from .indicators import add_indicators          # <- ver nota abaixo
from .strategies import evaluate_signal         # <- ver nota abaixo
from .sentiment import get_fear_greed
from .telegram_sender import (
    send,
    format_signal,
    format_scan_summary,
)
try:
    from .config import DASHBOARD_ENABLED
except ImportError:
    DASHBOARD_ENABLED = False
try:
    from .dashboard_writer import write_dashboard_state
    _DASHBOARD_AVAILABLE = True
except ImportError:
    _DASHBOARD_AVAILABLE = False
    write_dashboard_state = None  # type: ignore

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
        # Fase 2b.2: fetch multi-TF (4h tendencia + 15m timing) com graceful degradation
        df_4h = None
        df_15m = None
        if MTF_ENABLED:
            try:
                mtf = fetch_multi_tf(symbol, timeframes=("4h", "15m"))
                if "4h" in mtf:
                    df_4h = add_indicators(mtf["4h"])
                if "15m" in mtf:
                    df_15m = add_indicators(mtf["15m"])
            except Exception as e:
                log.warning("[MTF] %s: fetch_multi_tf falhou (%s) - degradando p/ 1h puro",
                            symbol, str(e)[:100])

        # Fase 2b.3: expõe contexto MTF no diag p/ visual no Telegram (aditivo, custo zero)
        try:
            from . import strategies as _strat
            diag["trend_4h"]     = _strat._check_trend_4h(df_4h) if df_4h is not None else None
            diag["pullback_15m"] = _strat._check_pullback_15m(df_15m) if df_15m is not None else None
        except Exception as _e_mtf:
            log.warning("[MTF-UI] %s: falha ao expor contexto MTF (%s)", symbol, _e_mtf)
            diag["trend_4h"]     = None
            diag["pullback_15m"] = None

        sig = evaluate_signal(df, symbol=symbol, timeframe=TIMEFRAME,
                              df_4h=df_4h, df_15m=df_15m)
        diag["signal"] = sig

    except Exception as e:
        log.exception("Falha no scan de %s", symbol)
        diag["error"] = f"{type(e).__name__}: {e}"

    return diag

def main() -> int:
    # Fase C4: gating por runtime_config (paused / scan_interval / DND)
    try:
        from . import runtime_config as rc
        cfg = rc.load()
        run_ok, motivo = rc.should_run_now(cfg)
        if not run_ok:
            log.info("⏭️  Scan PULADO — %s", motivo)
            return 0
        log.info("✅ Scan AUTORIZADO — %s", motivo)
        runtime_watchlist = cfg.get("watchlist") or []
        effective_symbols = list(runtime_watchlist) if runtime_watchlist else list(SYMBOLS)
    except Exception as e:
        log.warning("runtime_config indisponivel (%s) — usando defaults estaticos", e)
        cfg = None
        effective_symbols = list(SYMBOLS)

    log.info("🚀 Iniciando scan | symbols=%s | TF=%s | exchange=%s",
             effective_symbols, TIMEFRAME, EXCHANGE)

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

    for sym in effective_symbols:
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

    # 5) Escreve estado do dashboard (Fase C2 - D.1)
    if DASHBOARD_ENABLED and _DASHBOARD_AVAILABLE:
        try:
            fg_for_dash = fg if isinstance(fg, dict) else (
                {"score": fg} if isinstance(fg, (int, float)) else None
            )
            path = write_dashboard_state(
                diagnostics=diagnostics,
                signals_count=len(qualified_signals),
                fg=fg_for_dash,
                timeframe=TIMEFRAME,
                exchange=EXCHANGE,
            )
            if path:
                log.info("💾 Dashboard state: %s", path)
        except Exception:
            log.error("Falha ao gerar dashboard state:\n%s", traceback.format_exc())

    # Fase C4: registra timestamp do scan bem-sucedido
    try:
        from . import runtime_config as rc
        rc.mark_scan_ran(updated_by="scan")
    except Exception as e:
        log.warning("Falha ao gravar last_scan_utc: %s", e)

    log.info("✅ Scan finalizado.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
