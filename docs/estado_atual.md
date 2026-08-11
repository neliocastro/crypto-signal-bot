# Estado Atual do Bot — Consolidado (ago/2026)

> Documento de referencia do roteamento e da camada de execucao vigentes no
> `main`. Atualizado em 2026-08-11 apos o fechamento do caso OCO
> (ver `docs/gateio_limitacoes.md`).

## Roteamento por ativo (produção)

| Ativo | Estrategia | Observacao |
|---|---|---|
| BTC | Mare Alta D1 | validado no walk-forward |
| ETH | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| SOL | Mare Alta D1 | validado no walk-forward |
| XRP | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| TRX | Mare Alta D1 | validado no walk-forward |
| BNB | Mare Alta D1 | validado no walk-forward |
| LINK | Mare Alta D1 + MACD-only | **incluido no Mare Alta**; ainda gera sinal MACD-only 1h |
| HYPE | Breakout/Tendencia (lb=30/atr=2.5) | fast-path dedicado; nao passa pelo Mare Alta nem MACD-only |
| PAXG | Acumulacao RSI (BUY-only) | fora do trailing (nao registra stop) |

## Mare Alta D1 — universo atual

```python
MARE_ALTA_UNIVERSE = ["BTC/USDT", "ETH/USDT", "SOL/USDT",
                      "XRP/USDT", "TRX/USDT", "BNB/USDT", "LINK/USDT"]
```

- 7 ativos = **todos menos PAXG e HYPE**.
- Entrada (D1, vela fechada): MACD cruza acima do sinal + EMA9>EMA21.
- Saida: stop 2.5xATR -> TP1 +10% (50%) -> breakeven + trailing 3.0xATR.
- Commit: `6b1c8d5`.

### Nota de risco (ETH/XRP)
ETH e XRP foram **reprovados no walk-forward original** da estrategia e entraram
por decisao de negocio. Acompanhar de perto na avaliacao dos sinais.

### Ponta solta (LINK)
LINK esta no Mare Alta D1 **e** ainda no MACD-only 1h, entao pode gerar sinal
pelos dois caminhos. Decisao pendente: tornar exclusivo do Mare Alta (remover
do MACD-only) ou manter os dois.

## Trailing (Mare Alta ATR / mare_alta_trailing.py)

- `MARE_ALTA_SYMBOLS = []` -> mira **todos** os ativos com posicao registrada.
- PAXG fica de fora por arquitetura (acumulacao BUY-only, sem stop p/ trailar).
- Catraca: o stop so SOBE (cria novo -> confirma -> deleta antigo; se falhar,
  o antigo e mantido).

## Camada de execucao Gate.io — 🟢 GO-LIVE REAL (canario)

> **Atencao: o bot envia ORDENS REAIS.** A fase dry-run foi concluída; o
> go-live minimo esta ativo com travas rigidas nos DOIS lados (Python e PHP).

| Flag | Valor | Efeito |
|---|---|---|
| `EXECUTION_DRY_RUN` | `False` | ordens reais via relay |
| `EXECUTION_RELAY_URL` | `https://ineo.com.br/cryptosignals/execute.php` | braco PHP live (HMAC + IP whitelist) |
| `EXECUTION_PCT` | `0.02` | 2% do saldo por ordem |
| `EXECUTION_MAX_NOTIONAL_USDT` | `5.0` | teto por ordem (espelhado no PHP: `$MAX_NOTIONAL_USDT = 5.0`) |
| `EXECUTION_MIN_NOTIONAL_USDT` | `3.0` | piso (Gate.io rejeita < $3) |
| `EXECUTION_MAX_OPEN` | `10` | max posicoes simultaneas |
| `EXECUTION_MAX_TRADES_DAY` | `10` | max ordens/dia (UTC) |
| `EXECUTION_DAILY_LOSS_STOP` | `20.0` | para tudo se perder $20 no dia |
| `EXECUTION_TPSL_ENABLED` | `True` | TP/SL nativos anexados a cada compra (SL 2.0xATR, TP RR 2.0, piso stop 0.8%) |
| `REQUIRE_PROTECTION` (PHP) | `true` | compra SEM TP nem SL e RECUSADA (nunca posicao nua) |

- Modulos: `bot/executor.py`, `server/execute.php` (FIX 1..7 + `update_trailing` + `oco_sync`), `bot/paper_evaluator.py`.
- Contadores diarios: `state/execution_guard.json`.

### Bugs historicos do execute.php — RESOLVIDOS
1. ~~`pair_rules()` falha -> fallback precision=6 -> HTTP 400~~ ✅ fallback por
   tabela segura (`$SAFE_PRICE_PREC`/`$SAFE_AMOUNT_PREC`, conferida na API em 26/07)
   + validacao de casas antes do envio.
2. ~~`ATR=0` -> compra sem TP/SL~~ ✅ `REQUIRE_PROTECTION` recusa compra nua.
3. ~~`$gate['amount']` em MARKET BUY vem em QUOTE (bug FIX 7)~~ ✅ base derivada
   do fill real (`filled_total / fill_price`) + sanity-check de notional.

## 🛡️ OCO emulado — EM PRODUCAO (2026-08-11)

A Gate.io nao tem OCO nativo no spot (TP e SL sao price_orders independentes).
O circuito completo que fecha o buraco das ordens orfas:

```
COMPRA -> register_position() grava tp_order_id + sl_order_id
SCAN   -> oco_guard.sync() envia pares abertos ao relay
RELAY  -> oco_sync consulta status REAL de cada perna na API
       -> perna disparou (finish) + oposta open? DELETE na sobrevivente
PYTHON -> posicao vira closed_tp/closed_sl + aviso no Telegram
```

- Kill-switch: `OCO_GUARD_ENABLED` (config.py). Degradacao segura: falha nunca
  derruba o scan; a acao NUNCA cria ordem.
- Validado por smoke test em producao (11/08). Detalhes, evidencias e limpeza
  das orfas historicas: `docs/gateio_limitacoes.md` (secao 7).
- Ferramenta de reconciliacao manual no servidor: `~/gate_cleanup.php`
  (`orphans` = dry-run; `cancel-orphans` = cancela; log em `~/gate_cleanup_log.jsonl`).

## Relatorio semanal (Telegram/e-mail)

- Segunda 09:00 (America/Bahia). Consolida:
  - Parte 1: estrategia HYPE (breakout producao).
  - Parte 2: execucao real (P&L, win-rate, slippage medio).

## Proximos passos

- [ ] Avaliar sinais e mensagens que chegam no Telegram.
- [ ] Decidir exclusividade do LINK (Mare Alta vs MACD-only).
- [ ] Monitorar ETH/XRP no Mare Alta (reprovados no WF).
- [ ] Higiene no servidor: remover `~/oco_smoke.php` (cobaia do smoke test).
- [ ] (menor) `execution_guard.json` conta `open_positions` com leve drift
      (so decrementa; nao corrige p/ cima). Cosmetico — corrigir se incomodar.

---

_Historico: a versao anterior deste documento (jul/2026) descrevia a Fase 1
dry-run com cinto triplo. O go-live real ocorreu em seguida (teto $5, 2%,
stop diario $20) e o caso OCO foi encerrado em 2026-08-11._
