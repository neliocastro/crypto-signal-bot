# Mapa de Estratégias — crypto-signal-bot

> Documento de referência do roteamento E do detalhamento de cada estratégia.
> Reflete o estado real do código em `bot/strategies.py` e `bot/config.py`.
> Última atualização: 2026-05-31.

## 1. Ordem de roteamento (`evaluate_signal`)

Fast-paths dedicados e exclusivos (sem fallback). A ordem importa:

```
Sinal recebido
   |
   |-- 1) Breakout?   -> simbolo em BREAKOUT_SYMBOLS?      -> HYPE -> Breakout / Tendência
   |-- 2) Acúmulo?    -> simbolo em ACCUMULATION_SYMBOLS?  -> PAXG -> Acúmulo (RSI sobrevenda)
   |-- 3) Agressivo?  -> ACTIVE_PROFILE=agressivo + LINK?  -> LINK -> Tendência MACD — Agressivo
   `-- 4) Caminho normal -> os demais 7 ativos -> Integrada / Tendência MACD / Confluência
```

## 2. Estratégias por ativo (watchlist = 10 ativos)

| Ativo | Estratégia (label no sinal) |
|---|---|
| **HYPE** | `Breakout / Tendência` |
| **PAXG** | `Acúmulo (RSI sobrevenda)` |
| **LINK** | `Tendência MACD — Agressivo` |
| BTC, ETH, SOL, XRP, TRX, BNB, AAVE | `Integrada (Curto Prazo)` / `Tendência MACD` / `Integrada + MACD (Confluência)` |

---

## 3. Detalhamento de cada estratégia

### 3.1 Integrada (Curto Prazo)  — confiança 8/10
**Quem usa:** 7 ativos do caminho normal.
**Condições de entrada (LONG), todas obrigatórias:**
- Preço **acima do VWAP**
- **EMA9 > EMA21 > EMA50** (tendência empilhada)
- **MACD > linha de sinal** (ideal acima de zero; abaixo de zero = sinal mais fraco)
- **RSI entre 40 e 65** (saudável, sem sobrecompra)
- **Pullback**: preço a <= 0,5% da EMA9 **ou** do VWAP (timing de entrada)

### 3.2 Tendência MACD  — confiança 7/10
**Quem usa:** 7 ativos do caminho normal (sem VWAP).
**Condições de entrada (LONG):**
- Preço **acima da EMA200** (tendência de alta confirmada)
- **MACD cruzou acima da linha de sinal NA vela atual**
- Cruzamento ocorreu **abaixo da linha zero** (setup clássico de reversão de momentum)

### 3.3 Integrada + MACD (Confluência)  — confiança 10/10
**Quem usa:** 7 ativos do caminho normal.
**Condição:** as estratégias 3.1 e 3.2 **disparam na mesma vela** — sinal mais forte.
**Bônus Multi-TimeFrame (MTF):** +1 se tendência 4h confirmada (EMA50>EMA200 e preço>EMA200); +1 se houver pullback 15m próximo à EMA9.

### 3.4 Tendência MACD — Agressivo  — confiança 5/10
**Quem usa:** LINK (perfil `agressivo`). Validada em backtest 90d (LINK PF 3.26).
**Condições de entrada (vela fechada):**
- **MACD cruzou acima do sinal**
- Preço **acima da EMA200** (filtro mínimo de tendência)
- **RSI entre 40 e 70**
> Variante "MACD-only": menos filtros que o caminho normal → entra mais cedo, aceita mais risco.

### 3.5 Breakout / Tendência  — trend-following
**Quem usa:** HYPE. Config `lookback=30, atr_mult=2.5` (PF 2.55, +67% em ~150d, MDD -16,9%).
**Condições de entrada (vela fechada):**
- **EMA9 > EMA21 > EMA50** (tendência empilhada de alta)
- **Close rompe a máxima das últimas 30 velas** anteriores (sem lookahead)
- **RSI > 50** (momentum, sem teto → deixa correr)
**Saída:** stop inicial largo = entry − 2.5×ATR + **trailing stop**. Alvos R:R 1:2 e 1:3 são apenas informativos (filosofia: deixar o lucro correr).

### 3.6 Acúmulo (RSI sobrevenda)  — BUY only (DCA)
**Quem usa:** PAXG (ouro digital).
**Condição:** **RSI cruza para baixo de 30** no timeframe 4h (zona de sobrevenda).
- `rsi_extreme = 20` → marca "sobrevenda extrema" (oportunidade rara)
- `cooldown = 24h` → evita spam enquanto o RSI fica preso embaixo
**Saída:** **nenhuma** — é acúmulo/hold, sem stop nem alvo de venda.

---

## 4. Alvos e risco

| Parâmetro | Valor |
|---|---|
| Stop | entry − 1.5 × ATR |
| **TP1** | R:R **1:2** (entry + 3.0 × ATR) |
| **TP2** | R:R **1:3** (entry + 4.5 × ATR) |
| Risco/Retorno exibido | 1:2 (sobre o TP1) |

> Exceções: **HYPE** usa stop 2.5×ATR + trailing (alvos só informativos); **PAXG** não tem stop nem alvo.

## 5. Como aparece no sinal (Telegram)

Cada sinal agora mostra o **nome da estratégia + uma linha curta explicando**:

```
📐 *Estratégia:* `Tendência MACD — Agressivo`
   _MACD-only: cruzamento acima do sinal (perfil agressivo)_
```

## 6. Kill-switches

| Flag | Efeito |
|---|---|
| `BREAKOUT_ENABLED=False` | desliga HYPE |
| `BREAKOUT_SHADOW_MODE=True` | sinais HYPE marcados `[SHADOW]` |
| `ACTIVE_PROFILE="balanceado"` | tira LINK do agressivo → caminho normal |
| `ACCUMULATION_ENABLED=False` | desliga acúmulo PAXG |
