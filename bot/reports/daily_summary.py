"""
Resumo diario do Crypto Signal Bot -> Telegram.

Le state/orders_executed.csv + state/runtime_config.json + state/paper_positions.json,
monta um resumo das ultimas 24h e envia via bot.telegram_sender.send().

Uso:
    python -m bot.reports.daily_summary
"""
from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("bot.reports.daily_summary")

_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE = _ROOT / "state"
BR = timezone(timedelta(hours=-3))  # America/Bahia (sem DST)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _parse_ts(s: str):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def build_summary(now_utc: datetime | None = None) -> str:
    now_utc = now_utc or datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)
    now_local = now_utc.astimezone(BR)

    rows = _read_csv(_STATE / "orders_executed.csv")
    runtime = _read_json(_STATE / "runtime_config.json", {})
    paper = _read_json(_STATE / "paper_positions.json", {})

    recent = []
    for r in rows:
        ts = _parse_ts(r.get("ts_utc", ""))
        if ts and ts >= cutoff:
            r["_ts"] = ts
            recent.append(r)

    fg = runtime.get("fear_greed") or {}
    fg_score = fg.get("score", "n/d")
    fg_label = fg.get("label", "")
    fg_emoji = fg.get("emoji", "")
    signals_count = runtime.get("last_signals_count", "n/d")

    last_scan = _parse_ts(runtime.get("last_scan_utc", ""))
    last_scan_s = last_scan.astimezone(BR).strftime("%d/%m %H:%M") if last_scan else "n/d"
    watch = runtime.get("watchlist") or []
    interval = runtime.get("scan_interval_min", "?")
    paused = runtime.get("paused", False)

    pnl_24h = 0.0
    for p in paper.get("closed", []):
        ts = _parse_ts(p.get("closed_at", ""))
        if ts and ts >= cutoff:
            pnl_24h += float(p.get("pnl_usdt", 0.0) or 0.0)
    stop_hit = pnl_24h <= -10.0

    real_filled = sum(1 for r in recent if r.get("status") == "filled" and r.get("mode") == "REAL")
    blocked = sum(1 for r in recent if r.get("status") in ("blocked_by_guard", "rejected_by_exchange", "skipped"))

    L = []
    L.append("\U0001F4CA *RESUMO DIARIO - Crypto Signal Bot*")
    L.append(f"\U0001F5D3 {now_local.strftime('%d/%m/%Y %H:%M')} BRT (ultimas 24h)\n")
    L.append(f"{fg_emoji} *Fear & Greed:* {fg_score} {('- ' + fg_label) if fg_label else ''}".strip())
    L.append(f"\U0001F504 Ultimo scan: {last_scan_s} BRT | sinais no scan: {signals_count}")
    L.append(f"\U0001F3AF Watchlist: {len(watch)} pares | scan a cada {interval}min")
    L.append(f"\u23F8 Bot pausado: {'sim' if paused else 'nao'}")
    L.append(f"\U0001F6A8 Stop diario -$10: {'ATINGIDO' if stop_hit else 'nao atingido'} (PnL 24h paper: ${pnl_24h:+.2f})\n")
    L.append("\u2501" * 18)

    if not recent:
        L.append("\u2139\uFE0F *Nenhuma operacao nas ultimas 24h.*")
        L.append("\u2705 Bot ativo e monitorando - sem disparos no periodo.")
    else:
        L.append(f"\U0001F4C8 *Ordens (24h):* {len(recent)} | \u2705 REAL filled: {real_filled} | \U0001F6E1 bloqueadas/rejeitadas: {blocked}\n")
        by_sig = defaultdict(list)
        for r in recent:
            by_sig[r.get("signal_id", "?")].append(r)
        for sig, items in by_sig.items():
            items.sort(key=lambda x: x["_ts"])
            h = items[0]
            L.append(f"\U0001F516 `{sig}`")
            L.append(f"   {h.get('symbol','?')} {h.get('side','').upper()} | notional ${h.get('notional_usdt','?')}")
            for it in items:
                t = it["_ts"].astimezone(BR).strftime("%d/%m %H:%M")
                slp = f" | slip={it['slippage_pct']}%" if it.get("slippage_pct") else ""
                px = it.get("fill_price") or "-"
                rsn = f" - {it['reason']}" if it.get("reason") else ""
                L.append(f"   - {t} | {it.get('status','?')} | px={px}{slp} [{it.get('mode','?')}]{rsn}")
            L.append("")

    return "\n".join(L)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-7s | %(message)s",
                        datefmt="%H:%M:%S")
    text = build_summary()
    log.info("Resumo diario montado (%d chars).", len(text))
    try:
        from bot.telegram_sender import send
        ok = send(text)
        log.info("Resumo diario enviado ao Telegram: %s", ok)
        return 0 if ok else 1
    except Exception:
        import traceback
        log.error("Falha ao enviar resumo diario:\n%s", traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
