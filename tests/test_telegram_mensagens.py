"""
test_telegram_mensagens.py - menos mensagens + comandos no scan (D-046, 2026-10-21).

Sem rede e sem Telegram: confere flags, a ordem no main.py, o commander (ajuda, /status,
comandos de watchlist inertes, chat autorizado) e o resumo diario com estado temporario.

COMO RODAR
----------
    python tests/test_telegram_mensagens.py   # standalone, sai com codigo 0 se ok
    python -m pytest tests/ -q
"""
import importlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

os.environ.pop("ALLOWED_CHAT_ID", None)
os.environ["TELEGRAM_CHAT_ID"] = "4242"

# O commander importa `requests`, que o workflow `checks` nao instala. Os testes nao usam rede:
# um modulo falso basta para a importacao (qualquer chamada de rede quebraria o teste).
if "requests" not in sys.modules:
    import types
    sys.modules["requests"] = types.ModuleType("requests")

from bot import config                                  # noqa: E402
from bot import commander                               # noqa: E402
from bot import status_view as sv                       # noqa: E402
from bot.reports import daily_summary as ds             # noqa: E402

_AGORA = datetime.now(timezone.utc)


def _jsonl(path, recs):
    with open(path, "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def test_flags_do_d046():
    assert config.SCAN_SUMMARY_ENABLED is False
    assert config.TELEGRAM_COMMANDS_IN_SCAN is True
    assert config.PAPER_EVAL_ENABLED is False


def test_main_le_comandos_antes_da_pausa():
    src = open(os.path.join(_ROOT, "bot", "main.py"), encoding="utf-8").read()
    i_cmd = src.index("_commander.main()")
    i_gate = src.index("rc.should_run_now(cfg)")
    assert i_cmd < i_gate, "comandos precisam vir antes do gating (pausa/intervalo)"
    assert "if not _sum_on:" in src


def test_chat_autorizado_aceita_telegram_chat_id():
    assert commander.ALLOWED_CHAT_ID == "4242", commander.ALLOWED_CHAT_ID


def test_ajuda_sem_comandos_inertes():
    for c in ("/add", "/remover", "/rm "):
        assert c not in commander.HELP_TEXT, c
    assert "~5 min" in commander.HELP_TEXT


def test_comandos_de_watchlist_sao_inertes():
    cfg = {"watchlist": ["BTC/USDT"]}
    for t in ("/add XRP", "/remover BTC", "/rm 1"):
        resp, mudou = commander.handle_command(t, cfg)
        assert mudou is False and "D-004" in resp, (t, resp)
    assert cfg["watchlist"] == ["BTC/USDT"], cfg


def test_status_mostra_estrategias():
    resp, mudou = commander.handle_command("/status", {"watchlist": [], "scan_interval_min": 5})
    assert mudou is False
    assert "Tendência Diária" in resp and "BTC, SOL, TRX, BNB" in resp, resp
    assert "Rompimento 1h — DESLIGADA (D-013)" in resp, resp
    assert "Posições abertas do bot" in resp, resp


def test_linhas_estrategias_refletem_flags():
    ls = sv.linhas_estrategias()
    assert any(l.startswith("🟢 Tendência Diária — REAL") for l in ls), ls
    assert any("DCA semanal" in l and "BTC US$ 10" in l and "PAXG US$ 10" in l for l in ls), ls
    assert any("PAXG" in l and "substituído pelo DCA" in l for l in ls), ls
    assert any("US$ 10" in l for l in ls), ls


def test_posicoes_abertas_e_fechadas():
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    _jsonl(p, [
        {"symbol": "SOL/USDT", "status": "open", "entry_price": 100, "sl_price": 90, "tp_partial": True},
        {"symbol": "BTC/USDT", "status": "closed_sl", "closed_at": _AGORA.isoformat(), "pnl_usdt_est": -0.5},
        {"symbol": "BNB/USDT", "status": "closed_tp", "closed_at": (_AGORA - timedelta(days=3)).isoformat(),
         "pnl_usdt_est": 1.0},
    ])
    ab = sv.posicoes_abertas(p)
    assert len(ab) == 1 and "SOL/USDT" in ab[0] and "aguardando TP1" in ab[0], ab
    fe = sv.fechadas_desde((_AGORA - timedelta(hours=24)).isoformat(), p)
    assert fe == [("BTC/USDT", "closed_sl", -0.5)], fe
    assert sv.posicoes_abertas("/nao/existe.jsonl") == []
    os.remove(p)


def test_resumo_diario_sem_papel_e_com_trava_real():
    d = Path(tempfile.mkdtemp())
    _jsonl(d / "positions.jsonl", [
        {"symbol": "SOL/USDT", "status": "open", "entry_price": 100, "sl_price": 90},
        {"symbol": "BTC/USDT", "status": "closed_sl", "closed_at": (_AGORA - timedelta(hours=2)).isoformat(),
         "pnl_usdt_est": -0.4},
    ])
    (d / "runtime_config.json").write_text(json.dumps({"scan_interval_min": 5}), encoding="utf-8")
    antigo = ds._STATE
    ds._STATE = d
    try:
        txt = ds.build_summary(_AGORA)
    finally:
        ds._STATE = antigo
    assert "paper" not in txt.lower(), txt
    assert "-$10" not in txt, txt
    assert "Estrategias" in txt and "Tendência Diária" in txt, txt
    assert "Posicoes abertas do bot:* 1" in txt, txt
    assert "Fechadas em 24h:* 1" in txt and "$-0.40" in txt, txt
    assert "US$ 20" in txt, txt


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
