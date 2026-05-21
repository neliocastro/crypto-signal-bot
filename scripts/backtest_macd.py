"""
Backtest: MACD cross-above signal (modo "AGRESSIVO" candidato).

Config (modo rápido AAA):
  - Horizonte: 30 dias (~720 candles 1h)
  - Fonte: Gate.io via bot.data_fetcher.fetch_ohlcv (herda fallback se config mudar)
  - Saída: ATR fixo (SL 1.5×ATR, TP 3.0×ATR, timeout 48 barras)

Entrada (sinal):
  - MACD line cruza ACIMA do signal (prev<=signal, curr>signal)
  - Preço acima da EMA200
  - 40 <= RSI <= 70

Métricas geradas (por ativo + agregado):
  trades, win_rate, profit_factor, expectancy_pct,
  avg_win_pct, avg_loss_pct, max_dd_pct, total_return_pct

Saída:
  - state/backtest_results.json (machine-readable)
  - docs/backtest_report.md (humano)

Uso:
  python -m scripts.backtest_macd
  # ou via workflow .github/workflows/backtest.yml
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

# Permite executar tanto como "python -m scripts.backtest_macd"
# quanto "python scripts/backtest_macd.py"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.config import SYMBOLS, TIMEFRAME
from bot.data_fetcher import fetch_ohlcv
from bot.indicators import add_indicators

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backtest_macd")

# ────────────────────────────────────────────────────────────────────────────
# Parâmetros do backtest
# ────────────────────────────────────────────────────────────────────────────
CANDLES_LIMIT       = 2160   # ~90 dias de 1h
SL_ATR_MULT         = 1.5
TP_ATR_MULT         = 3.0
TIMEOUT_BARS        = 48     # ~2 dias
RSI_LOW, RSI_HIGH   = 40, 70
MIN_CANDLES_NEEDED  = 250    # precisa de EMA200 + buffer

RESULTS_JSON = "state/backtest_results.json"
REPORT_MD    = "docs/backtest_report.md"


@dataclass
class Trade:
    symbol: str
    entry_idx: int
    entry_ts: str
    entry_price: float
    exit_idx: int
    exit_ts: str
    exit_price: float
    exit_reason: str         # "tp_hit" | "sl_hit" | "timeout"
    pnl_pct: float
    bars_held: int
    entry_atr: float
    entry_rsi: float


def _to_iso(ts) -> str:
    """Aceita pandas Timestamp ou datetime; devolve ISO 8601."""
    try:
        return ts.isoformat()
    except Exception:
        return str(ts)


def simulate_symbol(symbol: str) -> list[Trade]:
    """Roda o simulador num único ativo e devolve lista de trades fechados."""
    log.info("📊 [%s] baixando candles…", symbol)
    df = fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=CANDLES_LIMIT)
    if df is None or df.empty or len(df) < MIN_CANDLES_NEEDED:
        log.warning("[%s] candles insuficientes (%s) — pulando",
                    symbol, 0 if df is None else len(df))
        return []

    df = add_indicators(df)

    trades: list[Trade] = []
    in_trade = False
    entry_price = 0.0
    entry_atr   = 0.0
    entry_idx   = 0
    entry_ts    = ""
    entry_rsi   = 0.0
    sl_price    = 0.0
    tp_price    = 0.0

    # Começa a iterar a partir do candle 200 (EMA200 confiável)
    for i in range(200, len(df) - 1):
        row      = df.iloc[i]
        prev     = df.iloc[i - 1]
        next_row = df.iloc[i + 1]

        if in_trade:
            high = float(next_row["high"])
            low  = float(next_row["low"])
            bars = i - entry_idx

            exit_reason: Optional[str] = None
            exit_price: float          = 0.0

            # 1) SL primeiro (worst case conservador)
            if low <= sl_price:
                exit_reason = "sl_hit"
                exit_price  = sl_price
            # 2) TP
            elif high >= tp_price:
                exit_reason = "tp_hit"
                exit_price  = tp_price
            # 3) Timeout
            elif bars >= TIMEOUT_BARS:
                exit_reason = "timeout"
                exit_price  = float(next_row["close"])

            if exit_reason:
                pnl = (exit_price - entry_price) / entry_price * 100.0
                trades.append(Trade(
                    symbol=symbol,
                    entry_idx=entry_idx,
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    exit_idx=i + 1,
                    exit_ts=_to_iso(next_row.name),
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    pnl_pct=round(pnl, 4),
                    bars_held=bars + 1,
                    entry_atr=round(entry_atr, 6),
                    entry_rsi=round(entry_rsi, 2),
                ))
                in_trade = False
            continue  # já está em trade, não procura nova entrada

        # ── Procura entrada ────────────────────────────────────────────────
        try:
            macd_prev    = float(prev["macd"])
            signal_prev  = float(prev["macd_signal"])
            macd_curr    = float(row["macd"])
            signal_curr  = float(row["macd_signal"])
            close_curr   = float(row["close"])
            ema200_curr  = float(row["ema200"])
            rsi_curr     = float(row["rsi"])
            atr_curr     = float(row.get("atr", float("nan")))
        except (KeyError, ValueError):
            continue

        # Filtra NaN
        if any(v != v for v in (macd_prev, signal_prev, macd_curr, signal_curr,
                                 close_curr, ema200_curr, rsi_curr, atr_curr)):
            continue
        if atr_curr <= 0:
            continue

        # Sinal: cross above + filtros
        crossed_above = (macd_prev <= signal_prev) and (macd_curr > signal_curr)
        above_ema200  = close_curr > ema200_curr
        rsi_ok        = RSI_LOW <= rsi_curr <= RSI_HIGH

        if crossed_above and above_ema200 and rsi_ok:
            # Abre trade no PRÓXIMO candle (open) — realismo
            entry_price = float(next_row["open"])
            entry_atr   = atr_curr
            entry_idx   = i + 1
            entry_ts    = _to_iso(next_row.name)
            entry_rsi   = rsi_curr
            sl_price    = entry_price - SL_ATR_MULT * entry_atr
            tp_price    = entry_price + TP_ATR_MULT * entry_atr
            in_trade    = True

    log.info("✅ [%s] %d trades simulados", symbol, len(trades))
    return trades


def compute_metrics(trades: list[Trade]) -> dict[str, Any]:
    """Estatísticas agregadas para um conjunto de trades."""
    n = len(trades)
    if n == 0:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "expectancy_pct": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
            "max_dd_pct": 0.0, "total_return_pct": 0.0,
            "tp_hits": 0, "sl_hits": 0, "timeouts": 0,
        }

    wins   = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    gross_win  = sum(t.pnl_pct for t in wins)
    gross_loss = abs(sum(t.pnl_pct for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    # Equity curve simples (soma de retornos) p/ drawdown
    cumulative = 0.0
    peak       = 0.0
    max_dd     = 0.0
    for t in trades:
        cumulative += t.pnl_pct
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak    # negativo durante drawdown
        if dd < max_dd:
            max_dd = dd

    return {
        "trades":           n,
        "win_rate":         round(len(wins) / n, 4),
        "profit_factor":    round(pf, 4) if pf != float("inf") else 999.0,
        "expectancy_pct":   round(sum(t.pnl_pct for t in trades) / n, 4),
        "avg_win_pct":      round(sum(t.pnl_pct for t in wins) / len(wins), 4) if wins else 0.0,
        "avg_loss_pct":     round(sum(t.pnl_pct for t in losses) / len(losses), 4) if losses else 0.0,
        "max_dd_pct":       round(max_dd, 4),
        "total_return_pct": round(sum(t.pnl_pct for t in trades), 4),
        "tp_hits":          sum(1 for t in trades if t.exit_reason == "tp_hit"),
        "sl_hits":          sum(1 for t in trades if t.exit_reason == "sl_hit"),
        "timeouts":         sum(1 for t in trades if t.exit_reason == "timeout"),
    }


def classify_symbol(metrics: dict[str, Any]) -> str:
    """Veredicto para o modo agressivo."""
    if metrics["trades"] < 5:
        return "insufficient_data"
    if metrics["win_rate"] >= 0.55 and metrics["profit_factor"] >= 1.5:
        return "approved"
    if metrics["win_rate"] >= 0.50 and metrics["profit_factor"] >= 1.2:
        return "borderline"
    return "rejected"


def build_report_md(payload: dict[str, Any]) -> str:
    by_sym = payload["by_symbol"]
    agg    = payload["aggregate"]
    lines = [
        "# 🧪 Backtest MACD Crossover — Modo Agressivo",
        "",
        f"- **Data:** {payload['backtest_date']}",
        f"- **Horizonte:** {payload['horizon_candles']} candles ({TIMEFRAME})",
        f"- **Saída:** SL {SL_ATR_MULT}×ATR · TP {TP_ATR_MULT}×ATR · timeout {TIMEOUT_BARS} barras",
        f"- **Filtros entrada:** MACD cross above · preço > EMA200 · {RSI_LOW} ≤ RSI ≤ {RSI_HIGH}",
        "",
        "## 📊 Resultados por ativo",
        "",
        "| Ativo | Trades | WinRate | PF | Expect | MaxDD | TP/SL/TO | Veredicto |",
        "|---|---:|---:|---:|---:|---:|---|:---:|",
    ]
    icon = {"approved": "⭐", "borderline": "⚠️", "rejected": "❌", "insufficient_data": "—"}
    for sym, info in by_sym.items():
        m = info["metrics"]
        v = info["verdict"]
        lines.append(
            f"| `{sym}` | {m['trades']} | {m['win_rate']*100:.1f}% | "
            f"{m['profit_factor']:.2f} | {m['expectancy_pct']:+.2f}% | "
            f"{m['max_dd_pct']:.1f}% | {m['tp_hits']}/{m['sl_hits']}/{m['timeouts']} | "
            f"{icon.get(v,'?')} {v} |"
        )
    lines += [
        "",
        "## 🌐 Agregado (todos os ativos)",
        "",
        f"- **Trades totais:** {agg['trades']}",
        f"- **Win rate:** {agg['win_rate']*100:.1f}%",
        f"- **Profit factor:** {agg['profit_factor']:.2f}",
        f"- **Expectancy:** {agg['expectancy_pct']:+.3f}% por trade",
        f"- **Retorno total acumulado:** {agg['total_return_pct']:+.2f}%",
        f"- **Drawdown máximo:** {agg['max_dd_pct']:.2f}%",
        "",
        "## ✅ Recomendação para perfil AGRESSIVO",
        "",
    ]
    approved = [s for s, info in by_sym.items() if info["verdict"] == "approved"]
    borderline = [s for s, info in by_sym.items() if info["verdict"] == "borderline"]
    rejected = [s for s, info in by_sym.items() if info["verdict"] == "rejected"]
    lines += [
        f"- ⭐ **Aprovados** (PF≥1.5 & WR≥55%): {', '.join(f'`{s}`' for s in approved) or '— nenhum'}",
        f"- ⚠️ **Limítrofes:** {', '.join(f'`{s}`' for s in borderline) or '— nenhum'}",
        f"- ❌ **Rejeitados:** {', '.join(f'`{s}`' for s in rejected) or '— nenhum'}",
        "",
        "> Gerado automaticamente por `scripts/backtest_macd.py`. Reproduza via workflow `backtest.yml`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    log.info("🚀 Backtest MACD iniciando · ativos=%s · TF=%s · limit=%d",
             SYMBOLS, TIMEFRAME, CANDLES_LIMIT)

    all_trades: list[Trade] = []
    by_symbol: dict[str, Any] = {}

    for sym in SYMBOLS:
        try:
            trades = simulate_symbol(sym)
        except Exception as e:
            log.exception("[%s] erro fatal: %s", sym, e)
            trades = []
        m = compute_metrics(trades)
        v = classify_symbol(m)
        by_symbol[sym] = {"metrics": m, "verdict": v, "trades": [asdict(t) for t in trades]}
        all_trades.extend(trades)

    aggregate = compute_metrics(all_trades)
    payload = {
        "backtest_date":    datetime.now(timezone.utc).isoformat(),
        "horizon_candles":  CANDLES_LIMIT,
        "timeframe":        TIMEFRAME,
        "params": {
            "sl_atr_mult":  SL_ATR_MULT,
            "tp_atr_mult":  TP_ATR_MULT,
            "timeout_bars": TIMEOUT_BARS,
            "rsi_low":      RSI_LOW,
            "rsi_high":     RSI_HIGH,
        },
        "by_symbol":  by_symbol,
        "aggregate":  aggregate,
        "approved_for_aggressive_profile": [
            s for s, info in by_symbol.items() if info["verdict"] == "approved"
        ],
    }

    os.makedirs("state", exist_ok=True)
    os.makedirs("docs",  exist_ok=True)
    with open(RESULTS_JSON, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    with open(REPORT_MD, "w") as f:
        f.write(build_report_md(payload))

    log.info("✅ Backtest concluído — %d trades totais, WR %.1f%%, PF %.2f",
             aggregate["trades"], aggregate["win_rate"] * 100, aggregate["profit_factor"])
    log.info("📁 Resultados em %s e %s", RESULTS_JSON, REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
