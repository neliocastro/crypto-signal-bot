# Pendências e próximos passos

> Estado volátil do projeto (D-038): o que falta fazer e o que acompanhar. Muda a cada sessão; as **decisões** ficam no
> `memoria.md`. Ao resolver um item, apague-o daqui e registre o resultado onde ele pertence (decisão → `memoria.md`,
> procedimento → `operacao.md`). Datas em AAAA-MM-DD; horários em UTC.
> Revisado em 2026-10-19.

## Pendências
- **Watchdog externo (D-037)**: instalado no servidor em 2026-10-16 (hash `a3832f5e…` conferido, segredos no `.env`,
  `--test-telegram` com HTTP 200, crontab no minuto 30). Falta conferir a 1ª execução pelo cron:
  `scan: ok` no `watchdog_cron.log` e `.watchdog_state.json` com dono `ineocom` (`operacao.md`, seção 8).
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
