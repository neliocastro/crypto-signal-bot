# Ajuste do stop — backtest de 180 dias (HYPE)

> Rodado em 2026-08-23 sobre **4.321 candles 1h reais** da Gate.io
> (24/02/2026 → 23/08/2026), pares HYPE_USDT, custo 0,1% ida + 0,1% volta.
> Motivacao: `docs/revisao_ativos_2026-08.md` mostrou PF REAL 0,60 contra 2,55
> do backtest original. Hipotese testada: **o stop de 2,0xATR esta dentro do
> ruido intraday do HYPE**.

## Metodo

Estrategia identica a de producao (`_check_breakout_trend`):
EMA9>EMA21>EMA50 + rompe maxima de 30 velas + RSI>50.
Saida: stop = `max(mult * ATR14, 0.8% do preco)`, TP = RR x risco.
Varrido apenas o **multiplicador do stop**; todo o resto constante.

## Resultado (RR 2.0 — igual a producao)

| SL mult | Trades | Wins | WR % | **PF** | Retorno % |
|---|---|---|---|---|---|
| 2,0 (atual) | 65 | 26 | 40,0 | **1,18** | +19,5 |
| 2,5 | 54 | 22 | 40,7 | 1,31 | +33,4 |
| **3,0** | **42** | **17** | **40,5** | **1,50** | **+47,1** |
| 3,5 | 39 | 14 | 35,9 | 1,26 | +27,6 |
| 4,0 | 31 | 13 | 41,9 | 1,49 | +44,1 |
| 5,0 | 26 | 11 | 42,3 | 1,55 | +51,1 |

### Controle com RR 3.0

| SL mult | Trades | WR % | PF | Retorno % |
|---|---|---|---|---|
| 2,0 | 51 | 37,3 | 1,71 | +60,8 |
| 3,0 | 31 | 35,5 | 1,73 | +53,6 |
| 5,0 | 20 | 35,0 | 1,77 | +60,5 |

## Leitura

1. **O win rate quase nao muda** (40,0% -> 40,5%). O que muda e o **numero de
   trades**: 65 -> 42. Ou seja, ~35% das operacoes atuais sao **ruido**:
   entradas validas estopadas antes de o movimento acontecer. Isso explica os
   9 SL contra 3 TP observados na producao.
2. **3,0xATR e o ponto de equilibrio.** 5,0xATR tem PF marginalmente maior
   (1,55) mas com apenas 26 trades e stop de ~13% do preco: amostra fraca e
   risco por trade alto demais para um canario de $10.
3. 3,5xATR quebra a monotonia (PF 1,26). A curva **nao e suave** — sinal de que
   a amostra ainda e pequena. Nao superajustar: 3,0 e uma escolha de regiao,
   nao de pico.
4. RR 3.0 tambem melhora o PF, mas reduz o win rate e alonga o tempo em
   posicao. **Nao alterado nesta rodada** — uma variavel por vez.

## Decisao

**`EXECUTION_ATR_MULT_SL`: 2.0 -> 3.0** (uma linha em `bot/config.py`).

### Alcance da mudanca (importante)

Esse parametro e da **camada de execucao**, nao do HYPE. Ele vale para **toda
compra que o executor protege** — inclui os 6 ativos do Mare Alta D1. O
backtest foi feito **so no HYPE**, entao para os demais isto e uma
**extrapolacao**. Justificativa para aceitar mesmo assim:

- O piso `EXECUTION_MIN_STOP_PCT = 0.8%` continua ativo (protege ativos de ATR
  baixo, caso TRX).
- Stop mais largo em D1 e coerente com a propria Mare Alta, que ja usa
  2,5xATR no stop inicial e 3,0xATR no trailing.
- O teto por ordem segue $10: o risco absoluto por trade continua irrisorio.

### Efeito pratico esperado

- Menos trades (estimativa: -35%), menos taxas.
- Perda por trade maior em % (de ~-1,8% para ~-2,7%), compensada por menos
  perdas.
- TP mais distante (RR 2.0 sobre risco maior): alvo passa de ~+3,6% para
  ~+5,4%.

## Reavaliacao

Revisar ao atingir **10 trades fechados** com a nova configuracao. Criterio de
sucesso: WR >= 33% (break-even com RR 2.0) e PF >= 1. Se o PF real continuar
abaixo de 1 com o stop largo, a hipotese do ruido estara descartada e o proximo
passo e voltar o HYPE para shadow.

**Rollback:** `EXECUTION_ATR_MULT_SL = 2.0` em `bot/config.py`.

---

_Backtest com dados publicos da Gate.io (`/api/v4/spot/candlesticks`). Nao usa
dados privados de conta._
