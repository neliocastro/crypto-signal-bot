# Backtest — AAVE e LINK na lógica Maré Alta D1 (2026-07-10)

## Contexto
Decisão de arquitetura (2026-07-10): cada ativo opera por UM único trilho executor.
Antes de rotear AAVE ao Maré Alta D1, foi rodado backtest dedicado da regra exata
(MACD 12/26/9 cruza p/ cima + EMA9>EMA21 na MESMA vela D1 fechada; trailing stop
ratchet 3×ATR14; custos 0,2% fee + 0,05% slippage por perna). Dados: Gate.io D1,
nov/2023 → jul/2026 (~970 velas). LINK incluído como auditoria (estava no universo
sem teste D1 dedicado). BTC/SOL/TRX/BNB como grupo de controle.

## Resultados
| Ativo | Trades | WR | PF | Total | Pior trade |
|---|---|---|---|---|---|
| AAVE | 9 | 22.2% | **0.86** | **-31.4%** | -21.1% |
| LINK | 10 | 40.0% | **0.80** | **-34.8%** | -28.7% |
| BTC | 11 | 45.5% | 1.45 | +10.7% | -12.2% |
| SOL | 7 | 57.1% | 3.49 | +63.9% | -15.6% |
| TRX | 11 | 54.5% | 3.46 | +91.5% | -16.8% |
| BNB | 10 | 70.0% | 4.13 | +59.7% | -9.4% |

## Decisões
1. **AAVE REMOVIDO da lista de ativos.** Reprovado em 3 lógicas: MACD-only 1h
   (PF 0.79), Breakout OOS (PF 0.74, "enfraqueceu"), Maré Alta D1 (PF 0.86).
2. **LINK REMOVIDO da lista de ativos.** Aprovado no MACD-only 1h/90d (PF 3.26),
   mas REPROVADO no D1 longo (PF 0.80, -34.8%). Sai do universo executor.
3. Ambos serão REAVALIADOS futuramente (junto com outros candidatos).
4. Controle valida os 4 do walk-forward original (BTC/SOL/TRX/BNB positivos).
5. ETH e XRP permanecem por decisão consciente do operador (reprovados no
   walk-forward original; risco aceito em 2026-07-05).

## Universo final Maré Alta D1
BTC, ETH, SOL, XRP, TRX, BNB.
