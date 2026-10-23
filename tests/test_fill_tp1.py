"""
test_fill_tp1.py - fill real da saida e renovacao do TP1 (D-050, 2026-10-23).

Sem rede: o relay e simulado. Os numeros do fill sao os da venda real do SOL de 2026-10-08
(stop a 108,39, executado a 108,40), lidos da Gate em 2026-10-23.

COMO RODAR
----------
    python tests/test_fill_tp1.py       # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot import oco_guard                              # noqa: E402
from bot import mare_alta_trailing as mt               # noqa: E402

oco_guard.EXIT_RECORD_ENABLED = True
oco_guard.EXIT_FEE_RATE = 0.001
oco_guard.SL_EXPIRED_ALERT_ENABLED = False

FILL_SOL = {"avg_deal_price": "108.4", "filled_amount": "0.089", "filled_total": "9.6476",
            "fee": "0.0096476", "fee_currency": "USDT", "finish_as": "filled"}


def _perto(a, b, tol=1e-6):
    return abs(a - b) <= tol


def _ago(dias):
    return (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()


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


def _sol(**kw):
    p = {"signal_id": "s1", "symbol": "SOL/USDT", "base_qty": "0.089", "entry_price": 110.71,
         "sl_price": 108.39, "sl_order_id": "SL1", "tp_price": 136.82, "tp_order_id": "TP1", "status": "open"}
    p.update(kw)
    return p


# ------------------------------- fill real -------------------------------
def test_fill_liquido_usa_avg_deal_price_e_desconta_taxa():
    preco, qtd, liq = oco_guard.fill_liquido(FILL_SOL)
    assert float(preco) == 108.4 and float(qtd) == 0.089, (preco, qtd)
    assert _perto(float(liq), 9.6476 - 0.0096476), liq
    assert oco_guard.fill_liquido({"avg_deal_price": "0", "filled_amount": "1", "filled_total": "1"}) is None
    assert oco_guard.fill_liquido(None) is None
    sem_usdt = dict(FILL_SOL, fee_currency="GT")
    assert _perto(float(oco_guard.fill_liquido(sem_usdt)[2]), 9.6476)       # taxa em pontos nao entra


def test_pnl_real_sol_08_10():
    r = oco_guard.exit_pnl_real(_sol(), FILL_SOL, None, 0.001)
    custo = 110.71 * 0.089 * 1.001
    assert _perto(r["pnl_usdt_est"], (9.6476 - 0.0096476) - custo), r
    assert r["exit_price"] == 108.4 and r["exit_qty"] == "0.089", r


def test_pnl_real_soma_tp1_real():
    p = _sol(base_qty="0.045", tp_partial=True, tp1_qty="0.045", tp1_done=True, tp1_price=121.78,
             tp_price=0.0, sl_price=110.71)
    tp1 = {"avg_deal_price": "121.9", "filled_amount": "0.045", "filled_total": "5.4855",
           "fee": "0.0054855", "fee_currency": "USDT"}
    saida = {"avg_deal_price": "110.6", "filled_amount": "0.045", "filled_total": "4.977",
             "fee": "0.004977", "fee_currency": "USDT"}
    r = oco_guard.exit_pnl_real(p, saida, tp1, 0.001)
    esperado = (5.4855 - 0.0054855) + (4.977 - 0.004977) - 110.71 * 0.090 * 1.001
    assert _perto(r["pnl_usdt_est"], esperado), r


def _sync(path, item):
    mt._sign_and_send = lambda payload, timeout=12: {"status": "oco_synced", "pairs": [item]}
    oco_guard.sync()
    return _read(path)[0]


def test_oco_grava_fill_real_quando_vem():
    path = _write([_sol()])
    p = _sync(path, {"signal_id": "s1", "closed_by": "sl", "cancel": None,
                     "tp": {"id": "TP1", "status": "open"},
                     "sl": {"id": "SL1", "status": "finish", "fired_order_id": 1145970229071, "fill": FILL_SOL}})
    assert p["status"] == "closed_sl" and p["exit_basis"] == "fill_real" and p["exit_price"] == 108.4, p
    os.remove(path)


def test_oco_cai_na_estimativa_sem_fill():
    path = _write([_sol()])
    p = _sync(path, {"signal_id": "s1", "closed_by": "sl", "cancel": None,
                     "tp": {"id": "TP1", "status": "open"},
                     "sl": {"id": "SL1", "status": "finish", "fill_err": {"http": 404}}})
    assert p["exit_basis"] == "gatilho_est" and p["exit_price"] == 108.39, p
    os.remove(path)


def test_breakeven_guarda_fill_do_tp1():
    path = _write([_sol(base_qty="0.09", tp_partial=True, tp1_qty="0.045", tp1_done=False,
                        tp_price=121.78, sl_price=99.0)])
    mt._sign_and_send = lambda payload, timeout=12: (
        {"status": "oco_synced", "pairs": [{"signal_id": "s1", "closed_by": None, "cancel": None, "tp1_hit": True,
                                            "tp": {"id": "TP1", "status": "finish", "fill": {"avg_deal_price": "121.9"}},
                                            "sl": {"id": "SL1", "status": "open"}}]}
        if payload.get("action") == "oco_sync" else
        {"status": "trailing_updated", "new_sl": {"id": "SL2", "price": "110.71"}})
    oco_guard.sync()
    p = _read(path)[0]
    assert p["tp1_done"] and p["tp1_fill"]["avg_deal_price"] == "121.9", p
    os.remove(path)


# ------------------------------- renovacao do TP1 -------------------------------
def _tp1(**kw):
    p = _sol(base_qty="0.09", tp_partial=True, tp1_qty="0.045", tp1_done=False, tp_price=121.78,
             tp_set_at=_ago(26))
    p.update(kw)
    return p


def _relay(resp, enviados):
    def f(payload, timeout=12):
        enviados.append(payload)
        return resp
    return f


def test_tp1_desligado_nao_faz_nada():
    path = _write([_tp1()])
    env = []
    mt._sign_and_send = _relay({"status": "tp_renewed"}, env)
    mt.TP_RENEW_ENABLED = False
    assert mt.renew_expiring_tp1() == [] and env == []
    os.remove(path)


def test_tp1_novo_nao_renova():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1(tp_set_at=_ago(10))])
    env = []
    mt._sign_and_send = _relay({"status": "tp_renewed"}, env)
    assert mt.renew_expiring_tp1() == [] and env == []
    os.remove(path)


def test_tp1_renova_mesmo_preco_e_qty():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1()])
    env = []
    mt._sign_and_send = _relay({"status": "tp_renewed", "new_tp": {"id": "TP2", "price": "121.78", "qty": "0.045"}}, env)
    r = mt.renew_expiring_tp1()
    assert env[0]["action"] == "renew_tp" and env[0]["tp_price"] == 121.78 and env[0]["tp_qty"] == "0.045", env
    assert env[0]["old_tp_order_id"] == "TP1" and r[0]["action"] == "tp_renewed", (env, r)
    p = _read(path)[0]
    assert p["tp_order_id"] == "TP2" and p["tp_renewed_count"] == 1 and mt._age_days(p["tp_set_at"]) < 0.01, p
    os.remove(path)


def test_tp1_que_ja_nao_esta_aberto_nao_muda_nada():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1()])
    mt._sign_and_send = _relay({"status": "not_open", "old_status": "finish"}, [])
    r = mt.renew_expiring_tp1()
    assert r[0]["action"] == "tp_not_open" and _read(path)[0]["tp_order_id"] == "TP1"
    os.remove(path)


def test_tp1_apagado_e_nao_criado_fica_pendente_e_recria():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1()])
    msgs = []
    mt._sign_and_send = _relay({"status": "error", "reason": "TP antigo apagado e novo NAO criado", "old_deleted": True}, [])
    mt.renew_expiring_tp1(notify=msgs.append)
    p = _read(path)[0]
    assert p["tp_order_id"] == "" and p["tp_renew_pending"] is True and len(msgs) == 1, (p, msgs)
    env = []
    mt._sign_and_send = _relay({"status": "tp_renewed", "new_tp": {"id": "TP3"}}, env)
    mt.renew_expiring_tp1(notify=msgs.append)
    assert env[0]["old_tp_order_id"] == "", env                # nao tenta apagar de novo
    p = _read(path)[0]
    assert p["tp_order_id"] == "TP3" and "tp_renew_pending" not in p, p
    os.remove(path)


def test_tp1_falha_sem_apagar_mantem_o_antigo_e_avisa_uma_vez():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1()])
    msgs = []
    mt._sign_and_send = _relay({"status": "error", "reason": "nao apagou o TP antigo; nada mudou"}, [])
    mt.renew_expiring_tp1(notify=msgs.append)
    mt.renew_expiring_tp1(notify=msgs.append)
    p = _read(path)[0]
    assert p["tp_order_id"] == "TP1" and not p.get("tp_renew_pending") and len(msgs) == 1, (p, msgs)
    os.remove(path)


def test_tp1_ignora_quem_ja_fez_tp1_ou_nao_tem_tp_parcial():
    mt.TP_RENEW_ENABLED = True
    path = _write([_tp1(tp1_done=True), _tp1(signal_id="s2", tp_partial=False), _tp1(signal_id="s3", status="closed_sl")])
    env = []
    mt._sign_and_send = _relay({"status": "tp_renewed"}, env)
    assert mt.renew_expiring_tp1() == [] and env == []
    os.remove(path)


def test_register_position_grava_tp_set_at():
    path = _write([])
    mt.register_position("s9", "BTC/USDT", "0.0001", 80000.0, sl_price=76000.0, sl_order_id="SLX",
                         tp_price=88000.0, tp_order_id="TPX", tp_qty="0.00005")
    assert mt._age_days(_read(path)[0]["tp_set_at"]) < 0.01
    os.remove(path)


# ------------------------------- relay (FIX 12) -------------------------------
def test_relay_renew_tp_confere_apaga_e_so_depois_cria():
    src = open(os.path.join(_ROOT, "server", "execute.php"), encoding="ascii").read()
    i = src.index("if ($action === 'renew_tp') {")
    bloco = src[i:src.index("if ($action === 'oco_sync') {")]
    i_open = bloco.index("if ($st !== 'open')")
    i_del = bloco.index("gate_delete(")
    i_post = bloco.index("gate_post(")
    assert i_open < i_del < i_post, "renew_tp precisa: conferir 'open' -> apagar -> criar"
    assert "'old_deleted'=>" in bloco
    assert re.search(r"^\$TP_RENEW_ENABLED\s*=\s*true;", src, re.M) and re.search(r"^\$FILL_LOOKUP\s*=\s*true;", src, re.M)
    assert "isset($g['avg_deal_price'])" in src and "$fetch_fill($fetch_st(" in src


def test_flag_python_desligada_ate_o_deploy():
    import importlib
    from bot import config
    importlib.reload(config)
    assert config.TP_RENEW_ENABLED is False, "so ligar depois do deploy do FIX 12 (CLAUDE.md)"


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
