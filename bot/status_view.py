"""
status_view.py - quadro das estrategias e posicoes para o Telegram (D-046, 2026-10-21).

So LE flags do config/mare_alta e o state/positions.jsonl. Nao muda nada.
Usado pelo /status do commander e pelo resumo diario, para os dois mostrarem a mesma
verdade: o que esta ligado, o que esta desligado e o que roda fora do bot.

Texto puro (sem markup): quem chama decide se envia em HTML ou Markdown.
"""
from __future__ import annotations

import json
import os


def _flag(mod, nome, padrao):
    try:
        return getattr(mod, nome)
    except Exception:
        return padrao


def linhas_estrategias() -> list:
    """Uma linha por estrategia: estado, ativos e o que faz."""
    try:
        from . import config as c
    except Exception:
        c = None
    try:
        from . import mare_alta as m
    except Exception:
        m = None

    out = []
    ma_on = bool(_flag(m, "MARE_ALTA_ENABLED", False))
    ma_shadow = bool(_flag(m, "MARE_ALTA_SHADOW_MODE", False))
    universo = ", ".join(s.split("/")[0] for s in (_flag(m, "MARE_ALTA_UNIVERSE", []) or []))
    if ma_on:
        modo = "SOMBRA (sem ordem)" if ma_shadow else "REAL"
        out.append("🟢 Maré Alta D1 — %s — %s — tendência diária, stop 2,5×ATR, TP1 +10%%" % (modo, universo or "?"))
    else:
        out.append("⚪ Maré Alta D1 — DESLIGADA")

    bo_on = bool(_flag(c, "BREAKOUT_ENABLED", False))
    bo_syms = ", ".join(s.split("/")[0] for s in (_flag(c, "BREAKOUT_SYMBOLS", {}) or {}))
    out.append(("🟢 Breakout 1h — %s" % (bo_syms or "?")) if bo_on else "⚪ Breakout 1h — DESLIGADA (D-013)")

    ac_on = bool(_flag(c, "ACCUMULATION_ENABLED", False))
    out.append("🟢 Acúmulo RSI (bot)" if ac_on else "⚪ Acúmulo RSI no bot — DESLIGADA (D-012)")
    out.append("🔵 PAXG RSI 4h < 30 — cron do SERVIDOR, fora do bot e do placar (D-032)")

    teto = _flag(c, "EXECUTION_MAX_NOTIONAL_USDT", None)
    if teto is not None:
        out.append("💵 Teto por ordem: US$ %s (D-024)" % (("%.0f" % float(teto)) if float(teto).is_integer() else teto))
    return out


def posicoes_abertas(caminho: str = "state/positions.jsonl") -> list:
    """Linhas das posicoes com status open* (todas contam na trava de concentracao)."""
    out = []
    if not os.path.exists(caminho):
        return out
    try:
        with open(caminho, encoding="utf-8") as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    p = json.loads(linha)
                except Exception:
                    continue
                if not str(p.get("status", "")).startswith("open"):
                    continue
                fase = "após TP1, trailing" if p.get("tp1_done") else (
                    "aguardando TP1" if p.get("tp_partial") else "TP/SL fixos")
                out.append("• %s entrada %s | SL %s | %s" % (
                    p.get("symbol", "?"), p.get("entry_price", "?"), p.get("sl_price", "?"), fase))
    except Exception:
        return out
    return out


def fechadas_desde(iso_inicio: str, caminho: str = "state/positions.jsonl") -> list:
    """[(symbol, status, pnl_usdt_est ou None)] das posicoes fechadas com closed_at >= iso_inicio."""
    out = []
    if not os.path.exists(caminho):
        return out
    try:
        with open(caminho, encoding="utf-8") as fh:
            for linha in fh:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    p = json.loads(linha)
                except Exception:
                    continue
                if not str(p.get("status", "")).startswith("closed"):
                    continue
                if str(p.get("closed_at") or "") < iso_inicio:
                    continue
                pnl = p.get("pnl_usdt_est")
                out.append((p.get("symbol", "?"), p.get("status"), float(pnl) if pnl is not None else None))
    except Exception:
        return out
    return out
