"""
test_saida_tp1.py - saida validada do Mare Alta (2026-10-15).

Cobre o ciclo TP1 +10% (50%) -> SL no breakeven c/ o restante -> trailing so
depois do TP1, sem rede: o relay PHP e simulado (_sign_and_send falso) com as
mesmas respostas do execute.php FIX 10.

COMO RODAR
----------
    python tests/test_saida_tp1.py      # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot import config, executor, oco_guard            # noqa: E402
from bot import mare_alta_trailing as mt               # noqa: E402


def _sig(strategy="MARE_ALTA_D1", symbol="SOL/USDT"):
    return {"symbol": symbol, "side": "BUY", "strategy": strategy,
            "price": 100.0, "atr": 4.0, "timestamp": 1789776000000}


def _with_flag(value, fn):
    old = config.MARE_ALTA_PARTIAL_TP_ENABLED
    config.MARE_ALTA_PARTIAL_TP_ENABLED = value
    try:
        return fn()
    finally:
        config.MARE_ALTA_PARTIAL_TP_ENABLED = old


def _tmp_positions():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    mt.POSITIONS_FILE = path
    return path


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def test_build_order_flag_ligada_mare_alta():
    o = _with_flag(True, lambda: executor.build_order(_sig(), 1000.0))
    assert o["tp_frac"] == 0.5, o
    assert abs(o["tp_price"] - 110.0) < 1e-9, o          # TP1 +10% do ref
    assert abs(o["sl_price"] - 90.0) < 1e-9, o           # SL inalterado: 100 - 2.5*4


def test_build_order_flag_desligada_ou_outro_trilho():
    off = _with_flag(False, lambda: executor.build_order(_sig(), 1000.0))
    assert "tp_frac" not in off and abs(off["tp_price"] - 120.0) < 1e-9, off   # 2.0R
    hype = _with_flag(True, lambda: executor.build_order(
        _sig("Breakout / Tendência", "HYPE/USDT"), 1000.0))
    assert "tp_frac" not in hype, hype


def test_ciclo_tp1_breakeven_trailing_fechamento():
    path = _tmp_positions()
    mt.register_position("s1", "SOL/USDT", "0.09", 100.5, sl_price=90.0, sl_order_id="SL1",
                         tp_price=110.0, tp_order_id="TP1", tp_qty="0.045")
    p = _read(path)[0]
    assert p["tp_partial"] and p["tp1_qty"] == "0.045" and not p["tp1_done"], p

    # 1) antes do TP1 o trailing NAO mexe no stop (stop inicial fixo)
    sent = []
    mt._sign_and_send = lambda payload, timeout=12: sent.append(payload) or None
    candles = [{"high": 130.0, "low": 120.0, "close": 128.0}] * 20
    r = mt.update_trailing(lambda s: candles)
    assert r[0]["reason"] == "aguardando TP1 (stop fixo)" and not sent, (r, sent)

    # 2) TP1 dispara: PHP devolve tp1_hit; Python troca o SL p/ breakeven c/ o restante
    def relay(payload, timeout=12):
        sent.append(payload)
        if payload["action"] == "oco_sync":
            assert payload["pairs"][0]["tp_partial"] is True, payload
            return {"status": "oco_synced", "pairs": [{
                "signal_id": "s1", "tp1_hit": True, "closed_by": None,
                "tp": {"status": "finish"}, "sl": {"status": "open"}}]}
        if payload["action"] == "update_trailing":
            return {"status": "trailing_updated",
                    "new_sl": {"id": "SL2", "price": "100.5"}}
    mt._sign_and_send = relay
    msgs = []
    oco_guard.sync(notify=msgs.append)
    be = [x for x in sent if x["action"] == "update_trailing"][0]
    assert be["new_sl_price"] == 100.5 and be["base_qty"] == "0.045", be
    assert be["old_sl_order_id"] == "SL1", be
    p = _read(path)[0]
    assert p["status"] == "open" and p["tp1_done"] and p["base_qty"] == "0.045", p
    assert p["sl_order_id"] == "SL2" and p["tp_order_id"] == "" and p["sl_price"] == 100.5, p
    assert any("TP1" in m for m in msgs), msgs

    # 3a) depois do TP1, candidato abaixo do breakeven (128 - 3*10 = 98): catraca segura
    sent.clear()
    mt._sign_and_send = lambda payload, timeout=12: (sent.append(payload) or
        {"status": "trailing_updated", "new_sl": {"id": "SL3", "price": payload["new_sl_price"]}})
    mt.update_trailing(lambda s: candles)
    assert not sent, sent
    # 3b) preco subiu (150 - 3*10 = 120 > 100.5): trailing anda c/ a qty restante
    mt.update_trailing(lambda s: [{"high": 155.0, "low": 145.0, "close": 150.0}] * 20)
    assert sent and sent[0]["base_qty"] == "0.045" and sent[0]["new_sl_price"] == 120.0, sent

    # 4) restante sai no stop: par sem TP e sem tp_partial -> closed_sl
    def relay_sl(payload, timeout=12):
        pr = payload["pairs"][0]
        assert pr["tp_partial"] is False and pr["tp_order_id"] == "", pr
        return {"status": "oco_synced", "pairs": [{"signal_id": "s1", "closed_by": "sl"}]}
    mt._sign_and_send = relay_sl
    oco_guard.sync()
    p = _read(path)[0]
    assert p["status"] == "closed_sl" and p["tp1_done"], p
    os.remove(path)


def test_breakeven_falha_mantem_sl_e_avisa_uma_vez():
    path = _tmp_positions()
    mt.register_position("s2", "BTC/USDT", "0.000115", 86000.0, sl_price=80000.0,
                         sl_order_id="SLA", tp_price=94600.0, tp_order_id="TPA", tp_qty="0.000057")

    def relay(payload, timeout=12):
        if payload["action"] == "oco_sync":
            return {"status": "oco_synced", "pairs": [{"signal_id": "s2", "tp1_hit": True,
                                                       "closed_by": None}]}
        return {"status": "error", "reason": "falha ao criar novo stop; antigo MANTIDO"}
    mt._sign_and_send = relay
    msgs = []
    oco_guard.sync(notify=msgs.append)
    oco_guard.sync(notify=msgs.append)
    p = _read(path)[0]
    assert p["status"] == "open" and not p["tp1_done"] and p["sl_order_id"] == "SLA", p
    assert len([m for m in msgs if "breakeven" in m]) == 1, msgs
    os.remove(path)


def test_tp1_e_sl_no_mesmo_intervalo_fecha_posicao():
    path = _tmp_positions()
    mt.register_position("s3", "BNB/USDT", "0.012", 780.0, sl_price=720.0, sl_order_id="SLB",
                         tp_price=858.0, tp_order_id="TPB", tp_qty="0.006")
    mt._sign_and_send = lambda payload, timeout=12: {"status": "oco_synced", "pairs": [
        {"signal_id": "s3", "tp1_hit": True, "closed_by": "sl"}]}
    oco_guard.sync()
    p = _read(path)[0]
    assert p["status"] == "closed_sl" and p.get("tp1_hit_at"), p
    os.remove(path)


def test_posicao_sem_tp_parcial_segue_modo_antigo():
    path = _tmp_positions()
    mt.register_position("s4", "TRX/USDT", "29.4", 0.34, sl_price=0.32, sl_order_id="SLC",
                         tp_price=0.37, tp_order_id="TPC")
    p = _read(path)[0]
    assert "tp_partial" not in p, p
    sent = []
    mt._sign_and_send = lambda payload, timeout=12: sent.append(payload) or None
    mt.update_trailing(lambda s: [{"high": 0.40, "low": 0.38, "close": 0.39}] * 20)
    assert sent and sent[0]["base_qty"] == "29.4", sent      # trailing desde o inicio
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
