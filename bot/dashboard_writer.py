"""
Dashboard state writer (Fase C2 - D.1).

Gera o JSON estatico que alimenta o dashboard web (GitHub Pages).
Arquivo de saida: docs/data/latest.json

Caracteristicas:
- Puramente aditivo: nao toca telegram nem estrategias.
- Falha silenciosa: se algo der errado aqui, o bot continua rodando.
- Kill switch: respeita DASHBOARD_ENABLED em config.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

_DEFAULT_OUTPUT = Path("docs") / "data" / "latest.json"


def _market_regime(fg_score):
    if fg_score is None:
        return {"label": "-", "arrow": "", "level": "unknown"}
    try:
        s = int(fg_score)
    except Exception:
        return {"label": "-", "arrow": "", "level": "unknown"}
    if s <= 24:
        return {"label": "Bear forte", "arrow": "down-strong", "level": "extreme_fear"}
    if s <= 44:
        return {"label": "Bear",       "arrow": "down",        "level": "fear"}
    if s <= 55:
        return {"label": "Lateral",    "arrow": "side",        "level": "neutral"}
    if s <= 74:
        return {"label": "Bull",       "arrow": "up",          "level": "greed"}
    return {"label": "Bull forte", "arrow": "up-strong", "level": "extreme_greed"}


def _classify(diag: dict) -> str:
    if "error" in diag:
        return "error"
    if diag.get("signal"):
        return "pronto"

    price  = diag.get("price")
    ema200 = diag.get("ema200")
    rsi    = diag.get("rsi")
    macd   = diag.get("macd")
    macd_signal = diag.get("macd_signal")
    macd_hist   = diag.get("macd_hist")
    macd_hist_prev = diag.get("macd_hist_prev")

    above_ema = bool(price and ema200 and price > ema200)
    if not above_ema:
        return "inativo"
    if rsi is not None and rsi >= 70:
        return "risco"

    macd_pos   = (macd is not None and macd > 0)
    macd_above = (macd is not None and macd_signal is not None and macd > macd_signal)
    hist_pos   = (macd_hist is not None and macd_hist > 0)
    hist_accel = (
        macd_hist is not None and macd_hist_prev is not None
        and macd_hist > 0 and macd_hist_prev > 0
        and macd_hist > macd_hist_prev * 1.5
    )
    if macd_above and hist_pos and rsi is not None and 50 <= rsi < 65:
        return "quase_la"
    if hist_accel and rsi is not None and 45 <= rsi < 70:
        return "quase_la"
    if macd_pos and rsi is not None and 45 <= rsi < 70:
        return "quase_la"
    return "observacao"


def _serialize_signal(sig: Any):
    if sig is None:
        return None
    if isinstance(sig, dict):
        return sig
    out = {}
    for attr in ("symbol", "strategy", "side", "entry", "stop",
                 "tp1", "tp2", "tp3", "risk_reward", "confidence", "notes"):
        if hasattr(sig, attr):
            out[attr] = getattr(sig, attr)
    return out or None


def _safe_float(v):
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except Exception:
        return None


def build_state(diagnostics: Iterable[dict], signals_count: int, fg: Any,
                timeframe: str, exchange: str) -> dict:
    fg_score = None
    fg_label = None
    if isinstance(fg, dict):
        fg_score = fg.get("score")
        fg_label = fg.get("label")
    elif isinstance(fg, (int, float)):
        fg_score = int(fg)
    regime = _market_regime(fg_score)

    items = []
    for d in diagnostics:
        item = {
            "symbol":      d.get("symbol", "-"),
            "price":       _safe_float(d.get("price")),
            "rsi":         _safe_float(d.get("rsi")),
            "macd":        _safe_float(d.get("macd")),
            "macd_signal": _safe_float(d.get("macd_signal")),
            "macd_hist":   _safe_float(d.get("macd_hist")),
            "ema200":      _safe_float(d.get("ema200")),
            "vol_ratio":   _safe_float(d.get("vol_ratio")),
            "category":    _classify(d),
            "signal":      _serialize_signal(d.get("signal")),
        }
        if "error" in d:
            item["error"] = str(d["error"])[:200]
        items.append(item)

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "timeframe": timeframe,
        "exchange": exchange,
        "fear_greed": {"score": fg_score, "label": fg_label},
        "market_regime": regime,
        "signals_count": signals_count,
        "assets_count": len(items),
        "assets": items,
    }


def write_dashboard_state(diagnostics, signals_count, fg, timeframe: str,
                          exchange: str, output_path=None):
    """Escreve docs/data/latest.json. Falha silenciosa - jamais derruba o bot."""
    try:
        out = Path(output_path) if output_path else _DEFAULT_OUTPUT
        out.parent.mkdir(parents=True, exist_ok=True)
        state = build_state(diagnostics, signals_count, fg, timeframe, exchange)
        out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("[dashboard] state escrito em %s (%d ativos)", out, state["assets_count"])
        return str(out)
    except Exception as e:
        log.warning("[dashboard] falha ao escrever state: %s", e)
        return None
