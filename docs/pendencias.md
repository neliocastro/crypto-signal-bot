# Pendências e próximos passos

> Estado volátil do projeto (D-038): o que falta fazer e o que acompanhar. Muda a cada sessão; as **decisões** ficam no
> `memoria.md`. Ao resolver um item, apague-o daqui e registre o resultado onde ele pertence (decisão → `memoria.md`,
> procedimento → `operacao.md`). Datas em AAAA-MM-DD; horários em UTC.
> Revisado em 2026-10-20.

## Pendências
- **Trigger do scan pelo servidor (D-039)**: código no Git; falta o `SELF_DISPATCH_PAT` no `.env` (token de 09/10 ou um
  novo, trocando também o secret do GitHub), o deploy por hash em `/home/ineocom/cryptosignals/bin/`, trocar a linha
  do crontab (hoje aponta para `/home/ineocom/Cryptosignas/`, inexistente) e conferir HTTP 204 no log (`operacao.md`,
  seção 9). Depois: guardar o `trigger_scan.sh` antigo como backup e removê-lo.
- **Re-disparo do `main.yml` tenta uma vez só**: um HTTP 500 passageiro do GitHub quebrou a corrente em 2026-10-19
  23:30 UTC (P-18). Avaliar nova tentativa no passo "Re-arm" (mudança no `main.yml`, com plano).
- **Watchdog externo (D-037)** alerta só depois de 60 a 90 min de parada (viu 58,1 min às 00:30 de 2026-10-20 e não
  alertou). Avaliar limite menor (ex.: 30 min) depois que o trigger do servidor estiver de pé.
- **Pasta pública (D-040)**: contida com `.htaccess`. Falta decidir se `gerar_teste_trx.php` (sem uso conhecido) sai
  do servidor e se os logs de acesso do domínio existem em outro caminho (o `grep` deu 0 linhas, não conclusivo).
- **Cron PAXG (D-032)**: fix do P-16 deployado em 2026-10-15 (commit `8dc5668a`, sha256 `0e3624f6…`). Falta ver o
  primeiro `COMPRA OK` no `paxg_cron.log` e o SL −15% na Gate. Em aberto (o usuário manteve o D-032 por enquanto):
  registrar essas compras em `positions.jsonl`; se for feito, o trailing precisa pular o PAXG, pois
  `MARE_ALTA_SYMBOLS = []` trocaria o SL −15% por `close − 3×ATR`. A whitelist do PHP precisa manter o PAXG.
- **Gatilhos expiram em 30 dias**: o SL é renovado (D-033). Falta renovar o TP1 (ação nova no PHP + deploy) e
  confirmar na API da Gate o nome do status de gatilho expirado (o alerta cobre `expired/cancelled/failed`).
- **Placar**: estimado pelo gatilho (D-034). Falta o fill real da saída (o `oco_sync` do PHP consultar a ordem
  executada; exige deploy).
- **Reauditoria do degrau**: `python scripts/placar.py --degrau`. Em 2026-10-15: 6/20 trades (−US$ 2,41, PF 0); sem os
  de cadência degradada, 3/20 (−US$ 1,15, PF 0). Reprovado; reauditar ao chegar a 20.
- **Tabelas de precisão de fallback divergem** entre PHP (`$SAFE_PRICE_PREC`: TRX 4, HYPE 2) e Python
  (`_SAFE_PRICE_PREC`: TRX 5, HYPE 3). Só valem se `/spot/currency_pairs` falhar; conferir na Gate e alinhar.
- **BTC manual do usuário** (0,0031756 BTC) sem ordens de proteção desde 2026-09-21: decisão do usuário.

## Próximos passos
1. Acompanhar a primeira compra com TP1 parcial (mensagens "TP1 parcial NAO aplicado" ou "🎯 TP1" no Telegram) e o
   primeiro fechamento com `pnl_usdt_est` gravado (D-034).
2. Revisar a estratégia só com amostra limpa (pós-2026-10-09): Maré Alta 0/6 desde 2026-09-04, parte em cadência
   degradada.
