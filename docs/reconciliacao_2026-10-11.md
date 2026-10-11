# Reconciliacao 11/10/2026 - HYPE legado, BTC manual e placar real

## Evidencia
- Portfolio Gate (11/10): sem HYPE; BTC 0.0031756; PAXG 0.0529; BNB 0.00281; USDT 664,55. Usuario confirmou: **sem ordens abertas**.
- Fill 32259235 (13/08 10:39 BRT): venda de 0.100 HYPE a 57.91 = TP 57.90 do lote legado. Vendas manuais de 11/08 (0.178 HYPE) antes disso. Lote zerado, ~-$2.41.
- BTC manual: TP1 disparou em 21/09 (fill 219897268, 0.0021 a 84.981,6). Nao ha venda posterior; o runner de 0.0031756 segue na carteira sem TP2/SL.
- `state/positions.jsonl` mantinha o lote HYPE legado como `open_unmanaged_protected`.

## Achado: o registro "aberto" bloqueava o HYPE
`executor._open_count_for_symbol` conta todo status que comeca com `open`. Com a trava de concentracao ligada (max 1 posicao viva por ativo), cada sinal de HYPE era recusado com "ja ha 1 posicao(oes) aberta(s) em HYPE/USDT". `state/paper_trades.jsonl` tem **17 bloqueios** desse tipo entre 23/08 e 11/10. Isso explica "nenhum trade de HYPE desde 22/08" (nao era ausencia de sinal).

## Decisao
1. Fechar o registro (`closed_manual`) em `state/positions.jsonl`, linha `legacy_hype_pre_bot`, sem apagar historico.
2. Corrigir `estado_atual.md`, `runbook_btc_manual.md` e `resultado_financeiro.md` (secao 6).
3. **Efeito colateral esperado:** o trilho Breakout HYPE volta a poder enviar ordens reais (teto $10, ate 2 por dia). Isso nao foi decidido por backtest; so deixou de ser bloqueado por um registro errado. HYPE ao vivo teve PF ~0.78 em 12 trades, abaixo do backtest.
   **Decisao (13/10/2026):** o usuario optou por NAO religar o HYPE. `BREAKOUT_ENABLED = False` em `bot/config.py` no mesmo commit da reconciliacao. Para religar: voltar para `True`.
4. BTC manual (0.0031756) e PAXG (0.0529) seguem sem protecao e fora do bot. Decisao de reproteger e do usuario.

## Rollback
- Para o bot parar de operar HYPE sem reabrir o registro: `BREAKOUT_SYMBOLS` sem `HYPE/USDT` (ou `BREAKOUT_ENABLED = False`) em `bot/strategies.py`/`config.py`.
- Para desfazer so o fechamento do registro: `git revert` do commit desta reconciliacao.

## Pendencias
- Conferir o fill de venda do BTC de 03/09 (stop de 15/09) entre 10/09 e 19/09 no historico da Gate.
- Pendencia 5 do contexto (HYPE legado ainda existe?): **resolvida, nao existe**.
