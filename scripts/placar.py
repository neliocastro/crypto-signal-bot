"""
placar.py - placar dos trades FECHADOS do bot a partir de state/positions.jsonl (D-034).

So LE o arquivo: nao altera state/, nao chama a exchange. Valores sao ESTIMATIVAS
(preco do gatilho, taxa 0,1% por ponta), o mesmo metodo da secao 5 de
docs/resultado_financeiro.md. O fill real da corretora pode diferir alguns centavos.

Base de cada trade (coluna "base"):
  est       pnl_usdt_est gravado pelo oco_guard no fechamento (D-034)
  reg       pnl_usdt gravado a mao numa reconciliacao
  saida     calculado do exit_price gravado
  gatilho   linha antiga sem exit_price: usa o preco da perna (tp_price/sl_price)
Estrategia com "*" = inferida pelo ativo (linhas antigas nao gravavam strategy).

USO
---
    python scripts/placar.py
    python scripts/placar.py --desde 2026-09-04     # trades ABERTOS a partir da data (regra D-024)
    python scripts/placar.py --arquivo outro.jsonl
"""
import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot.oco_guard import exit_pnl_est          # noqa: E402

FEE_RATE = 0.001
# Inferencia so p/ linhas antigas. ETH/XRP etc.: trilho incerto (D-003) -> nao_registrada.
_INFER = {"HYPE/USDT": "Breakout / Tendência", "PAXG/USDT": "Acúmulo (RSI sobrevenda)",
          "BTC/USDT": "MARE_ALTA_D1", "SOL/USDT": "MARE_ALTA_D1",
          "TRX/USDT": "MARE_ALTA_D1", "BNB/USDT": "MARE_ALTA_D1"}


def _strategy(p):
    if p.get("strategy"):
        return p["strategy"]
    return _INFER.get(p.get("symbol"), "nao_registrada") + "*"


def trade_pnl(p):
    """(pnl_usdt, pnl_pct, saida, base) de uma linha closed_tp/closed_sl."""
    closed_by = "tp" if p.get("status") == "closed_tp" else "sl"
    if p.get("pnl_usdt_est") is not None:
        return float(p["pnl_usdt_est"]), float(p.get("pnl_pct_est") or 0), p.get("exit_price"), "est"
    if p.get("pnl_usdt") is not None:
        return float(p["pnl_usdt"]), float(p.get("pnl_pct") or 0), p.get("exit_price"), "reg"
    q = dict(p)
    base = "gatilho"
    if p.get("exit_price"):
        q["tp_price" if closed_by == "tp" else "sl_price"] = p["exit_price"]
        base = "saida"
    est = exit_pnl_est(q, closed_by, FEE_RATE)
    return est["pnl_usdt_est"], est["pnl_pct_est"], est["exit_price"], base


def resumo(trades):
    wins = [t for t in trades if t["pnl"] > 0]
    gain = sum(t["pnl"] for t in wins)
    loss = -sum(t["pnl"] for t in trades if t["pnl"] <= 0)
    pf = (gain / loss) if loss > 0 else (float("inf") if gain > 0 else 0.0)
    return {"n": len(trades), "wins": len(wins), "pnl": sum(t["pnl"] for t in trades), "pf": pf}


def carregar(path, desde=None):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    trades, outros = [], []
    for p in rows:
        if p.get("status") in ("closed_tp", "closed_sl"):
            if desde and str(p.get("opened_at") or "")[:10] < desde:
                continue
            pnl, pct, saida, base = trade_pnl(p)
            trades.append({"symbol": p.get("symbol"), "strategy": _strategy(p),
                           "opened": str(p.get("opened_at") or "")[:10],
                           "closed": str(p.get("closed_at") or "")[:10],
                           "status": p.get("status"), "entry": p.get("entry_price"),
                           "exit": saida, "pnl": pnl, "pct": pct, "base": base})
        elif not str(p.get("status", "")).startswith("open"):
            outros.append(p)
    trades.sort(key=lambda t: t["closed"])
    return trades, outros


def _fmt_pf(pf):
    return "inf" if pf == float("inf") else "%.2f" % pf


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--arquivo", default=os.path.join(_ROOT, "state", "positions.jsonl"))
    ap.add_argument("--desde", help="AAAA-MM-DD: so trades abertos a partir desta data")
    a = ap.parse_args(argv)
    trades, outros = carregar(a.arquivo, a.desde)

    print("# Placar do bot%s\n" % (" (abertos desde %s)" % a.desde if a.desde else ""))
    print("| Fechou | Ativo | Estrategia | Entrada | Saida | Res. | P&L ($) | % | base |")
    print("|---|---|---|---|---|---|---|---|---|")
    for t in trades:
        print("| %s | %s | %s | %s | %s | %s | %+.2f | %+.1f%% | %s |" % (
            t["closed"], t["symbol"], t["strategy"], t["entry"], t["exit"],
            "TP" if t["status"] == "closed_tp" else "SL", t["pnl"], t["pct"], t["base"]))

    print("\n| Recorte | Trades | Wins | P&L ($) | PF |")
    print("|---|---|---|---|---|")
    r = resumo(trades)
    print("| Todos | %d | %d | %+.2f | %s |" % (r["n"], r["wins"], r["pnl"], _fmt_pf(r["pf"])))
    for grupo in ("strategy", "symbol"):
        for k in sorted({t[grupo] for t in trades}):
            r = resumo([t for t in trades if t[grupo] == k])
            print("| %s | %d | %d | %+.2f | %s |" % (k, r["n"], r["wins"], r["pnl"], _fmt_pf(r["pf"])))

    if outros:
        print("\nFora do placar (closed_manual, summary etc.):")
        for p in outros:
            print("- %s %s %s pnl_usdt=%s" % (p.get("status"), p.get("symbol"),
                                              p.get("signal_id"), p.get("pnl_usdt")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
