"""
executor.py - CEREBRO da execucao (lado Python, roda no GitHub Actions).

Responsabilidade: APENAS montar a "intencao de ordem" a partir de um sinal,
assinar com HMAC-SHA256 e enviar (POST) para o relay PHP no servidor de IP fixo.
NUNCA fala direto com a Gate.io. NUNCA guarda chave da exchange.

FASE 1 (atual) = DRY-RUN: nada e executado de verdade; tudo e registrado em
state/paper_trades.jsonl. O proprio servidor PHP tambem esta em dry-run.

Kill-switches (em bot/config.py):
  EXECUTION_ENABLED  -> liga/desliga a camada inteira
  EXECUTION_DRY_RUN  -> True na Fase 1 (nao envia ordem real)
  EXECUTION_PCT      -> fracao do saldo USDT por ordem (0.10 = 10%)
"""
from __future__ import annotations

import hashlib
import hmac
import csv
import json
import os
import time
import urllib.request
import logging
from datetime import datetime, timezone

log = logging.getLogger("bot.executor")

# --- Config com fallback seguro (se faltar no config.py, assume desligado) ---
try:
    from .config import (
        EXECUTION_ENABLED,
        EXECUTION_DRY_RUN,
        EXECUTION_PCT,
        EXECUTION_RELAY_URL,
        EXECUTION_MAX_NOTIONAL_USDT,
        EXECUTION_MIN_NOTIONAL_USDT,
        EXECUTION_ATR_MULT_SL,
        EXECUTION_TP_RR,
        EXECUTION_TPSL_ENABLED,
        EXECUTION_MAX_OPEN,
        EXECUTION_MAX_TRADES_DAY,
        EXECUTION_DAILY_LOSS_STOP,
        EXECUTION_STATE_FILE,
    )
    try:
        from .config import EXECUTION_MIN_STOP_PCT
    except Exception:
        EXECUTION_MIN_STOP_PCT = 0.8
except Exception:  # degradacao segura: sem config -> camada inerte
    EXECUTION_ENABLED = False
    EXECUTION_DRY_RUN = True
    EXECUTION_PCT = 0.02
    EXECUTION_RELAY_URL = ""
    EXECUTION_MAX_NOTIONAL_USDT = 5.0
    EXECUTION_MIN_NOTIONAL_USDT = 3.0
    EXECUTION_ATR_MULT_SL = 2.0
    EXECUTION_MIN_STOP_PCT = 0.8  # piso de afastamento do stop (% do preco)
    EXECUTION_TP_RR = 2.0
    EXECUTION_TPSL_ENABLED = True
    EXECUTION_MAX_OPEN = 2
    EXECUTION_MAX_TRADES_DAY = 6
    EXECUTION_DAILY_LOSS_STOP = 10.0
    EXECUTION_STATE_FILE = "state/execution_guard.json"

PAPER_TRADES_FILE = "state/paper_trades.jsonl"
ORDERS_CSV_FILE = "state/orders_executed.csv"
# O segredo HMAC vem de variavel de ambiente (GitHub Secret). NUNCA hardcode.
_HMAC_SECRET = os.environ.get("EXECUTION_HMAC_SECRET", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _signal_id(signal: dict) -> str:
    """ID estavel p/ idempotencia: mesmo sinal nunca vira 2 ordens."""
    base = f"{signal.get('symbol')}|{signal.get('strategy')}|{signal.get('timestamp') or signal.get('ts')}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def _ref_price(signal: dict):
    """Preco de referencia: 'entry' (breakout/MACD) ou 'price' (acumulo)."""
    return signal.get("entry") or signal.get("price")



# ===================== PROTECOES DE CAPITAL (go-live minimo) =====================
def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_guard_state() -> dict:
    """Estado diario das travas. Zera sozinho quando vira o dia (UTC)."""
    try:
        with open(EXECUTION_STATE_FILE, "r", encoding="utf-8") as fh:
            st = json.load(fh)
    except Exception:
        st = {}
    if st.get("day") != _today_utc():  # novo dia -> zera contadores
        st = {"day": _today_utc(), "trades_today": 0, "open_positions": 0, "realized_loss_today": 0.0}
    st.setdefault("trades_today", 0)
    st.setdefault("open_positions", 0)
    st.setdefault("realized_loss_today", 0.0)
    return st


def _save_guard_state(st: dict) -> None:
    os.makedirs(os.path.dirname(EXECUTION_STATE_FILE), exist_ok=True)
    with open(EXECUTION_STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(st, fh)


def check_guards(order: dict) -> tuple[bool, str]:
    """Retorna (pode_enviar, motivo). Travas RIGIDAS antes de qualquer envio."""
    st = _load_guard_state()
    # 1) stop de perda diaria (kill-switch)
    if float(st["realized_loss_today"]) >= float(EXECUTION_DAILY_LOSS_STOP):
        return False, f"stop diario atingido (perda {st['realized_loss_today']:.2f} >= {EXECUTION_DAILY_LOSS_STOP})"
    # 2) maximo de ordens por dia
    if int(st["trades_today"]) >= int(EXECUTION_MAX_TRADES_DAY):
        return False, f"limite diario de ordens atingido ({EXECUTION_MAX_TRADES_DAY})"
    # 3) maximo de posicoes abertas
    if int(st["open_positions"]) >= int(EXECUTION_MAX_OPEN):
        return False, f"limite de posicoes abertas atingido ({EXECUTION_MAX_OPEN})"
    # 4) teto por ordem (defesa em profundidade; PHP tambem recusa)
    if float(order.get("notional_usdt", 0)) > float(EXECUTION_MAX_NOTIONAL_USDT):
        return False, f"notional {order.get('notional_usdt')} acima do teto {EXECUTION_MAX_NOTIONAL_USDT}"
    return True, "ok"


def _register_sent_order() -> None:
    """Apos enviar uma ordem real, incrementa contadores diarios."""
    st = _load_guard_state()
    st["trades_today"] = int(st["trades_today"]) + 1
    st["open_positions"] = int(st["open_positions"]) + 1
    _save_guard_state(st)


def build_order(signal: dict, balance_usdt: float) -> dict:
    """Monta a intencao de ordem (a mercado) a partir de um sinal de COMPRA."""
    price = _ref_price(signal)
    notional = round(float(balance_usdt) * float(EXECUTION_PCT), 2)
    # piso: Gate.io rejeita ordem < $3 ("too small"). Eleva ao minimo...
    notional = max(notional, float(EXECUTION_MIN_NOTIONAL_USDT))
    # clamp rigido: ...mas nunca acima do teto (teto > piso garantido).
    notional = min(notional, float(EXECUTION_MAX_NOTIONAL_USDT))
    qty = (notional / price) if price else None

    # --- Saida automatica: calcula SL/TP por volatilidade (ATR) ---
    # SL = entrada - (mult * ATR)  |  TP = entrada + (RR * risco)
    sl_price = None
    tp_price = None
    try:
        if isinstance(signal, dict):
            atr = float(signal.get("atr") or 0)
        else:
            atr = float(getattr(signal, "atr", 0) or 0)
    except (TypeError, ValueError):
        atr = 0.0
    if EXECUTION_TPSL_ENABLED and price and atr > 0:
        risco = float(EXECUTION_ATR_MULT_SL) * atr   # distancia do stop em $
        # PISO DE VOLATILIDADE (bug TRX): em ativos de baixa vol (ATR ~0.25%),
        # 2*ATR gera stop coladissimo (-0.5%) -> estopado por ruido. Garante um
        # afastamento minimo do preco (EXECUTION_MIN_STOP_PCT, default 0.8%).
        try:
            _min_stop_pct = float(globals().get("EXECUTION_MIN_STOP_PCT", 0.8))
        except Exception:
            _min_stop_pct = 0.8
        _min_dist = float(price) * (_min_stop_pct / 100.0)
        if _min_dist > risco:
            risco = _min_dist
        sl_price = round(price - risco, 8)
        tp_price = round(price + float(EXECUTION_TP_RR) * risco, 8)
        if sl_price <= 0:                            # guarda: nunca SL negativo
            sl_price = None

    return {
        "signal_id": _signal_id(signal),
        "symbol": signal.get("symbol"),
        "side": "buy",                       # camada e LONG/BUY only (Fase 1)
        "type": "market",                    # a mercado (com slippage)
        "strategy": signal.get("strategy"),
        "notional_usdt": notional,
        "qty": qty,
        "ref_price": price,                  # preco no momento do sinal
        "atr": atr,                          # ATR usado p/ dimensionar SL/TP
        "sl_price": sl_price,                # stop-loss (None se ATR ausente)
        "tp_price": tp_price,                # take-profit
        "dry_run": bool(EXECUTION_DRY_RUN),
        "ts": _now_iso(),
    }


def _sign(payload_bytes: bytes) -> str:
    """Assinatura HMAC-SHA256 do corpo -> o PHP rejeita o que nao bater."""
    return hmac.new(_HMAC_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()


def _append_jsonl(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def send_order(order: dict, timeout: int = 10) -> dict:
    """Envia a ordem assinada ao relay PHP. Em Fase 1 o relay so loga."""
    if not EXECUTION_RELAY_URL or not _HMAC_SECRET:
        return {"status": "skipped", "reason": "relay/segredo nao configurado"}
    body = json.dumps(order, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        EXECUTION_RELAY_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Signature": _sign(body),       # HMAC do corpo
            "X-Signal-Id": order["signal_id"],  # idempotencia tambem no header
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # nunca derruba o scan por falha de execucao
        return {"status": "error", "reason": str(exc)}



# ------------------------------------------------------------------
# Alerta de EXECUCAO no Telegram (best-effort: nunca derruba o scan).
# ------------------------------------------------------------------


ORDERS_CSV_HEADER = [
    "ts_utc", "signal_id", "symbol", "side", "notional_usdt",
    "ref_price", "fill_price", "slippage_pct", "mode", "status", "reason",
]


def _append_execution_csv(orler: dict, result: dict) -> None:
    """Grava UMA linha por operacao no state/orders_executed.csv (legivel/Excel)."""
    pass
