"""
test_precisao_reserva.py - tabelas de precisao de reserva alinhadas (2026-10-23).

O relay le a precisao de cada par em /spot/currency_pairs; as tabelas $SAFE_* do
server/execute.php so valem se essa consulta falhar. O _SAFE_PRICE_PREC de
bot/mare_alta_trailing.py espelha a de preco para truncar o SL antes de enviar.
Canario: todo par da $SYMBOL_WHITELIST tem entrada nas tres tabelas do PHP e a tabela
de preco do Python e igual a do PHP. Le o PHP como texto; sem rede.

Valores conferidos na Gate em 2026-10-23 (precision / amount_precision / min_base_amount):
BTC 1/6/0.000001, SOL 2/3/0.001, TRX 4/1/0.1, BNB 1/3/0.001, HYPE 2/3/0.001, PAXG 2/3/0.001.

COMO RODAR
----------
    python tests/test_precisao_reserva.py   # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot.mare_alta_trailing import _SAFE_PRICE_PREC     # noqa: E402

_PHP = os.path.join(_ROOT, "server", "execute.php")

# Conferido em /spot/currency_pairs em 2026-10-23 (pares que o relay aceita hoje).
_GATE = {
    "BTC_USDT": (1, 6, 0.000001), "SOL_USDT": (2, 3, 0.001), "TRX_USDT": (4, 1, 0.1),
    "BNB_USDT": (1, 3, 0.001), "HYPE_USDT": (2, 3, 0.001), "PAXG_USDT": (2, 3, 0.001),
}


def _src():
    with open(_PHP, encoding="utf-8") as fh:
        return fh.read()


def _php_tabela(nome, conv):
    m = re.search(r"^\$%s\s*=\s*\[([^\]]*)\]" % re.escape(nome), _src(), re.M)
    assert m, "faltou $%s no execute.php" % nome
    return {k: conv(v) for k, v in re.findall(r"'([A-Z0-9]+_USDT)'\s*=>\s*([0-9.]+)", m.group(1))}


def _whitelist():
    m = re.search(r"^\$SYMBOL_WHITELIST\s*=\s*\[([^\]]*)\]", _src(), re.M)
    assert m, "faltou $SYMBOL_WHITELIST no execute.php"
    return {s.replace("/", "_") for s in re.findall(r"'([A-Z0-9]+/USDT)'", m.group(1))}


def test_toda_a_whitelist_tem_reserva_no_php():
    for nome in ("SAFE_PRICE_PREC", "SAFE_AMOUNT_PREC", "SAFE_MIN_BASE"):
        faltam = _whitelist() - set(_php_tabela(nome, float))
        assert not faltam, "$%s sem: %s" % (nome, sorted(faltam))


def test_python_igual_ao_php():
    php = _php_tabela("SAFE_PRICE_PREC", int)
    assert _SAFE_PRICE_PREC == php, ("diferem: %s" % sorted(
        k for k in set(php) | set(_SAFE_PRICE_PREC) if php.get(k) != _SAFE_PRICE_PREC.get(k)))


def test_valores_conferidos_na_gate():
    preco = _php_tabela("SAFE_PRICE_PREC", int)
    qtd = _php_tabela("SAFE_AMOUNT_PREC", int)
    minimo = _php_tabela("SAFE_MIN_BASE", float)
    for par, (p, a, mb) in _GATE.items():
        assert (preco[par], qtd[par], minimo[par]) == (p, a, mb), (par, preco[par], qtd[par], minimo[par])


def test_gate_cobre_a_whitelist():
    # par novo na whitelist exige conferir a Gate e acrescentar aqui
    assert _whitelist() <= set(_GATE), sorted(_whitelist() - set(_GATE))


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
