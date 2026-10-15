"""
oco_guard.py - Emulacao de OCO (One-Cancels-the-Other) p/ Gate.io spot.

CONTEXTO (2026-08-11): a Gate.io NAO vincula TP e SL no spot; sao price_orders
independentes. Quando uma perna dispara, a outra fica ORFA apontando p/ base ja
vendida - casos reais: TPs do HYPE orfaos apos SL (27/07) e SL do ETH orfao
apos TP (detectado pelo gate_cleanup em 11/08). Este modulo fecha o buraco:

  1. Le state/positions.jsonl (posicoes "open" com tp_order_id/sl_order_id,
     gravados pelo register_position no fill).
  2. Envia a acao "oco_sync" ao relay PHP (HMAC-SHA256, mesmo canal do
     update_trailing). O PHP consulta o status REAL de cada perna na API:
     se uma disparou (finish) e a outra segue open, cancela a sobrevivente.
  3. Marca a posicao local como closed_tp/closed_sl e notifica no Telegram.

Kill-switch: OCO_GUARD_ENABLED em config.py (default True; com relay vazio o
_sign_and_send ja e inerte). Degradacao segura: qualquer falha e logada e
ignorada - nunca derruba o scan, nunca cria ordem, nunca compra/vende.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from . import mare_alta_trailing as _mt

log = logging.getLogger("bot.oco_guard")

try:
    from .config import OCO_GUARD_ENABLED
except Exception:
    OCO_GUARD_ENABLED = True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _remaining_qty(p: dict) -> str:
    """Base que sobra apos o TP1 (base_qty - tp1_qty), com as casas da base."""
    base = Decimal(str(p.get("base_qty") or "0"))
    tp1 = Decimal(str(p.get("tp1_qty") or "0"))
    rest = base - tp1
    if rest <= 0:
        return ""
    return format(rest.normalize(), "f")


def _move_to_breakeven(p: dict, notify=None) -> dict | None:
    """TP1 disparou: troca o SL (base inteira) por um SL no BREAKEVEN so com o
    restante. Usa a acao update_trailing do relay: cria o novo -> confirma ->
    deleta o antigo (se a criacao falhar, o antigo e MANTIDO e tenta no proximo
    scan). Altera `p` no lugar; o chamador salva."""
    sym = p.get("symbol")
    rest = _remaining_qty(p)
    be = float(p.get("entry_price") or 0.0)
    if not rest or be <= 0:
        log.error("TP1 %s: restante/entrada invalidos (rest=%s, entry=%s) - SL mantido",
                  sym, rest, be)
        return None
    payload = {
        "action": "update_trailing",
        "symbol": sym,
        "new_sl_price": be,
        "base_qty": rest,
        "old_sl_order_id": str(p.get("sl_order_id", "") or ""),
        "signal_id": str(p.get("signal_id", "")),
    }
    resp = _mt._sign_and_send(payload)
    if not (resp and resp.get("status") == "trailing_updated"):
        log.warning("TP1 %s: breakeven NAO confirmado (SL antigo mantido; retenta): %s",
                    sym, resp)
        if notify and not p.get("tp1_be_fail_notified"):
            p["tp1_be_fail_notified"] = _now_iso()
            try:
                notify("⚠️ TP1 %s executado, mas o SL ainda NAO foi para o "
                       "breakeven (relay nao confirmou). Retentando no proximo scan." % sym)
            except Exception:
                pass
        return {"symbol": sym, "signal_id": p.get("signal_id"), "action": "tp1_be_failed"}
    new_sl = resp.get("new_sl") or {}
    p["tp1_done"] = True
    p["tp1_order_id"] = p.get("tp_order_id", "")
    p["tp1_price"] = p.get("tp_price", 0.0)
    p["tp_order_id"] = ""                 # restante segue sem TP (so trailing)
    p["tp_price"] = 0.0
    p["base_qty"] = rest
    p["sl_price"] = float(new_sl.get("price") or be)
    p["sl_order_id"] = str(new_sl.get("id") or "")
    p["updated_at"] = _now_iso()
    if notify:
        try:
            notify("\U0001F3AF TP1 %s: 50%% vendido em %s. Stop do restante (%s) "
                   "no breakeven %s; agora segue em trailing 3x ATR."
                   % (sym, p["tp1_price"], rest, p["sl_price"]))
        except Exception:
            pass
    return {"symbol": sym, "signal_id": p.get("signal_id"), "action": "tp1_breakeven",
            "new_sl": p["sl_price"], "base_qty": rest}


def sync(notify=None) -> list:
    """Reconcilia pares TP/SL das posicoes abertas. Retorna lista de fechamentos.

    NUNCA levanta excecao: qualquer erro e logado e devolve o que tiver.
    """
    results: list = []
    if not OCO_GUARD_ENABLED:
        return results
    try:
        positions = _mt._load_positions()
        open_pos = [
            p for p in positions
            if p.get("status") == "open"
            and (p.get("tp_order_id") or p.get("sl_order_id"))
        ]
        if not open_pos:
            return results

        pairs = [{
            "signal_id": str(p.get("signal_id", "")),
            "tp_order_id": str(p.get("tp_order_id", "") or ""),
            "sl_order_id": str(p.get("sl_order_id", "") or ""),
            # PHP FIX 10: TP1 parcial disparado NAO cancela o SL (devolve tp1_hit)
            "tp_partial": bool(p.get("tp_partial") and not p.get("tp1_done")),
        } for p in open_pos[:20]]  # espelha o teto de 20 pares do PHP

        payload = {
            "action": "oco_sync",
            "signal_id": "oco-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
            "pairs": pairs,
        }
        resp = _mt._sign_and_send(payload)
        if not resp or resp.get("status") != "oco_synced":
            log.warning("oco_sync nao confirmado pelo relay: %s", resp)
            return results

        by_sid = {str(i.get("signal_id")): i for i in (resp.get("pairs") or [])}
        changed = False
        for p in positions:
            item = by_sid.get(str(p.get("signal_id")))
            if not item or p.get("status") != "open":
                continue
            if item.get("tp1_hit") and p.get("tp_partial") and not p.get("tp1_done"):
                p["tp1_hit_at"] = p.get("tp1_hit_at") or _now_iso()
                changed = True
                if item.get("closed_by") is None:
                    r = _move_to_breakeven(p, notify)
                    if r:
                        results.append(r)
                    continue
            closed_by = item.get("closed_by")
            if closed_by not in ("tp", "sl"):
                continue
            p["status"] = "closed_" + closed_by
            p["closed_at"] = _now_iso()
            p["updated_at"] = _now_iso()
            p["oco_cancel"] = item.get("cancel")
            changed = True
            results.append({"symbol": p.get("symbol"),
                            "signal_id": p.get("signal_id"),
                            "closed_by": closed_by,
                            "cancel": item.get("cancel")})
            if notify:
                try:
                    _c = item.get("cancel") or {}
                    _extra = (" | perna oposta (%s) cancelada"
                              % _c.get("side")) if _c else ""
                    notify("\U0001F6E1 OCO: %s fechada por %s%s"
                           % (p.get("symbol"), closed_by.upper(), _extra))
                except Exception:
                    pass
        if changed:
            _mt._save_positions(positions)
    except Exception:
        log.exception("oco_guard.sync falhou (ignorado)")
    return results
