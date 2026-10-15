"""
test_renovacao_sl.py - renovacao do SL antes dos 30 dias da Gate (D-033, 2026-10-15).

Sem rede: o relay PHP e simulado (_sign_and_send falso) com as respostas da
acao update_trailing do execute.php.

COMO RODAR
----------
    python tests/test_renovacao_sl.py   # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot import oco_guard                              # noqa: E402
from bot import mare_alta_trailing as mt               # noqa: E402

mt.SL_RENEW_ENABLED = True
mt.SL_RENEW_AFTER_DAYS = 25
oco_guard.SL_EXPIRED_ALERT_ENABLED = True


def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


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
    p = {"signal_id": "s1", "symbol": "SOL/USDT", "base_qty": "0.09",
         "entry_price": 100.5, "sl_price": 90.0, "sl_order_id": "SL1",
         "tp_price": 110.0, "tp_order_id": "TP1", "status": "open",
         "tp_partial": True, "tp1_qty": "0.045", "tp1_done": False,
         "opened_at": _ago(26), "updated_at": _ago(26)}
    p.update(kw)
    return p


def _relay_ok(sent):
    def f(payload, timeout=12):
        sent.append(payload)
        return {"status": "trailing_updated",
                "new_sl": {"id": "SL2", "price": str(payload["new_sl_price"])}}
    return f


def test_renova_com_25_dias_mesmo_preco_e_qty():
    path = _write([_pos(sl_set_at=_ago(25.1))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    r = mt.renew_expiring_sl()
    assert len(sent) == 1, sent
    assert sent[0]["action"] == "update_trailing" and sent[0]["new_sl_price"] == 90.0, sent
    assert sent[0]["base_qty"] == "0.09" and sent[0]["old_sl_order_id"] == "SL1", sent
    p = _read(path)[0]
    assert p["sl_order_id"] == "SL2" and p["sl_price"] == 90.0, p
    assert p["sl_renewed_count"] == 1 and mt._age_days(p["sl_set_at"]) < 0.01, p
    assert p["tp_order_id"] == "TP1" and not p["tp1_done"], p     # TP1 intocado
    assert r[0]["action"] == "sl_renewed", r
    # segundo scan: SL novo, nada a fazer
    mt.renew_expiring_sl()
    assert len(sent) == 1, sent
    os.remove(path)


def test_nao_renova_antes_de_25_dias():
    path = _write([_pos(sl_set_at=_ago(24.9))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    assert mt.renew_expiring_sl() == [] and not sent
    os.remove(path)


def test_sem_sl_set_at_usa_opened_at():
    path = _write([_pos(opened_at=_ago(26)), _pos(signal_id="s2", opened_at=_ago(3))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    mt.renew_expiring_sl()
    assert [s["signal_id"] for s in sent] == ["s1"], sent
    os.remove(path)


def test_falha_mantem_sl_antigo_e_avisa_uma_vez_por_dia():
    path = _write([_pos(sl_set_at=_ago(27))])
    msgs = []
    mt._sign_and_send = lambda payload, timeout=12: {"status": "error",
                                                     "reason": "falha ao criar novo stop; antigo MANTIDO"}
    mt.renew_expiring_sl(notify=msgs.append)
    mt.renew_expiring_sl(notify=msgs.append)
    p = _read(path)[0]
    assert p["sl_order_id"] == "SL1" and "sl_renewed_count" not in p, p
    assert len(msgs) == 1 and "NAO foi renovado" in msgs[0], msgs
    os.remove(path)


def test_depois_do_tp1_usa_o_restante():
    path = _write([_pos(base_qty="0.045", tp1_done=True, tp_order_id="", tp_price=0.0,
                        sl_price=100.5, sl_set_at=_ago(26))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    mt.renew_expiring_sl()
    assert sent[0]["base_qty"] == "0.045" and sent[0]["new_sl_price"] == 100.5, sent
    os.remove(path)


def test_kill_switch_desligado_nao_renova():
    path = _write([_pos(sl_set_at=_ago(29))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    mt.SL_RENEW_ENABLED = False
    try:
        assert mt.renew_expiring_sl() == [] and not sent
    finally:
        mt.SL_RENEW_ENABLED = True
    os.remove(path)


def test_ignora_posicao_fechada_ou_sem_sl():
    path = _write([_pos(status="closed_sl", sl_set_at=_ago(40)),
                   _pos(signal_id="s2", sl_order_id="", sl_set_at=_ago(40))])
    sent = []
    mt._sign_and_send = _relay_ok(sent)
    mt.renew_expiring_sl()
    assert not sent, sent
    os.remove(path)


def test_register_position_grava_sl_set_at():
    path = _write([])
    mt.register_position("s9", "BTC/USDT", "0.0001", 80000.0, sl_price=76000.0,
                         sl_order_id="SLX")
    p = _read(path)[0]
    assert mt._age_days(p["sl_set_at"]) < 0.01, p
    os.remove(path)


def test_oco_alerta_sl_e_tp1_mortos_uma_vez():
    path = _write([_pos(sl_set_at=_ago(31))])
    msgs = []
    mt._sign_and_send = lambda payload, timeout=12: {
        "status": "oco_synced",
        "pairs": [{"signal_id": "s1", "closed_by": None, "cancel": None,
                   "tp": {"id": "TP1", "status": "expired"},
                   "sl": {"id": "SL1", "status": "expired"}}]}
    oco_guard.sync(notify=msgs.append)
    oco_guard.sync(notify=msgs.append)
    p = _read(path)[0]
    assert p["status"] == "open", p                      # nao fecha a posicao
    assert len(msgs) == 2, msgs                          # 1 do SL + 1 do TP1, sem repetir
    assert "SEM STOP" in msgs[0] and "TP1" in msgs[1], msgs
    os.remove(path)


def test_oco_sem_alerta_com_pernas_abertas():
    path = _write([_pos(sl_set_at=_ago(1))])
    msgs = []
    mt._sign_and_send = lambda payload, timeout=12: {
        "status": "oco_synced",
        "pairs": [{"signal_id": "s1", "closed_by": None, "cancel": None,
                   "tp": {"id": "TP1", "status": "open"},
                   "sl": {"id": "SL1", "status": "open"}}]}
    oco_guard.sync(notify=msgs.append)
    assert not msgs, msgs
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
