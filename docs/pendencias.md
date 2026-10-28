# Pendências e próximos passos

> Estado volátil do projeto (D-038): o que falta fazer e o que acompanhar. Muda a cada sessão; as **decisões** ficam no
> `memoria.md`. Ao resolver um item, apague-o daqui e registre o resultado onde ele pertence (decisão → `memoria.md`,
> procedimento → `operacao.md`). Datas em AAAA-MM-DD; horários em UTC.
> Revisado em 2026-10-26.

## Em andamento
Tarefas que atravessam sessões ou máquinas (D-051): objetivo, feito, próximo passo, bloqueios. Nada pessoal.
- **Claude Code na nuvem (D-051)**: `CLOUD_SETUP.md`, `.env.example` e `.gitignore` prontos em 2026-10-27. Próximo
  passo é do usuário: criar o ambiente (Trusted, sem variáveis, sem network secrets, setup da seção 2) e rodar o
  checklist da seção 7. No `main`, só o ruleset de Restrict deletions + Block force pushes (nada de exigir PR ou status check: P-22).

## Pendências
- **Relay FIX 12 (D-050)**: deployado e ligado em 2026-10-23 (sha256 `809cb3cc…`). Falta conferir o primeiro fechamento
  com `exit_basis: fill_real` e, quando houver um TP1 com 25 dias, a primeira renovação. O nome do status de
  gatilho vencido segue sem confirmação (nenhum venceu ainda); o alerta cobre `expired/cancelled/failed`.
- **DCA semanal (D-049)**: ligado em 2026-10-23 (FIX 11 no servidor, sha256 `945b2015…`). 1ª compra em 2026-10-26
  13:03 UTC (semana 2026W44), ambas `filled` em `state/dca.jsonl`: BTC US$ 9,94 (0,000124 BTC) e PAXG US$ 8,06
  (0,002 PAXG). Falta: conferir na Gate a ordem do PAXG `1155916130372` (`finish_as`, para descartar fill parcial por
  liquidez) e a do BTC `1155916086454`. O cron do PAXG foi aposentado em 2026-10-26 (linha fora do crontab; scripts
  em `/home/ineocom/cryptosignals/arquivo/`, junto com o `paxg_rsi_check.php.bak-20261015`).
- **DCA abaixo de US$ 10 (achado 2026-10-26)**: o PAXG ficou em US$ 8,06 porque a Gate compra em passos de 0,001
  PAXG (`amount_precision` 3, ~US$ 4) e arredonda para baixo: US$ 10 ÷ US$ 4.030 = 0,00248 → 0,002. Dedução pelos
  números do registro, ainda não confirmada na API. Não é bug e respeita o teto D-024; o aporte do PAXG fica
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
