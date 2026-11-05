# Backtest — Tendência Diária com a saída atual (2026-11-05)

> Script: `scripts/backtest_tendencia_diaria.py` (reconstrói o "backtest fiel" de 2026-08, que não estava no
> repositório; usa as funções de indicador do `bot/mare_alta.py`). Dados: velas D1 da Gate.io, de 2018 (ou da listagem)
> até 2026-11-04. Custos: taxa 0,1% e slippage 0,05% por ponta. Stop e TP1 no mesmo dia: conta o stop.
> Pedido do usuário: entender por que o resultado ao vivo está negativo e se convém mudar, simplificar ou ampliar o
> universo.

## 1. Os trades reais, refeitos com a regra atual
| Trade | Real (US$) | Regra atual (US$) | Observação |
|---|---|---|---|
| BTC 04/09 | −0,78 | −0,79 | queda direta até o stop |
| BNB 05/09 | −0,22 | **+0,52** | stop real −2,3% (trailing antigo); modelo −7,1% |
| TRX 10/09 | −0,15 | **+0,48** | stop real −1,3%; modelo −3,7% |
| SOL 20/09 | −0,23 | **+0,48** | chegou a +12,9% (o TP1 de +10% teria executado) |
| BNB 21/09 | −0,44 | −0,80 | |
| BTC 22/09 | −0,59 | −0,75 | |
| TRX 30/10 | −0,55 | −0,51 | único trade já com a regra atual |
| **Soma** | **−2,96** | **−1,37** | |

Os sinais do bot e do backtest caem nas mesmas velas (conferido de agosto a outubro). A diferença está na saída antiga,
corrigida em 2026-10-15 (D-026/D-027). Daí o D-053: o degrau conta só a regra atual.

## 2. A regra atual por período (4 ativos do universo)
| Ativo | 2019–2022 PF | 2023–2024 PF | 2025–hoje PF (trades) | 2025–hoje: estratégia × buy & hold × DCA |
|---|---|---|---|---|
| BTC | 2,49 | 1,66 | 1,53 (6) | +9,0% × −14,0% × −6,1% |
| SOL | 2,53 | 5,63 | 2,08 (6) | +13,2% × −49,5% × −19,3% |
| TRX | 1,36 | 3,76 | 1,21 (7) | +2,9% × +25,6% × +8,9% |
| BNB | 8,59 | 2,61 | 3,55 (6) | +31,3% × +2,5% × +2,6% |

Retornos compostos do capital alocado no ativo. Em 2025+ a pior queda da estratégia ficou entre −12% e −15%, contra
−26% a −76% do buy & hold. Em 2023–2024 o buy & hold ganhou de longe (BTC +466% contra +17%): a estratégia protege na
queda e fica para trás na alta forte.

## 3. Ampliar o universo e filtros (25 moedas líquidas, sem HYPE e PAXG por histórico curto)
| Variante | 2019–2022 | 2023–2024 | 2025–hoje |
|---|---|---|---|
| Regra atual, 25 moedas | PF 2,52 (251) | PF 1,66 (165) | **PF 0,92** (136) |
| + só entra com o ativo acima da SMA200 | 1,99 | 1,70 | 0,63 |
| + só entra com o BTC acima da SMA200 | 2,86 | 1,47 | 0,78 |
| 4 atuais + filtro SMA200 do ativo | 3,15 | 4,45 | 0,94 |

- **Ampliar o universo piora:** em 2025+ a média das 25 moedas fica abaixo de 1 (ATOM −59%, OP −60%, HYPE −83%,
  ETH, XRP, LTC, BCH negativos). Mais moedas trazem mais trades, não mais vantagem (R-005).
- **O filtro SMA200 piora em 2025+** em todas as versões. Não adotar.
- **Ressalva:** os 4 ativos foram escolhidos em 2026-07/08 com dados que incluem 2025, então o PF deles em 2025+ é
  otimista. A queda do PF médio das 25 moedas ao longo dos anos indica que a vantagem da estratégia está encolhendo.

## Conclusões
1. Manter a estratégia e o universo como estão. A regra atual quase não rodou ao vivo; medir a partir de 2026-10-15 (D-053).
2. Não ampliar o universo e não adicionar filtro SMA200.
3. Com US$ 10 por ordem, mesmo o cenário do backtest rende poucos dólares por ano. O que mais pesa no resultado em
   dinheiro é a alocação (DCA, estratégia, USDT parado), que é decisão do usuário.
4. Reavaliar com este script quando houver amostra nova ou queda forte, sem afrouxar regras (P-12).
