"""
Telegram Commander (Fase C4 MVP)
================================
Polling do getUpdates do Telegram, parsing de comandos e aplicação
em state/runtime_config.json.

Executado pelo workflow .github/workflows/commander.yml a cada 2min.

Segurança:
  - Apenas chat_id em ALLOWED_CHAT_ID processa comandos
  - Cada update é processado UMA vez (offset persistido em state/telegram_offset.txt)
  - Símbolos novos são validados na Gate.io antes de adicionar
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import runtime_config as rc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot.commander")

_REPO_ROOT = Path(__file__).resolve().parent.parent
OFFSET_PATH = _REPO_ROOT / "state" / "telegram_offset.txt"
LOG_PATH    = _REPO_ROOT / "state" / "command_log.jsonl"

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN", "").strip()
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ===================== I/O helpers =====================

def _load_offset() -> int:
    try:
        return int(OFFSET_PATH.read_text().strip())
    except Exception:
        return 0


def _save_offset(off: int) -> None:
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(str(off))


def _audit(event: dict) -> None:
    event["ts"] = datetime.now(timezone.utc).isoformat()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ===================== Telegram I/O =====================

def tg_get_updates(offset: int) -> list[dict]:
    try:
        r = requests.get(
            f"{API}/getUpdates",
            params={"offset": offset, "timeout": 0, "allowed_updates": '["message"]'},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:                                       # noqa: BLE001
        log.warning("getUpdates falhou: %s", e)
        return []


def tg_send(chat_id: int | str, text: str) -> bool:
    try:
        r = requests.post(
            f"{API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:                                       # noqa: BLE001
        log.warning("sendMessage falhou: %s", e)
        return False


# ===================== Símbolo: normalização + validação =====================

def normalize_symbol(s: str) -> str:
    """BTC -> BTC/USDT ; btc/usdt -> BTC/USDT"""
    s = s.strip().upper().replace(" ", "")
    if "/" not in s:
        s = f"{s}/USDT"
    return s


def validate_symbol_on_exchange(symbol: str) -> tuple[bool, str]:
    """Valida que o par existe na Gate.io (sem usar ccxt para ficar leve)."""
    try:
        base, quote = symbol.split("/")
        pair = f"{base}_{quote}"
        r = requests.get(
            "https://api.gateio.ws/api/v4/spot/currency_pairs/" + pair,
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("trade_status") == "tradable":
                return True, "ok"
            return False, f"par {symbol} existe mas não está negociável"
        if r.status_code == 404:
            return False, f"par {symbol} não existe na Gate.io"
        return False, f"http {r.status_code}"
    except Exception as e:                                       # noqa: BLE001
        return False, f"erro de validação: {e}"


# ===================== Comandos =====================

HELP_TEXT = (
    "<b>🤖 Crypto Signal Bot — Comandos</b>\n\n"
    "<b>📊 Info</b>\n"
    "/status — config atual + último scan\n"
    "/listar — watchlist numerada\n"
    "/ajuda — esta mensagem\n\n"
    "<b>📝 Watchlist</b>\n"
    "/add BTC — adiciona ativo\n"
    "/remover BTC — remove por símbolo\n"
    "/rm 3 — remove por número\n\n"
    "<b>⏱️ Frequência</b>\n"
    "/intervalo 5|15|30 — muda intervalo\n"
    "/dnd on|off — modo não perturbe\n\n"
    "<b>🛑 Controle</b>\n"
    "/pausar — para o bot\n"
    "/retomar — religa o bot\n"
    "/forcar — scan imediato (no próximo cron)\n"
)


def _fmt_status(cfg: dict) -> str:
    last = cfg.get("last_scan_utc") or "—"
    if last != "—":
        try:
            dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            last = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass
    paused = "⏸️ PAUSADO" if cfg.get("paused") else "▶️ ATIVO"
    dnd_on = "🌙 ON" if cfg.get("dnd_enabled") else "☀️ OFF"
    dnd_w = f"{cfg.get('dnd_start_hour_local')}h–{cfg.get('dnd_end_hour_local')}h"
    return (
        f"<b>📊 Status</b>\n\n"
        f"Estado: {paused}\n"
        f"Intervalo: {cfg.get('scan_interval_min')} min\n"
        f"DND: {dnd_on} (janela {dnd_w}, scan {cfg.get('dnd_interval_min')} min)\n"
        f"Watchlist: {len(cfg.get('watchlist') or [])} ativos\n"
        f"Último scan: {last}\n"
        f"Atualizado por: {cfg.get('_updated_by','—')}\n"
    )


def _fmt_listar(cfg: dict) -> str:
    items = cfg.get("watchlist") or []
    if not items:
        return "📋 Watchlist vazia."
    lines = [f"<b>📋 Watchlist ({len(items)} ativos)</b>"]
    for i, s in enumerate(items, 1):
        lines.append(f"{i:>2}. {s}")
    return "\n".join(lines)


def handle_command(text: str, cfg: dict) -> tuple[str, bool]:
    """
    Processa 1 comando. Retorna (mensagem_resposta, config_mudou?).
    """
    text = text.strip()
    if not text.startswith("/"):
        return "", False

    parts = text.split(maxsplit=2)
    cmd = parts[0].lower().split("@")[0]
    args = parts[1:] if len(parts) > 1 else []

    # --- Info ---
    if cmd in ("/ajuda", "/help", "/start"):
        return HELP_TEXT, False

    if cmd == "/status":
        return _fmt_status(cfg), False

    if cmd == "/listar":
        return _fmt_listar(cfg), False

    # --- Watchlist ---
    if cmd == "/add":
        if not args:
            return "❓ Uso: <code>/add BTC</code>", False
        sym = normalize_symbol(args[0])
        if sym in (cfg.get("watchlist") or []):
            return f"⚠️ <code>{sym}</code> já está na watchlist.", False
        ok, msg = validate_symbol_on_exchange(sym)
        if not ok:
            return f"❌ {msg}", False
        cfg.setdefault("watchlist", []).append(sym)
        return f"✅ <code>{sym}</code> adicionado.\nTotal: {len(cfg['watchlist'])} ativos.", True

    if cmd in ("/remover", "/remove"):
        if not args:
            return "❓ Uso: <code>/remover BTC</code>", False
        sym = normalize_symbol(args[0])
        wl = cfg.get("watchlist") or []
        if sym not in wl:
            return f"⚠️ <code>{sym}</code> não está na watchlist.", False
        wl.remove(sym)
        cfg["watchlist"] = wl
        return f"🗑️ <code>{sym}</code> removido.\nTotal: {len(wl)} ativos.", True

    if cmd == "/rm":
        if not args or not args[0].isdigit():
            return "❓ Uso: <code>/rm 3</code> (índice da lista)", False
        idx = int(args[0]) - 1
        wl = cfg.get("watchlist") or []
        if idx < 0 or idx >= len(wl):
            return f"⚠️ Índice fora do range (1..{len(wl)}).", False
        removed = wl.pop(idx)
        cfg["watchlist"] = wl
        return f"🗑️ <code>{removed}</code> removido.\nTotal: {len(wl)} ativos.", True

    # --- Frequência ---
    if cmd == "/intervalo":
        if not args or not args[0].isdigit():
            return "❓ Uso: <code>/intervalo 5</code> (ou 15 ou 30)", False
        v = int(args[0])
        if v not in (5, 15, 30):
            return "⚠️ Valores aceitos: 5, 15 ou 30 minutos.", False
        cfg["scan_interval_min"] = v
        return f"⏱️ Intervalo agora: <b>{v} min</b>.", True

    if cmd == "/dnd":
        if not args:
            estado = "ON" if cfg.get("dnd_enabled") else "OFF"
            return (f"🌙 DND atualmente: <b>{estado}</b>\n"
                    f"Janela: {cfg.get('dnd_start_hour_local')}h-{cfg.get('dnd_end_hour_local')}h\n"
                    f"Use: <code>/dnd on</code> ou <code>/dnd off</code>"), False
        a = args[0].lower()
        if a in ("on", "ligar", "1"):
            cfg["dnd_enabled"] = True
            return "🌙 DND <b>ATIVADO</b>.", True
        if a in ("off", "desligar", "0"):
            cfg["dnd_enabled"] = False
            return "☀️ DND <b>DESATIVADO</b>.", True
        return "❓ Use <code>/dnd on</code> ou <code>/dnd off</code>", False

    # --- Controle ---
    if cmd == "/pausar":
        if cfg.get("paused"):
            return "⏸️ Bot já estava pausado.", False
        cfg["paused"] = True
        return "⏸️ Bot <b>PAUSADO</b>. Nenhum scan rodará até /retomar.", True

    if cmd == "/retomar":
        if not cfg.get("paused"):
            return "▶️ Bot já estava ativo.", False
        cfg["paused"] = False
        return "▶️ Bot <b>RETOMADO</b>.", True

    if cmd == "/forcar":
        cfg["last_scan_utc"] = None
        return "🚀 Próximo cron fará scan imediato (intervalo zerado).", True

    return f"❓ Comando <code>{cmd}</code> desconhecido. /ajuda", False


# ===================== Main loop =====================

def main() -> int:
    if not TELEGRAM_TOKEN or not ALLOWED_CHAT_ID:
        log.error("TELEGRAM_TOKEN ou ALLOWED_CHAT_ID ausentes — abortando.")
        return 1

    offset = _load_offset()
    updates = tg_get_updates(offset)
    if not updates:
        log.info("Nenhum update novo (offset=%s).", offset)
        return 0

    log.info("Recebidos %d updates.", len(updates))
    cfg = rc.load()
    changed = False

    for upd in updates:
        new_offset = upd["update_id"] + 1
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = (msg.get("text") or "").strip()
        username = (msg.get("from") or {}).get("username", "?")

        # Whitelist
        if str(chat_id) != str(ALLOWED_CHAT_ID):
            log.warning("Comando recusado de chat_id=%s (@%s): %r",
                        chat_id, username, text[:50])
            _audit({"event":"denied","chat_id":chat_id,"username":username,"text":text[:200]})
            _save_offset(new_offset)
            continue

        if not text.startswith("/"):
            _save_offset(new_offset)
            continue

        reply, cfg_changed = handle_command(text, cfg)
        if reply:
            tg_send(chat_id, reply)
        if cfg_changed:
            changed = True
        _audit({"event":"command","chat_id":chat_id,"username":username,
                "cmd":text[:200],"changed":cfg_changed})
        log.info("Comando processado: %s (changed=%s)", text[:80], cfg_changed)
        _save_offset(new_offset)

    if changed:
        rc.save(cfg, updated_by="telegram")
        log.info("runtime_config.json atualizado.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
