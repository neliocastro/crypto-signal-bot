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
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

# --- Config com fallback seguro (se faltar no config.py, assume desligado) ---
try:
    from .config import (
        EXECUTION_ENABLED,
        EXECUTION_DRY_RUN,
        EXECUTION_PCT,
        EXECUTION_RELAY_URL,
    )
except Exception:  # degradacao segura: sem config -> camada inerte
    EXECUTION_ENABLED = False
    EXECUTION_DRY_RUN = True
    EXECUTION_PCT = 0.10
    EXECUTION_RELAY_URL = ""

PAPER_TRADES_FILE = "state/paper_trades.jsonl"
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


def build_order(signal: dict, balance_usdt: float) -> dict:
    """Monta a intencao de ordem (a mercado) a partir de um sinal de COMPRA."""
    price = _ref_price(signal)
    notional = round(float(balance_usdt) * float(EXECUTION_PCT), 2)
    qty = (notional / price) if price else None
    return {
        "signal_id": _signal_id(signal),
        "symbol": signal.get("symbol"),
        "side": "buy",                       # camada e LONG/BUY only (Fase 1)
        "type": "market",                    # a mercado (com slippage)
        "strategy": signal.get("strategy"),
        "notional_usdt": notional,
        "qty": qty,
        "ref_price": price,                  # preco no momento do sinal
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


def maybe_execute(signal: dict, balance_usdt: float) -> dict | None:
    """
    Ponto de entrada chamado pelo scan APOS um sinal de compra.
    Agnostico de estrategia: qualquer side buy/long vira ordem candidata.
    """
    if not EXECUTION_ENABLED:
        return None
    side = str(signal.get("side", "")).lower()
    if side not in ("buy", "long"):
        return None

    order = build_order(signal, balance_usdt)

    # 1) registra SEMPRE a intencao (verdade do lado do cerebro)
    _append_jsonl(PAPER_TRADES_FILE, {"event": "intent", **order})

    # 2) envia ao relay (Fase 1: relay responde simulando, nao executa)
    result = send_order(order)

    # 3) registra a resposta do relay (verdade do lado do braco)
    _append_jsonl(PAPER_TRADES_FILE, {
        "event": "relay_response", "signal_id": order["signal_id"], "result": result, "ts": _now_iso(),
    })
    return {"order": order, "result": result}
