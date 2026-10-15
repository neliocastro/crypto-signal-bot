# Estratégias, roteamento e parâmetros de execução

> Revisado em 2026-10-15. Descreve **o que o bot opera hoje** e com quais parâmetros. Valores conferidos em
> `bot/config.py` e `bot/mare_alta.py`; em divergência, o código vence. O porquê de cada escolha está em
> `memoria.md` (IDs D-/R-). Ao mudar roteamento, kill-switch ou parâmetro, atualize este arquivo no mesmo commit.

## Resposta curta

```
Maré Alta D1  -> BTC  SOL  TRX  BNB   (diário)   ÚNICO trilho que hoje pode gerar ordem real
Breakout 1h   -> HYPE                 DESLIGADO desde 2026-10-13 (D-013)
```

**Watchlist (scan intraday, 5):** BTC, SOL, TRX, BNB, HYPE (`WATCHLIST` em `bot/config.py`).
**Universo do Maré Alta (4):** `MARE_ALTA_UNIVERSE` em `bot/mare_alta.py`, independente da watchlist.

## Maré Alta D1 (`bot/mare_alta.py`) — em produção

- **Entrada (vela D1 fechada):** MACD(12,26,9) cruza acima da linha de sinal (vale abaixo de zero, D-014) **e**
  EMA9 > EMA21. Um alerta por vela (`state/mare_alta_state.json`).
- **Saída (D-027, `MARE_ALTA_PARTIAL_TP_ENABLED = True`):**

| Fase | Stop | Alvo |
|---|---|---|
| Compra | `ref − 2,5×ATR` (piso 0,8%), posição inteira | TP1 = `ref × 1,10`, **50%** da posição |
| Antes do TP1 | fixo (sem trailing) | TP1 aberto |
| TP1 executa | novo SL no **preço de entrada**, só o restante | nenhum |
| Depois do TP1 | trailing `close_D1 − 3×ATR`, vela fechada, catraca (só sobe; piso = breakeven) | nenhum |

  Se o relay não aplicar o TP parcial (qty abaixo do mínimo), o TP sai na base inteira e o bot avisa no Telegram;
  essa posição segue o modo antigo (TP 2,0R + trailing desde o início).
- **Validação:** walk-forward jul/2026 (carteira PF 1,64; OOS PF 2,08). Backtest fiel com stop 2,5×:
  BTC 1,28 · SOL 4,51 · TRX 2,21 · BNB 2,15. O script desse backtest não está no repositório.
- Kill-switches: `MARE_ALTA_ENABLED`, `MARE_ALTA_SHADOW_MODE` (False = ordens reais), `MARE_ALTA_TRAILING_ENABLED`,
  `MARE_ALTA_TRAILING_CLOSED_ONLY`, `MARE_ALTA_PARTIAL_TP_ENABLED`.
- **Validade dos gatilhos (D-033):** a Gate expira TP e SL em 30 dias. Com 25 dias ou mais, o SL de qualquer posição
  aberta é recriado no mesmo preço e qty (`SL_RENEW_ENABLED`, `SL_RENEW_AFTER_DAYS = 25`), antes e depois do TP1.
  O TP1 não é renovado: se expirar, o Telegram avisa e a posição segue só com o stop fixo.

## Breakout / Tendência 1h (`bot/strategies.py`) — desligado

- `BREAKOUT_ENABLED = False` (D-013). Com o switch desligado, `evaluate_signal` devolve `None` para o HYPE.
- Regra (para quando religar): EMA9 > EMA21 > EMA50 + rompe a máxima de 30 velas + RSI > 50;
  `BREAKOUT_SYMBOLS = {"HYPE/USDT": {"lookback": 30, "atr_mult": 2.5}}`.
- **Dois parâmetros parecidos:** o `atr_mult` de `BREAKOUT_SYMBOLS` é do **sinal**; o stop da **ordem** vem de
  `EXECUTION_ATR_MULT_SL_BY_SYMBOL = {"HYPE/USDT": 3.0}`.
- `BREAKOUT_SHADOW_MODE = True` acrescenta `[SHADOW]` ao nome e, de propósito, quebra o match da allowlist (sem ordem).
- Desempenho ao vivo: PF ~0,78 em 12 trades (backtest original 2,55).

## Desligadas ou removidas
| Estratégia | Estado |
|---|---|
| Acúmulo RSI 4h (PAXG) | `ACCUMULATION_ENABLED = False` desde 2026-09-04 (código mantido). **O cron do servidor segue ativo por decisão do usuário (D-032)**; compra fora do bot |
| MACD-only, Integrada, Tendência MACD, Confluência | removidas do código em 2026-08-24 |
| SHORT | descartado em definitivo (D-002) |

## Roteamento (1 ativo = 1 trilho, D-003)

```
evaluate_signal(symbol, df, ...)                    # bot/strategies.py
  fast-path BREAKOUT -> só se BREAKOUT_ENABLED e símbolo em BREAKOUT_SYMBOLS
  fast-path ACÚMULO  -> só se ACCUMULATION_ENABLED
  demais             -> None

INTRADAY_EXEC_ALLOWLIST = {                          # bot/main.py
    ("HYPE/USDT", "Breakout / Tendência"),
    ("PAXG/USDT", "Acúmulo (RSI sobrevenda)"),       # inerte
}
```

A allowlist casa por **string exata, com acento**. Renomear o campo `strategy` em `strategies.py` faz o ativo parar de
operar em silêncio; o canário `tests/test_roteamento_strings.py` pega isso. Altere os dois arquivos no mesmo commit.
O Maré Alta roda **fora** dessa allowlist, em bloco próprio do `main.py`.

🟢 PRONTO no Telegram vem do diagnóstico de todos os ativos e **não** significa que houve ordem.

## Parâmetros de execução (`bot/config.py`)

| Parâmetro | Valor | Nota |
|---|---|---|
| `EXECUTION_ENABLED` / `EXECUTION_DRY_RUN` | `True` / `False` | ordens **reais** |
| `EXECUTION_PCT` | 0,02 | 2% de `EXECUTION_PAPER_BALANCE` (1000) = US$ 20, limitado pelo teto: **na prática toda ordem é US$ 10** |
| `EXECUTION_MAX_NOTIONAL_USDT` | 10,0 | teto por ordem (D-024; espelhado no PHP) |
| `EXECUTION_MIN_NOTIONAL_USDT` | 3,0 | mínimo da Gate.io |
| `EXECUTION_ATR_MULT_SL` | 2,5 | stop inicial global (D-020) |
| `EXECUTION_ATR_MULT_SL_BY_SYMBOL` | `{"HYPE/USDT": 3.0}` | override (D-021) |
| `EXECUTION_MIN_STOP_PCT` | 0,8 | piso de distância do stop, % do preço |
| `EXECUTION_TP_RR` | 2,0 | TP = entrada + 2×risco (fora do Maré Alta com TP1 parcial) |
| `EXECUTION_TPSL_ENABLED` | `True` | TP/SL nativos em toda compra |
| `EXECUTION_MAX_OPEN` / `EXECUTION_MAX_TRADES_DAY` | 10 / 10 | limites globais (dia UTC) |
| `EXECUTION_DAILY_LOSS_STOP` | 20,0 | para tudo se perder US$ 20 no dia |
| Trava de concentração | 1 posição viva + 2 ordens/dia por ativo | D-022; defaults no `executor.py` |
| `OCO_GUARD_ENABLED` | `True` | OCO emulado (D-005) |
| `SL_RENEW_ENABLED` / `SL_RENEW_AFTER_DAYS` | `True` / 25 | renova o SL antes dos 30 dias da Gate (D-033) |
| `SL_EXPIRED_ALERT_ENABLED` | `True` | alerta 1x se SL ou TP1 pendente morrer sem executar (D-033) |
| `SIGNAL_COOLDOWN_HOURS` | 4 | cooldown por `símbolo|estratégia` |
| `REQUIRE_PROTECTION` (PHP) | `true` | compra sem TP nem SL é recusada (D-006) |

## Histórico do universo
| Data | Mudança |
|---|---|
| 2026-07-10 | AAVE e LINK fora (Maré Alta D1 PF 0,86 / 0,80) |
| 2026-08-23 | ETH e XRP fora do Maré Alta (backtest fiel PF 0,43 / 0,55) |
| 2026-08-24 | ETH e XRP fora da watchlist; estratégias mortas removidas |
| 2026-09-04 | PAXG fora; acúmulo desligado |
| 2026-09-16 | stop do HYPE 3,0×ATR |
| 2026-10-13 | Breakout HYPE desligado |
| 2026-10-15 | trailing com vela fechada; saída TP1 50% + breakeven ligada |
