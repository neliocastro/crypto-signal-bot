"""
paper_evaluator.py - camada de AVALIACAO do dry-run (paper trading).

Responsabilidade: medir o que TERIA acontecido com cada sinal de compra, sem
executar nada de verdade. Espelha a logica de saida de CADA estrategia:

  * Breakout/Tendencia (trailing_stop=True) -> TRAILING STOP que sobe junto com
    o preco (deixa o lucro correr). Mantem a distancia de risco inicial
    (entry - stop) e arrasta o stop para cima conforme o preco faz novas maximas.
  * MACD-only / Integrada (stop + tp2)      -> stop fixo (perda) ou alvo tp2
    (R:R 1:2). O que bater primeiro fecha a posicao-papel.
  * Acumulacao (side BUY, sem stop/alvo)    -> HOLD: nunca fecha por preco;
    so acompanha o retorno nao-realizado (DCA / reserva de valor).

Persistencia: state/paper_positions.json
  { "open": [...], "closed": [...], "last_report_utc": iso }

Cada scan chama update(diagnostics, paper_balance) -> abre novas posicoes-papel
e simula saidas com o preco ATUAL que o scan ja buscou (custo de rede zero).
maybe_send_weekly_report(send) dispara o relatorio no Telegram a cada
PAPER_REPORT_INTERVAL_DAYS dias.

Tudo e best-effort: qualquer falha e contida (o main ja envolve em try/except)
para NUNCA derrubar o scan.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

# --- Config com fallback seguro (sem config -> camada inerte) ---
try:
    from .config import (
        PAPER_EVAL_ENABLED,
        PAPER_POSITIONS_FILE,
        PAPER_REPORT_INTERVAL_DAYS,
        EXECUTION_PCT,
    )
except Exception:  # degradacao segura
    PAPER_EVAL_ENABLED = False
    PAPER_POSITIONS_FILE = "state/paper_positions.json"
    PAPER_REPORT_INTERVAL_DAYS = 7
    EXECUTION_PCT = 0.10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _signal_id(sig: dict) -> str:
    """ID estavel (mesmo esquema do executor) p/ idempotencia."""
    base = f"{sig.get('symbol')}|{sig.get('strategy')}|{sig.get('timestamp') or sig.get('ts')}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _ref_price(sig: dict):
    return sig.get("entry") or sig.get("price")


def _is_buy(sig: dict) -> bool:
    return str(sig.get("side", "")).lower() in ("buy", "long")


def _load() -> dict:
    try:
        if os.path.exists(PAPER_POSITIONS_FILE):
            with open(PAPER_POSITIONS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        else:
            data = {}
    except Exception:
        data = {}  # estado corrompido -> recomeca limpo
    data.setdefault("open", [])
    data.setdefault("closed", [])
    data.setdefault("last_report_utc", None)
    return data


def _save(data: dict) -> None:
    try:
        d = os.path.dirname(PAPER_POSITIONS_FILE)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(PAPER_POSITIONS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass  # best-effort


def _classify(sig: dict) -> str:
    """Define o tipo de saida a espelhar a partir do proprio sinal."""
    if sig.get("trailing_stop"):
        return "trailing"
    if str(sig.get("signal_type", "")).lower() == "accumulation":
        return "hold"
    if sig.get("stop") and (sig.get("tp2") or sig.get("targets")):
        return "fixed"
    return "hold"  # sem stop/alvo -> trata como hold (nao auto-fecha)


def _open_position(sig: dict) -> dict:
    entry = float(_ref_price(sig) or 0.0)
    stop = sig.get("stop")
    risk_dist = (entry - float(stop)) if (stop and entry) else None
    tp = sig.get("tp2") or (sig.get("targets") or [None])[0]
    return {
        "signal_id": _signal_id(sig),
        "symbol": sig.get("symbol"),
        "strategy": sig.get("strategy"),
        "exit_kind": _classify(sig),
        "entry": entry,
        "stop": float(stop) if stop else None,
        "risk_dist": risk_dist,         # p/ trailing: distancia fixa de risco
        "tp": float(tp) if tp else None,
        "peak": entry,                  # high-water mark (trailing)
        "opened_at": sig.get("timestamp") or _now_iso(),
        "opened_scan_utc": _now_iso(),
    }


def _simulate_exit(pos: dict, price: float) -> dict | None:
    """Aplica a regra de saida da posicao. Retorna pos fechada ou None."""
    if price is None or price <= 0:
        return None
    kind = pos.get("exit_kind")

    if kind == "trailing":
        # arrasta o stop para cima mantendo a distancia de risco inicial
        if price > pos.get("peak", price):
            pos["peak"] = price
        rd = pos.get("risk_dist")
        trail = (pos["peak"] - rd) if rd else pos.get("stop")
        if trail is not None:
            pos["stop"] = trail  # persiste o stop arrastado
            if price <= trail:
                return _close(pos, price, "trailing_stop")
        return None

    if kind == "fixed":
        stop = pos.get("stop")
        tp = pos.get("tp")
        if stop is not None and price <= stop:
            return _close(pos, price, "stop")
        if tp is not None and price >= tp:
            return _close(pos, price, "take_profit")
        return None

    # hold (acumulacao): nunca fecha por preco
    return None


def _close(pos: dict, price: float, reason: str) -> dict:
    entry = pos.get("entry") or 0.0
    pnl_pct = ((price - entry) / entry * 100.0) if entry else 0.0
    pos = dict(pos)
    pos["exit"] = price
    pos["exit_reason"] = reason
    pos["closed_at"] = _now_iso()
    pos["pnl_pct"] = round(pnl_pct, 4)
    pos["pnl_usdt"] = round(pnl_pct / 100.0, 6)  # P&L por 1 unidade de notional
    return pos


def update(diagnostics, paper_balance: float = 1000.0) -> dict:
    """
    Abre posicoes-papel a partir dos sinais de compra do scan e simula a saida
    das posicoes abertas usando o preco atual de cada ativo.
    Retorna {"open": n_abertas, "closed": n_fechadas_neste_scan}.
    """
    if not PAPER_EVAL_ENABLED:
        return {"open": 0, "closed": 0}

    data = _load()
    open_pos = data["open"]
    closed_pos = data["closed"]

    # mapa symbol -> preco atual (do proprio scan)
    price_map = {}
    for d in (diagnostics or []):
        try:
            sym = d.get("symbol")
            pr = d.get("price")
            if sym and pr and pr == pr:  # exclui NaN
                price_map[sym] = float(pr)
        except Exception:
            continue

    open_symbols = {p.get("symbol") for p in open_pos}

    # 1) abre novas posicoes (1 por ativo de cada vez -> sem piramide/duplicata)
    for d in (diagnostics or []):
        sig = d.get("signal")
        if not sig or not isinstance(sig, dict):
            continue
        if not _is_buy(sig):
            continue
        sym = sig.get("symbol")
        if sym in open_symbols:
            continue
        if not _ref_price(sig):
            continue
        open_pos.append(_open_position(sig))
        open_symbols.add(sym)

    # 2) simula saidas das posicoes abertas
    still_open = []
    n_closed = 0
    for pos in open_pos:
        price = price_map.get(pos.get("symbol"))
        result = _simulate_exit(pos, price) if price is not None else None
        if result is not None:
            closed_pos.append(result)
            n_closed += 1
        else:
            still_open.append(pos)

    data["open"] = still_open
    data["closed"] = closed_pos
    _save(data)
    return {"open": len(still_open), "closed": n_closed}


def _compute_stats(closed) -> dict:
    realized = [c for c in closed if c.get("exit_reason") != "hold"]
    wins = [c for c in realized if (c.get("pnl_pct") or 0) > 0]
    losses = [c for c in realized if (c.get("pnl_pct") or 0) <= 0]
    n = len(realized)
    wr = (len(wins) / n * 100.0) if n else 0.0
    total_pct = sum((c.get("pnl_pct") or 0) for c in realized)
    best = max(realized, key=lambda c: c.get("pnl_pct", 0)) if realized else None
    worst = min(realized, key=lambda c: c.get("pnl_pct", 0)) if realized else None
    # drawdown aproximado sobre a curva de equity (em % de notional)
    eq = 0.0
    peak = 0.0
    mdd = 0.0
    for c in realized:
        eq += (c.get("pnl_pct") or 0)
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return {
        "n": n, "wins": len(wins), "losses": len(losses), "wr": wr,
        "total_pct": total_pct, "best": best, "worst": worst, "mdd": mdd,
    }


def build_report(data: dict | None = None) -> str:
    if data is None:
        data = _load()
    s = _compute_stats(data.get("closed", []))
    n_open = len(data.get("open", []))
    holds = [c for c in data.get("closed", []) if c.get("exit_reason") == "hold"]

    lines = []
    lines.append("\U0001f4ca *RELATORIO PAPER TRADING (dry-run)*")
    lines.append("\u2500" * 30)
    lines.append(f"\U0001f3af Ordens simuladas (fechadas): {s['n']}")
    lines.append(f"\u2705 Vencedoras: {s['wins']}  \u00b7  \u274c Perdedoras: {s['losses']}  (WR {s['wr']:.1f}%)")
    lines.append(f"\U0001f4b0 P&L hipotetico: {s['total_pct']:+.2f}% sobre capital alocado")
    lines.append(f"\U0001f4c9 Maior drawdown: {s['mdd']:.2f}%")
    if s["best"]:
        lines.append(f"\U0001f947 Melhor: {s['best']['symbol']} {s['best'].get('pnl_pct', 0):+.2f}%")
    if s["worst"]:
        lines.append(f"\U0001f53b Pior: {s['worst']['symbol']} {s['worst'].get('pnl_pct', 0):+.2f}%")
    lines.append(f"\U0001f4cc Posicoes abertas agora: {n_open}")
    if holds:
        lines.append(f"\U0001f4b3 Acumulo (hold, sem venda): {len(holds)} registro(s)")
    lines.append("\u2500" * 30)
    if s["n"] == 0 and n_open == 0:
        lines.append("\U0001f9ea Ainda sem dados suficientes \u2014 coletando sinais.")
    else:
        verdict = "edge positivo" if s["total_pct"] > 0 else "sem edge ainda"
        lines.append(f"\U0001f9e0 Veredito parcial: {verdict} (dry-run, decisao p/ Fase 2).")
    return "\n".join(lines)


def maybe_send_weekly_report(send_func) -> bool:
    """Dispara o relatorio no Telegram se passou o intervalo configurado."""
    if not PAPER_EVAL_ENABLED:
        return False
    data = _load()
    last = data.get("last_report_utc")
    due = True
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed_days = (_now() - last_dt).total_seconds() / 86400.0
            due = elapsed_days >= float(PAPER_REPORT_INTERVAL_DAYS)
        except Exception:
            due = True
    if not due:
        return False
    try:
        send_func(build_report(data))
    except Exception:
        return False
    data["last_report_utc"] = _now_iso()
    _save(data)
    return True
