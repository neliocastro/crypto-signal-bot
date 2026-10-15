# Trailing do Mare Alta so com vela D1 fechada - 2026-10-15

> Mudanca de execucao **aprovada pelo usuario em 15/10/2026** (item 2 da auditoria
> abaixo). Kill-switch: `MARE_ALTA_TRAILING_CLOSED_ONLY` em `bot/config.py`.

## Contexto

A auditoria de 15/10 conferiu cadencia, relay, compras reais e SL/TP. Resultado:

- **Ativo e saudavel:** 278 scans com sucesso em 24h (intervalo max 5 min); relay
  `execute.php` no ar (HTTP 401 para pedido sem assinatura, correto).
- **Sem compra desde 22/09 por falta de sinal, nao por falha.** Recalculo da regra
  Mare Alta com velas D1 reais da Gate: unicos sinais desde 15/09 em 19/09 (SOL,
  TRX), 20/09 (BNB) e 21/09 (BTC), iguais a `state/mare_alta_state.json`. Em
  14/10 os 4 ativos estavam com MACD < sinal e EMA9 < EMA21.
- **SL/TP de entrada corretos:** SL = ref - 2.5 x ATR, TP = ref + 2.0 x risco.
  Ex.: SOL 20/09 ref 111.06, ATR 5.153 -> SL 98.18, TP 136.82 (batem com o log).

## Evidencia do problema (item 2)

`main._fetch_d1_candles` passava ao trailing as 60 velas D1 da Gate, **incluindo a
vela do dia em formacao**. `update_trailing` usa `candles[-1]["close"]` (preco ao
vivo) e um ATR que inclui o range parcial. Como roda a cada scan (~5 min), o stop
subia com picos intradia, nao com o fechamento diario usado no backtest.

Simulacao 20/09 -> 08/10 com candles reais:

| Ativo | SL real no fim | Sim. vela fechada | Sim. intradia (maxima) | Minima 08/10 |
|---|---|---|---|---|
| SOL | 108.39 | 107.13 | 108.43 | 105.72 |
| BNB | 743.5 | 727.54 | 745.63 | 717.2 |
| BTC | 80899.5 | 80390.28 | 80949.97 | 80397.1 |

Os stops reais batem com a simulacao pela maxima do dia. Com vela fechada, **o BTC
nao teria sido stopado em 08/10** (stop 80390 vs minima 80397). SOL e BNB sairiam
de qualquer forma.

## Decisao

`MARE_ALTA_TRAILING_CLOSED_ONLY = True`: `_fetch_d1_candles` descarta velas cuja
abertura + 1 dia ainda esta no futuro (a vela em formacao). O trailing passa a usar
o ultimo **fechamento D1** e o ATR so de velas fechadas.

- Stop inicial (2.5x ATR na compra), TP, catraca e relay: **inalterados**.
- Nenhum `EXECUTION_*` nem `server/execute.php` alterado.
- Na data da mudanca nao havia posicao aberta do bot (nenhum stop existente afetado).

**Teste (15/10, candles reais, relay simulado):** com a flag, 59 de 60 velas (a de
15/10 descartada), close usado = 14/10 (BTC 81672.0, SOL 104.29); sem a flag, 60
velas e close ao vivo. Canario e `py_compile` OK.

## Rollback

`MARE_ALTA_TRAILING_CLOSED_ONLY = False` em `bot/config.py`.

## Pendente de decisao do usuario (item 1 da auditoria, NAO alterado)

A saida validada no backtest fiel do Mare Alta e: TP1 +10% vendendo 50% -> stop no
breakeven -> trailing 3x ATR. **A execucao real nao faz TP1 parcial nem breakeven**:
envia um TP unico em 2.0x o risco (~+23%) para 100% da posicao + trailing. Os campos
`tp1` de `mare_alta.py` so aparecem na mensagem do Telegram. Opcoes: implementar a
saida validada ou backtestar a saida atual.

Item 3 (menor): posicoes `closed_sl` nao gravam `exit_price`; o placar usa o preco do stop.
