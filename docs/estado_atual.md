# Estado Atual do Bot — Consolidado (ago/2026)

> Documento de referencia do roteamento e da camada de execucao vigentes no
> `main`. **Atualizado em 2026-08-23** apos auditoria direta do codigo
> (`config.py`, `strategies.py`, `mare_alta.py`, `main.py`).
> Mapa detalhado de estrategias: **`docs/mapa_estrategias.md`** (fonte primaria).

## Roteamento por ativo (producao) — 1 token = 1 trilho

| Ativo | Estrategia que EXECUTA | Observacao |
|---|---|---|
| BTC | Mare Alta D1 | validado no walk-forward |
| ETH | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| SOL | Mare Alta D1 | validado no walk-forward |
| XRP | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| TRX | Mare Alta D1 | validado no walk-forward |
| BNB | Mare Alta D1 | validado no walk-forward |
| HYPE | Breakout/Tendencia (lb=30/atr=2.5) | fast-path dedicado |
| PAXG | Acumulacao RSI (BUY-only) | fora do trailing (nao registra stop) |

Watchlist (8): BTC, ETH, SOL, XRP, TRX, BNB, HYPE, PAXG.
**LINK e AAVE nao estao mais na watchlist** (reprovados na reavaliacao de
2026-08-12; ver comentario em `config.py`).

### A "ponta solta do LINK" foi RESOLVIDA

A versao anterior deste documento registrava que o LINK gerava sinal pelo Mare
Alta **e** pelo MACD-only 1h. Isso deixou de existir: LINK saiu da watchlist e
do universo do Mare Alta. Alem disso, a trava de roteamento do `main.py`
(L226-252) garante que **nenhum** ativo execute por dois trilhos.

## Mare Alta D1 — universo atual (6 ativos)

```python
MARE_ALTA_UNIVERSE = ["BTC/USDT", "ETH/USDT", "SOL/USDT",
                      "XRP/USDT", "TRX/USDT", "BNB/USDT"]
```

- `MARE_ALTA_ENABLED = True`, `MARE_ALTA_SHADOW_MODE = False` (producao real).
- Entrada (D1, vela fechada): MACD cruza acima do sinal + EMA9>EMA21.
- Saida: stop 2.5xATR -> TP1 +10% (50%) -> breakeven + trailing 3.0xATR.
- Universo proprio + `fetch_ohlcv` proprio: **nao depende da WATCHLIST**.

### Nota de risco (ETH/XRP)
ETH e XRP foram **reprovados no walk-forward original** e entraram por decisao
de negocio. O docstring do modulo ainda registra: *"Universo validado: BTC,
SOL, TRX, BNB (ETH e XRP reprovados nesta logica)"*. Acompanhar de perto.

## MACD-only 1h — roda, mas NAO executa

`ACTIVE_PROFILE = "agressivo"` com `approved_symbols = None` faz o MACD-only
gerar sinal para os 6 ativos do Mare Alta. Esses sinais sao **descartados** pelo
filtro de roteamento do `main.py` (nao viram Telegram nem ordem). E desperdicio
de CPU, nao risco financeiro. `MACD_ONLY_EXCLUDE = {"PAXG/USDT"}`.

A estrategia "Integrada Curto Prazo" (perfil `balanceado`) esta **inalcancavel**
hoje: os tres fast-paths do `evaluate_signal` retornam antes do caminho normal.

## Trailing (mare_alta_trailing.py)

- `MARE_ALTA_SYMBOLS = []` -> mira **todos** os ativos com posicao registrada.
- PAXG fica de fora por arquitetura (acumulacao BUY-only, sem stop p/ trailar).
- Catraca: o stop so SOBE (cria novo -> confirma -> deleta antigo; se falhar,
  o antigo e mantido).

## Camada de execucao Gate.io — GO-LIVE REAL (canario)

> **Atencao: o bot envia ORDENS REAIS.** Go-live minimo com travas rigidas nos
> DOIS lados (Python e PHP).

| Flag | Valor | Efeito |
|---|---|---|
| `EXECUTION_ENABLED` | `True` | camada ativa |
| `EXECUTION_DRY_RUN` | `False` | ordens reais via relay |
| `EXECUTION_RELAY_URL` | `https://ineo.com.br/cryptosignals/execute.php` | braco PHP live (HMAC + IP whitelist) |
| `EXECUTION_PCT` | `0.02` | 2% do saldo por ordem |
| `EXECUTION_MAX_NOTIONAL_USDT` | **`10.0`** | teto por ordem (DEGRAU 2 desde 2026-08-12; era 5.0) |
| `EXECUTION_MIN_NOTIONAL_USDT` | `3.0` | piso (Gate.io rejeita < $3) |
| `EXECUTION_MAX_OPEN` | `10` | max posicoes simultaneas |
| `EXECUTION_MAX_TRADES_DAY` | `10` | max ordens/dia (UTC) |
| `EXECUTION_DAILY_LOSS_STOP` | `20.0` | para tudo se perder $20 no dia |
| `EXECUTION_TPSL_ENABLED` | `True` | TP/SL nativos (SL 2.0xATR, TP RR 2.0, piso stop 0.8%) |
| `REQUIRE_PROTECTION` (PHP) | `true` | compra SEM TP nem SL e RECUSADA |

Proximo degrau ($20): **so no 20o trade** com P&L>0 e PF>=1 ex-ETH.

- Modulos: `bot/executor.py`, `server/execute.php`, `bot/paper_evaluator.py`.
- Contadores diarios: `state/execution_guard.json`.

### Bugs historicos do execute.php — RESOLVIDOS
1. ~~`pair_rules()` falha -> fallback precision=6 -> HTTP 400~~ fallback por
   tabela segura (`$SAFE_PRICE_PREC`/`$SAFE_AMOUNT_PREC`) + validacao de casas.
2. ~~`ATR=0` -> compra sem TP/SL~~ `REQUIRE_PROTECTION` recusa compra nua.
3. ~~`$gate['amount']` em MARKET BUY vem em QUOTE (FIX 7)~~ base derivada do
   fill real (`filled_total / fill_price`) + sanity-check de notional.

## OCO emulado — EM PRODUCAO (2026-08-11)

```
COMPRA -> register_position() grava tp_order_id + sl_order_id
SCAN   -> oco_guard.sync() envia pares abertos ao relay
RELAY  -> oco_sync consulta status REAL de cada perna na API
       -> perna disparou (finish) + oposta open? DELETE na sobrevivente
PYTHON -> posicao vira closed_tp/closed_sl + aviso no Telegram
```

- Kill-switch: `OCO_GUARD_ENABLED`. Degradacao segura; nunca cria ordem.
- **Limite importante:** o guard so reconcilia pares registrados em
  `state/positions.jsonl` (ordens do bot). Ordens manuais criadas pelo usuario
  na corretora **nao sao cobertas** — reconciliacao manual.
- Ferramenta manual no servidor: `~/gate_cleanup.php` (`orphans` = dry-run).

## Relatorio semanal (Telegram/e-mail)

- Segunda 09:00 (America/Bahia): Parte 1 estrategia HYPE, Parte 2 execucao real.

## Proximos passos

- [x] ~~Decidir exclusividade do LINK~~ resolvido (LINK fora da watchlist).
- [ ] Blindar a allowlist do `main.py`: hoje casa por **string exata** do campo
      `strategy`; mudar o texto quebra a execucao silenciosamente. Mover as
      strings para constantes em `config.py`.
- [ ] Avaliar desempenho por estrategia cruzando `state/positions.jsonl`.
- [ ] Monitorar ETH/XRP no Mare Alta (reprovados no WF).
- [ ] Higiene no servidor: remover `~/oco_smoke.php`.
- [ ] (menor) `execution_guard.json` conta `open_positions` com leve drift.

---

_Historico: versao jul/2026 descrevia a Fase 1 dry-run. O go-live real ocorreu
em seguida (teto $5 -> $10 em 12/08) e o caso OCO foi encerrado em 11/08.
Auditoria de 23/08 corrigiu: universo do Mare Alta (7->6), saida de LINK/AAVE
da watchlist e o teto por ordem._
