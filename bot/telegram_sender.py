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