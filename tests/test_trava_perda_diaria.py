"""
test_trava_perda_diaria.py - EXECUTION_DAILY_LOSS_STOP alimentada pelo positions.jsonl (D-035, 2026-10-15).

Sem rede e sem tocar em state/: positions e estado diario vao para arquivos temporarios.

COMO RODAR
----------
    python tests/test_trava_perda_diaria.py   # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot import executor as ex                         # noqa: E402

ex.EXECUTION_STATE_FILE = os.path.join(tempfile.mkdtemp(), "execution_guard.json")
ex.EXECUTION_CONCENTRATION_GUARD = False               # isola a trava de perda
ex.EXECUTION_DAILY_LOSS_STOP = 20.0
ex.EXECUTION_DAILY_LOSS_FROM_POSITIONS = True

_ORDER = {"symbol": "TEST/USDT", "notional_usdt": 10.0}
_HOJE = datetime.now(timezone.utc).isoformat()
_ONTEM = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def _write(recs):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    ex.POSITIONS_FILE = path
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    return path


def _closed(pnl, when=_HOJE, status="closed_sl", **kw):
    r = {"signal_id": "x", "symbol": "SOL/USDT", "status": status, "closed_at": when}
    if pnl is not None:
        r["pnl_usdt_est"] = pnl
    r.update(kw)
    return r


def test_bloqueia_quando_perda_do_dia_atinge_o_limite():
    path = _write([_closed(-12.0), _closed(-8.0)])
    assert ex._realized_loss_today() == 20.0
    ok, motivo = ex.check_guards(_ORDER)
    assert not ok and "stop diario" in motivo, motivo
    os.remove(path)


def test_nao_bloqueia_abaixo_do_limite():
    path = _write([_closed(-19.99)])
    ok, motivo = ex.check_guards(_ORDER)
    assert ok, motivo
    os.remove(path)


def test_ganho_do_dia_compensa_perda():
    path = _write([_closed(-25.0), _closed(10.0, status="closed_tp")])
    assert ex._realized_loss_today() == 15.0
    assert ex.check_guards(_ORDER)[0]
    os.remove(path)


def test_ignora_outros_dias_e_abertas():
    path = _write([_closed(-30.0, when=_ONTEM),
                   {"signal_id": "o", "symbol": "BTC/USDT", "status": "open",
                    "pnl_usdt_est": -30.0, "closed_at": _HOJE}])
    assert ex._realized_loss_today() == 0.0
    assert ex.check_guards(_ORDER)[0]
    os.remove(path)


def test_linha_sem_pnl_conta_zero():
    path = _write([_closed(None), _closed(-5.0), _closed("lixo")])
    assert ex._realized_loss_today() == 5.0
    os.remove(path)


def test_arquivo_ausente_nao_bloqueia():
    ex.POSITIONS_FILE = os.path.join(tempfile.mkdtemp(), "nao_existe.jsonl")
    assert ex._realized_loss_today() == 0.0
    assert ex.check_guards(_ORDER)[0]


def test_kill_switch_desligado_volta_ao_comportamento_antigo():
    path = _write([_closed(-50.0)])
    ex.EXECUTION_DAILY_LOSS_FROM_POSITIONS = False
    try:
        ok, motivo = ex.check_guards(_ORDER)
        assert ok, motivo                            # contador antigo = 0
    finally:
        ex.EXECUTION_DAILY_LOSS_FROM_POSITIONS = True
    os.remove(path)


def test_espelho_gravado_no_estado():
    path = _write([_closed(-3.5)])
    ex._register_sent_order()
    with open(ex.EXECUTION_STATE_FILE, encoding="utf-8") as fh:
        st = json.load(fh)
    assert st["realized_loss_today"] == 3.5 and "derivado" in st["realized_loss_source"], st
    os.remove(path)


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
