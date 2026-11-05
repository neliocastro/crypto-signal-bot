"""
backtest_tendencia_diaria.py - backtest da Tendencia Diaria (id MARE_ALTA_D1) com a saida ATUAL.

Reconstroi o "backtest fiel" que aprovou a estrategia (o script de 2026-08 nao estava no
repositorio). So LE dados publicos de mercado; nao toca em state/, nao envia ordem.

Regra (igual ao bot):
  - Sinal na vela D1 FECHADA: MACD(12,26,9) cruza acima do sinal E EMA9 > EMA21. Usa as mesmas
    funcoes _ema/_atr de bot/mare_alta.py, para o sinal ser o do bot.
  - Compra na abertura da vela seguinte (+ slippage).
  - Stop fixo = entrada - 2,5 x ATR(14) (piso 0,8%), posicao inteira.
  - TP1 = entrada +10%: vende 50%, stop do restante vai ao breakeven.
  - Depois do TP1: trailing close_D1 - 3 x ATR, em vela fechada, so sobe (D-026/D-027).
  - 1 posicao por ativo (D-022): sinal com posicao aberta e ignorado.
  - Custos: taxa 0,1% por ponta (D-034) + slippage 0,05% por ponta.
  - Stop e TP1 no mesmo dia: conta o stop (conservador).

Retorno de cada trade em % do valor da ordem. "Retorno composto" = reinvestindo trade a trade.

USO
---
    python scripts/backtest_tendencia_diaria.py                       # 4 ativos atuais, desde 2018
    python scripts/backtest_tendencia_diaria.py --ativos BTC ETH SOL  # outros ativos
    python scripts/backtest_tendencia_diaria.py --filtro sma200       # so entra acima da SMA200
Resultado de 2026-11-05: docs/backtests/tendencia_diaria_20261105.md
"""
import argparse
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
sys.path.insert(0, os.path.dirname(_AQUI))

import bt_comum as bt                                            # noqa: E402
from bot.mare_alta import (_ema, _atr, MARE_ALTA_STOP_ATR,       # noqa: E402
                           MARE_ALTA_TRAIL_ATR, MARE_ALTA_TP1_PCT, MARE_ALTA_TP1_FRAC,
                           MARE_ALTA_UNIVERSE)

TAXA = bt.TAXA            # 0,1% por ponta
SLIP = 0.0005             # 0,05% por ponta
PISO_STOP = 0.008         # EXECUTION_MIN_STOP_PCT (0,8%)
AQUECIMENTO = 40          # mesmo minimo do check_mare_alta
JANELAS = (("2019-2022", "2019-01-01", "2023-01-01"),
           ("2023-2024", "2023-01-01", "2025-01-01"),
           ("2025-hoje", "2025-01-01", None),
           ("desde a escolha do universo (2026-07-10)", "2026-07-10", None))


def _ms(d):
    import calendar
    import time
    return calendar.timegm(time.strptime(d, "%Y-%m-%d")) * 1000


def sinais(candles):
    """Lista de bool: True na vela FECHADA i em que o bot daria o sinal."""
    c = [x[4] for x in candles]
    e9, e21, e12, e26 = _ema(c, 9), _ema(c, 21), _ema(c, 12), _ema(c, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    sig = _ema(macd, 9)
    return [i >= AQUECIMENTO and macd[i - 1] <= sig[i - 1] and macd[i] > sig[i] and e9[i] > e21[i]
            for i in range(len(c))]


def simular(candles, sinal, filtro=None):
    """Trades {entrada_ts, saida_ts, ret, aberto}. filtro: None ou 'sma200'."""
    o = [x[1] for x in candles]
    h = [x[2] for x in candles]
    lo = [x[3] for x in candles]
    c = [x[4] for x in candles]
    a = _atr(h, lo, c, 14)
    m200 = bt.sma(c, 200)
    n, i, trades = len(candles), 0, []
    while i < n - 1:
        ok = sinal[i] and (filtro != "sma200" or (m200[i] is not None and c[i] > m200[i]))
        if not ok:
            i += 1
            continue
        ent = o[i + 1] * (1 + SLIP)
        stop = min(ent - MARE_ALTA_STOP_ATR * a[i], ent * (1 - PISO_STOP))
        alvo = ent * (1 + MARE_ALTA_TP1_PCT)
        resto, ret, tp1, j = 1.0, 0.0, False, i + 1

        def _perna(qtd, preco):
            return qtd * (preco * (1 - TAXA) / (ent * (1 + TAXA)) - 1)

        while j < n:
            if lo[j] <= stop:
                ret += _perna(resto, min(stop, o[j]) * (1 - SLIP))
                resto = 0.0
                break
            if not tp1 and h[j] >= alvo:
                ret += _perna(MARE_ALTA_TP1_FRAC, max(alvo, o[j]))
                resto, tp1 = 1 - MARE_ALTA_TP1_FRAC, True
                stop = max(stop, ent)                       # breakeven
            if tp1:
                stop = max(stop, c[j] - MARE_ALTA_TRAIL_ATR * a[j])   # vale a partir de j+1
            j += 1
        aberto = resto > 0
        if aberto:                                          # marca no ultimo fechamento
            j = n - 1
            ret += _perna(resto, c[j])
        trades.append({"entrada_ts": candles[i + 1][0], "saida_ts": candles[j][0],
                       "ret": ret, "aberto": aberto, "dias": j - i})
        i = j + 1
    return trades


def metricas(trades):
    if not trades:
        return {"n": 0, "wr": 0.0, "pf": 0.0, "media": 0.0, "composto": 0.0, "pior_queda": 0.0}
    g = sum(t["ret"] for t in trades if t["ret"] > 0)
    p = -sum(t["ret"] for t in trades if t["ret"] < 0)
    eq = pico = 1.0
    queda = 0.0
    for t in trades:
        eq *= 1 + t["ret"]
        pico = max(pico, eq)
        queda = min(queda, eq / pico - 1)
    return {"n": len(trades), "wr": sum(t["ret"] > 0 for t in trades) / len(trades),
            "pf": g / p if p else float("inf"), "media": sum(t["ret"] for t in trades) / len(trades),
            "composto": eq - 1, "pior_queda": queda}


def referencias(candles, ini, fim):
    """Buy & hold e DCA semanal (valor igual a cada 7 dias) na janela."""
    sub = [x for x in candles if ini <= x[0] < fim]
    if len(sub) < 8:
        return None
    bh = sub[-1][4] / sub[0][1] - 1
    compras = sub[::7]
    dca = sum(1 / x[1] for x in compras) * sub[-1][4] / len(compras) - 1
    return bh, dca


def _pf(v):
    return "inf" if v == float("inf") else "%.2f" % v


def relatorio(dados, filtro=None):
    linhas = ["| Ativo | Janela | Trades | WR | PF | Média/trade | Composto | Pior queda | Buy & hold | DCA semanal |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for ativo, candles in dados.items():
        tr = simular(candles, sinais(candles), filtro)
        for nome, d0, d1 in JANELAS:
            ini, fim = _ms(d0), (_ms(d1) if d1 else 9e15)
            m = metricas([t for t in tr if ini <= t["entrada_ts"] < fim])
            ref = referencias(candles, ini, fim)
            if ref is None:
                continue
            linhas.append("| %s | %s | %d | %.0f%% | %s | %+.1f%% | %+.1f%% | %.1f%% | %+.1f%% | %+.1f%% |" % (
                ativo, nome, m["n"], m["wr"] * 100, _pf(m["pf"]), m["media"] * 100,
                m["composto"] * 100, m["pior_queda"] * 100, ref[0] * 100, ref[1] * 100))
    return "\n".join(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ativos", nargs="*", default=[s.split("/")[0] for s in MARE_ALTA_UNIVERSE])
    ap.add_argument("--dias", type=int, default=3300, help="historico (padrao ~9 anos)")
    ap.add_argument("--filtro", choices=["sma200"], default=None)
    a = ap.parse_args(argv)
    dados = {}
    for ativo in a.ativos:
        candles = bt.baixar_candles("%s/USDT" % ativo, "1d", a.dias)
        if len(candles) > 300:
            dados[ativo] = candles
    print("\n# Tendência Diária, saída atual%s\n" % (" + filtro SMA200" if a.filtro else ""))
    print(relatorio(dados, a.filtro))
    return 0


if __name__ == "__main__":
    sys.exit(main())
