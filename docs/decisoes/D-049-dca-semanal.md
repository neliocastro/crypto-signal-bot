# D-049 — DCA semanal sem stop em BTC e PAXG

> Status: aprovada em 2026-10-23 | substitui: D-032 (cron de acúmulo do PAXG) e, em parte, D-006/R-006 e D-003 |
> substituída por: —

## Contexto
Os backtests de 2026-10-23 (D-048) mostraram que comprar pelo RSI 4h < 30 não supera um DCA simples de forma
consistente, que o stop de −15% destrói o acúmulo (72 de 90 lotes de BTC vendidos) e que o cron do PAXG (D-032),
que é exatamente esse RSI com stop, rendeu −2,2% contra +0,4% do DCA no período. O usuário decidiu trocar o
acúmulo por um DCA simples em BTC e PAXG e perguntou como isso convive com a Tendência Diária no BTC.

Restrições: o relay recusa qualquer compra sem TP nem SL (D-006, `REQUIRE_PROTECTION`); a exceção para o PAXG
comprar sem proteção tinha sido rejeitada (R-006); a trava de concentração permite 1 posição viva por ativo
(D-022); o teto é US$ 10 por ordem (D-024).

## Alternativas
| Opção | Prós | Contras |
|---|---|---|
| **A. DCA sem stop, com exceção no relay só para `strategy == "DCA"` (escolhida)** | o bot nunca vende o acúmulo; entra no Telegram e no placar; teto por ordem e mensal | muda o `execute.php` (FIX 11, deploy manual) e reverte o R-006 para o caso DCA |
| B. DCA com stop de catástrofe (ex.: −40%) | não mexe no PHP | numa queda forte vende a carteira; o backtest mostrou o estrago com −15% |
| C. Compra recorrente da própria Gate | zero código | fora do placar e do Telegram; não conferido se a conta tem o recurso |

## Decisão
Opção A, com US$ 10 por semana em BTC e em PAXG (escolha do usuário), a partir de segunda-feira 13:00 UTC.
- **Relay (FIX 11):** aceita compra sem TP/SL só com `strategy == "DCA"` e ativo em `$DCA_WHITELIST`
  (BTC, PAXG); o teto por ordem continua. Rollback: `$DCA_NO_PROTECTION = false`.
- **Bot (`bot/dca.py`):** uma tentativa por ativo por semana ISO (`signal_id = dca-<PAR>-<semana>`), grava a
  tentativa antes de enviar (sem compra dobrada), teto mensal por ativo (US$ 50), passa pelas travas do executor.
  Registro próprio em `state/dca.jsonl`. Kill-switch `DCA_ENABLED`, ligado só depois do deploy do FIX 11.
- **Convivência com a Tendência Diária no BTC:** o DCA fica **fora do `positions.jsonl`**. Por isso não conta na
  trava de 1 posição viva por ativo (D-022), não entra no trailing, no OCO nem na renovação de SL; a Tendência
  Diária compra e vende só a quantidade das posições dela. O DCA conta nas travas de ordens por dia e no teto por
  ordem. O D-003 ("1 ativo = 1 trilho") passa a valer para os trilhos de trade; o DCA é uma carteira à parte.
- **Cron do PAXG:** pausado já (`.paxg_pause`, escolha do usuário); a linha do crontab sai quando o DCA estiver no ar.

## Consequências
- O saldo de BTC na Gate é um só (trade, DCA e BTC manual). Os stops dos trades vendem só a quantidade de cada
  posição, mas os gatilhos não reservam saldo: venda manual pode deixar um stop sem saldo.
- Uso de capital: ~US$ 87/mês nos dois ativos; o saldo em USDT também serve aos trades.
- O DCA não tem saída: o resultado é medido por custo médio e valor atual, no placar, não por PF.
- Falha numa semana não gera nova tentativa automática (proteção contra compra dobrada): o Telegram avisa.

## Referências
`server/execute.php` (FIX 11), `bot/dca.py`, `tests/test_dca.py`, `docs/backtests/acumulo_20261023.md`, D-048.
