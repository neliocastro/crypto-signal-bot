"""
test_whitelist_php.py - $SYMBOL_WHITELIST do relay alinhada ao universo do Python (D-036, 2026-10-15).

Canario: a whitelist do server/execute.php deve ser exatamente
WATCHLIST (bot/config.py) + MARE_ALTA_UNIVERSE (bot/mare_alta.py) + PAXG/USDT
(cron de acumulacao do servidor, D-032). Mudou um lado sem o outro -> falha.
Le o PHP como texto; nao executa nada.

COMO RODAR
----------
    python tests/test_whitelist_php.py  # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from bot.config import WATCHLIST                       # noqa: E402
from bot.mare_alta import MARE_ALTA_UNIVERSE           # noqa: E402

_PHP = os.path.join(_ROOT, "server", "execute.php")
_EXTRA_SERVIDOR = {"PAXG/USDT"}                        # D-032: cron PAXG fora do bot


def _php_whitelist():
    with open(_PHP, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^\$SYMBOL_WHITELIST\s*=\s*\[([^\]]*)\]", src, re.M)
    assert m, "linha $SYMBOL_WHITELIST nao encontrada no execute.php"
    return re.findall(r"'([A-Z0-9]+/USDT)'", m.group(1))


def test_whitelist_igual_ao_universo():
    php = _php_whitelist()
    esperado = set(WATCHLIST) | set(MARE_ALTA_UNIVERSE) | _EXTRA_SERVIDOR
    assert set(php) == esperado, ("PHP a mais: %s | PHP a menos: %s"
                                  % (sorted(set(php) - esperado), sorted(esperado - set(php))))


def test_whitelist_sem_duplicatas():
    php = _php_whitelist()
    assert len(php) == len(set(php)), php


def test_fora_do_universo_nao_aceitos():
    php = set(_php_whitelist())
    for s in ("ETH/USDT", "XRP/USDT", "LINK/USDT", "AAVE/USDT"):   # D-010 / R-005
        assert s not in php, s


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
