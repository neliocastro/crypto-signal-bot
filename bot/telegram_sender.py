"""
Envio de mensagens para o Telegram.
Funções públicas:
  - send_message(text)         -> envia texto puro
  - format_signal(sig, fg=None)-> formata um Signal para Markdown
  - send_signal(sig, fg=None)  -> formata e envia
  - send_heartbeat(text)       -> envia heartbeat/status do scan
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import requests

from .config import settings  # espera settings.telegram_token / settings.telegram_chat_id

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ---------------------------------------------------------------------------
# helpers internos
# ---------------------------------------------------------------------------
def _get_credentials() -> tuple[str, str]:
    """
    Busca token e chat_id em settings (config.py) ou nas variáveis de ambiente.
    """
    token = (
        getattr(settings, "telegram_token", None)
        or os.getenv("TELEGRAM_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
    )
    chat_id = (
        getattr(settings, "telegram_chat_id", None)
        or os.getenv("TELEGRAM_CHAT_ID")
    )
    if not token or not chat_id:
        raise RuntimeError(
            "Credenciais do Telegram ausentes (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID)."
        )
    return str(token), str(chat_id)

def _escape_md(text: str) -> str:
    """
    Escape mínimo para MarkdownV1 (suficiente para nosso uso).
    """
    if text is None:
        return ""
    return (
        str(text)
        .replace("_", r"\_")
        .replace("*", r"\*")
        .replace("`", r"\`")
        .replace("[", r"\[")
    )

def _fmt_price(v: float) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:.4f}"
    return f"{v:.6f}"

def _fg_label(fg: Optional[int]) -> str:
    """Classifica o Fear & Greed."""
    if fg is None:
        return ""
    if fg < 25:
        return "😱 Medo Extremo"
    if fg < 45:
        return "😟 Medo"
    if fg < 55:
        return "😐 Neutro"
    if fg < 75:
        return "🙂 Ganância"
    return "🤑 Ganância Extrema"

# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Envia uma mensagem de texto para o chat configurado.
    Retorna True em caso de sucesso.
    """
    try:
        token, chat_id = _get_credentials()
    except RuntimeError as e:
        log.error("%s", e)
        return False

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            log.error("Telegram %s: %s", r.status_code, r.text)
            # fallback sem parse_mode (caso o Markdown quebre)
            if parse_mode:
                payload.pop("parse_mode", None)
                r2 = requests.post(url, json=payload, timeout=15)
                return r2.status_code == 200
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log.exception("Falha ao enviar Telegram: %s", e)
        return False

def format_signal(sig, fg: Optional[int] = None) -> str:
    """
    Formata um objeto Signal em Markdown amigável.
    `fg` é o índice Fear & Greed (0-100), opcional.
    """
    side_emoji = "🟢 LONG" if sig.side == "LONG" else "🔴 SHORT"

    # alvos
    targets_str = ""
    if sig.targets:
        targets_str = "\n".join(
            f"  • TP{i+1}: `{_fmt_price(t)}`" for i, t in enumerate(sig.targets)
        )

    # motivos
    reasons_str = ""
    if sig.reasons:
        reasons_str = "\n".join(f"  ✓ {_escape_md(r)}" for r in sig.reasons)

    # cabeçalho do F&G
    fg_line = ""
    if fg is not None:
        fg_line = f"\n🌡️ *F&G:* {fg} — {_fg_label(fg)}"

    # confidence em estrelas (10 = ★★★★★)
    stars = "★" * min(5, max(1, round(sig.confidence / 2)))
    stars = stars.ljust(5, "☆")

    msg = (
        f"🤖 *Sinal {side_emoji}*\n"
        f"📊 *Par:* `{_escape_md(sig.symbol)}`  ⏱ `{_escape_md(sig.timeframe)}`\n"
        f"🎯 *Confiança:* {stars}  ({sig.confidence}/10)"
        f"{fg_line}\n"
        f"\n"
        f"💰 *Entrada:* `{_fmt_price(sig.entry)}`\n"
        f"🛑 *Stop:* `{_fmt_price(sig.stop)}`\n"
        f"🎯 *Alvos:*\n{targets_str}\n"
        f"\n"
        f"🧠 *Confluências:*\n{reasons_str}\n"
        f"\n"
        f"🕒 _{_escape_md(sig.timestamp)}_"
    )
    return msg

def send_signal(sig, fg: Optional[int] = None) -> bool:
    """Conveniência: formata e envia um Signal."""
    return send_message(format_signal(sig, fg))

def send_heartbeat(text: str) -> bool:
    """
    Mensagem curta de status do scan (ex.: 'Scan concluído: 3 ativos, 0 sinais').
    """
    return send_message(f"🤖 _{_escape_md(text)}_")
