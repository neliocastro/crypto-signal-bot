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
Coluna "deg" = cadencia_degradada: trade ABERTO entre 2026-09-14 21:13 e 2026-10-09 01:02 UTC
(token expirado, scans atrasados; docs/historico/incidente_2026-10-08_stops_e_cadencia.md).

USO
---
    python scripts/placar.py
    python scripts/placar.py --desde 2026-09-04     # trades ABERTOS a partir da data (regra D-024)
    python scripts/placar.py --arquivo outro.jsonl
    python scripts/placar.py --degrau               # criterios do degrau US$ 20 (D-024), com e sem deg
"""
import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot.oco_guard import exit_pnl_est          # noqa: E402

FEE_RATE = 0.001
DEGRADADA_INI = "2026-09-14T21:13"     # janela de cadencia degradada (UTC, por opened_at)
DEGRADADA_FIM = "2026-10-09T01:02"
DEGRAU_DESDE = "2026-09-04"            # D-024: so trades abertos a partir daqui
DEGRAU_MIN_TRADES = 20
# Inferencia so p/ linhas antigas. ETH/XRP etc.: trilho incerto (D-003) -> nao_registrada.
_INFER = {"HYPE/USDT": "Breakout / Tendência", "PAXG/USDT": "Acúmulo (RSI sobrevenda)",
          "BTC/USDT": "MARE_ALTA_D1", "SOL/USDT": "MARE_ALTA_D1",
          "TRX/USDT": "MARE_ALTA_D1", "BNB/USDT": "MARE_ALTA_D1"}


def cadencia_degradada(p) -> bool:
    """True se o trade foi aberto dentro da janela de cadencia degradada."""
    o = str(p.get("opened_at") or "")[:16]
    return bool(o) and DEGRADADA_INI <= o < DEGRADADA_FIM


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
                           "exit": saida, "pnl": pnl, "pct": pct, "base": base,
                           "deg": cadencia_degradada(p)})
        elif not str(p.get("status", "")).startswith("open"):
            outros.append(p)
    trades.sort(key=lambda t: t["closed"])
    return trades, outros


def _fmt_pf(pf):
    return "inf" if pf == float("inf") else "%.2f" % pf


def degrau(trades) -> list:
    """Linhas (recorte, n, pnl, pf, aprovado) dos criterios D-024, com e sem deg.
    Recebe os trades ja filtrados por DEGRAU_DESDE."""
    out = []
    for nome, ts in (("Com cadencia degradada", trades),
                     ("Sem cadencia degradada", [t for t in trades if not t["deg"]])):
        r = resumo(ts)
        ok = r["n"] >= DEGRAU_MIN_TRADES and r["pnl"] > 0 and r["pf"] >= 1
        out.append((nome, r["n"], r["pnl"], r["pf"], ok))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--arquivo", default=os.path.join(_ROOT, "state", "positions.jsonl"))
    ap.add_argument("--desde", help="AAAA-MM-DD: so trades abertos a partir desta data")
    ap.add_argument("--degrau", action="store_true",
                    help="criterios do degrau US$ 20 (D-024) desde %s, com e sem deg" % DEGRAU_DESDE)
    a = ap.parse_args(argv)
    if a.degrau:
        trades, _ = carregar(a.arquivo, DEGRAU_DESDE)
        print("# Degrau US$ 20 (D-024): trades abertos desde %s\n" % DEGRAU_DESDE)
        print("| Recorte | Trades (min %d) | P&L ($) > 0 | PF >= 1 | Aprovado |" % DEGRAU_MIN_TRADES)
        print("|---|---|---|---|---|")
        for nome, n, pnl, pf, ok in degrau(trades):
            print("| %s | %d | %+.2f | %s | %s |" % (nome, n, pnl, _fmt_pf(pf), "SIM" if ok else "NAO"))
        return 0
    trades, outros = carregar(a.arquivo, a.desde)

    print("# Placar do bot%s\n" % (" (abertos desde %s)" % a.desde if a.desde else ""))
    print("| Fechou | Ativo | Estrategia | Entrada | Saida | Res. | P&L ($) | % | base | deg |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for t in trades:
        print("| %s | %s | %s | %s | %s | %s | %+.2f | %+.1f%% | %s | %s |" % (
            t["closed"], t["symbol"], t["strategy"], t["entry"], t["exit"],
            "TP" if t["status"] == "closed_tp" else "SL", t["pnl"], t["pct"], t["base"],
            "sim" if t["deg"] else ""))

    print("\n| Recorte | Trades | Wins | P&L ($) | PF |")
    print("|---|---|---|---|---|")
    r = resumo(trades)
    print("| Todos | %d | %d | %+.2f | %s |" % (r["n"], r["wins"], r["pnl"], _fmt_pf(r["pf"])))
    r = resumo([t for t in trades if not t["deg"]])
    print("| Sem cadencia degradada | %d | %d | %+.2f | %s |" % (r["n"], r["wins"], r["pnl"], _fmt_pf(r["pf"])))
    for grupo in ("strategy", "symbol"):
        for k in sorted({t[grupo] for t in trades}):
            r = resumo([t for t in trades if t[grupo] == k])
            print("| %s | %d | %d | %+.2f | %s |" % (k, r["n"], r["wins"], r["pnl"], _fmt_pf(r["pf"])))

    caminho_dca = os.path.join(os.path.dirname(a.arquivo), "dca.jsonl")
    if os.path.exists(caminho_dca):
        from bot import dca as _dca
        regs = _dca.ler_registro(caminho_dca)
        ativos = sorted({r.get("symbol") for r in regs if r.get("status") == "filled"})
        if ativos:
            print("\n## DCA semanal (D-049; sem stop, o bot nunca vende)\n")
            print("| Ativo | Compras | Investido (US$) | Quantidade estimada | Custo médio |")
            print("|---|---|---|---|---|")
            for s in ativos:
                x = _dca.acumulado(regs, s)
                print("| %s | %d | %.2f | %.8f | %.2f |" % (s, x["compras"], x["investido"], x["qtd"], x["custo_medio"] or 0))

    if outros:
        print("\nFora do placar (closed_manual, summary etc.):")
        for p in outros:
            print("- %s %s %s pnl_usdt=%s" % (p.get("status"), p.get("symbol"),
                                              p.get("signal_id"), p.get("pnl_usdt")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
