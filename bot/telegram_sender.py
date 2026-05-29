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

def _fg_parts(fg: Any) -> tuple[Optional[int], str, str]:
    """Aceita int OU dict {score,label,emoji}. Retorna (score, label, emoji)."""
    if fg is None:
        return None, "", ""
    if isinstance(fg, dict):
        score = fg.get("score")
        label = fg.get("label") or ""
        emoji = fg.get("emoji") or ""
        if score is not None and label and emoji:
            return score, label, emoji
        fg = score
    try:
        score = int(fg)
    except (TypeError, ValueError):
        return None, "", ""
    if score < 25:  return score, "Extreme Fear",  "😱"
    if score < 45:  return score, "Fear",          "😟"
    if score < 55:  return score, "Neutral",       "😐"
    if score < 75:  return score, "Greed",         "🙂"
    return score, "Extreme Greed", "🤑"

def _fg_emoji(fg: Any) -> str:
    """Compat: retorna apenas o emoji."""
    return _fg_parts(fg)[2]

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
    strategy   = _get(sig, "strategy", "")
    entry      = _get(sig, "entry")
    stop       = _get(sig, "stop") or _get(sig, "stop_loss")
    tp2        = _get(sig, "tp2") or _get(sig, "take_profit_2")
    tp3        = _get(sig, "tp3")
    targets    = _get(sig, "targets") or [t for t in (tp2, tp3) if t is not None]
    order_type = _get(sig, "order_type", "")
    risk_reward= _get(sig, "risk_reward")
    confidence = _get(sig, "confidence", 0)
    reasons    = _get(sig, "reasons") or []
    timeframe  = _get(sig, "timeframe", "")
    timestamp  = _get(sig, "timestamp", "")

    side_emoji = "🟢 LONG" if side == "LONG" else "🔴 SHORT"

    # alvos (2 TPs: R:R 1:2 e 1:3)
    _rr_labels = ["1:2", "1:3"]
    _tp_labels = ["TP1", "TP2"]
    targets_lines = []
    for i, t in enumerate(targets):
        lab = _tp_labels[i] if i < len(_tp_labels) else f"TP{i+2}"
        rr  = _rr_labels[i] if i < len(_rr_labels) else ""
        suffix = f"  _(R:R {rr})_" if rr else ""
        targets_lines.append(f"  • {lab}: `{_fmt_price(t)}`{suffix}")
    targets_block = "\n".join(targets_lines) if targets_lines else "  —"

    # confluências
    reasons_block = "\n".join(f"  ✓ {r}" for r in reasons) if reasons else "  —"

    # estrelas (0-10 → 0-5★)
    n_stars = min(5, max(0, round(int(confidence) / 2)))
    stars = "★" * n_stars + "☆" * (5 - n_stars)

    _fg_s, _fg_l, _fg_e = _fg_parts(fg)
    fg_line = f"\n🌡️ *F&G:* {_fg_s} ({_fg_l}) {_fg_e}" if _fg_s is not None else ""

    # linhas opcionais
    strat_line = f"📐 *Estratégia:* `{strategy}`\n" if strategy else ""
    order_suffix = f"  _[{order_type}]_" if order_type else ""
    rr_line = "📊 *Risco/Retorno:* `1:2` (arrisca 1 p/ ganhar 2)\n" if risk_reward else ""

    msg = (
        f"🤖 *Sinal {side_emoji}*\n"
        f"📊 *Par:* `{symbol}`  ⏱ `{timeframe}`\n"
        f"{strat_line}"
        f"🎯 *Confiança:* {stars}  ({confidence}/10)"
        f"{fg_line}\n"
        f"\n"
        f"💰 *Entrada:* `{_fmt_price(entry)}`{order_suffix}\n"
        f"🛑 *Stop:* `{_fmt_price(stop)}`\n"
        f"🎯 *Alvos:*\n{targets_block}\n"
        f"{rr_line}"
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
    _fg_s, _fg_l, _fg_e = _fg_parts(fg)
    fg_str = f" | F&G: {_fg_s} ({_fg_l}) {_fg_e}" if _fg_s is not None else ""
    return send(f"🤖 _Scan concluído: {checked} ativos verificados, {signals} sinal(is).{fg_str}_")

def _market_regime(fg_score):
    """Mapeia F&G score para (label, emoji, arrow). Visual v2."""
    if fg_score is None:
        return ("-", "", "")
    try:
        s = int(fg_score)
    except Exception:
        return ("-", "", "")
    if s <= 24:
        return ("Bear forte", "⚛️", "⬇️")
    if s <= 44:
        return ("Bear", "📉", "⬇️")
    if s <= 55:
        return ("Lateral", "↔️", "→")
    if s <= 74:
        return ("Bull", "📈", "⬆️")
    return ("Bull forte", "🚀", "⬆️⬆️")


def _local_time_str(tz_name: str = "America/Bahia") -> str:
    """Hora local atual no formato HH:MM · TZ. Fallback UTC."""
    try:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz_name)).strftime("%H:%M") + f" · {tz_name}"
        except Exception:
            return datetime.utcnow().strftime("%H:%M") + " UTC"
    except Exception:
        return ""


def format_scan_summary(
    diagnostics: List[dict],
    signals_count: int,
    fg: Any = None,
    timeframe: str = "",
    exchange: str = "",
) -> str:
    """Resumo do scan - visual v2 (Format Inteligente)."""
    _fg_s, _fg_l, _fg_e = _fg_parts(fg)
    regime_label, regime_emoji, regime_arrow = _market_regime(_fg_s)
    # Fase A: tag do perfil ativo (so aparece quando ACTIVE_PROFILE != balanceado)
    _profile_tag = ""
    try:
        from .config import ACTIVE_PROFILE  # type: ignore
        if ACTIVE_PROFILE and ACTIVE_PROFILE != "balanceado":
            _profile_tag = f" · 🔥 modo *{ACTIVE_PROFILE.upper()}*"
    except Exception:
        _profile_tag = ""

    if _fg_s is not None:
        header_2 = (
            f"{regime_emoji} *{regime_label}* {regime_arrow} ▸ "
            f"{_fg_e} F&G: {_fg_s} ({_fg_l}) ▸ "
            f"⏱️ `{timeframe}` ▸ {exchange}{_profile_tag}"
        )
    else:
        header_2 = f"⏱️ `{timeframe}` ▸ {exchange}{_profile_tag}"

    head = (
        f"🤖 *Crypto Signal Bot*\n"
        f"{header_2}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 *Sinais qualificados:* {signals_count}\n"
    )

    pronto, quase_la, observacao, risco, inativo, erros = [], [], [], [], [], []
    for d in diagnostics:
        sym = d.get("symbol", "-")
        if "error" in d:
            erros.append((sym, str(d["error"])[:60]))
            continue
        price          = d.get("price")
        rsi            = d.get("rsi")
        macd           = d.get("macd")
        macd_signal    = d.get("macd_signal")
        macd_hist      = d.get("macd_hist")
        macd_hist_prev = d.get("macd_hist_prev")
        vol_ratio      = d.get("vol_ratio")
        ema200         = d.get("ema200")
        signal         = d.get("signal")

        above_ema200 = bool(price and ema200 and price > ema200)
        macd_pos     = (macd is not None and macd > 0)
        macd_above   = (macd is not None and macd_signal is not None and macd > macd_signal)
        hist_pos     = (macd_hist is not None and macd_hist > 0)
        hist_accel   = (
            macd_hist is not None and macd_hist_prev is not None
            and macd_hist > 0 and macd_hist_prev > 0
            and macd_hist > macd_hist_prev * 1.5
        )
        vol_strong = (vol_ratio is not None and vol_ratio > 1.5)
        vol_weak   = (vol_ratio is not None and vol_ratio < 0.7)
        if vol_strong:
            vol_suffix = " · 🔥 volume forte"
        elif vol_weak:
            vol_suffix = " · 💤 volume fraco"
        else:
            vol_suffix = ""

        item = {"sym": sym, "price": price, "rsi": rsi, "macd": macd,
                "ema200": ema200, "signal": signal,
                "trend_4h": d.get("trend_4h"), "pullback_15m": d.get("pullback_15m")}

        if signal:
            pronto.append(item)
            continue
        if not above_ema200:
            inativo.append(item)
            continue
        if rsi is not None and rsi >= 70:
            item["reason"] = f"RSI sobrecomprado ({rsi:.0f} ≥ 70) - evita comprar topo"
            risco.append(item)
            continue
        if macd_above and hist_pos and rsi is not None and 50 <= rsi < 65:
            item["reason"] = "MACD cruzou o sinal · RSI saudavel" + vol_suffix
            quase_la.append(item)
            continue
        if hist_accel and rsi is not None and 45 <= rsi < 70:
            item["reason"] = "Histograma 1.5x maior - cruzamento iminente" + vol_suffix
            quase_la.append(item)
            continue
        if macd_pos and rsi is not None and 45 <= rsi < 70:
            item["reason"] = "MACD positivo e RSI ok - falta cruzamento final" + vol_suffix
            quase_la.append(item)
            continue
        if rsi is not None and rsi < 30:
            item["reason"] = "RSI sobrevendido - aguardando reversao"
        elif macd is not None and macd < 0:
            item["reason"] = "Acima da EMA200 - aguardando MACD virar positivo"
        else:
            item["reason"] = "Acima da EMA200 - aguardando confluencia"
        observacao.append(item)

    def _mtf_tag(it) -> str:
        """Prefixo visual indicando alinhamento 4h. Vazio se desconhecido."""
        trend = it.get("trend_4h")
        if trend is True:
            return "⬆️4h "
        if trend is False:
            return "⬇️4h "
        return ""

    def _fmt_quase_la(it):
        """Mesmo layout do _fmt_full mas com tag MTF prefixando o símbolo."""
        rsi_s  = f"{it['rsi']:.1f}"  if it['rsi']  is not None else "-"
        macd_s = f"{it['macd']:.2f}" if it['macd'] is not None else "-"
        ema_s  = _fmt_price(it['ema200']) if it['ema200'] is not None else "-"
        mtf    = _mtf_tag(it)
        return (
            f"{mtf}`{it['sym']}`  {_fmt_price(it['price'])}\n"
            f"  RSI `{rsi_s}` ▸ MACD `{macd_s}` ▸ EMA200 {ema_s}\n"
            f"  └ _{it['reason']}_"
        )

    def _fmt_full(it):
        rsi_s  = f"{it['rsi']:.1f}"  if it['rsi']  is not None else "-"
        macd_s = f"{it['macd']:.2f}" if it['macd'] is not None else "-"
        ema_s  = _fmt_price(it['ema200']) if it['ema200'] is not None else "-"
        return (
            f"`{it['sym']}`  {_fmt_price(it['price'])}\n"
            f"  RSI `{rsi_s}` ▸ MACD `{macd_s}` ▸ EMA200 {ema_s}\n"
            f"  └ _{it['reason']}_"
        )

    def _fmt_pronto(it):
        sig = it.get("signal") or {}
        strat = sig.get("strategy", "-")
        entry = sig.get("entry")
        stop  = sig.get("stop")
        tp2   = sig.get("tp2")
        tp3   = sig.get("tp3")
        rr    = sig.get("risk_reward")
        rr_s  = f"1:{rr}" if rr is not None else "-"
        return (
            f"`{it['sym']}`  {_fmt_price(it['price'])}\n"
            f"  🎯 *{strat}*\n"
            f"  Entry {_fmt_price(entry)} ▸ SL {_fmt_price(stop)}\n"
            f"  TP {_fmt_price(tp2)} / {_fmt_price(tp3)}  ·  R:R {rr_s}"
        )

    def _section(emoji, title, items, fmt_fn):
        if not items:
            return ""
        body = "\n\n".join(fmt_fn(it) for it in items)
        return (
            f"\n─────────────\n\n"
            f"{emoji} *{title}* ({len(items)})\n\n{body}\n"
        )

    parts = []
    parts.append(_section("🟢", "PRONTO PARA OPERAR", pronto,     _fmt_pronto))
    parts.append(_section("🟡", "QUASE LA",            quase_la,   _fmt_quase_la))
    parts.append(_section("🔵", "OBSERVACAO",          observacao, _fmt_full))
    parts.append(_section("🔴", "RISCO",               risco,      _fmt_full))

    if inativo:
        names = " ▸ ".join(f"`{it['sym'].split('/')[0]}`" for it in inativo)
        parts.append(
            f"\n─────────────\n\n"
            f"⚪️ *INATIVOS* ({len(inativo)})\n{names}\n"
            f"  └ _Preco abaixo da EMA200 (filtro base bloqueia LONG)_\n"
        )

    if erros:
        err_body = "\n".join(f"⚠️ `{s}` - {msg}" for s, msg in erros)
        parts.append(
            f"\n─────────────\n\n"
            f"⚠️ *Erros* ({len(erros)})\n{err_body}\n"
        )

    body_str = "".join(parts) if parts else "\n_Sem dados._\n"
    foot = f"\n🕐 _{_local_time_str()}_"
    return head + body_str + foot
