"""
Gera e envia ao Telegram um resumo diario do crypto-signal-bot.

Le os estados locais do repo:
  - state/orders_executed.csv   (ordens das ultimas 24h)
  - state/runtime_config.json   (ultimo scan, watchlist, F&G se gravado)
  - state/paper_positions.json  (PnL paper p/ checar stop diario)

Uso:
  python -m bot.reports.daily_summary

Credenciais do Telegram vem do ambiente (mesmos secrets do bot):
TELEGRAM_TOKEN / TELEGRAM_CHAT_ID, via bot.telegram_sender.send().
"""
from __future__ import annotations

import os
import csv
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from bot import telegram_sender

log = logging.getLogger(__name__)

BR = timezone(timedelta(hours=-3))  # America/Bahia (sem DST)
STOP_DIARIO_USD = float(os.getenv("DAILY_LOSS_STOP_USD", "10"))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, "state")


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def build_summary(now_utc=None) -> str:
    now_utc = now_utc or datetime.now(timezone.utc)
    now_br = now_utc.astimezone(BR)
    cutoff = now_utc - timedelta(hours=24)

    orders = _read_csv(os.path.join(STATE, "orders_executed.csv"))
    runtime = _read_json(os.path.join(STATE, "runtime_config.json"), {})
    paper = _read_json(os.path.join(STATE, "paper_positions.json"), {})

    recent = []
    for r in orders:
        ts = _parse_ts(r.get("ts_utc"))
        if ts and ts >= cutoff:
            r["_ts"] = ts
            recent.append(r)

    real_filled = sum(1 for r in recent if r.get("status") == "filled" and r.get("mode") == "REAL")
    blocked = sum(1 for r in recent if r.get("status") in
                  ("blocked_by_guard", "rejected_by_exchange", "rejected", "skipped"))

    pnl_24h = 0.0
    for p in paper.get("closed", []):
        ts = _parse_ts(p.get("closed_at"))
        if ts and ts >= cutoff:
            pnl_24h += float(p.get("pnl_usdt", 0.0) or 0.0)
    stop_hit = pnl_24h <= -STOP_DIARIO_USD

    fg = runtime.get("fear_greed") or {}
    fg_score = fg.get("score", "n/d")
    fg_label = fg.get("label", "")
    fg_emoji = fg.get("emoji", "🌡")
    last_scan = _parse_ts(runtime.get("last_scan_utc"))
    last_scan_s = last_scan.astimezone(BR).strftime("%d/%m %H:%M") if last_scan else "n/d"
    n_signals = runtime.get("last_signals_count", "n/d")
    watch = runtime.get("watchlist", [])

    L = []
    L.append("📊 *RESUMO DIÁRIO — Crypto Signal Bot*")
    L.append(f"🗓 {now_br.strftime('%d/%m/%Y %H:%M')} BRT (janela últimas 24h)\n")
    L.append(f"{fg_emoji} *Fear & Greed:* {fg_score} — {fg_label}".rstrip(" —"))
    L.append(f"🔄 Último scan: {last_scan_s} BRT · sinais gerados: {n_signals}")
    L.append(f"🎯 Watchlist: {len(watch)} pares · TF={runtime.get('timeframe','1h')}"
             f" · scan a cada {runtime.get('scan_interval_min','?')}min")
    L.append(f"⏸ Bot pausado: {'sim' if runtime.get('paused') else 'não'}")
    L.append(f"🚨 Stop diário −${STOP_DIARIO_USD:.0f}: "
             f"{'ATINGIDO ❌' if stop_hit else 'não atingido ✅'} "
             f"(PnL 24h paper: ${pnl_24h:+.2f})\n")
    L.append("━━━━━━━━━━━━━━━━━━━━")

    if not recent:
        L.append("ℹ️ *Nenhuma operação nas últimas 24h.*")
        L.append("✅ Bot ativo e monitorando — sem disparos no período.")
    else:
        L.append(f"📈 *Ordens (24h):* {len(recent)} · ✅ REAL filled: {real_filled}"
                 f" · 🛡 bloqueadas/rejeitadas: {blocked}\n")
        by_sig = defaultdict(list)
        for r in recent:
            by_sig[r.get("signal_id", "—")].append(r)
        for sig, items in by_sig.items():
            items.sort(key=lambda x: x["_ts"])
            h = items[0]
            L.append(f"🔖 `{sig}`")
            L.append(f"   {h.get('symbol','?')} {str(h.get('side','')).upper()}"
                     f" · notional ${h.get('notional_usdt','?')}")
            for it in items:
                t = it["_ts"].astimezone(BR).strftime("%d/%m %H:%M")
                slp = f" · slip={it['slippage_pct']}%" if it.get("slippage_pct") else ""
                px = it.get("fill_price") or "—"
                rsn = f" — _{it['reason']}_" if it.get("reason") else ""
                L.append(f"   • {t} | `{it.get('status','?')}` | px={px}{slp}"
                         f" [{it.get('mode','?')}]{rsn}")
            L.append("")

    return "\n".join(L).rstrip()


def main():
    logging.basicConfig(level=logging.INFO)
    text = build_summary()
    log.info("Resumo gerado (%d chars). Enviando ao Telegram...", len(text))
    ok = telegram_sender.send(text)
    log.info("Envio %s", "OK ✅" if ok else "FALHOU ❌")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
