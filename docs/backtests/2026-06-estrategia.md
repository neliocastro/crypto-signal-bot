# Backtests de Estratégia — Junho/2026

> **Status:** Documentação para avaliação posterior. **NENHUMA mudança de código foi feita.** O bot segue operando no perfil atual (`agressivo` / MACD-only). Estes resultados servem como base de decisão futura.

**Gatilho da investigação:** dúvida sobre por que o bot não comprou ETH/USDT na virada do MACD (~02:00 de 19/06/2026), quando o preço fez fundo em 1.671 e recuperou para ~1.737.

**Contexto de mercado no período:** Fear & Greed = 23 (*Extreme Fear*). 0 sinais gerados no scan do dia.

**Metodologia comum:**
- Dados: candles H1 reais da Gate.io (API pública `spot/candlesticks`).
- Janela: ~167 dias (4.000 candles H1 por ativo) nos backtests estendidos.
- Ativos: BTC, ETH, SOL, XRP, TRX, BNB, LINK, AAVE (8 ativos que usam lógica MACD).
- Custos (quando indicado): fee 0,2%/perna + slippage 0,05%/perna (~0,5% round-trip).
- Indicadores replicados do código: EMA 9/21/50/200, RSI 14, MACD 12/26/9, ATR 14, VWAP de sessão (com volume real no teste fiel).

## Ressalvas honestas (ler antes de decidir)
- 167 dias incluem a alta de maio (onde o `config.py` registrou PF 2–3) **e** a queda/medo de junho — os números refletem fortemente o **regime ruim atual**.
- A simulação de fee (0,2%/perna) pode ser **pessimista** se a conta tiver fee menor (VIP/maker).
- Não modela cooldown, filtro F&G em produção, nem TP parcial/trailing real da estratégia de breakout (HYPE).
- O VWAP só usa volume real no Backtest 5 (fiel); nos anteriores era aproximado.

---

## Backtest 1 — Sensibilidade do filtro de spread (anti-lateral)

~42 dias, sem custos. Variando o limiar `spread_ok` das EMAs.

| Cenário | Trades | Win% | PF | Retorno |
|---|---|---|---|---|
| A (atual) 0,15% | 18 | 50,0% | 0,94 | −0,6% |
| B 0,08% | 18 | 50,0% | 0,94 | −0,6% |
| C 0,00% (off) | 19 | 52,6% | 0,99 | −0,1% |

**Conclusão:** afrouxar o spread quase não muda nada (0 a 1 trade extra). O ETH seria, no máximo, 1 trade isolado — não um padrão. Mexer no filtro **não** resolve.

---

## Backtest 2 — Estendido com custos: agressivo vs balanceado (simplificado)

167 dias, COM fee+slippage.

| Perfil | Trades | Win% | PF | Retorno | Max DD |
|---|---|---|---|---|---|
| Agressivo (MACD spread 0,15) | 175 | 38,3% | 0,50 | −84,1% | −86,0% |
| Agressivo (spread OFF) | 188 | 39,4% | 0,52 | −83,5% | −85,4% |
| Balanceado (simplificado) | 1.864 | 34,8% | 0,51 | −923,6% | −929,8% |

**Sem fee:** Agressivo PF 1,03 / +3,4% · Balanceado PF 1,01 / +8,4%.

**Conclusão crítica:** o edge **bruto** é frágil (PF ~1,01–1,03). Com qualquer custo realista, as estratégias viram **perdedoras**. O problema não é entrada/filtro — é a ausência de edge no regime atual.

> O balanceado simplificado (1.864 trades) era pessimista/impreciso — corrigido no Backtest 5.

---

## Backtest 3 — Trailing stop + R:R maior (perfil agressivo)

167 dias, COM custos. Entrada MACD-only fixa (175 trades), variando só a SAÍDA.

| Config de saída | Win% | PF | Retorno | Max DD |
|---|---|---|---|---|
| Baseline (TP 1.5SL/3ATR) | 38,3% | 0,50 | −84% | −86% |
| Fixo SL2.0 / R:R 1:4 | 20,0% | 0,53 | −121% | −133% |
| Fixo SL2.0 / R:R 1:6 | 10,9% | 0,39 | −172% | −173% |
| Trailing 2.0/3.0 ATR | 25,7% | 0,39 | −114% | −116% |
| Trailing 2.0/4.0 ATR | 24,0% | 0,33 | −136% | −136% |
| Trailing 2.5/2.5 (estilo HYPE) | 28,0% | 0,44 | −95% | −98% |
| Trailing 3.0/5.0 (solto) | 26,3% | 0,37 | −161% | −161% |

**Conclusão:** TODAS as variações de saída pioram. R:R maior derruba o win-rate (38%→11-28%) porque os movimentos não se sustentam no regime lateral/medo. O baseline atual é o "menos ruim".

---

## Backtest 4 — Balanceado FIEL (VWAP real + veto 4h + pullback)

167 dias, COM custos. Replica fielmente: estratégia Integrada + Tendência MACD + gating MTF 4h + VWAP de sessão com volume real + 1 posição por ativo.

| Perfil | Trades | Win% | PF | Retorno | Max DD |
|---|---|---|---|---|---|
| Agressivo (MACD-only) | 175 | 38,3% | 0,50 | −84,1% | −86,0% |
| **Balanceado FIEL** | 207 | 37,2% | **0,45** | **−97,8%** | −96,8% |

Apenas **1** trade de confluência 10/10 em 167 dias. O veto 4h não salvou (mercado todo em downtrend).

**Conclusão:** o balanceado **não é melhor** — é ligeiramente pior. Trocar de perfil não resolve.

---

## Síntese geral

| Hipótese testada | Resultado |
|---|---|
| Afrouxar filtro de spread | ❌ não muda nada |
| R:R maior (1:4, 1:6) | ❌ piora |
| Trailing stop (5 variações) | ❌ todas pioram |
| Trocar para balanceado | ❌ pior (−98% vs −84%) |
| Edge bruto sem fee | ⚠️ PF ~1,01–1,03 (frágil demais) |

**Verdade central:** nenhuma estratégia de sinal (agressivo OU balanceado) tem edge real após custos no regime de *Extreme Fear*. MACD/EMA em mercado de medo não funciona.

**O que funciona nos dados:** trend-following / breakout em tendência forte (ex.: HYPE, 44k→55k, EMAs empilhadas, PF ~2,55 documentado). A diferença é o **REGIME**, não a estratégia.

## Recomendações para avaliação futura (NÃO implementadas)
1. **Filtro de regime F&G** — suspender entradas quando `score < 25` (Extreme Fear). Maior impacto, menor risco.
2. **Priorizar breakout/trend** sobre MACD-cross.
3. **Investigar/replicar** a lógica do HYPE breakout nos demais ativos.

## Proteções já ativas (mitigam o risco enquanto avaliamos)
- Teto de $5/ordem; stop diário $10.
- TP/SL nativos na Gate.io (commit 400b2d7).
- Resumo diário 09:00 BRT.

---
*Gerado em 20/06/2026. Para avaliação posterior. Sem alteração de código de produção.*
