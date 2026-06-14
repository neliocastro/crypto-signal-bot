# Glossário de Estratégias e Indicadores — crypto-signal-bot

Guia didático para entender, sem jargão, como o bot decide comprar.
Leitura recomendada antes de mexer em qualquer estratégia.

---

## Parte 1 — Os ingredientes (indicadores)

Toda estratégia é uma receita feita com estes 4 blocos:

| Indicador | O que é (analogia) | Para que serve |
|---|---|---|
| **EMA** (média móvel) | O "preço médio recente" suavizado | Mede TENDÊNCIA |
| **MACD** | Duas linhas que se cruzam | Mede o IMPULSO (momentum) e sua direção |
| **RSI** (0-100) | Termômetro: <30 barato, >70 caro | Diz se está CARO ou BARATO |
| **ATR** | Mede o quanto o preço balança | Calcula o tamanho do STOP (volatilidade) |

Resumo: **EMA = tendência · MACD = impulso · RSI = caro/barato · ATR = volatilidade.**

### EMAs usadas
- **EMA9 / EMA21 / EMA50** → curto e médio prazo (timing).
- **EMA200** → longo prazo (regime: alta vs. baixa).

### Dois usos diferentes de EMA (não confundir!)
- **EMA9 > EMA21 > EMA50** ("empilhadas") = a tendência de curto prazo
  está ALINHADA e forte. Responde: "a subida está organizada AGORA?"
- **Preço > EMA200** = estamos em mercado de alta no geral. Responde:
  "estamos do lado certo da maré (macro)?"
- Boas estratégias usam as duas: EMA200 = mapa macro; empilhamento = timing fino.

---

## Parte 2 — As 4 estratégias (receitas)

Cada estratégia é um "caçador" esperando uma presa diferente.

### 1. MACD-only Agressivo — "caçador rápido de viradas"
- **Filosofia:** entra na virada do impulso, pega o movimento e sai rápido.
- **Compra se (as 3 juntas, na vela fechada):**
  1. MACD cruzou ACIMA do sinal (impulso virou positivo)
  2. Preço > EMA200 (mercado de alta)
  3. RSI entre 40 e 70 (nem caro, nem barato demais)
- **Sai:** stop curto (1.5x ATR) + alvos fixos (TP1 R:R 1:2, TP2 1:3).
- **Perfil:** rápida e reativa. Sofre quando o mercado "serra" (sobe-desce),
  pois o stop curto é estourado com facilidade.
- **Validada em backtest:** apenas LINK e HYPE (90d).
- **Usa hoje:** BTC, ETH, SOL, XRP, TRX, BNB, LINK, AAVE.

### 2. Breakout / Tendência — "caçador paciente de grandes ondas"
- **Filosofia:** não sai rápido; monta numa tendência GRANDE e cavalga.
- **Compra se:**
  1. EMA9 > EMA21 > EMA50 (empilhadas = tendência forte)
  2. Preço rompe a máxima das últimas 30 velas (explosão de alta)
  3. RSI > 50 (compradores no controle)
- **Sai:** stop largo (2.5x ATR) + TRAILING STOP (deixa o lucro correr até
  a tendência virar).
- **Perfil:** ganha de POUCOS trades muito grandes; perde pequeno em vários
  quando o mercado fica lateral. Retorno concentrado em 2-3 ralis.
- **Usa hoje:** apenas HYPE.

### 3. Acumulação RSI — "comprador de oportunidade / poupança"
- **Filosofia:** não é trade; é acumular um bom ativo quando fica barato.
- **Compra se:** RSI cruza ABAIXO de 30 no gráfico de 4h (sobrevenda).
  RSI < 20 = barato extremo (oportunidade rara).
- **Sai:** NÃO SAI. Sem stop, sem alvo. Comprar e guardar (estilo DCA).
- **Usa hoje:** apenas PAXG (ouro digital / reserva de valor).

### 4. Integrada + Tendência MACD + MTF — "caçador cauteloso"
- **Filosofia:** só compra quando vários sinais concordam, em vários prazos.
- **Como funciona:** combina EMAs + MACD + RSI numa nota de confiança (1-10)
  e exige confirmação Multi-Timeframe (MTF): 4h (tendência) + 1h (entrada)
  + 15m (timing). Mais segura, menos sinais.
- **Usa hoje:** ninguém — o perfil "agressivo" atual roteia todos para
  MACD-only. É a estratégia "de fábrica" (padrão quando não há regra especial).

---

## Parte 3 — Tabela comparativa

| | MACD-only | Breakout | Acumulação | Integrada/MTF |
|---|---|---|---|---|
| Personalidade | Rápida, reativa | Paciente, monta na onda | Poupança | Cautelosa |
| Gatilho | MACD cruza | Rompe máxima | RSI<30 | Vários sinais + 3 prazos |
| Stop | Curto (1.5 ATR) | Largo (2.5 ATR)+trailing | Sem stop | Médio |
| Sai quando | Alvo fixo | Tendência acaba | Nunca | Alvo/confiança |
| Ganha de | Muitos trades pequenos | Poucos trades grandes | Longo prazo | Trades de qualidade |
| Usa hoje | 8 ativos | HYPE | PAXG | (inativa) |

---

## Parte 4 — O roteamento (o "porteiro")

A função `evaluate_signal` decide qual receita aplicar a cada ativo,
nesta ordem de prioridade:

```
É o HYPE?  -> Breakout/Tendência
É o PAXG?  -> Acumulação RSI 4h
Qualquer outro? -> MACD-only Agressivo
```

Cada ativo passa por UMA estratégia só.

---

## Parte 5 — Por que isso importa (regime de mercado)

Todas as estratégias ativas (MACD-only e Breakout) são de TENDÊNCIA.
Elas funcionam bem quando o mercado sobe de forma direcional, e SOFREM
quando o mercado fica lateral ("serrado"):
- Breakout leva vários stops pequenos esperando uma onda que não vem.
- MACD-only entra e toma stop rápido (stop curto).

Por isso o paper trading (dry-run) é essencial: ele revela se a estratégia
tem edge no regime ATUAL — sem custar dinheiro real.

---

_Documento didático. Para o histórico de decisões e backtests, ver
`docs/strategy_decisions.md`._
