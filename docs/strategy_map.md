# Mapa de Estratégias (roteamento por trilho — vigente desde 2026-07-10)

| Trilho | Ativos | Timeframe | Executa ordem? | Telegram? |
|---|---|---|---|---|
| Maré Alta D1 | BTC, ETH, SOL, XRP, TRX, BNB | D1 | SIM (único p/ esses 6) | SIM |
| Breakout / Tendência | HYPE | 1h | SIM | SIM |
| Acúmulo (RSI sobrevenda) | PAXG | 4h | SIM | SIM |

## Regras
- O scan 1h NÃO emite mais sinais informativos no Telegram nem executa ordens
  fora do allowlist `INTRADAY_EXEC_ALLOWLIST` em `bot/main.py`
  {(HYPE, Breakout), (PAXG, Acúmulo)}.
- Estratégias "Tendência MACD — Agressivo", "Integrada (Curto Prazo)",
  "Tendência MACD" e "Integrada + MACD (Confluência)" estão DESATIVADAS como
  fonte de sinal/execução (código permanece p/ referência).
- AAVE e LINK removidos da watchlist (2026-07-10); ver
  docs/backtests/2026-07-mare-alta-d1.md. Reavaliação futura prevista.

## Incidentes que motivaram a mudança
- 2026-07-05: ETH comprado pelo trilho 1h "Tendência MACD — Agressivo" (fill
  1779.58) enquanto a política previa ETH exclusivo no Maré Alta D1.
- 2026-07-10: constatado na Gate.io que TP/SL logados como HTTP 201 NÃO
  existiam na corretora (gatilho órfão de 02/07 cancelado manualmente pelo
  operador). PENDÊNCIA ABERTA: verificação pós-criação de TP/SL no relay
  (consultar gatilhos após criar; não confiar apenas no HTTP 201).
