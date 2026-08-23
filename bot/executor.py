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
    # --- TRAVA DE CONCENTRACAO (2026-08-23) ---
    # Aditiva: se as chaves nao existirem no config.py, valem estes defaults
    # (ja LIGADOS). Para desligar/ajustar, basta declarar em bot/config.py:
    #   EXECUTION_CONCENTRATION_GUARD = False   <- rollback de 1 linha
    #   EXECUTION_MAX_OPEN_PER_SYMBOL = 1
    #   EXECUTION_MAX_TRADES_DAY_PER_SYMBOL = 2
    try:
        from .config import EXECUTION_CONCENTRATION_GUARD
    except Exception:
        EXECUTION_CONCENTRATION_GUARD = True
    try:
        from .config import EXECUTION_MAX_OPEN_PER_SYMBOL
    except Exception:
        EXECUTION_MAX_OPEN_PER_SYMBOL = 1
    try:
        from .config import EXECUTION_MAX_TRADES_DAY_PER_SYMBOL
    except Exception:
        EXECUTION_MAX_TRADES_DAY_PER_SYMBOL = 2
    try:
        from .config import POSITIONS_FILE
    except Exception:
        POSITIONS_FILE = "state/positions.jsonl"
except Exception:  # degradacao segura: sem config -> camada inerte
    EXECUTION_CONCENTRATION_GUARD = False
    EXECUTION_MAX_OPEN_PER_SYMBOL = 1
    EXECUTION_MAX_TRADES_DAY_PER_SYMBOL = 2
    POSITIONS_FILE = "state/positions.jsonl"
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


def _open_count_for_symbol(symbol: str) -> int:
    """Posicoes ABERTAS do ativo, lidas de state/positions.jsonl.

    Fonte da verdade real (a mesma do oco_guard/trailing). NAO usa o contador
    de execution_guard.json: ele so incrementa; nada o decrementa no TP/SL.
    Degradacao segura: qualquer erro -> 0 (nunca bloqueia por engano).
    """
    try:
        n = 0
        with open(POSITIONS_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("symbol") != symbol:
                    continue
                if str(rec.get("status", "")).startswith("open"):
                    n += 1
        return n
    except Exception:
        return 0


def _sent_today_for_symbol(symbol: str) -> int:
    """Ordens ENVIADAS hoje (UTC) para o ativo (state/paper_trades.jsonl).

    Conta os 'relay_response' do dia (so existem apos passar as travas); o
    'intent' de mesmo signal_id fornece o simbolo. Erro -> 0.
    """
    try:
        today = _today_utc()
        sym_by_id, vistos, n = {}, set(), 0
        with open(PAPER_TRADES_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("event") == "intent":
                    sym_by_id[rec.get("signal_id")] = rec.get("symbol")
                if not str(rec.get("ts", "")).startswith(today):
                    continue
                if rec.get("event") == "relay_response":
                    sid = rec.get("signal_id")
                    if sym_by_id.get(sid) == symbol and sid not in vistos:
                        vistos.add(sid)
                        n += 1
        return n
    except Exception:
        return 0


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
    # 5/6) TRAVA DE CONCENTRACAO (por ativo). EVIDENCIA: 13 dos 17 registros de
    # state/positions.jsonl sao HYPE (76%) e os 9 stops sao TODOS dele. O teto
    # global EXECUTION_MAX_OPEN=10 nunca segurou nada porque o bot repetia o
    # MESMO ativo. Ver docs/trava_concentracao_2026-08-23.md.
    if EXECUTION_CONCENTRATION_GUARD:
        sym = str(order.get("symbol", ""))
        abertas = _open_count_for_symbol(sym)
        if abertas >= int(EXECUTION_MAX_OPEN_PER_SYMBOL):
            return False, f"concentracao: ja ha {abertas} posicao(oes) aberta(s) em {sym} (max {EXECUTION_MAX_OPEN_PER_SYMBOL})"
        hoje = _sent_today_for_symbol(sym)
        if hoje >= int(EXECUTION_MAX_TRADES_DAY_PER_SYMBOL):
            return False, f"concentracao: {sym} ja teve {hoje} ordem(ns) hoje (max {EXECUTION_MAX_TRADES_DAY_PER_SYMBOL}/dia)"
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


def _append_execution_csv(order: dict, result: dict) -> None:
    """Grava UMA linha por operacao no state/orders_executed.csv (legivel/Excel)."""
    try:
        os.makedirs(os.path.dirname(ORDERS_CSV_FILE), exist_ok=True)
        new_file = not os.path.exists(ORDERS_CSV_FILE) or os.path.getsize(ORDERS_CSV_FILE) == 0
        row = {
            "ts_utc": _now_iso(),
            "signal_id": order.get("signal_id", ""),
            "symbol": order.get("symbol", ""),
            "side": order.get("side", "buy"),
            "notional_usdt": order.get("notional_usdt", ""),
            "ref_price": order.get("ref_price", ""),
            "fill_price": result.get("sim_fill_price") or result.get("fill_price") or result.get("avg_price") or "",
            "slippage_pct": result.get("slippage_pct", "") if result.get("slippage_pct") is not None else "",
            "mode": "DRY_RUN" if EXECUTION_DRY_RUN else "REAL",
            "status": result.get("status", ""),
            "reason": result.get("reason", ""),
        }
        with open(ORDERS_CSV_FILE, "a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=ORDERS_CSV_HEADER)
            if new_file:
                w.writeheader()
            w.writerow(row)
    except Exception as e:  # log de CSV jamais pode quebrar a execucao
        log.warning("falha ao gravar orders_executed.csv: %s", e)


def _notify_execution(order: dict, result: dict) -> None:
    """Envia ao Telegram o resultado de uma ordem (real, bloqueada ou rejeitada)."""
    # registro estruturado em CSV (alem do .jsonl) - legivel e versionado no Git
    _append_execution_csv(order, result)
    try:
        from . import telegram_sender as tg
    except Exception:
        return
    try:
        status = str(result.get("status", "?"))
        sym = order.get("symbol", "?")
        notional = order.get("notional_usdt", "?")
        sid = order.get("signal_id", "?")
        mode = "DRY-RUN (simulado)" if EXECUTION_DRY_RUN else "REAL"

        if status in ("filled", "accepted", "ok"):
            fill = result.get("sim_fill_price") or result.get("fill_price") or result.get("avg_price")
            slip = result.get("slippage_pct")
            head = "\u2705 *ORDEM EXECUTADA*" if not EXECUTION_DRY_RUN else "\U0001f9ea *Ordem simulada (dry-run)*"
            msg = (
                f"{head}\n"
                f"Par: *{sym}*\n"
                f"Lado: COMPRA\n"
                f"Valor: *${notional}* USDT\n"
                f"Modo: {mode}\n"
                + (f"Pre\u00e7o: {fill}\n" if fill else "")
                + (f"Slippage: {slip}%\n" if slip is not None else "")
                + f"ID: `{sid}`"
            )
        elif status == "blocked_by_guard":
            msg = (
                f"\U0001f6e1\ufe0f *Ordem BLOQUEADA por trava de capital*\n"
                f"Par: *{sym}*  \u2022  Valor: ${notional}\n"
                f"Motivo: {result.get('reason','?')}\n"
                f"ID: `{sid}`"
            )
        elif status == "dry_run":
            msg = (
                f"\U0001f9ea *Ping dry-run* \u2014 *{sym}* ${notional} "
                f"(relay confirmou, ordem N\u00c3O enviada)\nID: `{sid}`"
            )
        else:
            msg = (
                f"\u26a0\ufe0f *Ordem n\u00e3o executada* \u2014 *{sym}* ${notional}\n"
                f"Status: `{status}`  \u2022  {result.get('reason','')}\n"
                f"ID: `{sid}`"
            )
        tg.send(msg)
    except Exception as e:  # alerta jamais pode quebrar o fluxo de execucao
        log.warning("falha ao notificar execucao no telegram: %s", e)


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

    # 1.5) PROTECOES DE CAPITAL: travas rigidas antes de enviar.
    ok, reason = check_guards(order)
    if not ok:
        blocked = {"status": "blocked_by_guard", "reason": reason}
        _append_jsonl(PAPER_TRADES_FILE, {"event": "guard_block", "signal_id": order["signal_id"], "result": blocked, "ts": _now_iso()})
        _notify_execution(order, blocked)
        return {"order": order, "result": blocked}

    # 2) envia ao relay (Fase 1: relay responde simulando, nao executa)
    result = send_order(order)

    # 2.5) se a ordem REAL foi de fato enviada (nao dry-run/skip), conta nos limites do dia
    if isinstance(result, dict) and result.get("status") in ("filled", "accepted", "ok"):
        _register_sent_order()

    # 3) registra a resposta do relay (verdade do lado do braco)
    _append_jsonl(PAPER_TRADES_FILE, {
        "event": "relay_response", "signal_id": order["signal_id"], "result": result, "ts": _now_iso(),
    })

    # 4) ALERTA NO TELEGRAM: avisa o resultado da operacao (real/dry-run/bloqueio).
    if isinstance(result, dict):
        _notify_execution(order, result)

    return {"order": order, "result": result}
