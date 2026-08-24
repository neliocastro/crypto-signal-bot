# Limpeza de estrategias mortas — 2026-08-24

> Remocao de codigo que **rodava mas nunca podia virar ordem nem mensagem**.
> Nenhuma estrategia com execucao real foi tocada. Rollback: `git revert`.

## O que foi removido

| # | Estrategia | Onde vivia | Por que era morta |
|---|---|---|---|
| 4 | **MACD-only "agressivo"** (`_check_aggressive_macd`) | `bot/strategies.py` | Rodava a cada scan para BTC/ETH/SOL/XRP/TRX/BNB. 100% dos sinais eram descartados pelo `INTRADAY_EXEC_ALLOWLIST` do `main.py` (que so aceita HYPE-Breakout e PAXG-Acumulo). Custo de CPU e rate-limit, zero ordens. |
| 5 | **Integrada (Curto Prazo)** | `bot/strategies.py` | Inalcancavel: o fast-path do perfil agressivo interceptava todos os ativos com `return` antes de chegar aqui. |
| 6 | **Tendencia MACD** (EMA200 + cruzamento abaixo de zero) | `bot/strategies.py` | Idem — mesmo caminho legado inalcancavel. |
| 7 | **Integrada + MACD (Confluencia)** | `bot/strategies.py` | Fusao das duas acima; morria junto. |

Junto saiu a config que so servia a elas, em `bot/config.py`:
`RISK_PROFILES`, `ACTIVE_PROFILE`, `MACD_ONLY_EXCLUDE`.
Tambem saiu o helper `_xup` (usado apenas pelo caminho legado).

## O que ficou (as estrategias que realmente executam)

| Trilho | Ativos | Modulo |
|---|---|---|
| **Mare Alta D1** | BTC, SOL, TRX, BNB | `bot/mare_alta.py` (scan proprio, nao passa por `strategies.py`) |
| **Breakout / Tendencia** | HYPE | `_check_breakout_trend` (lb=30, atr=2.5) |
| **Acumulo (RSI sobrevenda)** | PAXG | `_check_accumulation` (RSI 4h < 30, BUY-only) |

`evaluate_signal()` agora e explicito: fast-path de breakout, fast-path de
acumulo, e **`return None`** para qualquer outro ativo. Nada de caminho legado
silencioso. O diagnostico dos demais ativos no Telegram **continua igual** —
ele e montado a partir do `diag` de cada ativo, nao de `qualified_signals`.

## Validacao feita antes do commit

- `py_compile` OK em `strategies.py` e `config.py`.
- Import real do pacote + chamada de `evaluate_signal` com DataFrame sintetico:
  - `HYPE/USDT` em rompimento -> sinal `Breakout / Tendência`, RR 2.0, `trailing_stop=True`;
  - `PAXG/USDT` com RSI 4h cruzando 30 p/ baixo -> sinal `Acúmulo (RSI sobrevenda)`, side BUY;
  - `BTC/USDT` e `ETH/USDT` -> `None` (correto: so Mare Alta D1);
  - tuplas `(symbol, strategy)` batem com o `INTRADAY_EXEC_ALLOWLIST` do `main.py`;
  - aliases `evaluate` / `evaluate_signals` preservados;
  - `_check_trend_4h` / `_check_pullback_15m` preservados (o `main.py` os usa no diag MTF).
- Busca por consumidores externos: `paper_evaluator.py` e `tests/test_roteamento_strings.py`
  nao referenciam nada do que foi removido.

## Efeito colateral cosmetico (esperado)

`bot/telegram_sender.py` importa `ACTIVE_PROFILE` dentro de um `try/except` so
para imprimir a tag "🔥 modo AGRESSIVO" no cabecalho. Com a constante removida,
o `except` assume e a tag **simplesmente deixa de aparecer** — que e o correto,
ja que o perfil agressivo nao existe mais. Nenhum erro, nenhuma quebra.

## Ganho pratico

- Menos CPU e menos chamadas por scan (6 ativos deixam de calcular MACD-only inutilmente).
- `strategies.py` cai de ~700 para ~390 linhas, sem nenhuma perda funcional.
- O mapa mental passa a bater com a realidade: **3 trilhos, 6 ativos operados**.
