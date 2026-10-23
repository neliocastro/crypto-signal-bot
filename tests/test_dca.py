"""
test_dca.py - DCA semanal sem TP/SL (D-049, 2026-10-23).

Sem rede: o relay e as travas sao simulados e todos os arquivos de estado vao para uma pasta
temporaria. Prova: uma compra por ativo por semana, sem compra dobrada (nem se o envio
quebrar), teto mensal, travas respeitadas, e nenhum efeito no positions.jsonl (a Tendencia
Diaria no BTC segue com a trava de concentracao livre).

COMO RODAR
----------
    python tests/test_dca.py            # standalone, sai com codigo 0 se ok
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

from bot import config                                  # noqa: E402
from bot import dca                                     # noqa: E402
from bot import executor as ex                          # noqa: E402

SEG_13H = datetime(2026, 10, 26, 13, 0, tzinfo=timezone.utc)     # segunda-feira, semana 2026W44


def _ambiente():
    """Aponta todo o estado para uma pasta temporaria e liga o DCA."""
    d = tempfile.mkdtemp()
    config.DCA_ENABLED = True
    config.DCA_ASSETS = {"BTC/USDT": 10.0, "PAXG/USDT": 10.0}
    config.DCA_WEEKDAY, config.DCA_HOUR_UTC, config.DCA_MONTHLY_CAP_USDT = 0, 13, 50.0
    config.DCA_FILE = os.path.join(d, "dca.jsonl")
    ex.PAPER_TRADES_FILE = os.path.join(d, "paper_trades.jsonl")
    ex.ORDERS_CSV_FILE = os.path.join(d, "orders_executed.csv")
    ex.EXECUTION_STATE_FILE = os.path.join(d, "execution_guard.json")
    ex.POSITIONS_FILE = os.path.join(d, "positions.jsonl")
    ex.EXECUTION_ENABLED = True
    return d


def _relay(enviados, status="filled"):
    def f(ordem):
        enviados.append(ordem)
        return {"status": status, "fill_price": 100.0, "filled_total": 10.0, "order_id": "G1"}
    return f


def _ok(_ordem):
    return True, "ok"


def _preco(_s):
    return 100.0


def _regs():
    return dca.ler_registro(config.DCA_FILE)


def test_semana_e_horario():
    assert dca.semana_iso(SEG_13H) == "2026W44"
    assert dca.hora_de_comprar(SEG_13H, 0, 13)
    assert not dca.hora_de_comprar(SEG_13H.replace(hour=12, minute=59), 0, 13)
    assert dca.hora_de_comprar(SEG_13H.replace(day=27, hour=1), 0, 13)      # terca: compra se segunda falhou
    assert dca.hora_de_comprar(SEG_13H.replace(day=25), 0, 13)              # domingo = fim da semana ISO: ainda compra
    assert not dca.hora_de_comprar(SEG_13H.replace(hour=0), 0, 13)          # segunda antes das 13h: ainda nao


def test_ordem_sem_tp_sl_e_id_da_semana():
    o = dca.montar_ordem("BTC/USDT", 10.0, "2026W44", 100.0)
    assert o["strategy"] == "DCA" and o["sl_price"] is None and o["tp_price"] is None, o
    assert o["signal_id"] == "dca-BTC_USDT-2026W44" and o["notional_usdt"] == 10.0, o


def test_desligado_nao_faz_nada():
    _ambiente()
    config.DCA_ENABLED = False
    env = []
    assert dca.run_dca(SEG_13H, enviar=_relay(env), guardas=_ok, preco=_preco) == [] and env == []


def test_antes_do_horario_nao_compra():
    _ambiente()
    env = []
    assert dca.run_dca(SEG_13H.replace(hour=12), enviar=_relay(env), guardas=_ok, preco=_preco) == []
    assert env == []


def test_compra_uma_vez_por_semana_e_avisa():
    _ambiente()
    env, msgs = [], []
    res = dca.run_dca(SEG_13H, notify=msgs.append, enviar=_relay(env), guardas=_ok, preco=_preco)
    assert [r["status"] for r in res] == ["filled", "filled"], res
    assert [o["symbol"] for o in env] == ["BTC/USDT", "PAXG/USDT"]
    assert len(msgs) == 2 and all("DCA semanal" in m and "nunca vende" in m for m in msgs), msgs
    # segundo scan da mesma semana: nada novo
    assert dca.run_dca(SEG_13H.replace(hour=18), enviar=_relay(env), guardas=_ok, preco=_preco) == []
    assert len(env) == 2
    # semana seguinte: compra de novo
    prox = SEG_13H + timedelta(days=7)
    assert len(dca.run_dca(prox, enviar=_relay(env), guardas=_ok, preco=_preco)) == 2 and len(env) == 4


def test_envio_quebrado_nao_gera_compra_dobrada():
    _ambiente()
    chamadas = []

    def quebra(ordem):
        chamadas.append(ordem)
        raise RuntimeError("caiu depois de enviar")

    dca.run_dca(SEG_13H, enviar=quebra, guardas=_ok, preco=_preco)
    assert len(chamadas) == 2
    assert all(r["status"] == "tentativa" for r in _regs()), _regs()
    env = []
    assert dca.run_dca(SEG_13H.replace(hour=20), enviar=_relay(env), guardas=_ok, preco=_preco) == []
    assert env == [], "nao pode reenviar na mesma semana"


def test_teto_mensal():
    _ambiente()
    # 5 compras de BTC ja feitas em outubro (semanas antigas: so o teto mensal pode bloquear)
    with open(config.DCA_FILE, "w", encoding="utf-8") as fh:
        for k in range(5):
            fh.write(json.dumps({"symbol": "BTC/USDT", "status": "filled", "notional_usdt": 10.0,
                                 "semana": "2026W%02d" % (35 + k),
                                 "ts": "2026-10-0%dT13:00:00+00:00" % (k + 1),
                                 "filled_total": 10.0, "fill_price": 100.0}) + "\n")
    env, msgs = [], []
    res = {r["symbol"]: r["status"] for r in dca.run_dca(SEG_13H.replace(month=10, day=26), notify=msgs.append,
                                                           enviar=_relay(env), guardas=_ok, preco=_preco)}
    assert res == {"BTC/USDT": "teto_mensal", "PAXG/USDT": "filled"}, res
    assert [o["symbol"] for o in env] == ["PAXG/USDT"], env
    assert any("teto mensal" in m for m in msgs), msgs


def test_trava_bloqueia_e_nao_tenta_de_novo():
    _ambiente()
    env, msgs = [], []
    res = dca.run_dca(SEG_13H, notify=msgs.append, enviar=_relay(env),
                      guardas=lambda o: (False, "stop diario atingido"), preco=_preco)
    assert {r["status"] for r in res} == {"blocked_by_guard"} and env == [], res
    assert all("NAO comprou" in m for m in msgs), msgs
    assert dca.run_dca(SEG_13H.replace(hour=22), enviar=_relay(env), guardas=_ok, preco=_preco) == []


def test_nao_mexe_no_positions_nem_na_trava_da_tendencia():
    _ambiente()
    dca.run_dca(SEG_13H, enviar=_relay([]), guardas=_ok, preco=_preco)
    assert not os.path.exists(ex.POSITIONS_FILE), "DCA nao pode escrever no positions.jsonl"
    assert ex._open_count_for_symbol("BTC/USDT") == 0       # Tendencia Diaria segue livre para comprar BTC


def test_acumulado():
    regs = [{"symbol": "BTC/USDT", "status": "filled", "filled_total": 10.0, "fill_price": 100.0},
            {"symbol": "BTC/USDT", "status": "filled", "filled_total": 10.0, "fill_price": 50.0},
            {"symbol": "BTC/USDT", "status": "blocked_by_guard", "filled_total": 10.0, "fill_price": 1.0},
            {"symbol": "PAXG/USDT", "status": "filled", "filled_total": 10.0, "fill_price": 4000.0}]
    a = dca.acumulado(regs, "BTC/USDT")
    assert a["compras"] == 2 and abs(a["investido"] - 20.0) < 1e-9
    assert abs(a["qtd"] - 0.3 * 0.999) < 1e-12 and abs(a["custo_medio"] - 20.0 / (0.3 * 0.999)) < 1e-6, a


def test_relay_aceita_sem_protecao_so_para_dca_dos_ativos_do_config():
    src = open(os.path.join(_ROOT, "server", "execute.php"), encoding="utf-8").read()
    m = re.search(r"^\$DCA_WHITELIST\s*=\s*\[([^\]]*)\]", src, re.M)
    assert m, "faltou $DCA_WHITELIST no execute.php"
    whitelist = set(re.findall(r"'([A-Z0-9]+/USDT)'", m.group(1)))
    import importlib
    importlib.reload(config)                                # valores reais do config.py
    assert set(config.DCA_ASSETS) <= whitelist, (config.DCA_ASSETS, whitelist)
    assert "(($order['strategy'] ?? '') === 'DCA')" in src
    assert "&& !$is_dca" in src
    assert all(v <= config.EXECUTION_MAX_NOTIONAL_USDT for v in config.DCA_ASSETS.values())
    assert config.DCA_ENABLED is False, "so ligar depois do deploy do FIX 11 (CLAUDE.md)"


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
