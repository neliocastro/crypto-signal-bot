# Pendências e próximos passos

> Estado volátil do projeto (D-038): o que falta fazer e o que acompanhar. Muda a cada sessão; as **decisões** ficam no
> `memoria.md`. Ao resolver um item, apague-o daqui e registre o resultado onde ele pertence (decisão → `memoria.md`,
> procedimento → `operacao.md`). Datas em AAAA-MM-DD; horários em UTC.
> Revisado em 2026-10-21.

## Pendências
- **Backup do `.env`**: apagar `/home/ineocom/cryptosignals/secrets/.env.bak-20261020` depois da primeira compra
  real bem-sucedida (é ela que exercita as chaves da Gate e o HMAC do `.env` atual). Tokens antigos já revogados e
  backups com token vencido já apagados em 2026-10-21.
- **DCA semanal (D-049)**: código no Git, `DCA_ENABLED = False`. Falta: deploy do `execute.php` com o FIX 11 (por
  hash), ligar `DCA_ENABLED`, conferir a 1ª compra de cada ativo (segunda 13:00 UTC) e, depois, tirar a linha do cron
  do PAXG do crontab (já pausado com `.paxg_pause`) e arquivar `paxg_rsi_check.php`/`gerar_teste_paxg.php` fora da
  pasta pública.
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
- **Telegram, Fases 2 a 4** (plano de 2026-10-21): catálogo de estratégias no `config.py` com liga/desliga pelo
  Telegram (exige decisão que ajuste o D-004 e a proibição do `CLAUDE.md`); DCA (decidir proteção: D-006/R-006);
  combinações novas (Maré Alta no HYPE, range trading) só após backtest (P-12).
1. Acompanhar a primeira compra com TP1 parcial (mensagens "TP1 parcial NAO aplicado" ou "🎯 TP1" no Telegram) e o
   primeiro fechamento com `pnl_usdt_est` gravado (D-034).
2. Revisar a estratégia só com amostra limpa (pós-2026-10-09): Maré Alta 0/6 desde 2026-09-04, parte em cadência
   degradada.
