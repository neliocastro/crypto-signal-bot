"""
coleta.py - coleta automatica da auditoria do crypto-signal-bot (skill auditoria-crypto-bot).

SO LE: nao altera state/, nao commita, nao envia ordem, nao usa segredo.
Chama a API PUBLICA da Gate.io (tickers) so para precos; se a rede bloquear, segue sem.

USO (na raiz do repositorio):
    python .claude/skills/auditoria-crypto-bot/scripts/coleta.py
    python .claude/skills/auditoria-crypto-bot/scripts/coleta.py --dias 7 --ultimas 10 --sem-testes

Saida: markdown no stdout, com marcadores [OK] / [ATENCAO] / [FALHA] / [NAO VERIFICADO]
que a skill usa para montar o relatorio.
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.getcwd()
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)


def p(*a):
    print(*a)


def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 99, str(e)


def parse_ts(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except Exception:  # noqa: BLE001
        return None


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"_erro": "linha invalida", "_raw": line[:120]})
    return out


# ---------------------------------------------------------------- 1. codigo
def secao_codigo(sem_testes):
    p("## 1. Codigo e testes")
    rc, out = run([sys.executable, "-m", "py_compile", *sorted(glob.glob("bot/*.py"))])
    p(f"- {'[OK]' if rc == 0 else '[FALHA]'} py_compile bot/*.py" + ("" if rc == 0 else f"\n```\n{out[-800:]}\n```"))
    if sem_testes:
        p("- [NAO VERIFICADO] testes pulados (--sem-testes)")
        return
    falhas = 0
    for t in sorted(glob.glob("tests/test_*.py")):
        rc, out = run([sys.executable, t])
        if rc != 0:
            falhas += 1
            p(f"- [FALHA] {t}\n```\n{out[-1200:]}\n```")
    n_py = len(glob.glob("tests/test_*.py"))
    p(f"- {'[OK]' if falhas == 0 else '[FALHA]'} testes Python: {n_py - falhas}/{n_py} passaram")
    php = shutil.which("php")
    php_tests = sorted(glob.glob("tests/test_*.php"))
    if php:
        pf = 0
        for t in php_tests:
            rc, out = run([php, t])
            if rc != 0:
                pf += 1
                p(f"- [FALHA] {t}\n```\n{out[-1200:]}\n```")
        p(f"- {'[OK]' if pf == 0 else '[FALHA]'} testes PHP: {len(php_tests) - pf}/{len(php_tests)} passaram")
        for f in sorted(glob.glob("server/*.php")):
            rc, out = run([php, "-l", f])
            if rc != 0:
                p(f"- [FALHA] php -l {f}: {out.strip()[-300:]}")
    else:
        p("- [NAO VERIFICADO] PHP nao instalado: testes PHP e php -l ficam para o workflow `checks`")
    try:
        import yaml  # noqa: F401
        rc, out = run([sys.executable, "scripts/check_workflows.py"])
        p(f"- {'[OK]' if rc == 0 else '[FALHA]'} check_workflows.py" + ("" if rc == 0 else f"\n```\n{out[-800:]}\n```"))
    except ImportError:
        p("- [NAO VERIFICADO] check_workflows.py (PyYAML ausente)")


# ------------------------------------------------------------- 2. cadencia
def secao_cadencia(dias):
    p("\n## 2. Cadencia do scan")
    rt = {}
    try:
        rt = json.load(open("state/runtime_config.json", encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        p(f"- [FALHA] nao li state/runtime_config.json: {e}")
    last = parse_ts(rt.get("last_scan_utc"))
    if last:
        idade = (NOW - last).total_seconds() / 60
        tag = "[OK]" if idade <= 30 else "[FALHA]"
        p(f"- {tag} ultimo scan: {last:%Y-%m-%d %H:%M} UTC (ha {idade:.0f} min; >30 min = scan parado)")
    p(f"- {'[ATENCAO]' if rt.get('paused') else '[OK]'} paused = {rt.get('paused')}; "
      f"intervalo = {rt.get('scan_interval_min')} min; watchlist runtime = {rt.get('watchlist')}")

    rc, out = run(["git", "log", f"--since={dias} days ago", "--format=%ct", "--", "state/"])
    ts = sorted(int(x) for x in out.split() if x.isdigit()) if rc == 0 else []
    if len(ts) < 2:
        p(f"- [NAO VERIFICADO] historico git insuficiente ({len(ts)} commits de state/ em {dias} dias;"
          " clone raso? rode `git fetch --shallow-since=...`)")
        return
    gaps = sorted(((b - a) / 60, a) for a, b in zip(ts, ts[1:]))
    med = gaps[len(gaps) // 2][0]
    grandes = [(g, a) for g, a in gaps if g > 30]
    p(f"- {'[OK]' if not grandes else '[ATENCAO]'} {len(ts)} commits de state/ em {dias} dias; "
      f"intervalo mediano {med:.1f} min; lacunas > 30 min: {len(grandes)}")
    for g, a in sorted(grandes, reverse=True)[:8]:
        p(f"  - {g:.0f} min a partir de {dt.datetime.fromtimestamp(a, UTC):%Y-%m-%d %H:%M} UTC")
    p("- Obs.: commits do state/ sao um proxy da cadencia; a fonte direta e `gh run list --workflow main.yml`.")


# --------------------------------------------------------------- 3. config
def secao_config():
    p("\n## 3. Configuracao (bot/config.py, fonte unica)")
    sys.path.insert(0, ROOT)
    try:
        from bot import config as c
    except Exception as e:  # noqa: BLE001
        p(f"- [FALHA] nao importei bot/config.py: {e}")
        return
    g = lambda n: getattr(c, n, "<ausente>")  # noqa: E731
    p(f"- EXECUTION_ENABLED={g('EXECUTION_ENABLED')}  EXECUTION_DRY_RUN={g('EXECUTION_DRY_RUN')}  "
      f"(True/False = dinheiro real)")
    teto = g("EXECUTION_MAX_NOTIONAL_USDT")
    p(f"- {'[OK]' if teto == 10.0 else '[ATENCAO]'} teto por ordem = US$ {teto} (D-024: US$ 10 ate o degrau aprovar)")
    p(f"- EXECUTION_DAILY_LOSS_STOP=US$ {g('EXECUTION_DAILY_LOSS_STOP')}  MAX_TRADES_DAY={g('EXECUTION_MAX_TRADES_DAY')}"
      f"  MAX_OPEN={g('EXECUTION_MAX_OPEN')}  TPSL_ENABLED={g('EXECUTION_TPSL_ENABLED')}")
    p(f"- {'[OK]' if g('BREAKOUT_ENABLED') is False else '[ATENCAO]'} BREAKOUT_ENABLED={g('BREAKOUT_ENABLED')} (D-013: desligado)")
    p(f"- PAPER_EVAL_ENABLED={g('PAPER_EVAL_ENABLED')} (D-046: desligado)  DASHBOARD_ENABLED={g('DASHBOARD_ENABLED')}")
    p(f"- DCA_ENABLED={g('DCA_ENABLED')}  DCA_ASSETS={g('DCA_ASSETS')}  MARE_ALTA_TRAILING_ENABLED={g('MARE_ALTA_TRAILING_ENABLED')}"
      f"  MARE_ALTA_PARTIAL_TP_ENABLED={g('MARE_ALTA_PARTIAL_TP_ENABLED')}")
    p(f"- WATCHLIST (config) = {g('WATCHLIST')}")
    p("- A skill compara estes valores com as decisoes do memoria.md; divergencia = PARAR E AVISAR.")


# ------------------------------------------------------------- 4. posicoes
def secao_posicoes(ultimas):
    p("\n## 4. Posicoes e ultimas operacoes")
    pos = read_jsonl("state/positions.jsonl")
    invalidas = [x for x in pos if "_erro" in x]
    if invalidas:
        p(f"- [FALHA] {len(invalidas)} linha(s) invalida(s) em positions.jsonl")
    abertas = [x for x in pos if str(x.get("status", "")).startswith("open")]
    if abertas:
        p(f"- [ATENCAO] {len(abertas)} posicao(oes) viva(s) (status open*):")
        for x in abertas:
            semstop = "" if x.get("sl_order_id") else "  **SEM sl_order_id**"
            p(f"  - {x.get('symbol')} qtd {x.get('base_qty')} entrada {x.get('entry_price')} SL {x.get('sl_price')} "
              f"TP {x.get('tp_price')} aberta {str(x.get('opened_at'))[:16]} ({x.get('status')}){semstop}")
    else:
        p("- [OK] nenhuma posicao viva do bot (status open*)")

    try:
        guard = json.load(open("state/execution_guard.json", encoding="utf-8"))
        p(f"- execution_guard: dia {guard.get('day')}, trades_today {guard.get('trades_today')}, "
          f"open_positions (espelho informativo, +1 na hora do envio) {guard.get('open_positions')}, "
          f"realized_loss_today {guard.get('realized_loss_today')} (real hoje: {len(abertas)} abertas)")
    except Exception as e:  # noqa: BLE001
        p(f"- [ATENCAO] execution_guard.json ilegivel: {e}")

    fechadas = [x for x in pos if str(x.get("status", "")).startswith("closed") and x.get("closed_at")]
    fechadas.sort(key=lambda x: str(x.get("closed_at")))
    p(f"\n### Ultimos {ultimas} fechamentos (positions.jsonl)")
    p("| Fechou (UTC) | Ativo | Estrategia | Entrada | Saida | Status | P&L est. | base |")
    p("|---|---|---|---|---|---|---|---|")
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from placar import trade_pnl, _strategy   # mesmo calculo do placar (D-034)
    except Exception:  # noqa: BLE001
        trade_pnl = _strategy = None
    for x in fechadas[-ultimas:][::-1]:
        pnl, saida, base, estr = None, x.get("exit_price"), x.get("exit_basis") or "-", x.get("strategy") or "-"
        if trade_pnl and x.get("status") in ("closed_tp", "closed_sl"):
            try:
                pnl, _pct, saida, base = trade_pnl(x)
                estr = _strategy(x)
            except Exception:  # noqa: BLE001
                pass
        if pnl is None:
            pnl = x.get("pnl_usdt_est", x.get("pnl_usdt"))
        pnl = f"{float(pnl):+.2f}" if pnl is not None else "-"
        p(f"| {str(x['closed_at'])[:16]} | {x.get('symbol')} | {estr} | {x.get('entry_price')} | "
          f"{saida or '-'} | {x.get('status')} | {pnl} | {base} |")

    p(f"\n### Ultimas {ultimas} ordens (orders_executed.csv)")
    try:
        rows = list(csv.DictReader(open("state/orders_executed.csv", encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        p(f"- [FALHA] orders_executed.csv ilegivel: {e}")
        return
    p("| ts (UTC) | Ativo | Valor | Ref | Fill | Slippage | Status | Motivo |")
    p("|---|---|---|---|---|---|---|---|")
    for r in rows[-ultimas:][::-1]:
        slip = ""
        try:
            slip = f"{(float(r['fill_price']) / float(r['ref_price']) - 1) * 100:+.2f}%"
        except Exception:  # noqa: BLE001
            pass
        p(f"| {r['ts_utc'][:16]} | {r['symbol']} | {r['notional_usdt']} | {r['ref_price']} | {r['fill_price'] or '-'} | "
          f"{slip or '-'} | {r['status']} | {(r.get('reason') or '')[:60]} |")
    desde = (NOW - dt.timedelta(days=7)).isoformat()
    ruins = [r for r in rows if r["ts_utc"] >= desde and r["status"] not in ("filled", "blocked_by_guard")]
    p(f"- {'[OK]' if not ruins else '[ATENCAO]'} ordens nos ultimos 7 dias com status diferente de filled/blocked: {len(ruins)}")
    for r in ruins[-5:]:
        p(f"  - {r['ts_utc'][:16]} {r['symbol']} {r['status']}: {r.get('reason')}")


# ------------------------------------------------------------------ 5. DCA
def secao_dca(precos):
    p("\n## 5. DCA semanal (D-049)")
    regs = read_jsonl("state/dca.jsonl")
    if not regs:
        p("- [NAO VERIFICADO] state/dca.jsonl vazio ou ausente")
        return
    semanas = {}
    for r in regs:
        semanas.setdefault((r.get("semana"), r.get("symbol")), set()).add(r.get("status"))
    sem_fill = [k for k, v in semanas.items() if "filled" not in v]
    p(f"- {'[OK]' if not sem_fill else '[ATENCAO]'} semanas x ativo registradas: {len(semanas)}; sem `filled`: {sem_fill or 'nenhuma'}")
    try:
        from bot.dca import acumulado
    except Exception as e:  # noqa: BLE001
        p(f"- [FALHA] nao importei bot.dca.acumulado: {e}")
        return
    p("| Ativo | Compras | Investido | Qtd (sem taxa) | Custo medio | Preco agora | Valor agora | P&L aberto |")
    p("|---|---|---|---|---|---|---|---|")
    simbolos = sorted({r.get("symbol") for r in regs if r.get("symbol")})
    for s in simbolos:
        a = acumulado(regs, s)
        px = precos.get(s.replace("/", "_"))
        if px and a["qtd"]:
            val = a["qtd"] * px
            mtm = f"{val - a['investido']:+.2f} ({(val / a['investido'] - 1) * 100:+.1f}%)"
            p(f"| {s} | {a['compras']} | {a['investido']:.2f} | {a['qtd']:.8f} | {a['custo_medio']:.2f} | {px} | {val:.2f} | {mtm} |")
        else:
            cm = f"{a['custo_medio']:.2f}" if a["custo_medio"] else "-"
            p(f"| {s} | {a['compras']} | {a['investido']:.2f} | {a['qtd']:.8f} | {cm} | n/d | n/d | n/d |")
    ultimas = [r for r in regs if r.get("status") == "filled"][-2:]
    for r in ultimas:
        try:
            frac = float(r["filled_total"]) / float(r["notional_usdt"]) * 100
            if frac < 90:
                p(f"- [ATENCAO] {r['semana']} {r['symbol']}: comprou {frac:.0f}% do valor "
                  "(arredondamento do passo da Gate; conhecido em docs/pendencias.md, nao e bug)")
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------- 6. placar
def secao_placar():
    p("\n## 6. P&L do bot (scripts/placar.py, estimativa D-034)")
    for args in ([], ["--degrau"]):
        rc, out = run([sys.executable, "scripts/placar.py", *args])
        if rc != 0:
            p(f"- [FALHA] placar.py {' '.join(args)}\n```\n{out[-800:]}\n```")
        else:
            p(out.strip())
            p("")


# --------------------------------------------------------------- precos
def precos_gate():
    try:
        req = urllib.request.Request("https://api.gateio.ws/api/v4/spot/tickers",
                                     headers={"User-Agent": "crypto-signal-bot-auditoria"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        return {t["currency_pair"]: float(t["last"]) for t in data if t.get("last")}
    except Exception as e:  # noqa: BLE001
        return {"_erro": str(e)[:160]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7, help="janela da cadencia (dias)")
    ap.add_argument("--ultimas", type=int, default=8, help="quantas operacoes listar")
    ap.add_argument("--sem-testes", action="store_true")
    a = ap.parse_args()
    if not os.path.exists("bot/config.py"):
        sys.exit("Rode na raiz do crypto-signal-bot (nao achei bot/config.py).")
    rc, head = run(["git", "log", "-1", "--format=%h %ci"])
    p(f"# Coleta da auditoria - {NOW:%Y-%m-%d %H:%M} UTC (HEAD {head.strip()})\n")
    precos = precos_gate()
    erro_px = precos.pop("_erro", None)
    secao_codigo(a.sem_testes)
    secao_cadencia(a.dias)
    secao_config()
    secao_posicoes(a.ultimas)
    secao_dca(precos)
    secao_placar()
    p("\n## 7. Precos ao vivo (API publica Gate.io)")
    if erro_px:
        p(f"- [NAO VERIFICADO] API da Gate inacessivel ({erro_px}); sem P&L aberto do DCA")
    else:
        for s in ("BTC_USDT", "PAXG_USDT", "SOL_USDT", "TRX_USDT", "BNB_USDT", "HYPE_USDT"):
            p(f"- {s}: {precos.get(s, 'n/d')}")


if __name__ == "__main__":
    main()
