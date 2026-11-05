# D-053 — Degrau conta só trades com a saída atual

> Status: aprovada em 2026-11-05 | ajusta: D-024 (só a janela de contagem) | substituída por: —

## Contexto
O D-024 conta, para o degrau de US$ 20, os trades abertos desde 2026-09-04. Até 2026-10-15 a Tendência Diária usava
outra saída: TP único em 2,0R e trailing desde o primeiro dia, que subia o stop com a vela D1 ainda em formação
(P-11). Em 2026-10-15 entraram a saída validada (D-027: TP1 +10% em 50%, breakeven, trailing só depois do TP1) e o
trailing com vela fechada (D-026).

A auditoria de 2026-11-05 refez os 7 trades da janela com a regra atual
(`docs/backtests/tendencia_diaria_20261105.md`). O resultado foi de −US$ 2,96 para −US$ 1,37: três trades que
perderam (BNB 05/09, TRX 10/09, SOL 20/09) teriam ganhado. O SOL subiu +12,9% e saiu no prejuízo porque o stop
tinha subido junto. Só 1 dos 7 (TRX 30/10) rodou com a regra atual. O R-003 já diz que só conta o regime atual.

## Alternativas
| Opção | Prós | Contras |
|---|---|---|
| A (escolhida): contar desde 2026-10-15 | mede a estratégia que roda hoje (R-003) | recomeça do zero; com ~16 trades/ano nos 4 ativos, 20 trades levam mais de 1 ano |
| B: manter 2026-09-04 | amostra maior já acumulada | 6 dos 7 trades medem uma regra que não existe mais; reprova (ou aprova) pela regra errada |
| C: mudar a estratégia já | resposta rápida ao resultado ruim | sem evidência: a regra atual quase não rodou e o backtest dela segue positivo nos 4 ativos |

## Decisão
O degrau de US$ 20 passa a contar só trades **abertos a partir de 2026-10-15**, com os mesmos critérios do D-024
(20 trades, P&L > 0, PF ≥ 1). `scripts/placar.py --degrau` usa a nova data (`DEGRAU_DESDE`) e mostra a janela antiga
só como referência. Rollback de 1 linha: `DEGRAU_DESDE = "2026-09-04"`.

## Consequências
- Mais demora para o degrau, de propósito: é o custo de medir a regra certa.
- O teto continua US$ 10 por ordem e nenhum parâmetro de execução muda.
- Reavaliar a estratégia com a amostra nova. Se houver queda forte de PF antes dos 20 trades, revisar com o backtest
  versionado (`scripts/backtest_tendencia_diaria.py`), sem afrouxar regra para "fazer passar" (P-12).

## Referências
`docs/backtests/tendencia_diaria_20261105.md`, `scripts/backtest_tendencia_diaria.py`, `scripts/placar.py`;
D-024, D-026, D-027, R-003, P-11.
