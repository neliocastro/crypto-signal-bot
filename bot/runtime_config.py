"""
Runtime Config (Fase C4 MVP)
============================
Lê e grava state/runtime_config.json. Esta é a fonte da verdade
para parâmetros que podem mudar SEM commit manual (via Telegram).

Tudo aqui é defensivo: se o JSON for inválido ou estiver ausente,
retornamos os defaults — o bot continua operando.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Resolve sempre a partir da raiz do repo
_REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _REPO_ROOT / "state" / "runtime_config.json"

DEFAULTS: dict[str, Any] = {
    "scan_interval_min": 15,
    "watchlist": [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "TRX/USDT",
        "BNB/USDT", "LINK/USDT", "HYPE/USDT", "AAVE/USDT", "PAXG/USDT",
    ],
    "dnd_enabled": False,
    "dnd_start_hour_local": 23,
    "dnd_end_hour_local": 7,
    "dnd_interval_min": 60,
    "timezone": "America/Bahia",
    "paused": False,
    "last_scan_utc": None,
    "_updated_at_utc": None,
    "_updated_by": "init",
}


def load() -> dict[str, Any]:
    """Carrega config; preenche defaults para chaves ausentes."""
    if not CONFIG_PATH.exists():
        log.info("runtime_config.json ausente — usando defaults em memoria")
        return dict(DEFAULTS)
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data or {})
        return merged
    except Exception as e:                                       # noqa: BLE001
        log.warning("Falha ao ler runtime_config.json (%s) — usando defaults", e)
        return dict(DEFAULTS)


def save(cfg: dict[str, Any], updated_by: str = "system") -> None:
    """Persiste config com metadados de auditoria."""
    cfg = dict(cfg)
    cfg["_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["_updated_by"] = updated_by
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(CONFIG_PATH)
    log.info("runtime_config.json gravado por %s", updated_by)


def _in_window(hour: int, start: int, end: int) -> bool:
    """True se hour cair na janela [start, end). Suporta cruzamento de meia-noite."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # janela que cruza meia-noite (ex: 23..7)
    return hour >= start or hour < end


def should_run_now(cfg: dict[str, Any], now_utc: datetime | None = None) -> tuple[bool, str]:
    """
    Decide se o scan deve rodar agora ou pular.
    Retorna (rodar?, motivo).

    Regras:
      1. paused=True  -> nunca roda
      2. last_scan_utc ausente -> roda (primeiro scan)
      3. DND ativo + hora local dentro da janela -> usa dnd_interval_min
      4. caso contrario -> usa scan_interval_min
      5. Tolerancia de -30s para evitar perder ticks por jitter do cron
    """
    if cfg.get("paused"):
        return False, "bot pausado"

    now_utc = now_utc or datetime.now(timezone.utc)
    last_iso = cfg.get("last_scan_utc")
    if not last_iso:
        return True, "primeiro scan"

    try:
        last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception:
        return True, "last_scan_utc invalido — rodando"

    minutes_since = (now_utc - last).total_seconds() / 60.0

    # Determina intervalo efetivo (DND ou normal)
    interval = int(cfg.get("scan_interval_min", 15))
    if cfg.get("dnd_enabled"):
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(cfg.get("timezone", "America/Bahia"))
            local_hour = now_utc.astimezone(tz).hour
            if _in_window(local_hour, int(cfg.get("dnd_start_hour_local", 23)),
                          int(cfg.get("dnd_end_hour_local", 7))):
                interval = int(cfg.get("dnd_interval_min", 60))
        except Exception as e:                                   # noqa: BLE001
            log.warning("DND timezone falhou (%s) — usando intervalo normal", e)

    # tolerancia de 30s contra jitter do cron
    if minutes_since >= (interval - 0.5):
        return True, f"intervalo {interval}min atingido ({minutes_since:.1f}min)"
    return False, f"aguardando — proximo em {interval - minutes_since:.1f}min"


def mark_scan_ran(updated_by: str = "scan") -> None:
    """Atualiza last_scan_utc para agora."""
    cfg = load()
    cfg["last_scan_utc"] = datetime.now(timezone.utc).isoformat()
    save(cfg, updated_by=updated_by)
