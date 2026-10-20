# Arquivo da memória — decisões substituídas

Decisões que já valeram e foram trocadas. Ficam aqui para explicar o caminho; **não** valem mais.
A decisão vigente está no `memoria.md`. Evidência em `docs/historico/`.

| Decisão antiga | Data | Substituída por | Motivo |
|---|---|---|---|
| Teto US$ 5 por ordem (canário do go-live) | 2026-06-16 | D-024 (US$ 10, 2026-08-12) | infra provada em 9 trades |
| Estratégia MACD-only agressiva em todos os ativos (exceto PAXG) | 2026-06-12 | D-003 / D-011 | sem edge após custos; removida do código em 08/24 |
| ETH e XRP no Maré Alta por decisão consciente, apesar do walk-forward | 2026-07-05 | D-010 (2026-08-23) | backtest fiel PF 0,43 / 0,55 |
| Universo Maré Alta com 6 ativos (BTC, ETH, SOL, XRP, TRX, BNB) | 2026-07-10 | D-010 | idem |
| Stop global 2,0×ATR | go-live | D-020 (2,5×, 2026-08-23) | 2,0× ficava dentro do ruído |
| Stop global 3,0×ATR (decidido de manhã, revertido no mesmo dia) | 2026-08-23 | D-020 + D-021 | 3,0× piora o D1; aplicado só ao HYPE |
| Watchlist do runtime (`state/runtime_config.json`) prevalecia sobre `config.py` | até 2026-08-24 | D-004 | dupla fonte deixou o PAXG como código morto |
| PAXG em acúmulo automático (RSI 4h < 30), BUY-only | 2026-05-29 / 2026-06-28 | D-012 (2026-09-04) | 2 stops em 2 sinais; o "acúmulo sem stop" nunca existiu na execução |
| Breakout HYPE operando real (promovido em shadow em 05/28; data do shadow OFF não registrada) | 2026-05-28 | D-013 (2026-10-13) | PF ao vivo ~0,78 |
| Saída do Maré Alta: TP único 2,0R na base inteira + trailing desde o início | até 2026-10-15 | D-027 | divergia da saída validada |
| Trailing com a vela D1 em formação | 2026-07-04 | D-026 (2026-10-15) | stop subia com picos intradia |
| Diários de decisões (`strategy_decisions.md`, hoje em `historico/`) e um `.md` solto por decisão | 2026-05 a 2026-10 | D-030 | redundância e regras espalhadas |
| D-007 (trecho): token do servidor dentro do script `trigger_scan.sh` chamado pelo crontab | 2026-10-09 | D-039 (2026-10-20) | script não versionado, sem checar HTTP, caminho errado no crontab (P-18) |
| D-030: estrutura `CLAUDE.md` + `memoria.md` (com pendências) + 4 docs + `historico/`, sem `.gitignore`, sem fluxo de trabalho escrito | 2026-10-15 | D-038 (2026-10-19) | pendências voláteis dentro da memória, buracos apontados na comparação com o framework de contexto |
