"""
Envia mensagens formatadas para o Telegram.
"""
import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send(text: str):
    if not TOKEN or not CHAT_ID:
        print("⚠️ TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausentes.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    if not r.ok:
        print("Telegram error:", r.text)
    return r.ok

def format_signal(sig, fg=None) -> str:
    side_emoji = "🟢" if sig.side == "BUY" else "🔴"
    side_text = "COMPRA" if sig.side == "BUY" else "VENDA"
    stars = "⭐" * sig.confidence

    fg_line = ""
    if fg:
        fg_line = f"\n*Sentimento:* {fg['emoji']} {fg['score']}/100 ({fg['label']})"

    return (
        f"{side_emoji} *SINAL DE {side_text}* — `{sig.symbol}`\n"
        f"_Timeframe: 1H | Estratégia: MACD + EMA200_\n\n"
        f"*Entrada:* `{sig.entry}`\n"
        f"*Stop Loss:* `{sig.stop_loss}` ({sig.extras['stop_pct']}%)\n"
        f"*TP1:* `{sig.take_profit_1}` (R:R 1:{sig.rr_tp1:.0f})\n"
        f"*TP2:* `{sig.take_profit_2}` (R:R 1:3)\n\n"
        f"*Confiança:* {sig.confidence}/10 {stars}\n"
        f"*Risco:* {sig.risk_level} ⚠️"
        f"{fg_line}\n\n"
        f"*Indicadores:*\n"
        f"• RSI: `{sig.extras['rsi']}`\n"
        f"• MACD: `{sig.extras['macd']}` / Sig: `{sig.extras['macd_signal']}`\n"
        f"• EMA200: `{sig.extras['ema200']}`\n\n"
        f"*Racional:* _{sig.rationale}_\n\n"
        f"🕐 Candle: `{sig.timestamp}`\n"
        f"📌 _Análise educacional. Execute manualmente na sua corretora._"
    )

def send_heartbeat(checked: int, signals_found: int, fg=None):
    """Envia ping silencioso quando NÃO houver sinais (opcional)."""
    fg_text = f" | F&G: {fg['score']} {fg['emoji']}" if fg else ""
    msg = f"🤖 _Scan concluído: {checked} ativos verificados, {signals_found} sinal(is).{fg_text}_"
    return send(msg)

from datetime import datetime

def _fg_emoji(score: int) -> str:
    if score <= 24: return "😱"
    if score <= 49: return "😟"
    if score <= 54: return "😐"
    if score <= 74: return "🙂"
    return "🤑"

def _fg_label(score: int) -> str:
    if score <= 24: return "Medo Extremo"
    if score <= 49: return "Medo"
    if score <= 54: return "Neutro"
    if score <= 74: return "Ganância"
    return "Ganância Extrema"

def _trend_emoji(rsi: float, price: float, ema200: float) -> str:
    """Cor do bullet por leitura combinada."""
    if rsi != rsi:  # NaN
        return "⚪"
    if rsi >= 55 and price > ema200:
        return "🟢"
    if rsi <= 45 and price < ema200:
        return "🔴"
    return "🟡"

def _fmt_price(v: float) -> str:
    if v != v:  # NaN
        return "—"
    if v >= 1000:
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if v >= 1:
        return f"$ {v:,.2f}"
    return f"$ {v:.4f}"

def _fmt(v: float, decimals: int = 2) -> str:
    if v != v:  # NaN
        return "—"
    return f"{v:.{decimals}f}"

def format_scan_summary(diagnostics, signals_count, fg, timeframe, exchange):
    now = datetime.now().strftime("%d/%m %H:%M")
    fg_score = fg if isinstance(fg, int) else fg.get("score", 0)

    lines = [
        f"🤖 *Scan Concluído* • {now}",
        f"{_fg_emoji(fg_score)} *Fear & Greed:* {fg_score} ({_fg_label(fg_score)})",
        "",
        f"📊 *Ativos Verificados* ({len(diagnostics)}) — TF {timeframe} • {exchange}",
        "",
    ]

    for d in diagnostics:
        if "error" in d:
            lines.append(f"⚠️ *{d['symbol']}* — erro: {d['error'][:60]}")
            lines.append("")
            continue

        price = d["price"]
        ema200 = d["ema200"]
        rsi = d["rsi"]
        bullet = _trend_emoji(rsi, price, ema200)

        ema_status = ""
        if ema200 == ema200 and price == price:
            ema_status = " (preço acima ✅)" if price > ema200 else " (preço abaixo ⚠️)"

        lines.append(f"{bullet} *{d['symbol']}*")
        lines.append(f"   💰 {_fmt_price(price)}")
        lines.append(f"   📈 RSI(14): `{_fmt(rsi, 1)}`  |  MACD: `{_fmt(d['macd'], 2)}`")
        lines.append(f"   📉 Signal: `{_fmt(d['macd_signal'], 2)}`  |  Hist: `{_fmt(d['macd_hist'], 2)}`")
        lines.append(f"   🎯 EMA200: {_fmt_price(ema200)}{ema_status}")
        lines.append("")

    lines.append(f"🎯 *Sinais qualificados:* {signals_count}")

    return "\n".join(lines)
