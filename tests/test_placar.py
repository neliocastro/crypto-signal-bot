"""
test_placar.py - saida e P&L estimados no fechamento + scripts/placar.py (D-034, 2026-10-15).

Sem rede: o relay PHP e simulado (_sign_and_send falso) com respostas do oco_sync.

COMO RODAR
----------
    python tests/test_placar.py         # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from bot import oco_guard                              # noqa: E402
from bot import mare_alta_trailing as mt               # noqa: E402
import placar                                          # noqa: E402

oco_guard.EXIT_RECORD_ENABLED = True
oco_guard.EXIT_FEE_RATE = 0.001
oco_guard.SL_EXPIRED_ALERT_ENABLED = False


def _close(a, b):
    return abs(a - b) < 1e-6


def _write(recs):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    mt.POSITIONS_FILE = path
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return path


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _pos(**kw):
    p = {"signal_id": "s1", "symbol": "SOL/USDT", "base_qty": "0.1", "entry_price": 100.0,
         "sl_price": 90.0, "sl_order_id": "SL1", "tp_price": 120.0, "tp_order_id": "TP1",
         "status": "open", "opened_at": "2026-10-01T00:00:00+00:00"}
    p.update(kw)
    return p


def test_pnl_sl_simples():
    e = oco_guard.exit_pnl_est(_pos(), "sl")
    # 0.1 x 90 x 0.999 - 0.1 x 100 x 1.001
    assert _close(e["pnl_usdt_est"], 8.991 - 10.01) and e["exit_price"] == 90.0, e
    assert e["exit_qty"] == "0.1", e


def test_pnl_tp_simples():
    e = oco_guard.exit_pnl_est(_pos(), "tp")
    assert _close(e["pnl_usdt_est"], 12 * 0.999 - 10.01) and e["exit_price"] == 120.0, e


def test_pnl_tp1_e_depois_sl_no_breakeven():
    p = _pos(base_qty="0.045", tp_partial=True, tp1_qty="0.045", tp1_done=True,
             tp1_price=110.0, tp_price=0.0, sl_price=100.0)
    e = oco_guard.exit_pnl_est(p, "sl")
    # (0.045 x 110 + 0.045 x 100) x 0.999 - 0.09 x 100 x 1.001
    assert _close(e["pnl_usdt_est"], 9.45 * 0.999 - 9.009), e
    assert e["exit_qty"] == "0.045", e


def test_pnl_tp1_e_sl_no_mesmo_intervalo():
    p = _pos(base_qty="0.09", tp_partial=True, tp1_qty="0.045", tp1_done=False,
             tp1_hit_at="2026-10-10T00:00:00+00:00", tp_price=110.0, sl_price=90.0)
    e = oco_guard.exit_pnl_est(p, "sl")
    assert _close(e["pnl_usdt_est"], 9.0 * 0.999 - 9.009) and e["exit_qty"] == "0.045", e


def test_oco_grava_saida_no_fechamento():
    path = _write([_pos()])
    mt._sign_and_send = lambda payload, timeout=12: {
        "status": "oco_synced",
        "pairs": [{"signal_id": "s1", "closed_by": "sl",
                   "cancel": {"side": "tp", "id": "TP1", "http": 200, "err": None},
                   "tp": {"id": "TP1", "status": "open"},
                   "sl": {"id": "SL1", "status": "finish", "fired_order_id": "F9",
                          "ftime": 1789000000}}]}
    oco_guard.sync()
    p = _read(path)[0]
    assert p["status"] == "closed_sl" and p["exit_price"] == 90.0, p
    assert p["exit_basis"] == "gatilho_est" and p["exit_fired_order_id"] == "F9", p
    assert p["exit_ftime"] == 1789000000 and _close(p["pnl_usdt_est"], -1.019), p
    os.remove(path)


def test_kill_switch_desligado_nao_grava():
    path = _write([_pos()])
    mt._sign_and_send = lambda payload, timeout=12: {
        "status": "oco_synced",
        "pairs": [{"signal_id": "s1", "closed_by": "tp", "cancel": None,
                   "tp": {"id": "TP1", "status": "finish"}, "sl": {"id": "SL1", "status": "open"}}]}
    oco_guard.EXIT_RECORD_ENABLED = False
    try:
        oco_guard.sync()
    finally:
        oco_guard.EXIT_RECORD_ENABLED = True
    p = _read(path)[0]
    assert p["status"] == "closed_tp" and "exit_price" not in p and "pnl_usdt_est" not in p, p
    os.remove(path)


def test_register_position_grava_strategy():
    path = _write([])
    mt.register_position("s9", "BTC/USDT", "0.0001", 80000.0, sl_price=76000.0,
                         sl_order_id="SLX", strategy="MARE_ALTA_D1")
    mt.register_position("s8", "BTC/USDT", "0.0001", 80000.0, sl_price=76000.0,
                         sl_order_id="SLY")
    rows = {r["signal_id"]: r for r in _read(path)}
    assert rows["s9"]["strategy"] == "MARE_ALTA_D1" and "strategy" not in rows["s8"], rows
    os.remove(path)


def test_placar_bases_e_resumo():
    path = _write([
        _pos(signal_id="a", status="closed_sl"),                                  # gatilho
        _pos(signal_id="b", status="closed_tp", exit_price=110.0),                # saida
        _pos(signal_id="c", status="closed_tp", pnl_usdt=0.5, pnl_pct=5.0),       # reg
        _pos(signal_id="d", status="closed_sl", pnl_usdt_est=-0.2, pnl_pct_est=-2.0,
             strategy="MARE_ALTA_D1", opened_at="2026-09-10T00:00:00+00:00"),     # est
        _pos(signal_id="e", status="open"),
        _pos(signal_id="f", status="closed_manual"),
    ])
    trades, outros = placar.carregar(path)
    base = {t["pnl"]: t["base"] for t in trades}
    assert sorted(base.values()) == ["est", "gatilho", "reg", "saida"], base
    assert [o["signal_id"] for o in outros] == ["f"], outros
    t_saida = [t for t in trades if t["base"] == "saida"][0]
    assert _close(t_saida["pnl"], 11 * 0.999 - 10.01), t_saida
    r = placar.resumo(trades)
    assert r["n"] == 4 and r["wins"] == 2, r
    gain = 0.5 + (11 * 0.999 - 10.01)
    loss = 0.2 + 1.019
    assert _close(r["pnl"], gain - loss) and _close(r["pf"], gain / loss), r
    # --desde filtra pela data de ABERTURA (regra D-024)
    assert [t["base"] for t in placar.carregar(path, "2026-10-01")[0]] != []
    assert len(placar.carregar(path, "2026-10-02")[0]) == 0
    os.remove(path)


def test_placar_estrategia_inferida():
    assert placar._strategy({"symbol": "HYPE/USDT"}) == "Breakout / Tendência*"
    assert placar._strategy({"symbol": "BNB/USDT"}) == "MARE_ALTA_D1*"
    assert placar._strategy({"symbol": "ETH/USDT"}) == "nao_registrada*"
    assert placar._strategy({"symbol": "ETH/USDT", "strategy": "X"}) == "X"


def test_cadencia_degradada_pela_abertura():
    assert placar.cadencia_degradada({"opened_at": "2026-09-14T21:13:00+00:00"})
    assert placar.cadencia_degradada({"opened_at": "2026-10-09T01:01:59+00:00"})
    assert not placar.cadencia_degradada({"opened_at": "2026-09-14T21:12:59+00:00"})
    assert not placar.cadencia_degradada({"opened_at": "2026-10-09T01:02:00+00:00"})
    assert not placar.cadencia_degradada({})


def test_degrau_com_e_sem_degradada():
    ganho = {"pnl": 1.0, "deg": False}
    perda_deg = {"pnl": -3.0, "deg": True}
    trades = [dict(ganho) for _ in range(20)] + [perda_deg]
    linhas = {l[0]: l for l in placar.degrau(trades)}
    com, sem = linhas["Com cadencia degradada"], linhas["Sem cadencia degradada"]
    assert com[1] == 21 and abs(com[2] - 17.0) < 1e-9 and com[4], com
    assert sem[1] == 20 and sem[4], sem
    poucos = placar.degrau([dict(ganho) for _ in range(19)])
    assert not poucos[0][4] and not poucos[1][4], poucos     # amostra < 20 reprova


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
