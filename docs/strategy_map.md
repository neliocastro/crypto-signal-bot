# Mapa de Estratégias — crypto-signal-bot

> Documento de referência do roteamento de estratégias por ativo.
> Reflete o estado real do código em `bot/strategies.py` e `bot/config.py`.
> Última atualização: 2026-05-31.

## 1. Ordem de roteamento (`evaluate_signal`)

Os ativos são interceptados por **fast-paths dedicados e exclusivos**
(não fazem fallback para o caminho normal). A ordem importa:

```
Sinal recebido
   |
   |-- 1) Breakout?   -> simbolo em BREAKOUT_SYMBOLS?      -> HYPE -> Breakout / Tendência
   |
   |-- 2) Acúmulo?    -> simbolo em ACCUMULATION_SYMBOLS?  -> PAXG -> Acúmulo (RSI sobrevenda)
   |
   |-- 3) Agressivo?  -> ACTIVE_PROFILE=agressivo + LINK?  -> LINK -> Tendência MACD — Agressivo
   |
   `-- 4) Caminho normal -> os demais 7 ativos -> Integrada / Tendência MACD / Confluência
```

## 2. Estratégias por ativo (watchlist = 10 ativos)

| Ativo | Estratégia ativa (label no sinal) | Lógica resumida |
|---|---|---|
| **HYPE** | `Breakout / Tendência` | EMA9>21>50 + rompe máx. 30 velas + RSI>50; stop 2.5xATR + trailing |
| **PAXG** | `Acúmulo (RSI sobrevenda)` | RSI sobrevendido no 4h -> zona de compra (sem alvo de venda) |
| **LINK** | `Tendência MACD — Agressivo` | MACD-only: cruzamento da linha acima do sinal (vela fechada) |
| BTC, ETH, SOL, XRP, TRX, BNB, AAVE | `Integrada (Curto Prazo)` / `Tendência MACD` / `Integrada + MACD (Confluência)` | ver seção 3 |

## 3. Detalhe do caminho normal (7 ativos)

| Label | Quando dispara | Confiança |
|---|---|---|
| `Integrada (Curto Prazo)` | VWAP + EMAs(9/21/50) + MACD + RSI + pullback | 8/10 |
| `Tendência MACD` | EMA200 + cruzamento MACD abaixo da linha zero (sem VWAP) | 7/10 |
| `Integrada + MACD (Confluência)` | as duas acima disparam juntas | 10/10 |
| bônus MTF | +1 se tendência 4h confirmada; +1 se pullback 15m | até 10 |

## 4. Alvos e risco (sinais com stop/alvo)

| Parâmetro | Valor |
|---|---|
| Stop | entry - 1.5 x ATR |
| **TP1** | R:R **1:2** (entry + 3.0 x ATR) |
| **TP2** | R:R **1:3** (entry + 4.5 x ATR) |
| Risco/Retorno exibido | 1:2 (calculado sobre o TP1) |

> Exceção: PAXG (Acúmulo) é zona de compra para DCA — **sem stop nem alvo de venda**.

## 5. Acúmulo PAXG — parâmetros

| Parâmetro | Valor |
|---|---|
| Timeframe | 4h |
| `rsi_threshold` (sobrevenda) | 30.0 |
| `rsi_extreme` (sobrevenda extrema) | 20.0 |
| `cooldown_hours` | 24 |
| Saída | sem venda — retorno medido em janelas fixas |

## 6. Kill-switches

| Flag | Onde | Efeito |
|---|---|---|
| `BREAKOUT_ENABLED=False` | config.py | desliga o HYPE (breakout) |
| `BREAKOUT_SHADOW_MODE=True` | config.py | sinais HYPE marcados `[SHADOW]` |
| `ACTIVE_PROFILE="balanceado"` | config.py | tira LINK do agressivo -> caminho normal |
| `ACCUMULATION_ENABLED=False` | config.py | desliga o acúmulo PAXG |

## 7. Notas

- Os **labels exibidos** foram padronizados (acentuação) no commit de estilo;
  nenhum alterou a lógica de roteamento.
- O **LINK** mantém a variante Agressiva de propósito (PF 3.26 no backtest):
  o label deixa claro que pertence à família *Tendência MACD*.
- Decisões históricas (PAXG, HYPE, LINK) estão em `docs/strategy_decisions.md`.
