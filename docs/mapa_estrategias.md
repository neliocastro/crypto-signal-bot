# Mapa de Estrategias — 1 token = 1 trilho

> Referencia rapida. **Reverificado no codigo do `main` em 2026-10-08** (HEAD `84388d2`:
> `bot/config.py`, `bot/strategies.py`, `bot/mare_alta.py`, `bot/main.py`, `bot/executor.py`).
> Substitui a versao de 2026-08-23, que ainda citava ETH, XRP, PAXG e o MACD-only.

## 1. Resposta curta

```
Mare Alta D1 -> BTC  SOL  TRX  BNB     (diario)
Breakout     -> HYPE                   (1h)
```

**Cada ativo opera por UM unico trilho executor.** Watchlist (5): BTC, SOL, TRX, BNB, HYPE.

## 2. Tabela por ativo

| Ativo | Estrategia que EXECUTA | TF | Stop inicial da ordem | Modulo |
|---|---|---|---|---|
| BTC/USDT | Mare Alta D1 | 1d | 2.5x ATR | `bot/mare_alta.py` |
| SOL/USDT | Mare Alta D1 | 1d | 2.5x ATR | `bot/mare_alta.py` |
| TRX/USDT | Mare Alta D1 | 1d | 2.5x ATR | `bot/mare_alta.py` |
| BNB/USDT | Mare Alta D1 | 1d | 2.5x ATR | `bot/mare_alta.py` |
| HYPE/USDT | Breakout / Tendencia (lb=30) | 1h | **3.0x ATR** (override) | `bot/strategies.py` |

## 3. Estrategias no codigo

| Estrategia | Onde | Kill-switch | Estado |
|---|---|---|---|
| Mare Alta D1 | `mare_alta.py` | `MARE_ALTA_ENABLED` | producao (shadow OFF) |
| Breakout / Tendencia | `strategies.py` | `BREAKOUT_ENABLED` | producao (shadow OFF) |
| Acumulo RSI (PAXG) | `strategies.py` | `ACCUMULATION_ENABLED = False` | **desligado** desde 04/09 (codigo mantido) |
| MACD-only / Integrada / Tendencia MACD / Confluencia | — | — | **removidas do codigo** em 24/08 |
| SHORT | — | — | descartado permanentemente |

## 4. Roteamento no `evaluate_signal` (`bot/strategies.py`)

```
evaluate_signal(symbol, df, ...)
  fast-path BREAKOUT  -> symbol em BREAKOUT_SYMBOLS (HYPE)              -> return
  fast-path ACUMULO   -> so se ACCUMULATION_ENABLED (hoje False)        -> return
  sem fast-path       -> return None (nao ha mais caminho legado)
```

Ativos do Mare Alta nao geram sinal intraday: retornam `None` aqui e operam so pelo bloco D1.

## 5. A trava de 1 trilho por ativo (`bot/main.py` ~L234)

```python
INTRADAY_EXEC_ALLOWLIST = {
    ("HYPE/USDT", "Breakout / Tendência"),
    ("PAXG/USDT", "Acúmulo (RSI sobrevenda)"),   # inerte: acumulo desligado
}
```

O Mare Alta roda **fora** desse filtro, em bloco proprio (`main.py` ~L405):
`run_mare_alta(notify=send)` -> `_executor.maybe_execute(...)`, com universo
proprio (`MARE_ALTA_UNIVERSE`) e `fetch_ohlcv` D1 proprio.

## 6. Fragilidades conhecidas

1. **Allowlist casa por STRING EXATA** (com acento). Mudar o campo `strategy` em
   `strategies.py` faz o ativo parar de operar em silencio. Canario:
   `tests/test_roteamento_strings.py`. Alterar os dois arquivos no mesmo commit.
2. **`[SHADOW]` no nome quebra o match de proposito:** se `BREAKOUT_SHADOW_MODE=True`,
   a string vira `"Breakout / Tendência [SHADOW]"` e nao passa na allowlist (sem ordem).
3. **Dois `atr_mult` diferentes no HYPE:** `BREAKOUT_SYMBOLS["HYPE/USDT"]["atr_mult"]=2.5`
   e do SINAL; o stop da ORDEM vem de `EXECUTION_ATR_MULT_SL_BY_SYMBOL = {"HYPE/USDT": 3.0}`.
4. A entrada PAXG na allowlist e residuo inofensivo; remover so junto com o codigo do acumulo.

## 7. Camada comum de execucao

| Trava | Valor |
|---|---|
| `EXECUTION_PCT` | 2% do saldo por ordem |
| `EXECUTION_MAX_NOTIONAL_USDT` | $10 (degrau $20 **congelado**, ver `reauditoria_degrau_2026-10-08.md`) |
| `EXECUTION_MIN_NOTIONAL_USDT` | $3 |
| `EXECUTION_ATR_MULT_SL` / `..._BY_SYMBOL` | 2.5x global / HYPE 3.0x |
| `EXECUTION_TP_RR` / `EXECUTION_MIN_STOP_PCT` | 2.0 / 0.8% |
| `EXECUTION_MAX_OPEN` / `EXECUTION_MAX_TRADES_DAY` | 10 / 10 |
| `EXECUTION_DAILY_LOSS_STOP` | $20/dia |
| `EXECUTION_CONCENTRATION_GUARD` | 1 posicao viva + 2 ordens/dia por ativo |
| `REQUIRE_PROTECTION` (PHP) | compra sem TP/SL e recusada |
| `OCO_GUARD_ENABLED` | OCO emulado (so ordens do bot) |
| `MARE_ALTA_TRAILING_ENABLED` | trailing D1 3.0x ATR, catraca so sobe |

## 8. Historico do universo

| Data | Mudanca |
|---|---|
| 12/08 | LINK e AAVE removidos (sem edge em 165d) |
| 23-24/08 | ETH e XRP removidos (PF 0.43 / 0.55 no backtest fiel); MACD-only e legado removidos |
| 04/09 | PAXG removido; `ACCUMULATION_ENABLED=False` |
| 16/09 | override de stop do HYPE (3.0x ATR) |

---

_Reverificado no codigo em 2026-10-08. Ao alterar roteamento, atualizar este arquivo no mesmo commit._
