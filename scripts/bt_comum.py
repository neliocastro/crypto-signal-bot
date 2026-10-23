"""
bt_comum.py - base comum dos backtests de 2026-10 (acumulo x DCA e range), em Python PURO.

Candle = tupla (ts_ms, open, high, low, close). Indicadores devolvem listas do mesmo tamanho,
com None onde ainda nao ha dados. Sem pandas: os testes rodam no workflow `checks`, que nao
instala as dependencias do bot. So `baixar_candles` usa ccxt (importado sob demanda).
"""
from __future__ import annotations

import math
import time

MS_H = 3600 * 1000
MS_D = 24 * MS_H
TAXA = 0.001          # 0,1% por ponta (Gate spot, mesma premissa do placar, D-034)


# ------------------------------- indicadores --------------------------------
def sma(xs, p):
    out, soma = [None] * len(xs), 0.0
    for i, x in enumerate(xs):
        soma += x
        if i >= p:
            soma -= xs[i - p]
        if i >= p - 1:
            out[i] = soma / p
    return out


def desvio(xs, p):
    out = [None] * len(xs)
    for i in range(p - 1, len(xs)):
        jan = xs[i - p + 1:i + 1]
        m = sum(jan) / p
        out[i] = math.sqrt(sum((v - m) ** 2 for v in jan) / (p - 1))
    return out


def rsi_wilder(closes, p=14):
    """RSI de Wilder (mesma formula do cron PAXG, server/paxg_rsi_check.php)."""
    out = [None] * len(closes)
    if len(closes) <= p:
        return out
    ganho = perda = 0.0
    for i in range(1, p + 1):
        d = closes[i] - closes[i - 1]
        ganho += max(d, 0.0)
        perda += max(-d, 0.0)
    mg, mp = ganho / p, perda / p
    out[p] = 100.0 if mp == 0 else 100 - 100 / (1 + mg / mp)
    for i in range(p + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        mg = (mg * (p - 1) + max(d, 0.0)) / p
        mp = (mp * (p - 1) + max(-d, 0.0)) / p
        out[i] = 100.0 if mp == 0 else 100 - 100 / (1 + mg / mp)
    return out


def _tr(c, ant):
    return max(c[2] - c[3], abs(c[2] - ant[4]), abs(c[3] - ant[4]))


def atr(candles, p=14):
    out = [None] * len(candles)
    if len(candles) <= p:
        return out
    trs = [None] + [_tr(candles[i], candles[i - 1]) for i in range(1, len(candles))]
    a = sum(trs[1:p + 1]) / p
    out[p] = a
    for i in range(p + 1, len(candles)):
        a = (a * (p - 1) + trs[i]) / p
        out[i] = a
    return out


def adx(candles, p=14):
    """ADX de Wilder. Abaixo de ~20 = sem tendencia (lateral)."""
    n = len(candles)
    out = [None] * n
    if n <= 2 * p:
        return out
    tr, pdm, mdm = [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n):
        up = candles[i][2] - candles[i - 1][2]
        dn = candles[i - 1][3] - candles[i][3]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = _tr(candles[i], candles[i - 1])
    s_tr, s_p, s_m = sum(tr[1:p + 1]), sum(pdm[1:p + 1]), sum(mdm[1:p + 1])
    dxs = []
    for i in range(p, n):
        if i > p:
            s_tr = s_tr - s_tr / p + tr[i]
            s_p = s_p - s_p / p + pdm[i]
            s_m = s_m - s_m / p + mdm[i]
        if s_tr <= 0:
            dxs.append((i, 0.0))
            continue
        pdi, mdi = 100 * s_p / s_tr, 100 * s_m / s_tr
        dxs.append((i, 0.0 if pdi + mdi == 0 else 100 * abs(pdi - mdi) / (pdi + mdi)))
    if len(dxs) < p:
        return out
    a = sum(d for _, d in dxs[:p]) / p
    out[dxs[p - 1][0]] = a
    for i, d in dxs[p:]:
        a = (a * (p - 1) + d) / p
        out[i] = a
    return out


def diario_de_4h(candles_4h):
    """Agrega candles 4h em D1 (UTC). So dias completos (6 candles)."""
    dias, ordem = {}, []
    for c in candles_4h:
        d = c[0] // MS_D
        if d not in dias:
            dias[d] = []
            ordem.append(d)
        dias[d].append(c)
    out = []
    for d in ordem:
        cs = dias[d]
        if len(cs) < 6:
            continue
        out.append((d * MS_D, cs[0][1], max(c[2] for c in cs), min(c[3] for c in cs), cs[-1][4]))
    return out


# ------------------------------- dados (ccxt) --------------------------------
def baixar_candles(simbolo, timeframe, dias, exchanges=("gateio", "binance", "bybit")):
    """Candles fechados dos ultimos `dias`, da primeira exchange que tiver o par."""
    import ccxt  # so aqui: os testes nao precisam de ccxt
    passo = {"1h": MS_H, "4h": 4 * MS_H, "1d": MS_D}[timeframe]
    for nome in exchanges:
        try:
            ex = getattr(ccxt, nome)({"enableRateLimit": True})
            ex.load_markets()
            if simbolo not in ex.markets:
                continue
            fim = ex.milliseconds()
            cursor = fim - dias * MS_D
            linhas, vistos = [], set()
            for _ in range(60):
                lote = ex.fetch_ohlcv(simbolo, timeframe, since=cursor, limit=1000)
                if not lote:
                    break
                novos = [r for r in lote if r[0] not in vistos]
                if not novos:
                    break
                for r in novos:
                    vistos.add(r[0])
                    linhas.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
                cursor = lote[-1][0] + passo
                if cursor >= fim:
                    break
                time.sleep(ex.rateLimit / 1000)
            linhas.sort()
            linhas = [c for c in linhas if c[0] + passo <= fim]     # descarta a vela em formacao
            if len(linhas) > 100:
                print("  [%s %s] %d candles via %s (%.0f dias)" % (
                    simbolo, timeframe, len(linhas), nome, (linhas[-1][0] - linhas[0][0]) / MS_D))
                return linhas
        except Exception as e:                                       # noqa: BLE001
            print("  [%s] %s falhou: %s" % (simbolo, nome, str(e)[:80]))
    print("  [%s] SEM DADOS" % simbolo)
    return []


def data(ts_ms):
    return time.strftime("%Y-%m-%d", time.gmtime(ts_ms / 1000))
