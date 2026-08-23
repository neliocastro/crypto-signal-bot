# Mapa de Estrategias — 1 token = 1 trilho

> Documento de referencia rapida. **Verificado diretamente no codigo do `main`**
> em 2026-08-23 (`bot/config.py`, `bot/strategies.py`, `bot/mare_alta.py`,
> `bot/main.py`). Substitui, no que houver divergencia, o que estiver escrito em
> `docs/estado_atual.md` (ver secao "Correcoes" no fim).

## 1. Resposta curta (para explicar a qualquer um)

```
Mare Alta D1   -> BTC  ETH  SOL  XRP  TRX  BNB      (diario)
Breakout       -> HYPE                              (1h)
Acumulacao RSI -> PAXG                              (4h)
```

**Cada ativo opera por UM unico trilho executor.** Nao ha ativo com duas
estrategias enviando ordem.

## 2. Tabela por ativo

| Ativo | Estrategia que EXECUTA | TF | Modulo |
|---|---|---|---|
| BTC/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| ETH/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| SOL/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| XRP/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| TRX/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| BNB/USDT | Mare Alta D1 | 1d | `bot/mare_alta.py` |
| HYPE/USDT | Breakout / Tendencia (lb=30, atr=2.5) | 1h | `bot/strategies.py` |
| PAXG/USDT | Acumulo (RSI sobrevenda) — BUY only | 4h | `bot/strategies.py` |

## 3. Estrategias existentes no codigo

| # | Estrategia | Arquivo | Kill-switch | Estado |
|---|---|---|---|---|
| 1 | Mare Alta D1 | `mare_alta.py` | `MARE_ALTA_ENABLED` | producao (shadow OFF) |
| 2 | Breakout / Tendencia | `strategies.py` | `BREAKOUT_ENABLED` | producao (shadow OFF) |
| 3 | Acumulacao RSI | `strategies.py` | `ACCUMULATION_ENABLED` | producao |
| 4 | MACD-only Agressivo | `strategies.py` | `ACTIVE_PROFILE` | **roda, mas o sinal e descartado** |
| 5 | Integrada Curto Prazo | `strategies.py` | perfil `balanceado` | **codigo morto** (perfil ativo e `agressivo`) |

### Por que a #4 nao executa

Com `ACTIVE_PROFILE = "agressivo"` e `approved_symbols = None`, o MACD-only 1h
ainda **gera** sinal para os 6 ativos do Mare Alta. Esse sinal e **filtrado**
no `main.py` (secao 5) e nunca vira Telegram nem ordem. E desperdicio de CPU,
nao risco financeiro.

### Por que a #5 nao roda

Os tres fast-paths do `evaluate_signal` fazem `return` antes de chegar no
caminho normal (linha 557+). Com a watchlist atual, nenhum ativo alcanca a
Integrada.

## 4. Roteamento dentro do `evaluate_signal` (`bot/strategies.py`)

```
evaluate_signal(symbol, df, ...)
  L491  df < 210 velas -> None
  L499  fast-path BREAKOUT      -> HYPE  ... return
  L516  fast-path ACUMULACAO    -> PAXG  ... return
  L542  fast-path MACD-ONLY     -> demais ... return
  L557+ caminho normal (Integrada + Tendencia MACD + gating MTF)  [inalcancavel hoje]
```

Cada fast-path e exclusivo (`return` direto) e envolto em `try/except` com
degradacao segura.

## 5. A trava que garante 1 trilho por ativo (`bot/main.py`, L226-252)

```python
# --- ROTEAMENTO POR TRILHO (2026-07-10) ---
INTRADAY_EXEC_ALLOWLIST = {
    ("HYPE/USDT", "Breakout / Tendência"),
    ("PAXG/USDT", "Acúmulo (RSI sobrevenda)"),
}
qualified_signals = [s for s in qualified_signals
                     if (s["symbol"], s["strategy"]) in INTRADAY_EXEC_ALLOWLIST]
```

Motivo historico registrado no proprio codigo: *"fim da duplicidade que comprou
ETH pelo trilho errado em 05/07"*.

O Mare Alta roda **fora** desse filtro, em bloco proprio (`main.py` L402-406):

```python
from .mare_alta import run_mare_alta
_ma_signals = run_mare_alta(notify=send)
for _ma_sig in _ma_signals:
    _executor.maybe_execute(_ma_sig, _paper_balance)
```

Ele tem universo proprio (`MARE_ALTA_UNIVERSE`) e faz o proprio `fetch_ohlcv`,
portanto **nao depende da WATCHLIST**.

## 6. Fragilidades conhecidas (ler antes de mexer)

1. **A allowlist casa por STRING EXATA da estrategia.** Mudar o texto do campo
   `strategy` em `strategies.py` (ate corrigir um acento) faz o ativo **parar de
   operar silenciosamente**, sem erro e sem log de falha. Os dois valores
   acoplados sao `"Breakout / Tendência"` e `"Acúmulo (RSI sobrevenda)"`.
   **NAO ALTERAR** sem atualizar `main.py` no mesmo commit.
2. **A watchlist pode ser sobrescrita em runtime** (`main.py` L170,
   `state/runtime_config.json` via Telegram Commander). Um ativo adicionado por
   la entra no scan mas **nao tem trilho executor** -> sera filtrado e nunca
   virara ordem.
3. **MACD-only queimando CPU** para 6 ativos cujo sinal e descartado. Limpeza
   opcional: adicionar os 6 a `MACD_ONLY_EXCLUDE`. Atencao: isso os joga no
   **caminho normal** (Integrada), nao os deixa sem estrategia.

## 7. Camada comum de execucao (nao e estrategia)

Vale para qualquer sinal que passe pelo executor:

| Trava | Valor |
|---|---|
| `EXECUTION_PCT` | 2% do saldo por ordem |
| `EXECUTION_MAX_NOTIONAL_USDT` | $10 (degrau 2) |
| `EXECUTION_MIN_NOTIONAL_USDT` | $3 (piso da Gate.io) |
| `EXECUTION_MAX_OPEN` | 10 posicoes |
| `EXECUTION_MAX_TRADES_DAY` | 10 ordens/dia |
| `EXECUTION_DAILY_LOSS_STOP` | $20/dia |
| `EXECUTION_TPSL_ENABLED` | SL 2.0xATR, TP RR 2.0, piso stop 0.8% |
| `REQUIRE_PROTECTION` (PHP) | compra sem TP/SL e RECUSADA |
| `OCO_GUARD_ENABLED` | reconcilia TP<->SL (Gate.io nao tem OCO nativo) |
| `MARE_ALTA_TRAILING_ENABLED` | trailing D1 3.0xATR, catraca so sobe |

## 8. Correcoes ao `docs/estado_atual.md`

O documento anterior esta desatualizado nos seguintes pontos:

| `estado_atual.md` diz | Realidade no `main` (2026-08-23) |
|---|---|
| Mare Alta com 7 ativos, incluindo LINK | 6 ativos; **LINK saiu** |
| "Ponta solta do LINK" (Mare Alta + MACD-only) | **nao existe mais**: LINK fora da watchlist |
| `EXECUTION_MAX_NOTIONAL_USDT = 5.0` | **10.0** (degrau 2, desde 12/08) |
| LINK na tabela de roteamento | removido (reprovado; ver reavaliacao 12/08 em `config.py`) |

Watchlist real (8): BTC, ETH, SOL, XRP, TRX, BNB, HYPE, PAXG.

## 9. Nota de risco herdada

ETH e XRP foram **reprovados no walk-forward original** do Mare Alta e entraram
por decisao de negocio. O docstring do `mare_alta.py` ainda registra:
*"Universo validado: BTC, SOL, TRX, BNB (ETH e XRP reprovados nesta logica)"*.
Acompanhar de perto.

---

_Gerado a partir de leitura direta do codigo em 2026-08-23. Ao alterar
roteamento, atualizar este arquivo no mesmo commit._
