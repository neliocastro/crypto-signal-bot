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


def _nome_ma(m) -> str:
    """Nome exibido da estrategia de tendencia diaria (id interno MARE_ALTA_D1, D-047)."""
    return str(_flag(m, "MARE_ALTA_DISPLAY", "Tendência Diária"))


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
        out.append("🟢 %s — %s — %s — tendência no diário, stop 2,5×ATR, TP1 +10%%" % (_nome_ma(m), modo, universo or "?"))
    else:
        out.append("⚪ %s — DESLIGADA" % _nome_ma(m))

    bo_on = bool(_flag(c, "BREAKOUT_ENABLED", False))
    bo_syms = ", ".join(s.split("/")[0] for s in (_flag(c, "BREAKOUT_SYMBOLS", {}) or {}))
    out.append(("🟢 Rompimento 1h — %s" % (bo_syms or "?")) if bo_on else "⚪ Rompimento 1h — DESLIGADA (D-013)")

    ac_on = bool(_flag(c, "ACCUMULATION_ENABLED", False))
    out.append("🟢 Acúmulo na Queda (bot)" if ac_on else "⚪ Acúmulo na Queda no bot — DESLIGADA (D-012)")
    dca_on = bool(_flag(c, "DCA_ENABLED", False))
    dca_ativos = _flag(c, "DCA_ASSETS", {}) or {}
    if dca_ativos:
        desc = ", ".join("%s US$ %.0f" % (s.split("/")[0], float(v)) for s, v in dca_ativos.items())
        out.append(("🧺 DCA semanal — %s — LIGADO, sem stop (D-049)" if dca_on else
                    "⚪ DCA semanal — %s — DESLIGADO (aguarda o relay FIX 11, D-049)") % desc)
    out.append("⏸ PAXG RSI 4h < 30 (cron do servidor) — substituído pelo DCA (D-049)")

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


def linhas_dca(caminho: str = "state/dca.jsonl") -> list:
    """Uma linha por ativo com compras DCA confirmadas: compras, quantidade e custo medio."""
    try:
        from . import dca as d
        regs = d.ler_registro(caminho)
    except Exception:
        return []
    out = []
    for simbolo in sorted({r.get("symbol") for r in regs if r.get("status") == "filled"}):
        a = d.acumulado(regs, simbolo)
        out.append("• %s: %d compra(s), %.8f %s, custo médio %.2f (US$ %.2f)" % (
            simbolo, a["compras"], a["qtd"], simbolo.split("/")[0], a["custo_medio"] or 0.0, a["investido"]))
    return out

