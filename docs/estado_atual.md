# Estado Atual do Bot — Consolidado (set/2026)

> Documento de referencia do roteamento e da camada de execucao vigentes no
> `main`. **Atualizado em 2026-09-04** apos remocao do PAXG e auditoria do
> codigo (`config.py`, `strategies.py`, `mare_alta.py`, `main.py`).
> Mapa complementar de estrategias: **`docs/mapa_estrategias.md`**.

## Roteamento por ativo (producao) — 1 token = 1 trilho

| Ativo | Estrategia que EXECUTA | Timeframe | Observacao |
|---|---|---|---|
| BTC/USDT | Mare Alta D1 | D1 | validado no walk-forward |
| SOL/USDT | Mare Alta D1 | D1 | validado no walk-forward |
| TRX/USDT | Mare Alta D1 | D1 | validado no walk-forward |
| BNB/USDT | Mare Alta D1 | D1 | validado no walk-forward |
| HYPE/USDT | Breakout / Tendencia (lb=30/atr=2.5) | 1h | fast-path dedicado, operando real |

**WATCHLIST ativa (5 ativos):** `BTC/USDT`, `SOL/USDT`, `TRX/USDT`, `BNB/USDT`, `HYPE/USDT`.

### Historico de remocoes da Watchlist
- **PAXG/USDT (removido em 2026-09-04):** saiu da watchlist e `ACCUMULATION_ENABLED = False`. Motivo: 2 stops seguidos (28/08 e 01/09) e incompatibilidade estrutural entre acumulacao BUY-only ("sem stop") e a trava global de protecao `REQUIRE_PROTECTION` / `EXECUTION_TPSL_ENABLED`. Ver `docs/paxg_removido_2026-09-04.md`.
- **ETH/USDT e XRP/USDT (removidos em 2026-08-24):** fora do universo do Mare Alta D1 (PF 0.43 e 0.55 no backtest fiel) e sem fast-path proprio. Ver `docs/limpeza_estrategias_2026-08-24.md` e `docs/watchlist_runtime_2026-08-24.md`.
- **LINK/USDT e AAVE/USDT (removidos em 2026-08-12):** reprovados no backtest de robustez de 165d (sem edge).

---

## Mare Alta D1 — universo atual (4 ativos)

```python
MARE_ALTA_UNIVERSE = ["BTC/USDT", "SOL/USDT", "TRX/USDT", "BNB/USDT"]
```

- `MARE_ALTA_ENABLED = True`, `MARE_ALTA_SHADOW_MODE = False` (producao real).
- Entrada (D1, vela fechada): MACD cruza acima do sinal + EMA9>EMA21.
- Saida: stop 2.5xATR -> TP1 +10% (50%) -> breakeven + trailing 3.0xATR.
- Universo proprio + `fetch_ohlcv` proprio (D1): nao depende da WATCHLIST intraday.
- Todos os 4 ativos do universo sao validados no walk-forward original.

---

## Breakout / Trend-Following (HYPE/USDT)

```python
BREAKOUT_ENABLED = True
BREAKOUT_SHADOW_MODE = False
BREAKOUT_SYMBOLS = {
    "HYPE/USDT": {"lookback": 30, "atr_mult": 2.5},
}
```

- Entrada (1h): EMA9 > EMA21 > EMA50 + rompe maxima de 30 velas + RSI > 50.
- Saida: stop 2.5xATR + trailing stop manual.
- Validado por teste de robustez (PF 2.55, +67% em 150d no backtest).

---

## Estrategias Desativadas / Limpas do Codigo

1. **Acumulo (PAXG - RSI sobrevenda 4h):** `ACCUMULATION_ENABLED = False`. Desligado em 2026-09-04.
2. **MACD-only agressivo:** removido do codigo em 2026-08-24. Nao existe mais.
3. **Caminho legado (Integrada / Tendencia MACD / Confluencia):** removido em 2026-08-24. `strategies.py` agora contem apenas a logica de breakout do HYPE.

---

## Trailing (mare_alta_trailing.py)

- `MARE_ALTA_TRAILING_ENABLED = True`
- `MARE_ALTA_SL_ATR_MULT = 3.0`
- `MARE_ALTA_ATR_PERIOD = 14`
- `MARE_ALTA_SYMBOLS = []` -> mira qualquer posicao aberta registrada no `state/positions.jsonl`.
- Catraca: o stop so SOBE (cria novo -> confirma -> deleta antigo; se falhar, o antigo e mantido).

---

## Camada de execucao Gate.io — GO-LIVE REAL

> **Atencao: o bot envia ORDENS REAIS.** Travas rigidas nos DOIS lados (Python e PHP).

| Parametro | Valor | Efeito |
|---|---|---|
| `EXECUTION_ENABLED` | `True` | camada ativa |
| `EXECUTION_DRY_RUN` | `False` | ordens reais via relay |
| `EXECUTION_RELAY_URL` | `https://ineo.com.br/cryptosignals/execute.php` | relay live (HMAC + IP whitelist) |
| `EXECUTION_PCT` | `0.02` | 2% do saldo por ordem |
| `EXECUTION_MAX_NOTIONAL_USDT` | **`10.0`** | teto por ordem (degrau 2 desde 2026-08-12) |
| `EXECUTION_MIN_NOTIONAL_USDT` | `3.0` | piso da Gate.io |
| `EXECUTION_ATR_MULT_SL` | **`2.5`** | stop-loss = entrada - (2.5 * ATR) [ajustado em 23/08 de 2.0 p/ 2.5] |
| `EXECUTION_TP_RR` | `2.0` | take-profit = entrada + (2.0 * risco) |
| `EXECUTION_TPSL_ENABLED` | `True` | TP/SL nativos anexados a compra |
| `EXECUTION_MIN_STOP_PCT` | `0.8` | piso de afastamento do stop (% do preco) |
| `EXECUTION_MAX_OPEN` | `10` | max posicoes live simultaneas |
| `EXECUTION_MAX_TRADES_DAY` | `10` | max ordens/dia (UTC) |
| `EXECUTION_DAILY_LOSS_STOP` | `20.0` | para tudo se perder $20 no dia |
| `REQUIRE_PROTECTION` (PHP) | `true` | compra SEM TP nem SL e recusada |

Proximo degrau ($20): **so no 20o trade** com P&L>0 e PF>=1 ex-ETH.

- Modulos: `bot/executor.py`, `server/execute.php`, `bot/paper_evaluator.py`.
- Contadores diarios: `state/execution_guard.json`.

---

## OCO emulado — EM PRODUCAO (desde 2026-08-11)

```
COMPRA -> register_position() grava tp_order_id + sl_order_id
SCAN   -> oco_guard.sync() envia pares abertos ao relay
RELAY  -> oco_sync consulta status REAL de cada perna na API
       -> perna disparou (finish) + oposta open? DELETE na sobrevivente
PYTHON -> posicao vira closed_tp/closed_sl + aviso no Telegram
```

- Kill-switch: `OCO_GUARD_ENABLED = True`. Degradacao segura; nunca cria ordem.
- **Limite importante:** o guard so reconcilia pares registrados em `state/positions.jsonl` (ordens do bot). Ordens manuais criadas pelo usuario na corretora **nao sao cobertas** — reconciliacao manual (ex: `~/btc_tp.php`).

---

## Fonte Unica de Verdade da Watchlist

Desde 2026-08-24 (`docs/watchlist_runtime_2026-08-24.md`), `bot/config.py` e a fonte unica de verdade da watchlist. `runtime_config._static_watchlist()` forca a lista estatica de `config.py` para evitar divergencias silenciosas.

---

## Posicao Manual de BTC (Gate.io)

Posicao propria do usuario (0.00527384 BTC, preco medio ~$60.749,8).
Protegida por ordens manuais via script `~/btc_tp.php` no servidor:
- TP1: 85.000 (0.0021 BTC)
- TP2: 95.000 (0.0019 BTC)
- SL: 69.200 (0.0040 BTC)
- Runner livre: 0.00127384 BTC
**Nao gerenciada pelo bot** (ver `docs/runbook_btc_manual.md`).
