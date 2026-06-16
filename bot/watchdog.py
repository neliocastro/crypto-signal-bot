"""
Watchdog de cadencia (Fase D1)
==============================
Detecta quando o scan ficou tempo demais SEM rodar e avisa no Telegram.

Necessario porque o cron do GitHub foi removido: agora o disparo depende
do servidor (ineocom) + self-scheduling. Se AMBOS falharem, o scan para
silenciosamente. Este watchdog quebra esse silencio.

Defensivo: qualquer falha aqui NUNCA derruba o scan (retorna sem alarde).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# Limite padrao: se o intervalo entre scans passar disto, alerta.
# scan_interval_min e 5; usamos folga generosa p/ evitar falso positivo.
DEFAULT_MAX_GAP_MIN = 20


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def check_gap(cfg: dict[str, Any] | None,
              now_utc: datetime | None = None,
              max_gap_min: int | None = None) -> dict[str, Any]:
    """
    Compara o ultimo scan (cfg['last_scan_utc']) com agora.
    Se o gap exceder o limite, envia alerta no Telegram.

    IMPORTANTE: chamar ANTES de mark_scan_ran() sobrescrever last_scan_utc.

    Retorna dict de diagnostico (nunca levanta excecao).
    """
    result = {"alerted": False, "gap_min": None, "reason": ""}
    try:
        if not cfg:
            result["reason"] = "cfg ausente"
            return result

        now_utc = now_utc or datetime.now(timezone.utc)
        last = _parse_iso(cfg.get("last_scan_utc"))
        if last is None:
            result["reason"] = "sem last_scan_utc (primeiro scan)"
            return result

        gap_min = (now_utc - last).total_seconds() / 60.0
        result["gap_min"] = round(gap_min, 1)

        limit = int(max_gap_min if max_gap_min is not None
                    else cfg.get("watchdog_max_gap_min", DEFAULT_MAX_GAP_MIN))

        # respeita DND: se o intervalo noturno e maior, nao alarmar a toa
        if cfg.get("dnd_enabled"):
            dnd_int = int(cfg.get("dnd_interval_min", 60))
            if limit < dnd_int + 10:
                limit = dnd_int + 10

        if gap_min <= limit:
            result["reason"] = f"ok ({gap_min:.1f}min <= {limit}min)"
            return result

        # GAP excedido -> alerta
        msg = (
            "\u26a0\ufe0f *WATCHDOG \u2014 scan ficou parado*\n\n"
            f"\u23f1\ufe0f Sem rodar h\u00e1 *{gap_min:.0f} min* "
            f"(limite: {limit} min)\n"
            "\U0001f50c Disparo depende do servidor (ineocom) + self-scheduling.\n"
            "\U0001f50d Verifique: cron do cPanel e o secret SELF_DISPATCH_PAT.\n\n"
            "_Este scan rodou normalmente \u2014 alerta \u00e9 sobre o intervalo anterior._"
        )
        try:
            from .telegram_sender import send
            ok = send(msg)
            result["alerted"] = bool(ok)
            result["reason"] = f"GAP {gap_min:.1f}min > {limit}min \u2014 alerta enviado={ok}"
            log.warning("\u26a0\ufe0f Watchdog: gap %.1fmin > %dmin \u2014 alerta Telegram=%s",
                        gap_min, limit, ok)
        except Exception as e:  # noqa: BLE001
            result["reason"] = f"GAP detectado mas falha ao enviar: {e}"
            log.error("Watchdog: falha ao enviar alerta: %s", e)
        return result
    except Exception as e:  # noqa: BLE001
        result["reason"] = f"erro interno (ignorado): {e}"
        log.warning("Watchdog erro interno (ignorado): %s", e)
        return result
