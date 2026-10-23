#!/usr/bin/env python3
"""
backtest_acumulo.py - ACUMULO NA QUEDA (RSI 4h < 30) x DCA simples (2026-10-23).

Pergunta: comprar US$ 10 quando o RSI 4h cai abaixo de 30 (espera de 12 h entre compras,
como o cron do PAXG, D-032) compra MAIS BARATO do que um DCA de US$ 10 por semana?
Num acumulo o que importa e o CUSTO MEDIO e o pior momento da carteira, nao o PF.

Tres carteiras, no mesmo periodo e com taxa de 0,1% por ponta:
  dca        US$ 10 a cada 7 dias, no fechamento da vela 4h
  rsi        US$ 10 quando RSI(14, 4h) < 30, no fechamento; espera de 12 h; sem stop
  rsi_stop   igual ao rsi, mas cada lote tem stop de -15% (o que o cron do PAXG faz hoje)

O periodo inteiro e tambem as duas metades sao rodados separadamente (consistencia).
Veredito do rsi (em cada recorte): custo medio pelo menos 2% abaixo do DCA = MAIS BARATO;
dentro de +-2% = EMPATE; acima = MAIS CARO. Aprovado so se MAIS BARATO nos tres recortes.

Uso:
  python -m scripts.backtest_acumulo                       # BTC e PAXG, 730 dias
  python -m scripts.backtest_acumulo --simbolos PAXG/USDT --dias 365
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    from scripts.bt_comum import TAXA, MS_H, MS_D, rsi_wilder, baixar_candles, data
except ImportError:                                                  # rodando de dentro de scripts/
    from bt_comum import TAXA, MS_H, MS_D, rsi_wilder, baixar_candles, data

VALOR = 10.0
LIMIAR = 30.0
ESPERA_H = 12
STOP_PCT = 0.15
DCA_DIAS = 7
AQUECIMENTO = 30     # velas 4h antes de comecar (RSI estavel)


def carteira(candles, compras_idx, stop_pct=None, valor=VALOR):
    """Simula uma carteira que compra `valor` no fechamento das velas em `compras_idx`.
    Com stop_pct, cada lote e vendido no stop (entrada x (1 - stop_pct)) se a minima tocar.
    Devolve metricas; `custo_medio` e o das moedas que ainda estao na carteira."""
    compras = set(compras_idx)
    lotes = []                     # [qtd, preco_entrada, preco_stop]
    investido = recuperado = 0.0
    n_stops = 0
    pior = 0.0
    datas = []
    for i, c in enumerate(candles):
        if stop_pct is not None:
            vivos = []
            for q, pe, ps in lotes:
                if c[3] <= ps:
                    recuperado += q * ps * (1 - TAXA)
                    n_stops += 1
                else:
                    vivos.append([q, pe, ps])
            lotes = vivos
        if i in compras:
            preco = c[4]
            qtd = valor * (1 - TAXA) / preco
            lotes.append([qtd, preco, preco * (1 - stop_pct) if stop_pct else 0.0])
            investido += valor
            datas.append(c[0])
        if investido > 0:
            valor_atual = sum(q for q, _, _ in lotes) * c[4] + recuperado
            pior = min(pior, valor_atual / investido - 1)
    qtd = sum(q for q, _, _ in lotes)
    custo_lotes = sum(q * pe / (1 - TAXA) for q, pe, _ in lotes)   # quanto custou o que sobrou
    final = qtd * candles[-1][4] + recuperado if candles else 0.0
    gaps = [(b - a) / MS_D for a, b in zip(datas, datas[1:])]
    return {
        "compras": len(datas), "investido": investido, "qtd": qtd,
        "custo_medio": (custo_lotes / qtd) if qtd > 0 else None,
        "stops": n_stops, "recuperado": recuperado, "final": final,
        "retorno": (final / investido - 1) if investido > 0 else 0.0,
        "pior": pior, "maior_intervalo_dias": max(gaps) if gaps else None,
    }


def idx_dca(candles, dias=DCA_DIAS, inicio=AQUECIMENTO):
    out, prox = [], None
    for i in range(inicio, len(candles)):
        if prox is None or candles[i][0] >= prox:
            out.append(i)
            prox = candles[i][0] + dias * MS_D
    return out


def idx_rsi(candles, limiar=LIMIAR, espera_h=ESPERA_H, inicio=AQUECIMENTO):
    r = rsi_wilder([c[4] for c in candles])
    out, ultima = [], None
    for i in range(max(inicio, 15), len(candles)):
        if r[i] is None or r[i] >= limiar:
            continue
        if ultima is not None and candles[i][0] - candles[ultima][0] < espera_h * MS_H:
            continue
        out.append(i)
        ultima = i
    return out


def veredito(custo_rsi, custo_dca):
    if custo_rsi is None or custo_dca is None:
        return "SEM COMPRAS"
    d = custo_rsi / custo_dca - 1
    if d <= -0.02:
        return "MAIS BARATO"
    if d < 0.02:
        return "EMPATE"
    return "MAIS CARO"


def rodar(candles):
    """As tres carteiras num recorte de candles."""
    d = carteira(candles, idx_dca(candles))
    r = carteira(candles, idx_rsi(candles))
    rs = carteira(candles, idx_rsi(candles), stop_pct=STOP_PCT)
    return {"dca": d, "rsi": r, "rsi_stop": rs, "veredito": veredito(r["custo_medio"], d["custo_medio"])}


def _fmt(v, casas=2):
    return "n/d" if v is None else ("%.*f" % (casas, v))


def relatorio(simbolo, recortes):
    L = ["### %s" % simbolo, "",
         "| Recorte | Carteira | Compras | Investido | Custo médio | Stops | Retorno | Pior momento | Maior intervalo sem compra |",
         "|---|---|---|---|---|---|---|---|---|"]
    for nome, (ini, fim, res) in recortes:
        for k in ("dca", "rsi", "rsi_stop"):
            m = res[k]
            L.append("| %s (%s a %s) | %s | %d | US$ %.0f | %s | %d | %+.1f%% | %+.1f%% | %s dias |" % (
                nome, data(ini), data(fim), k, m["compras"], m["investido"], _fmt(m["custo_medio"]),
                m["stops"], 100 * m["retorno"], 100 * m["pior"], _fmt(m["maior_intervalo_dias"], 0)))
    L.append("")
    vs = [(nome, res["veredito"]) for nome, (_, _, res) in recortes]
    L.append("Veredito do RSI contra o DCA: " + "; ".join("%s = **%s**" % v for v in vs))
    aprovado = all(v == "MAIS BARATO" for _, v in vs)
    L.append("**%s**" % ("APROVADO: compra mais barato nos três recortes" if aprovado else "NÃO APROVADO"))
    return L, aprovado


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--simbolos", default="BTC/USDT,PAXG/USDT")
    ap.add_argument("--dias", type=int, default=730)
    ap.add_argument("--saida", default="docs/backtests")
    a = ap.parse_args(argv)
    hoje = time.strftime("%Y-%m-%d", time.gmtime())
    L = ["# Backtest: Acúmulo na Queda x DCA (%s)" % hoje, "",
         "RSI(14, 4h) < %.0f, espera %d h, US$ %.0f por compra; DCA US$ %.0f a cada %d dias; "
         "stop do `rsi_stop` = -%.0f%%; taxa %.1f%% por ponta. Gerado por `scripts/backtest_acumulo.py`."
         % (LIMIAR, ESPERA_H, VALOR, VALOR, DCA_DIAS, 100 * STOP_PCT, 100 * TAXA), ""]
    for s in [x.strip() for x in a.simbolos.split(",") if x.strip()]:
        cs = baixar_candles(s, "4h", a.dias)
        if len(cs) < 200:
            L += ["### %s" % s, "", "Sem dados suficientes.", ""]
            continue
        meio = len(cs) // 2
        recortes = [("inteiro", (cs[0][0], cs[-1][0], rodar(cs))),
                    ("1ª metade", (cs[0][0], cs[meio - 1][0], rodar(cs[:meio]))),
                    ("2ª metade", (cs[meio][0], cs[-1][0], rodar(cs[meio:])))]
        linhas, _ = relatorio(s, recortes)
        L += linhas + [""]
    texto = "\n".join(L)
    print(texto)
    os.makedirs(a.saida, exist_ok=True)
    caminho = os.path.join(a.saida, "acumulo_%s.md" % hoje.replace("-", ""))
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    print("\nRelatorio gravado em %s" % caminho)
    return 0


if __name__ == "__main__":
    sys.exit(main())
