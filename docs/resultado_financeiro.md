# Resultado Financeiro - Baseline Oficial

> **Atualizado em 08/10/2026:** ver **secao 5** (22 trades fechados do bot). As secoes 1-4 sao o baseline original de 12/08 e foram mantidas como registro.

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

---

## 5. ATUALIZACAO 08/10/2026 - 22 trades fechados do bot

**Fonte:** `state/positions.jsonl` (HEAD `84388d2`). **Metodo:** P&L = (saida - entrada) x qtd - fee 0.1% ida e volta; saida = `exit_price` ou preco da perna disparada (TP/SL). E estimativa: nao usa o fill real da corretora, entao pode divergir alguns centavos dos numeros da secao 1. Linhas em ordem de abertura (por isso o TRX #9, aberto em 10/08, fecha em 21/08).

| # | Saida | Ativo | Entrada | Saida | Qtd | Resultado | P&L ($) |
|---|---|---|---|---|---|---|---|
| 1 | 26/07 | ETH | 1709.66 | 1957.54 | 0.0058 | TP (+14.5%) | +1.42 |
| 2 | 27/07 | HYPE | 59.99 | 59.2 | 0.082 | SL (-1.3%) | -0.07 |
| 3 | 27/07 | HYPE | 60.4 | 59.44 | 0.081 | SL (-1.6%) | -0.09 |
| 4 | 04/08 | HYPE | 53.55 | 55.66 | 0.092 | TP (+3.9%) | +0.18 |
| 5 | 05/08 | HYPE | 55.2 | 57.02 | 0.089 | TP (+3.3%) | +0.15 |
| 6 | 06/08 | HYPE | 56.38 | 55.42 | 0.087 | SL (-1.7%) | -0.09 |
| 7 | 06/08 | HYPE | 57.21 | 55.91 | 0.086 | SL (-2.3%) | -0.12 |
| 8 | 07/08 | HYPE | 56.86 | 55.95 | 0.086 | SL (-1.6%) | -0.09 |
| 9 | 21/08 | TRX | 0.3298 | 0.3436 | 15 | TP (+4.2%) | +0.20 |
| 10 | 11/08 | HYPE | 56.07 | 54.93 | 0.088 | SL (-2.0%) | -0.11 |
| 11 | 21/08 | HYPE | 74.93 | 72.25 | 0.132 | SL (-3.6%) | -0.37 |
| 12 | 22/08 | HYPE | 74.01 | 81.79 | 0.134 | TP (+10.5%) | +1.02 |
| 13 | 22/08 | HYPE | 76.17 | 73.64 | 0.13 | SL (-3.3%) | -0.35 |
| 14 | 22/08 | HYPE | 80.79 | 77.39 | 0.122 | SL (-4.2%) | -0.43 |
| 15 | 31/08 | PAXG | 4461.67 | 4401.85 | 0.001 | SL (-1.3%) | -0.07 |
| 16 | 01/09 | PAXG | 4379.47 | 4342.77 | 0.001 | SL (-0.8%) | -0.05 |
| 17 | 15/09 | BTC | 81238.3 | 75033.4 | 0.000122 | SL (-7.6%) | -0.78 |
| 18 | 10/09 | BNB | 721.4 | 704.5 | 0.012 | SL (-2.3%) | -0.22 |
| 19 | 26/09 | TRX | 0.3391 | 0.3346 | 29.3 | SL (-1.3%) | -0.15 |
| 20 | 08/10 | SOL | 110.71 | 108.39 | 0.089 | SL (-2.1%) | -0.23 |
| 21 | 08/10 | BNB | 782.3 | 743.5 | 0.011 | SL (-5.0%) | -0.44 |
| 22 | 08/10 | BTC | 85868.5 | 80899.5 | 0.000115 | SL (-5.8%) | -0.59 |

### Placar

| Recorte | Trades | Wins | P&L aprox. | PF |
|---|---|---|---|---|
| Todos os fechados | 22 | 5 | **-$1.28** | ~0.70 |
| Sem o ETH | 21 | 4 | -$2.70 | ~0.37 |
| Breakout HYPE | 12 | 3 | -$0.37 | ~0.78 |
| Mare Alta D1 (BTC/SOL/TRX/BNB) | 7 | 1 | -$2.21 | ~0.08 |
| PAXG acumulo (desligado) | 2 | 0 | -$0.11 | 0 |
| Desde 04/09 (universo atual) | 6 | 0 | -$2.41 | 0 |

### Leituras

1. **O lucro de agosto (+$1.21) foi devolvido.** O bot saiu do verde para cerca de -$1.28 realizado.
2. **O ETH continua sendo o unico trade relevante a favor** (+$1.42). Sem ele, PF ~0.37.
3. **Mare Alta D1: 1 de 7 ao vivo** (so o TRX de 10/08 no TP). No regime de setembro e outubro foi 0 de 6, todos no stop. O backtest (PF 1.64, OOS 2.08) **ainda nao se confirmou ao vivo**. Amostra pequena, mas a tendencia e negativa.
4. **HYPE breakout: PF ~0.78 ao vivo (12 trades) contra 2.55 no backtest.** Os 4 ultimos (20-22/08, ja com teto de $10) somaram -$0.13; nenhum trade de HYPE desde 22/08.
5. **08/10 17:40 UTC:** SOL, BNB e BTC fecharam no stop **no mesmo minuto**. Causa (queda real ou reconciliacao do guard) **a confirmar** no `execution_log.jsonl` do relay antes de tirar conclusao.
6. As posicoes manuais (BTC, PAXG, XRP, HYPE legado) **nao foram reprecificadas** nesta atualizacao. As secoes 2-4 continuam sendo o snapshot de 12/08.

*Atualizado em 08/10/2026. Decisao de capital derivada: `docs/reauditoria_degrau_2026-10-08.md`.*
