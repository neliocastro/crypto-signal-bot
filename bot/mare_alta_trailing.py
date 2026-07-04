"""
mare_alta_trailing.py - Trailing sintetico "Mare Alta" por ATR no timeframe D1.

CODIGO NOVO (escrito do zero em 2026-07, NAO e recuperacao de versao antiga -
o arquivo antigo nunca existiu como fonte no Git). Encaixa no contrato real do
relay PHP (server/execute.php, acao "update_trailing"): cria novo stop -> confirma
2xx+id -> DELETE do antigo; se o create falhar, o PHP MANTEM o stop antigo.

Responsabilidade (lado Python / CEREBRO):
  1. register_position(): apos um fill de compra, guarda a posicao aberta
     (symbol, base_qty, entry, sl atual, sl_order_id) em state/positions.jsonl.
  2. update_trailing(): a cada vela D1, recalcula o SL por ATR e, se ele SOBE,
     envia a acao "update_trailing" ao relay (assinada com HMAC-SHA256, igual
     ao executor.py). Trailing e CATRACA: nunca rebaixa o stop.

Kill-switch: MARE_ALTA_TRAILING_ENABLED (default False -> modulo inerte).
Degradacao segura: qualquer excecao e capturada; nunca derruba o scan e nunca
deixa a posicao sem protecao (na duvida, NAO mexe no stop existente).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

log = logging.getLogger("bot.mare_alta_trailing")

# --- Config com fallback seguro (se faltar no config.py, modulo fica inerte) ---
try:
    from .config import (
        MARE_ALTA_TRAILING_ENABLED,
        MARE_ALTA_SL_ATR_MULT,
        MARE_ALTA_ATR_PERIOD,
        MARE_ALTA_SYMBOLS,
        EXECUTION_RELAY_URL,
    )
except Exception:  # degradacao segura: sem config -> desligado
    MARE_ALTA_TRAILING_ENABLED = False
    MARE_ALTA_SL_ATR_MULT = 3.0
    MARE_ALTA_ATR_PERIOD = 14
    MARE_ALTA_SYMBOLS = ["HYPE/USDT"]
    EXECUTION_RELAY_URL = ""

_HMAC_SECRET = os.environ.get("EXECUTION_HMAC_SECRET", "")
POSITIONS_FILE = "state/positions.jsonl"

# Casas de preco por par (espelha $SAFE_PRICE_PREC do execute.php).
# Usado apenas para pre-validar/truncar o SL ANTES de enviar (o PHP revalida).
_SAFE_PRICE_PREC = {
    "BTC_USDT": 1, "ETH_USDT": 2, "SOL_USDT": 2, "XRP_USDT": 4, "TRX_USDT": 5,
    "BNB_USDT": 1, "LINK_USDT": 3, "HYPE_USDT": 3, "AAVE_USDT": 2, "PAXG_USDT": 2,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pair(symbol: str) -> str:
    return symbol.replace("/", "_")


def _price_prec(symbol: str) -> int:
    return _SAFE_PRICE_PREC.get(_pair(symbol), 4)


def _fmt_floor(value: float, places: int) -> str:
    """Trunca (nunca arredonda p/ cima) a `places` casas. Espelha fmt_floor do PHP."""
    if value <= 0:
        return "0"
    factor = 10 ** places
    truncated = int(value * factor) / factor
    return f"{truncated:.{places}f}"


def compute_atr(candles, period: int) -> float:
    """ATR simples (media dos true ranges) sobre candles D1.
    candles: lista de dicts/tuplas com high, low, close (mais antigo -> mais recente).
    Retorna 0.0 se nao houver dados suficientes (o chamador trata ATR=0)."""
    try:
        rows = []
        for c in candles:
            if isinstance(c, dict):
                rows.append((float(c["high"]), float(c["low"]), float(c["close"])))
            else:
                # aceita [ts, open, high, low, close, ...] ou (high, low, close)
                if len(c) >= 5:
                    rows.append((float(c[2]), float(c[3]), float(c[4])))
                elif len(c) == 3:
                    rows.append((float(c[0]), float(c[1]), float(c[2])))
        if len(rows) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(rows)):
            high, low, _ = rows[i]
            prev_close = rows[i - 1][2]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        window = trs[-period:]
        return sum(window) / len(window) if window else 0.0
    except Exception:
        log.exception("compute_atr falhou")
        return 0.0


# ----------------------------- Persistencia --------------------------------- #
def _load_positions() -> list:
    if not os.path.exists(POSITIONS_FILE):
        return []
    out = []
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        log.exception("falha ao ler %s", POSITIONS_FILE)
    return out


def _save_positions(positions: list) -> None:
    try:
        os.makedirs(os.path.dirname(POSITIONS_FILE) or ".", exist_ok=True)
        tmp = POSITIONS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for p in positions:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        os.replace(tmp, POSITIONS_FILE)
    except Exception:
        log.exception("falha ao salvar %s", POSITIONS_FILE)


def register_position(signal_id, symbol, base_qty, entry_price,
                      sl_price, sl_order_id) -> None:
    """Registra/atualiza uma posicao aberta apos o fill. Chave: signal_id.
    Idempotente: mesma signal_id sobrescreve a entrada anterior."""
    try:
        positions = _load_positions()
        rec = {
            "signal_id": str(signal_id),
            "symbol": symbol,
            "base_qty": str(base_qty),
            "entry_price": float(entry_price),
            "sl_price": float(sl_price) if sl_price else 0.0,
            "sl_order_id": str(sl_order_id) if sl_order_id else "",
            "status": "open",
            "opened_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        positions = [p for p in positions if p.get("signal_id") != rec["signal_id"]]
        positions.append(rec)
        _save_positions(positions)
        log.info("posicao registrada: %s %s qty=%s sl=%s",
                 signal_id, symbol, base_qty, sl_price)
    except Exception:
        log.exception("register_position falhou (%s)", symbol)


# ------------------------------ Relay / HMAC -------------------------------- #
def _sign_and_send(payload: dict, timeout: int = 12) -> dict | None:
    """Assina o corpo com HMAC-SHA256 e faz POST ao relay.
    Assina EXATAMENTE os bytes enviados (o PHP faz hash_hmac('sha256', $raw)).
    Corpo byte-identico ao executor.py: json.dumps(..., ensure_ascii=False).
    Retorna o dict de resposta ou None em caso de falha de rede/config."""
    if not EXECUTION_RELAY_URL:
        log.warning("EXECUTION_RELAY_URL vazio -> update_trailing nao enviado")
        return None
    if not _HMAC_SECRET:
        log.warning("EXECUTION_HMAC_SECRET ausente -> update_trailing nao enviado")
        return None
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = hmac.new(_HMAC_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        EXECUTION_RELAY_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Signature": sig,                       # HMAC-SHA256 do corpo cru
            "X-Signal-Id": str(payload.get("signal_id", "")),  # idempotencia no header
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return json.loads(raw)
            except Exception:
                return {"status": "unparsed", "http": resp.status, "raw": raw[:400]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"status": "http_error", "http": e.code, "raw": raw[:400]}
    except Exception:
        log.exception("falha de rede no _sign_and_send")
        return None


# ------------------------------ Trailing core ------------------------------- #
def _new_sl_from_atr(close_d1: float, atr_d1: float) -> float:
    return close_d1 - (MARE_ALTA_SL_ATR_MULT * atr_d1)


def update_trailing(fetch_d1_candles) -> list:
    """Percorre as posicoes abertas e sobe o SL por ATR (catraca).

    fetch_d1_candles(symbol) -> lista de candles D1 (mais antigo -> recente).
    Retorna lista de resultados (um dict por posicao avaliada). NUNCA levanta:
    qualquer erro por posicao e isolado para nao derrubar o scan.
    """
    results = []
    if not MARE_ALTA_TRAILING_ENABLED:
        log.info("MARE_ALTA_TRAILING_ENABLED=False -> trailing inerte")
        return results

    positions = _load_positions()
    changed = False

    for pos in positions:
        if pos.get("status") != "open":
            continue
        symbol = pos.get("symbol", "")
        try:
            if MARE_ALTA_SYMBOLS and symbol not in MARE_ALTA_SYMBOLS:
                continue

            candles = fetch_d1_candles(symbol) or []
            atr = compute_atr(candles, MARE_ALTA_ATR_PERIOD)
            if atr <= 0:
                results.append({"symbol": symbol, "signal_id": pos.get("signal_id"),
                                "action": "skip", "reason": "atr<=0 (mantem stop)"})
                continue

            close_d1 = float(candles[-1]["close"]) if isinstance(candles[-1], dict) \
                else float(candles[-1][4])
            raw_new = _new_sl_from_atr(close_d1, atr)
            ppz = _price_prec(symbol)
            cand_s = _fmt_floor(raw_new, ppz)
            cand = float(cand_s)
            cur_sl = float(pos.get("sl_price") or 0.0)

            # CATRACA: so sobe. Nunca rebaixa (protege lucro, nunca amplia risco).
            if cand <= cur_sl:
                results.append({"symbol": symbol, "signal_id": pos.get("signal_id"),
                                "action": "hold", "reason": "novo_sl <= sl_atual",
                                "cur_sl": cur_sl, "cand_sl": cand})
                continue

            payload = {
                "action": "update_trailing",
                "symbol": symbol,
                "new_sl_price": cand,
                "base_qty": str(pos.get("base_qty", "")),
                "old_sl_order_id": str(pos.get("sl_order_id", "")),
                "signal_id": str(pos.get("signal_id", "")),
            }
            resp = _sign_and_send(payload)

            if resp and resp.get("status") == "trailing_updated":
                new_id = (resp.get("new_sl") or {}).get("id", "")
                pos["sl_price"] = float((resp.get("new_sl") or {}).get("price", cand))
                pos["sl_order_id"] = str(new_id)
                pos["updated_at"] = _now_iso()
                changed = True
                results.append({"symbol": symbol, "signal_id": pos.get("signal_id"),
                                "action": "updated", "new_sl": pos["sl_price"],
                                "new_sl_order_id": new_id})
                log.info("trailing SUBIU %s: %s -> %s (id=%s)",
                         symbol, cur_sl, pos["sl_price"], new_id)
            else:
                # Falhou -> PHP mantem o stop antigo. NAO alteramos o estado local.
                results.append({"symbol": symbol, "signal_id": pos.get("signal_id"),
                                "action": "send_failed", "reason": "relay nao confirmou",
                                "response": resp})
                log.warning("trailing NAO confirmado %s (stop antigo mantido): %s",
                            symbol, resp)
        except Exception:
            log.exception("update_trailing falhou p/ %s (stop mantido)", symbol)
            results.append({"symbol": symbol, "action": "error",
                            "reason": "excecao isolada; stop antigo mantido"})

    if changed:
        _save_positions(positions)
    return results
