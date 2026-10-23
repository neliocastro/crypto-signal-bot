#!/usr/bin/env python3
"""
backtest_range.py - FAIXA LATERAL (range trading, SO COMPRA - D-002) (2026-10-23).

Pergunta: comprar perto do fundo de uma faixa lateral e vender no meio dela da lucro, depois
da taxa, fora da amostra? Regras FIXAS (sem otimizar nos dados, para nao enganar o teste):

  Regime lateral (vela D1 do dia ANTERIOR, sem olhar o futuro):
    ADX(14, D1) < 20  e  largura da faixa de 20 dias (max - min) / fechamento <= 25%
  Entrada (fechamento da vela 4h), perto do SUPORTE da faixa:
    regime lateral  e  fechamento no quarto inferior da faixa de 20 dias (<= fundo + 25% da
    largura)  e  RSI(14, 4h) < 35  e  fechamento ainda acima do fundo
  Saida (precos fixados na entrada):
    alvo   meio da faixa (fundo + topo) / 2   [--alvo topo: topo - 10% da largura]
    stop   fundo da faixa - 0,5 x ATR(14, D1); se a minima tocar, sai no stop
    tempo  30 velas 4h (5 dias) sem alvo nem stop: sai no fechamento
  (Versao anterior usava a media de Bollinger 4h como alvo: ela atrasa e "atingia o alvo"
  abaixo da entrada; descartada antes de qualquer rodada com dados reais.)
  Taxa de 0,1% por ponta. Uma posicao por vez por ativo.

Validacao: os primeiros 60% do periodo sao "dentro da amostra" e os ultimos 40% "fora".
Veredito por ativo: APROVADO se fora da amostra tiver >= 15 trades, PF >= 1,2 e, dentro,
PF >= 1,0; AMOSTRA PEQUENA se tiver menos de 15 trades fora; REPROVADO no resto.

Uso:
  python -m scripts.backtest_range                      # BTC, SOL, TRX, BNB, PAXG; 730 dias
  python -m scripts.backtest_range --simbolos PAXG/USDT --alvo topo
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    from scripts.bt_comum import (TAXA, MS_D, rsi_wilder, atr, adx, diario_de_4h, baixar_candles, data)
except ImportError:
    from bt_comum import (TAXA, MS_D, rsi_wilder, atr, adx, diario_de_4h, baixar_candles, data)

ADX_MAX = 20.0
LARGURA_MAX = 0.25
JANELA_FAIXA = 20
RSI_MAX = 35.0
QUARTO_INFERIOR = 0.25
ALVO_TOPO_FOLGA = 0.10
STOP_ATR = 0.5
TEMPO_MAX = 30
FRACAO_DENTRO = 0.60
MIN_TRADES_FORA = 15


def regime_diario(dias):
    """Por dia d (indice em `dias`): (lateral?, fundo, topo, atr_d) usando dias ATE d inclusive.
    Quem usa deve olhar o dia ANTERIOR ao candle 4h, para nao ver o futuro."""
    ax = adx(dias, 14)
    at = atr(dias, 14)
    out = []
    for d in range(len(dias)):
        if d < JANELA_FAIXA - 1 or ax[d] is None or at[d] is None:
            out.append((False, None, None, None))
            continue
        jan = dias[d - JANELA_FAIXA + 1:d + 1]
        topo, fundo = max(c[2] for c in jan), min(c[3] for c in jan)
        largura = (topo - fundo) / dias[d][4]
        out.append((ax[d] < ADX_MAX and largura <= LARGURA_MAX, fundo, topo, at[d]))
    return out


def simular(c4h, alvo="meio"):
    """Lista de trades (ts_entrada, retorno_liquido, saida, velas) sobre candles 4h."""
    dias = diario_de_4h(c4h)
    reg = regime_diario(dias)
    dia_idx = {c[0] // MS_D: i for i, c in enumerate(dias)}
    r = rsi_wilder([c[4] for c in c4h], 14)
    trades = []
    i, n = 15, len(c4h)
    while i < n - 1:
        c = c4h[i]
        di = dia_idx.get(c[0] // MS_D - 1)           # dia ANTERIOR completo
        if di is None or r[i] is None:
            i += 1
            continue
        lateral, fundo, topo, atr_d = reg[di]
        if not lateral:
            i += 1
            continue
        largura = topo - fundo
        if not (fundo < c[4] <= fundo + QUARTO_INFERIOR * largura and r[i] < RSI_MAX):
            i += 1
            continue
        entrada = c[4]
        stop = fundo - STOP_ATR * atr_d
        alvo_px = (fundo + topo) / 2 if alvo == "meio" else topo - ALVO_TOPO_FOLGA * largura
        if stop >= entrada or alvo_px <= entrada:
            i += 1
            continue
        saida, motivo, j = None, None, i + 1
        fim = min(n - 1, i + TEMPO_MAX)
        while j <= fim:
            cj = c4h[j]
            if cj[3] <= stop:
                saida, motivo = stop, "stop"
                break
            if cj[2] >= alvo_px:
                saida, motivo = alvo_px, "alvo"
                break
            j += 1
        if saida is None:
            j = fim
            saida, motivo = c4h[fim][4], "tempo"
        ret = (saida * (1 - TAXA)) / (entrada * (1 + TAXA)) - 1
        trades.append((c[0], ret, motivo, j - i))
        i = j + 1
    return trades, sum(1 for x in reg if x[0]) / len(reg) if reg else 0.0


def metricas(trades):
    rets = [t[1] for t in trades]
    ganhos = sum(x for x in rets if x > 0)
    perdas = -sum(x for x in rets if x <= 0)
    eq = pico = mdd = 0.0
    for x in rets:
        eq += x
        pico = max(pico, eq)
        mdd = min(mdd, eq - pico)
    return {"n": len(rets), "wr": (100.0 * sum(1 for x in rets if x > 0) / len(rets)) if rets else 0.0,
            "pf": (ganhos / perdas) if perdas > 0 else (float("inf") if ganhos > 0 else 0.0),
            "total": 100 * sum(rets), "mdd": 100 * mdd,
            "stops": sum(1 for t in trades if t[2] == "stop")}


def veredito(dentro, fora):
    if fora["n"] < MIN_TRADES_FORA:
        return "AMOSTRA PEQUENA"
    if fora["pf"] >= 1.2 and dentro["pf"] >= 1.0:
        return "APROVADO"
    return "REPROVADO"


def _pf(v):
    return "inf" if v == float("inf") else "%.2f" % v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--simbolos", default="BTC/USDT,SOL/USDT,TRX/USDT,BNB/USDT,PAXG/USDT")
    ap.add_argument("--dias", type=int, default=730)
    ap.add_argument("--alvo", choices=["meio", "topo"], default="meio")
    ap.add_argument("--saida", default="docs/backtests")
    a = ap.parse_args(argv)
    hoje = time.strftime("%Y-%m-%d", time.gmtime())
    L = ["# Backtest: Faixa Lateral (range, só compra) (%s)" % hoje, "",
         "Regime: ADX(14, D1) < %.0f e faixa de %d dias com largura <= %.0f%%. Entrada: fechamento 4h no quarto "
         "inferior da faixa e RSI(14, 4h) < %.0f. Alvo: %s (fixo na entrada). Stop: fundo da faixa - %.1f x ATR(D1). "
         "Tempo máximo: %d velas 4h. Taxa %.1f%% por ponta. Dentro da amostra = primeiros %.0f%% do período. "
         "Gerado por `scripts/backtest_range.py`."
         % (ADX_MAX, JANELA_FAIXA, 100 * LARGURA_MAX, RSI_MAX,
            "meio da faixa" if a.alvo == "meio" else "topo da faixa - 10% da largura", STOP_ATR, TEMPO_MAX,
            100 * TAXA, 100 * FRACAO_DENTRO), "",
         "| Ativo | Período | Dias em regime lateral | Recorte | Trades | Acerto | PF | Retorno somado | Pior queda | Stops | Veredito |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    aprovados = []
    for s in [x.strip() for x in a.simbolos.split(",") if x.strip()]:
        cs = baixar_candles(s, "4h", a.dias)
        if len(cs) < 300:
            L.append("| %s | sem dados | | | | | | | | | |" % s)
            continue
        trades, frac_lateral = simular(cs, a.alvo)
        corte = cs[0][0] + FRACAO_DENTRO * (cs[-1][0] - cs[0][0])
        dentro = metricas([t for t in trades if t[0] < corte])
        fora = metricas([t for t in trades if t[0] >= corte])
        v = veredito(dentro, fora)
        if v == "APROVADO":
            aprovados.append(s)
        per = "%s a %s" % (data(cs[0][0]), data(cs[-1][0]))
        for nome, m, ver in (("dentro", dentro, ""), ("fora", fora, "**%s**" % v)):
            L.append("| %s | %s | %.0f%% | %s | %d | %.0f%% | %s | %+.1f%% | %+.1f%% | %d | %s |" % (
                s, per, 100 * frac_lateral, nome, m["n"], m["wr"], _pf(m["pf"]), m["total"], m["mdd"],
                m["stops"], ver))
    L += ["", "Aprovados: %s" % (", ".join(aprovados) if aprovados else "nenhum")]
    texto = "\n".join(L)
    print(texto)
    os.makedirs(a.saida, exist_ok=True)
    caminho = os.path.join(a.saida, "range_%s.md" % hoje.replace("-", ""))
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    print("\nRelatorio gravado em %s" % caminho)
    return 0


if __name__ == "__main__":
    sys.exit(main())
