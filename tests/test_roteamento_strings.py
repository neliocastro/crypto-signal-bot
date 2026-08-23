"""
CANARIO DE ROTEAMENTO - protege a fragilidade #1 do sistema.

PROBLEMA QUE ESTE TESTE RESOLVE
-------------------------------
O filtro de roteamento do bot/main.py (secao "ROTEAMENTO POR TRILHO") casa
cada sinal por TUPLA (symbol, strategy) usando a STRING EXATA do campo
`strategy` produzido em bot/strategies.py:

    INTRADAY_EXEC_ALLOWLIST = {
        ("HYPE/USDT", "Breakout / Tend\u00eancia"),
        ("PAXG/USDT", "Ac\u00famulo (RSI sobrevenda)"),
    }

Se alguem editar o texto da estrategia em strategies.py (ate corrigir um
acento, um espaco ou a barra), a tupla deixa de casar e o ativo PARA DE
OPERAR SILENCIOSAMENTE: sem excecao, sem log de erro, sem alerta no Telegram.
O scan continua verde. So se percebe quando alguem nota que ha semanas nao
acontece nada.

Este teste falha ALTO e CEDO nesse cenario.

COMO RODAR
----------
    python -m pytest tests/ -q
    python tests/test_roteamento_strings.py     # tambem roda standalone

Se este teste falhar, NAO "conserte" o teste: alinhe as strings nos dois
arquivos no MESMO commit e atualize docs/mapa_estrategias.md.
"""
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAIN = os.path.join(_ROOT, "bot", "main.py")
_STRATEGIES = os.path.join(_ROOT, "bot", "strategies.py")

# Contrato explicito: o que o roteamento PRECISA encontrar em strategies.py.
# Fonte da verdade documentada em docs/mapa_estrategias.md (secao 5).
CONTRATO = {
    "HYPE/USDT": "Breakout / Tend\u00eancia",
    "PAXG/USDT": "Ac\u00famulo (RSI sobrevenda)",
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_allowlist_do_main_bate_com_o_contrato():
    """As tuplas escritas no main.py sao exatamente as do contrato."""
    src = _read(_MAIN)
    bloco = re.search(r"INTRADAY_EXEC_ALLOWLIST\s*=\s*\{(.*?)\}", src, re.S)
    assert bloco, "INTRADAY_EXEC_ALLOWLIST nao encontrada em bot/main.py"
    achadas = set(re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', bloco.group(1)))
    esperadas = set(CONTRATO.items())
    assert achadas == esperadas, (
        "A allowlist do main.py divergiu do contrato.\n"
        f"  no main.py: {sorted(achadas)}\n"
        f"  esperado  : {sorted(esperadas)}\n"
        "Se a mudanca foi intencional, atualize CONTRATO aqui, strategies.py "
        "e docs/mapa_estrategias.md no MESMO commit."
    )


def test_strings_existem_em_strategies():
    """Cada nome de estrategia do contrato existe literalmente em strategies.py.

    Este e o teste que pega o cenario perigoso: alguem renomeia a estrategia
    em strategies.py e esquece do main.py -> o ativo para de operar sem erro.
    """
    src = _read(_STRATEGIES)
    for symbol, nome in CONTRATO.items():
        assert f'"{nome}"' in src, (
            f"A estrategia de {symbol} deveria produzir strategy == {nome!r}, "
            "mas essa string NAO existe em bot/strategies.py.\n"
            "=> O roteamento do main.py vai descartar o sinal em silencio e o "
            "ativo PARA DE OPERAR sem nenhum erro visivel.\n"
            "Alinhe os dois arquivos no mesmo commit."
        )


def test_mare_alta_nao_depende_da_allowlist():
    """O trilho D1 roda FORA do filtro intraday (nao pode ser filtrado).

    Garante que run_mare_alta continua sendo chamado no main.py. Se alguem
    mover essa chamada para dentro do loop filtrado, os 6 ativos do D1
    deixariam de executar.
    """
    src = _read(_MAIN)
    assert "run_mare_alta" in src, "run_mare_alta sumiu do bot/main.py"
    pos_filtro = src.find("INTRADAY_EXEC_ALLOWLIST")
    pos_mare = src.find("run_mare_alta")
    assert pos_mare > pos_filtro, (
        "run_mare_alta() aparece ANTES do filtro de roteamento. O trilho D1 "
        "deve rodar em bloco proprio, depois e fora do filtro intraday."
    )


if __name__ == "__main__":
    ok = True
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {nome}")
            except AssertionError as e:
                ok = False
                print(f"FAIL  {nome}\n      {e}")
    raise SystemExit(0 if ok else 1)
