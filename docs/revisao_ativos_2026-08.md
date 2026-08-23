# Revisao de ativos por desempenho REAL — ago/2026

> Fonte: `state/positions.jsonl` (18 registros) lido do `main` em 2026-08-23.
> **Nao e backtest.** Sao ordens reais executadas pelo bot no go-live canario.
> Complementa `docs/mapa_estrategias.md` (o que roda) respondendo: **o que deu
> dinheiro**.

## 1. Placar geral

| Estrategia | Trades fechados | TP | SL | Win rate | P&L apurado |
|---|---|---|---|---|---|
| Breakout (HYPE) | 12 | 3 | 9 | **25%** | **-$0,23** |
| Mare Alta D1 | 2 | 2 | 0 | 100% | +$1,44 (ver ressalva) |
| Acumulacao (PAXG) | **0** | 0 | 0 | — | $0,00 |

P&L consolidado dos 7 trades com preco de saida gravado: **+$1,21**.

> ⚠️ 7 dos 14 trades **nao tem `exit_price`** no arquivo. Os numeros abaixo
> valem para a amostra com dados; a direcao e clara, a magnitude e aproximada.

## 2. HYPE — o problema real

12 dos 14 trades do bot foram HYPE. Detalhe dos 7 com dados completos:

| Saida | pnl % |
|---|---|
| TP | +3,84 |
| TP | +3,19 |
| SL | -1,51 |
| SL | -1,79 |
| SL | -1,70 |
| SL | -2,27 |
| SL | -1,60 |
| SL | -2,03 |

```
ganhos brutos  = $0,3469
perdas brutas  = $0,5752
PROFIT FACTOR REAL = 0,60
```

| Metrica | Backtest 05/2026 | Revalidacao 165d (08/2026) | **REAL** |
|---|---|---|---|
| Profit Factor | 2,55 | 1,49 | **0,60** |
| Win rate | 42% | — | **25%** |

**Leitura:** a assimetria por trade continua correta (ganha ~+3,5%, perde
~-1,8%, razao ~1:2 como projetado). O que quebrou foi a **frequencia**: o
backtest previa ~42% de acerto e a realidade entregou 25%. Com 1:2 de payoff,
o break-even exige ~33% de acerto — estamos abaixo disso.

Hipoteses (nao verificadas):
- O edge do breakout depende de 2-3 ralis grandes por janela (risco ja
  documentado no teste de robustez). Nesta janela eles nao vieram.
- Stop de 2,5xATR pode estar dentro do ruido intraday do HYPE.
- Custos (0,2% ida+volta) pesam muito mais em trade de $5-10 do que no backtest.

## 3. Mare Alta D1 — positivo, mas amostra insuficiente

| Trade | Entrada | Saida | Resultado |
|---|---|---|---|
| ETH | 1.709,66 | 1.957,54 (TP 26/07) | **+$1,44 / +14,5%** |
| TRX | 0,3298 (10/08) | TP em 21/08 | valor nao gravado |

⚠️ **Ressalva de atribuicao (importante):** o trade vencedor do ETH abriu em
**02/07**, ou seja, **ANTES** do fix de roteamento de 10/07 — justamente o
periodo em que o ETH era comprado "pelo trilho errado" (o proprio comentario do
`main.py` registra isso). Portanto **nao e limpo creditar esse lucro ao Mare
Alta D1**.

Descontando o ETH, o unico trade limpo do trilho D1 e o **TRX** (aberto 10/08,
fechado no TP em 21/08) — **1 trade**. Estatisticamente, o Mare Alta ainda
**nao foi testado ao vivo**.

## 4. ETH e XRP no Mare Alta — revisao pedida

Contexto: ambos foram **reprovados no walk-forward original** e entraram por
decisao de negocio.

| Ativo | Trades reais no trilho D1 | Evidencia acumulada |
|---|---|---|
| ETH | 0 limpos (o de 07/07 e pre-fix) | inconclusivo |
| XRP | **0** | inconclusivo |

**Recomendacao: NAO mexer agora.** Nao ha um unico dado real contra ou a favor
de ETH/XRP no trilho D1. Remove-los seria decidir sem evidencia, e o custo de
mante-los e baixo (o teto por ordem e $10). Revisar quando houver >=5 trades
fechados do D1.

## 5. PAXG — zero disparos

Nenhum sinal de acumulacao em ~2 meses: o RSI 4h nao cruzou 30 para baixo no
periodo. Custo: CPU do scan. Nenhum risco. Manter (e uma estrategia de DCA
rara por design), mas ciente de que ela ainda **nao foi exercitada**.

## 6. Decisao sobre o degrau de capital

O criterio gravado em `config.py` para subir o teto de $10 para $20 e:

> *proximo degrau ($20) SO no 20o trade com P&L>0 e PF>=1 ex-ETH*

Estado atual em relacao ao criterio:

| Condicao | Situacao |
|---|---|
| 20 trades | 14 — **nao atingido** |
| P&L > 0 | +$1,21 total, mas **-$0,23 ex-ETH** — **nao atingido** |
| PF >= 1 ex-ETH | **0,60** — **nao atingido** |

**Conclusao: NAO subir o teto.** As tres condicoes falham. O criterio que o
proprio usuario escreveu esta funcionando — respeita-lo.

## 7. Recomendacoes

| Prioridade | Acao | Justificativa |
|---|---|---|
| 🔴 Alta | Reavaliar o HYPE (shadow, stop mais largo ou pausa) | PF real 0,60 vs 2,55 projetado; 12 dos 14 trades |
| 🟡 Media | Gravar `exit_price`/`pnl_usdt` em TODO fechamento | 7 de 14 trades sem dados inviabilizam a analise |
| 🟢 Baixa | Manter ETH/XRP no D1 | sem evidencia real em nenhuma direcao |
| ⚪ | Manter PAXG | estrategia rara por design, custo zero |
| ⛔ | **Nao** subir o teto para $20 | 3 de 3 criterios falham |

### Ressalva final
14 trades e amostra pequena. Isto e **sinal de alerta**, nao veredito. A acao
mais valiosa aqui nao e desligar nada — e **corrigir a instrumentacao** (item
amarelo) para que a proxima revisao seja conclusiva.

---

_Revisao gerada a partir de leitura direta de `state/positions.jsonl` em
2026-08-23. Proxima revisao sugerida: ao atingir 20 trades fechados._
