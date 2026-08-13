# Resultado Financeiro - Baseline Oficial

**Periodo coberto:** 02/07/2026 (primeiro trade ETH) ate 12/08/2026.
**Fontes:** `state/positions.jsonl` (100% reconciliado com a exchange em 11-12/08), `execution_log.jsonl` do relay, historico de ordens do app Gate.io e precos ao vivo da API publica.
**Snapshot de precos:** 12/08/2026 ~15:50 BRT (HYPE 56.59 / TRX 0.3362 / BTC 63,422.5 / PAXG 4,411.95 / XRP 1.0099).

---

## 1. Trades do BOT - fechados (realizado)

| # | Saida | Ativo | Entrada | Saida | Qtd | Resultado | P&L |
|---|-------|-------|---------|-------|-----|-----------|-----|
| 1 | 26/07 | ETH | 1,709.66 | 1,957.54 | 0.0059 | TP (+14.5%) | **+$1.44** |
| 2 | 27/07 | HYPE | 59.99 | 59.20 | 0.082 | SL (-1.5%) | -$0.07 |
| 3 | 27/07 | HYPE | 60.40 | 59.44 | 0.081 | SL (-1.8%) | -$0.09 |
| 4 | 04/08 | HYPE | 53.55 | 55.66 | 0.092 | TP (+3.8%) | **+$0.19** |
| 5 | 05/08 | HYPE | 55.20 | 57.02 | 0.089 | TP (+3.2%) | **+$0.16** |
| 6 | 06/08 | HYPE | 56.38 | 55.42 | 0.087 | SL (-1.9%) | -$0.09 |
| 7 | 06/08 | HYPE | 57.21 | 55.91 | 0.086 | SL (-2.5%) | -$0.12 |
| 8 | 07/08 | HYPE | 56.86 | 55.95 | 0.086 | SL (-1.8%) | -$0.09 |
| 9 | 11/08 | HYPE | 56.07 | 54.93 | 0.088 | SL (-2.3%) | -$0.11 |

**TOTAL BOT REALIZADO: +$1.21** | 9 trades | 3 TP / 6 SL | WR 33% | PF realizado ~3.1

Ganho medio por TP: +$0.60 | Perda media por SL: -$0.10 (assimetria ~6:1 no trade medio... dominada pelo ETH; ver Leituras).

## 2. Operacoes MANUAIS - realizado

| Data | Operacao | Qtd | Preco | vs custo 64.20 | P&L |
|------|----------|-----|-------|----------------|-----|
| 11/08 | Venda HYPE legado | 0.089 | 53.97 | -15.9% | -$0.91 |
| 11/08 | Venda HYPE legado | 0.089 | 54.11 | -15.7% | -$0.91 |

**TOTAL MANUAL REALIZADO: -$1.82**

## 3. Posicoes abertas - nao realizado (snapshot 12/08)

| Posicao | Qtd | Custo | Preco | P&L aberto | Protecao |
|---------|-----|-------|-------|-----------|----------|
| TRX (bot) | 15 | 0.3298 | 0.3362 | +$0.10 (+1.9%) | SL 0.3275 (trailing) + TP 0.3436 |
| HYPE legado | 0.094 | 64.20 | 56.59 | -$0.72 (-11.9%) | SL 53.40 + TP 57.90 (OCO manual) |
| BTC | 0.00527384 | 60,749.8 | 63,422.5 | +$14.10 (+4.4%) | nenhuma |
| PAXG | 0.050904 | 4,454.4 | 4,411.95 | -$2.16 (-0.9%) | nenhuma |
| XRP | 4.495 | 1.1006 | 1.0099 | -$0.41 (-8.2%) | nenhuma |

**TOTAL NAO REALIZADO: +$10.91**

## 4. Placar consolidado

| Frente | Realizado | Nao realizado | Total |
|--------|-----------|---------------|-------|
| Bot (canario) | +$1.21 | +$0.10 | +$1.31 |
| Manual/legado | -$1.82 | +$10.91 | +$9.09 |
| **GERAL** | **-$0.61** | **+$11.01** | **+$10.40** |

## Leituras principais

1. **Bot no verde (+$1.21)** apesar de WR 33% - os TPs pagaram muito mais que os SLs custaram (perfil trend-following: perde pequeno, ganha maior).
2. **ATENCAO estatistica:** o trade do ETH (+$1.44) responde por mais de 100% do lucro do bot. Isolando o HYPE: 8 trades, -$0.22 (PF ~0.6). O edge live do HYPE AINDA NAO esta comprovado - amostra pequena e regime de agosto foi de serrote.
3. A unica perda relevante do periodo (-$1.82) foi do lote manual pre-bot, comprado sem stop. Com protecao sistematica, 6 stops somaram -$0.57.
4. BTC (+$14.10) carrega o nao-realizado, mas esta SEM protecao - maior exposicao nua do portfolio.

## Notas de metodo

- Trades 6-9: P&L calculado com fee 0.1% ida e volta; demais usam deal real da corretora.
- HYPE legado: custo medio 64.20 confirmado pelo usuario; vendas de 11/08 com precos reais do historico.
- BTC/PAXG/XRP: custo medio dos prints do app (11/08). Rendimentos de staking/Earn NAO incluidos.
- Trade 4 (69778f7b): saida estimada no trigger 55.66 (fill real nao disponivel; 3 provas independentes documentadas no positions.jsonl).

---
*Baseline criado em 12/08/2026. Proxima revisao sugerida: apos o 20o trade do bot ou 30 dias.*
