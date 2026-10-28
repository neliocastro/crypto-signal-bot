# Pendências e próximos passos

> Estado volátil do projeto (D-038): o que falta fazer e o que acompanhar. Muda a cada sessão; as **decisões** ficam no
> `memoria.md`. Ao resolver um item, apague-o daqui e registre o resultado onde ele pertence (decisão → `memoria.md`,
> procedimento → `operacao.md`). Datas em AAAA-MM-DD; horários em UTC.
> Revisado em 2026-10-26.

## Em andamento
Tarefas que atravessam sessões ou máquinas (D-051): objetivo, feito, próximo passo, bloqueios. Nada pessoal.
- Nenhuma. O Claude Code na nuvem (D-051) foi concluído em 2026-10-28: ambiente `crypto-signal-bot` criado e validado,
  ruleset do `main` ativo (só Restrict deletions + Block force pushes; nada de exigir PR ou status check: P-22) e setup
  script só com o `ccxt`.

## Pendências
- **Relay FIX 12 (D-050)**: deployado e ligado em 2026-10-23 (sha256 `809cb3cc…`). Falta conferir o primeiro fechamento
  com `exit_basis: fill_real` e, quando houver um TP1 com 25 dias, a primeira renovação. O nome do status de
  gatilho vencido segue sem confirmação (nenhum venceu ainda); o alerta cobre `expired/cancelled/failed`.
- **DCA semanal (D-049)**: ligado em 2026-10-23 (FIX 11 no servidor, sha256 `945b2015…`). 1ª compra em 2026-10-26
  13:03 UTC (semana 2026W44), ambas `filled` em `state/dca.jsonl`: BTC US$ 9,94 (0,000124 BTC) e PAXG US$ 8,06
  (0,002 PAXG). Conferidas na Gate em 2026-10-28 (`GET /spot/orders/{id}`): PAXG `1155916130372` e BTC `1155916086454`
  estão `closed`, `finish_as: filled`, sem fill parcial, e batem com o registro (PAXG `filled_total` 8,06024 a
  4.030,12; BTC 9,9419673 a 80.177,16). O cron do PAXG foi aposentado em 2026-10-26 (linha fora do crontab; scripts
  em `/home/ineocom/cryptosignals/arquivo/`, junto com o `paxg_rsi_check.php.bak-20261015`).
- **DCA abaixo de US$ 10 (achado 2026-10-26)**: o PAXG ficou em US$ 8,06 porque a Gate compra em passos de 0,001
  PAXG (`amount_precision` 3, ~US$ 4) e arredonda para baixo: US$ 10 ÷ US$ 4.030 = 0,00248 → 0,002. Confirmado
  pela ordem na Gate em 2026-10-28: o `left` de US$ 1,93976 é exatamente `10 − filled_total` (arredondamento do passo,
  não falta de liquidez); o `amount_precision` em si não foi consultado. Não é bug e respeita o teto D-024; o aporte do PAXG fica
  abaixo do valor (hoje ~80%; com o preço menor pode cair mais, ex.: ~57% a US$ 3.500). Recomendação: não mexer (compensar o resto ou subir o valor mexe em sizing e pede
  aprovação). O `acumulado()` do `bot/dca.py` usa o `filled_total` real, então o custo médio fica certo.
- **Reauditoria do degrau**: `python scripts/placar.py --degrau`. Em 2026-10-15: 6/20 trades (−US$ 2,41, PF 0); sem os
  de cadência degradada, 3/20 (−US$ 1,15, PF 0). Reprovado; reauditar ao chegar a 20.
- **BTC manual do usuário** (0,0031756 BTC) sem ordens de proteção desde 2026-09-21: decisão do usuário.

## Próximos passos
- **Telegram, Fases 2 a 4** (plano de 2026-10-21): catálogo de estratégias no `config.py` com liga/desliga pelo
  Telegram (exige decisão que ajuste o D-004 e a proibição do `CLAUDE.md`); DCA (decidir proteção: D-006/R-006);
  combinações novas (Maré Alta no HYPE, range trading) só após backtest (P-12).
1. Acompanhar a primeira compra com TP1 parcial (mensagens "TP1 parcial NAO aplicado" ou "🎯 TP1" no Telegram) e o
   primeiro fechamento com `pnl_usdt_est` gravado (D-034).
2. Revisar a estratégia só com amostra limpa (pós-2026-10-09): Maré Alta 0/6 desde 2026-09-04, parte em cadência
   degradada.
