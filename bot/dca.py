"""
dca.py - DCA semanal SEM TP/SL (D-049, 2026-10-23).

Compra um valor fixo por semana em cada ativo de config.DCA_ASSETS, a mercado, a partir do
dia/hora configurados (o primeiro scan depois disso). O bot NUNCA vende o DCA.

Por que fora do positions.jsonl: as compras DCA ficam em state/dca.jsonl. Assim nao contam
na trava de "1 posicao viva por ativo" (D-022) e nao entram no trailing, no OCO nem na
renovacao de SL, que so olham o positions.jsonl. A Tendencia Diaria no BTC segue igual.

Seguranca:
  - uma tentativa por ativo por semana ISO (signal_id = dca-<PAR>-<ano>W<semana>); se falhar,
    NAO tenta de novo na mesma semana (uma resposta perdida poderia virar compra dobrada);
  - teto mensal por ativo (DCA_MONTHLY_CAP_USDT) alem do teto por ordem do executor (D-024);
  - passa pelas travas normais do executor (perda do dia, ordens por dia, teto por ordem);
  - o relay so aceita compra sem TP/SL com strategy == "DCA" e ativo na whitelist do FIX 11.
Kill-switch: config.DCA_ENABLED. Qualquer falha e contida: nunca derruba o scan.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone

log = logging.getLogger("bot.dca")

TAXA = 0.001   # a Gate desconta 0,1% da moeda comprada (estimativa da quantidade)


def _cfg(nome, padrao):
    try:
        from . import config as c
        return getattr(c, nome)
    except Exception:
        return padrao


# ------------------------------- regras puras --------------------------------
def semana_iso(dt: datetime) -> str:
    ano, sem, _ = dt.isocalendar()
    return "%dW%02d" % (ano, sem)


def hora_de_comprar(dt: datetime, dia_semana: int, hora_utc: int) -> bool:
    """True a partir do dia/hora da semana (UTC). Se o scan daquele dia falhar, compra depois."""
    return dt.weekday() > dia_semana or (dt.weekday() == dia_semana and dt.hour >= hora_utc)


def ler_registro(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    out = []
    try:
        with open(caminho, encoding="utf-8") as fh:
            for linha in fh:
                linha = linha.strip()
                if linha:
                    try:
                        out.append(json.loads(linha))
                    except Exception:
                        continue
    except Exception:
        log.exception("falha ao ler %s", caminho)
    return out


def ja_tentou(registros: list, simbolo: str, semana: str) -> bool:
    return any(r.get("symbol") == simbolo and r.get("semana") == semana for r in registros)


def gasto_no_mes(registros: list, simbolo: str, ano_mes: str) -> float:
    return sum(float(r.get("notional_usdt") or 0) for r in registros
               if r.get("symbol") == simbolo and r.get("status") == "filled"
               and str(r.get("ts", "")).startswith(ano_mes))


def acumulado(registros: list, simbolo: str) -> dict:
    """Compras confirmadas: quantidade estimada (ja sem a taxa), investido e custo medio."""
    n, investido, qtd = 0, 0.0, 0.0
    for r in registros:
        if r.get("symbol") != simbolo or r.get("status") != "filled":
            continue
        try:
            total, preco = float(r.get("filled_total") or 0), float(r.get("fill_price") or 0)
        except (TypeError, ValueError):
            continue
        if total <= 0 or preco <= 0:
            continue
        n += 1
        investido += total
        qtd += total / preco * (1 - TAXA)
    return {"compras": n, "investido": investido, "qtd": qtd,
            "custo_medio": (investido / qtd) if qtd > 0 else None}


def montar_ordem(simbolo: str, valor: float, semana: str, preco_ref) -> dict:
    return {
        "signal_id": "dca-%s-%s" % (simbolo.replace("/", "_"), semana),
        "symbol": simbolo,
        "side": "buy",
        "type": "market",
        "strategy": "DCA",                 # o relay so aceita compra sem TP/SL com este valor (FIX 11)
        "notional_usdt": float(valor),
        "ref_price": preco_ref,
        "sl_price": None,                  # DCA nunca leva stop nem alvo (D-049)
        "tp_price": None,
        "dry_run": bool(_cfg("EXECUTION_DRY_RUN", True)),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ------------------------------- efeitos --------------------------------
def _preco_gate(simbolo: str):
    """Ultimo preco publico da Gate (so referencia de escorregamento; o relay usa o seu)."""
    try:
        url = "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=" + simbolo.replace("/", "_")
        with urllib.request.urlopen(url, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        return float(d[0]["last"])
    except Exception:
        return None


def _gravar(caminho: str, rec: dict) -> None:
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _avisar(notify, texto: str) -> None:
    if notify:
        try:
            notify(texto)
        except Exception:
            pass


def run_dca(agora=None, notify=None, enviar=None, guardas=None, preco=None) -> list:
    """Executa o DCA da semana. Devolve uma lista de resultados por ativo tentado."""
    if not _cfg("DCA_ENABLED", False):
        return []
    agora = agora or datetime.now(timezone.utc)
    if not hora_de_comprar(agora, int(_cfg("DCA_WEEKDAY", 0)), int(_cfg("DCA_HOUR_UTC", 13))):
        return []
    from . import executor as ex
    if not getattr(ex, "EXECUTION_ENABLED", False):
        return []
    enviar = enviar or ex.send_order
    guardas = guardas or ex.check_guards
    preco = preco or _preco_gate
    caminho = _cfg("DCA_FILE", "state/dca.jsonl")
    teto_mes = float(_cfg("DCA_MONTHLY_CAP_USDT", 50.0))
    semana, ano_mes = semana_iso(agora), agora.strftime("%Y-%m")
    resultados = []
    for simbolo, valor in (_cfg("DCA_ASSETS", {}) or {}).items():
        try:
            regs = ler_registro(caminho)
            if ja_tentou(regs, simbolo, semana):
                continue
            base = {"semana": semana, "symbol": simbolo, "notional_usdt": float(valor),
                    "ts": agora.isoformat()}
            if gasto_no_mes(regs, simbolo, ano_mes) + float(valor) > teto_mes:
                rec = dict(base, status="teto_mensal", reason="teto de US$ %.0f/mes atingido" % teto_mes)
                _gravar(caminho, rec)
                _avisar(notify, "⚠️ DCA %s: teto mensal de US$ %.0f atingido; nada comprado nesta semana."
                        % (simbolo, teto_mes))
                resultados.append(rec)
                continue
            ordem = montar_ordem(simbolo, valor, semana, preco(simbolo))
            # Grava a TENTATIVA antes de enviar: se algo quebrar depois do envio, o proximo scan
            # ve que a semana ja foi tentada e nao compra de novo.
            _gravar(caminho, dict(base, signal_id=ordem["signal_id"], status="tentativa"))
            ex._append_jsonl(ex.PAPER_TRADES_FILE, {"event": "intent", **ordem})
            ok, motivo = guardas(ordem)
            if not ok:
                res = {"status": "blocked_by_guard", "reason": motivo}
            else:
                res = enviar(ordem) or {"status": "error", "reason": "sem resposta do relay"}
                if res.get("status") in ("filled", "accepted", "ok"):
                    ex._register_sent_order()
            ex._append_jsonl(ex.PAPER_TRADES_FILE, {"event": "relay_response", "signal_id": ordem["signal_id"],
                                                    "result": res, "ts": agora.isoformat()})
            ex._append_execution_csv(ordem, res)
            rec = dict(base, signal_id=ordem["signal_id"], status=res.get("status"),
                       reason=res.get("reason"), fill_price=res.get("fill_price"),
                       filled_total=res.get("filled_total"), order_id=res.get("order_id"))
            _gravar(caminho, rec)
            resultados.append(rec)
            if rec["status"] == "filled":
                a = acumulado(ler_registro(caminho), simbolo)
                moeda = simbolo.split("/")[0]
                _avisar(notify, "\U0001F9FA DCA semanal: comprou US$ %.0f de %s a %s.\nAcumulado: %.8f %s em %d compra(s), "
                        "custo medio %.2f (US$ %.2f investidos). O bot nunca vende o DCA."
                        % (float(valor), simbolo, rec["fill_price"], a["qtd"], moeda, a["compras"],
                           a["custo_medio"] or 0.0, a["investido"]))
            else:
                _avisar(notify, "⚠️ DCA %s NAO comprou nesta semana (%s: %s). Sem nova tentativa ate a "
                        "proxima semana." % (simbolo, rec["status"], rec.get("reason") or "-"))
        except Exception:
            log.exception("DCA %s falhou (ignorado; sem nova tentativa automatica)", simbolo)
    return resultados
