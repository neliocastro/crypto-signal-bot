"""
test_backtests.py - logica dos backtests de acumulo x DCA e de range (2026-10-23).

Dados sinteticos, sem rede e sem pandas/ccxt: confere indicadores, a cadencia das compras,
o stop dos lotes, o filtro de regime e a ausencia de entradas fora do regime lateral.

COMO RODAR
----------
    python tests/test_backtests.py      # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import bt_comum as bt                 # noqa: E402
import backtest_acumulo as ac         # noqa: E402
import backtest_range as rg           # noqa: E402

H4 = 4 * bt.MS_H
T0 = 1_700_000_000_000 // bt.MS_D * bt.MS_D      # meia-noite UTC


def _velas(precos, amp=0.002):
    """Candles 4h a partir de fechamentos: abre no fechamento anterior, maxima/minima +-amp."""
    out, ant = [], precos[0]
    for k, p in enumerate(precos):
        hi, lo = max(ant, p) * (1 + amp), min(ant, p) * (1 - amp)
        out.append((T0 + k * H4, ant, hi, lo, p))
        ant = p
    return out


def _perto(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_sma_desvio_rsi():
    assert bt.sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]
    d = bt.desvio([1, 2, 3, 4], 2)
    assert d[0] is None and _perto(d[1], math.sqrt(0.5))
    sobe = bt.rsi_wilder([float(x) for x in range(1, 40)])
    assert sobe[14] == 100.0 and sobe[-1] == 100.0
    zigue = bt.rsi_wilder([100.0 + (1 if k % 2 else 0) for k in range(60)])
    assert 45 < zigue[-1] < 55, zigue[-1]


def test_adx_tendencia_x_lateral():
    tendencia = [(T0 + k * bt.MS_D, 100 + k, 101 + k, 99 + k, 100.5 + k) for k in range(80)]
    lateral = [(T0 + k * bt.MS_D, 100, 102 + (k % 2), 98 - (k % 2), 100 + (1 if k % 2 else -1)) for k in range(80)]
    at, al = bt.adx(tendencia)[-1], bt.adx(lateral)[-1]
    assert at > 40 and al < 20, (at, al)


def test_diario_de_4h_so_dias_completos():
    cs = _velas([100 + k for k in range(14)])          # 2 dias completos + 2 velas
    ds = bt.diario_de_4h(cs)
    assert len(ds) == 2 and ds[0][0] == T0 and ds[0][1] == cs[0][1] and ds[0][4] == cs[5][4]
    assert ds[0][2] == max(c[2] for c in cs[:6]) and ds[0][3] == min(c[3] for c in cs[:6])


def test_dca_a_cada_7_dias():
    cs = _velas([100.0] * (6 * 30))                    # 30 dias de 4h
    idx = ac.idx_dca(cs, dias=7, inicio=0)
    assert idx == [0, 42, 84, 126, 168], idx


def test_rsi_respeita_espera_de_12h():
    cs = _velas([100 * (0.99 ** k) for k in range(80)])  # queda continua: RSI fica < 30
    idx = ac.idx_rsi(cs, limiar=30, espera_h=12, inicio=0)
    assert len(idx) > 5
    assert all(b - a >= 3 for a, b in zip(idx, idx[1:])), idx   # 3 velas 4h = 12 h


def test_carteira_custo_medio_e_stop():
    cs = _velas([100.0, 100.0, 80.0, 80.0], amp=0.0)
    sem = ac.carteira(cs, [0])
    assert _perto(sem["custo_medio"], 100.0 / 0.999) and sem["stops"] == 0   # custo medio inclui a taxa and _perto(sem["retorno"], 0.8 * 0.999 - 1)
    com = ac.carteira(cs, [0], stop_pct=0.15)
    assert com["stops"] == 1 and com["qtd"] == 0 and com["custo_medio"] is None
    assert _perto(com["recuperado"], 10 * 0.999 / 100 * 85 * 0.999), com["recuperado"]


def test_veredito_acumulo():
    assert ac.veredito(97.0, 100.0) == "MAIS BARATO"
    assert ac.veredito(99.0, 100.0) == "EMPATE"
    assert ac.veredito(103.0, 100.0) == "MAIS CARO"
    assert ac.veredito(None, 100.0) == "SEM COMPRAS"


def _lateral(dias=120):
    """Oscila +-4% em torno de 100 com periodo de 5 dias (30 velas 4h)."""
    return _velas([100 * (1 + 0.04 * math.sin(2 * math.pi * k / 30)) for k in range(6 * dias)])


def test_range_opera_em_lateral():
    trades, frac = rg.simular(_lateral())
    assert frac > 0.5, frac
    assert len(trades) >= 5, len(trades)
    assert all(t[2] in ("alvo", "stop", "tempo") for t in trades)
    assert sum(1 for t in trades if t[2] == "alvo") >= len(trades) // 2, trades
    # alvo fixado na entrada e acima dela: sair no alvo nunca pode dar prejuizo (bug da 1a versao)
    assert all(t[1] > 0 for t in trades if t[2] == "alvo"), [t for t in trades if t[2] == "alvo" and t[1] <= 0]
    topo, _ = rg.simular(_lateral(), alvo="topo")
    assert topo and all(t[1] > 0 for t in topo if t[2] == "alvo")


def test_range_nao_opera_em_tendencia():
    sobe = _velas([100 * (1.004 ** k) for k in range(6 * 120)])
    trades, frac = rg.simular(sobe)
    assert frac == 0.0 and trades == [], (frac, trades[:3])


def test_range_metricas_e_veredito():
    tr = [(0, 0.02, "alvo", 3), (1, -0.01, "stop", 2), (2, 0.01, "alvo", 4)]
    m = rg.metricas(tr)
    assert m["n"] == 3 and _perto(m["pf"], 3.0) and _perto(m["total"], 2.0) and m["stops"] == 1
    bom = {"n": 20, "pf": 1.5}
    assert rg.veredito({"n": 30, "pf": 1.1}, bom) == "APROVADO"
    assert rg.veredito({"n": 30, "pf": 0.9}, bom) == "REPROVADO"
    assert rg.veredito({"n": 30, "pf": 2.0}, {"n": 10, "pf": 3.0}) == "AMOSTRA PEQUENA"


if __name__ == "__main__":
    falhas = 0
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS ", nome)
            except Exception as e:                       # noqa: BLE001
                falhas += 1
                print("FAIL ", nome, "->", repr(e))
    sys.exit(1 if falhas else 0)
