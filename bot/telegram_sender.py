"""
Envio de mensagens para o Telegram.

Funções públicas:
  - send(text)                       -> envia texto puro
  - send_message(text)               -> alias de send()
  - format_signal(sig, fg=None)      -> formata sinal (dict OU dataclass)
  - send_signal(sig, fg=None)        -> formata e envia
  - send_heartbeat(checked, signals, fg=None) -> resumo do scan
  - format_scan_summary(...)         -> mantido para compatibilidade
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Any, List

import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ---------------------------------------------------------------------------
# credenciais (lidas direto do ambiente — secrets do GitHub Actions)
# ---------------------------------------------------------------------------
def _get_credentials() -> tuple[str, str]:
    token = (
        os.getenv("TELEGRAM_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    )
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or ""
    return token.strip(), chat_id.strip()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _fmt_price(v: Optional[float]) -> str:
    if v is None or v != v:   # None ou NaN
        return "—"
    if abs(v) >= 1000:
        s = f"{v:,.2f}"
        # formato BR
        return "$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    if abs(v) >= 1:
        return f"$ {v:.4f}".replace(".", ",")
    return f"$ {v:.6f}".replace(".", ",")

def _fg_emoji(fg: Optional[int]) -> str:
    if fg is None:
        return ""
    if fg < 25:  return "😱"
    if fg < 45:  return "😟"
    if fg < 55:  return "😐"
    if fg < 75:  return "🙂"
    return "🤑"

def _get(obj: Any, key: str, default=None):
    """Lê chave/atributo de dict OU dataclass."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

# ---------------------------------------------------------------------------
# envio
# ---------------------------------------------------------------------------
def send(text: str, parse_mode: str = "Markdown") -> bool:
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        log.error("⚠️ TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausentes nas envs.")
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
        if r.status_code == 200:
            return True
        log.error("Telegram %s: %s", r.status_code, r.text)
        # fallback: reenvia sem parse_mode (caso o Markdown tenha quebrado)
        payload.pop("parse_mode", None)
        r2 = requests.post(url, json=payload, timeout=15)
        if r2.status_code == 200:
            return True
        log.error("Telegram fallback %s: %s", r2.status_code, r2.text)
        return False
    except Exception as e:                       # noqa: BLE001
        log.exception("Falha ao enviar Telegram: %s", e)
        return False

# alias
send_message = send

# ---------------------------------------------------------------------------
# formatação de sinal
# ---------------------------------------------------------------------------
def format_signal(sig: Any, fg: Optional[int] = None) -> str:
    """
    `sig` pode ser dict (vindo do strategies.evaluate_signal) ou dataclass.
    """
    symbol     = _get(sig, "symbol", "—")
    side       = _get(sig, "side", "—")
    entry      = _get(sig, "entry")
    stop       = _get(sig, "stop") or _get(sig, "stop_loss")
    tp1        = _get(sig, "tp1") or _get(sig, "take_profit_1")
    tp2        = _get(sig, "tp2") or _get(sig, "take_profit_2")
    tp3        = _get(sig, "tp3")
    targets    = _get(sig, "targets") or [t for t in (tp1, tp2, tp3) if t is not None]
    confidence = _get(sig, "confidence", 0)
    reasons    = _get(sig, "reasons") or []
    timeframe  = _get(sig, "timeframe", "")
    timestamp  = _get(sig, "timestamp", "")

    side_emoji = "🟢 LONG" if side == "LONG" else "🔴 SHORT"

    # alvos
    targets_lines = []
    for i, t in enumerate(targets, start=1):
        targets_lines.append(f"  • TP{i}: `{_fmt_price(t)}`")
    targets_block = "\n".join(targets_lines) if targets_lines else "  —"

    # confluências
    reasons_block = "\n".join(f"  ✓ {r}" for r in reasons) if reasons else "  —"

    # estrelas (0-10 → 0-5★)
    n_stars = min(5, max(0, round(int(confidence) / 2)))
    stars = "★" * n_stars + "☆" * (5 - n_stars)

    fg_line = f"\n🌡️ *F&G:* {fg} {_fg_emoji(fg)}" if fg is not None else ""

    msg = (
        f"🤖 *Sinal {side_emoji}*\n"
        f"📊 *Par:* `{symbol}`  ⏱ `{timeframe}`\n"
        f"🎯 *Confiança:* {stars}  ({confidence}/10)"
        f"{fg_line}\n"
        f"\n"
        f"💰 *Entrada:* `{_fmt_price(entry)}`\n"
        f"🛑 *Stop:* `{_fmt_price(stop)}`\n"
        f"🎯 *Alvos:*\n{targets_block}\n"
        f"\n"
        f"🧠 *Confluências:*\n{reasons_block}\n"
        f"\n"
        f"🕒 _{timestamp}_"
    )
    return msg

def send_signal(sig: Any, fg: Optional[int] = None) -> bool:
    return send(format_signal(sig, fg))

# ---------------------------------------------------------------------------
# heartbeat / resumo
# ---------------------------------------------------------------------------
def send_heartbeat(checked: int, signals: int, fg: Optional[int] = None) -> bool:
    fg_str = f" | F&G: {fg} {_fg_emoji(fg)}" if fg is not None else ""
    return send(f"🤖 _Scan concluído: {checked} ativos verificados, {signals} sinal(is).{fg_str}_")

def format_scan_summary(
    diagnostics: List[dict],
    signals_count: int,
    fg: Any = None,
    timeframe: str = "",
    exchange: str = "",
) -> str:
    """
    Resumo detalhado do scan (1 mensagem com diagnóstico de todos ativos).
    """
    fg_val = fg.get("score") if isinstance(fg, dict) else fg
    fg_line = f"{_fg_emoji(fg_val)} *Fear & Greed:* {fg_val}\n" if fg_val is not None else ""

    head = (
        f"🤖 *Scan Concluído*\n"
        f"{fg_line}"
        f"📊 *Ativos:* {len(diagnostics)} — TF `{timeframe}` • {exchange}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )

    body_lines = []
    for d in diagnostics:
        sym = d.get("symbol", "—")
        if "error" in d:
            body_lines.append(f"⚠️ `{sym}` — erro: {str(d['error'])[:60]}")
            continue
        price  = d.get("price")
        rsi    = d.get("rsi")
        macd   = d.get("macd")
        ema200 = d.get("ema200")
        trend  = "✅" if (price and ema200 and price > ema200) else "⚠️"
        rsi_s  = f"{rsi:.1f}" if rsi is not None else "—"
        macd_s = f"{macd:.2f}" if macd is not None else "—"

        body_lines.append(
            f"`{sym}`  {_fmt_price(price)}\n"
            f"  RSI: `{rsi_s}` | MACD: `{macd_s}` | EMA200 {trend}"
        )

    body = "\n\n".join(body_lines) if body_lines else "_Sem dados._"
    foot = f"\n━━━━━━━━━━━━━━━━━━\n🎯 *Sinais qualificados:* {signals_count}"

    return head + body + foot
