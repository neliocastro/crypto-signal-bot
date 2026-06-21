# Validacao Out-of-Sample da Estrategia Nova — Junho/2026

> **Status:** Documentacao para avaliacao. **NENHUMA mudanca de codigo de producao.** Fecha o ciclo de descobertas iniciado pela duvida do ETH.

## Objetivo

No backtest anterior, a estrategia nova (Breakout + Regime + Momentum + Trailing) rodada nos 9 ativos deu PF 0,77 / -52%. Selecionando "a posteriori" os 3 melhores (HYPE+AAVE+XRP) chegou a PF 1,14 / +8,1%. **Essa selecao tinha vies** (escolher vencedores depois de ver o resultado completo). Esta validacao out-of-sample (OOS) testa se o edge e real ou overfit.

## Metodologia

- Dados: candles H1 reais da Gate.io, ~167 dias, 9 ativos.
- **Split temporal:** cada ativo dividido ao meio por indice. IN-SAMPLE = 1a metade; OUT-OF-SAMPLE = 2a metade.
- **Regra anti-vies:** vencedores escolhidos OLHANDO SO a 1a metade (PF>1, n>=4 trades). Depois mede-se o desempenho deles na 2a metade, nunca vista.
- Estrategia nova fixa: regime bull (EMA50>EMA200 e preco>EMA200) + EMA9>EMA21>EMA50 + breakout (preco >= maxima 30 velas) + RSI>52 + MACD>sinal. Saida: stop inicial 2,5xATR, trailing 3,0xATR.
- Custos: fee 0,2%/perna + slippage 0,05%/perna.

## Resultado por ativo: In-Sample vs Out-of-Sample

| Ativo | IS trades | IS PF | IS ret | OOS trades | OOS PF | OOS ret | Veredito |
|---|---|---|---|---|---|---|---|
| HYPE | 12 | 1,85 | +21,3% | 15 | **2,96** | **+42,6%** | EDGE PERSISTE E MELHORA |
| SOL | 7 | 0,07 | -11,4% | 10 | 1,43 | +3,9% | instavel (inverteu) |
| AAVE | 5 | 1,01 | +0,1% | 10 | 0,74 | -4,6% | enfraqueceu |
| XRP | 4 | 5,05 | +10,6% | 12 | 0,80 | -2,4% | era sorte (n=4) |
| BTC | 5 | 1,89 | +1,7% | 14 | 0,15 | -11,6% | era sorte |
| ETH | 8 | 0,92 | -0,6% | 13 | 0,24 | -14,6% | sem edge |
| TRX | 17 | 0,81 | -1,5% | 22 | 0,37 | -8,9% | sem edge |
| BNB | 7 | 0,50 | -1,4% | 19 | 0,28 | -17,0% | sem edge |
| LINK | 6 | 0,16 | -4,9% | 14 | 0,24 | -17,5% | sem edge |

## Selecao anti-vies (escolhida so pela 1a metade)

Vencedores in-sample (PF>1, n>=4): BTC, XRP, AAVE, HYPE.

- **OOS dessa selecao cega:** 51 trades | PF 1,37 | +24,0% (positivo, mas o lucro vem majoritariamente do HYPE).
- Carteira que havia sido escolhida olhando o full (HYPE+AAVE+XRP) so na 2a metade: 37 trades | PF 1,70 | +35,6% (de novo, puxada pelo HYPE).

## Conclusoes

1. **HYPE e o unico edge que sobrevive ao teste cego:** PF 1,85 (IS) -> 2,96 (OOS). Persistiu e melhorou num periodo totalmente separado = assinatura de edge estrutural, nao overfit.
2. **XRP, AAVE e BTC eram parcialmente sorte:** PF alto in-sample com poucos trades (XRP n=4, PF 5,05) colapsou no OOS. Confirma o risco de selecao previamente alertado.
3. **Majors (ETH/BTC/BNB/LINK) nao tem edge** nesta logica no regime atual (OOS PF < 0,4).
4. **A validacao confirma a configuracao ja em producao:** HYPE roda em breakout (lb=30/atr=2.5) com relatorio semanal de acompanhamento. Nao ha mudanca de codigo a fazer.

## O que NAO fazer (evidenciado pelo OOS)

- Nao adicionar XRP/AAVE/BTC a estrategia breakout (nao sobrevivem ao OOS).
- Nao confiar em PF alto com poucos trades.
- Nao reativar MACD-only nos majors.

## Ressalvas honestas

- HYPE tem ~150d de historia real; cada metade e ~75d. Robusto para o tamanho, mas exige monitoramento continuo via relatorio semanal.
- O edge do HYPE depende de poucos ralis grandes (trend-following). OOS forte mitiga mas nao elimina essa caracteristica.
- 167d incluem alta de maio + queda/medo de junho (F&G 23, Extreme Fear no momento).

## Recomendacao final

Manter a configuracao atual (HYPE em breakout/trailing; majors no caminho conservador). A ciencia confirma a decisao ja tomada. Continuar coletando dados em dry-run/paper e revisar o edge do HYPE periodicamente.

---
*Gerado em 21/06/2026. Para avaliacao. Sem alteracao de codigo de producao.*
