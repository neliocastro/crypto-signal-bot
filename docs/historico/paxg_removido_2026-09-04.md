# PAXG removido da watchlist — 2026-09-04

## TL;DR

O PAXG/USDT saiu da `WATCHLIST` e a estratégia de acúmulo foi desligada
(`ACCUMULATION_ENABLED = False`). Motivo: quando finalmente passou a ser
avaliada de verdade, produziu **2 sinais e 2 stops em 11 dias** — e revelou
uma incompatibilidade de design entre a tese da estratégia e a camada de
execução.

Watchlist: **6 → 5 ativos** (BTC, SOL, TRX, BNB, HYPE).

---

## 1. Linha do tempo

| Data | Evento |
|---|---|
| até 2026-08-24 | PAXG estava fora da watchlist **efetiva** (runtime) → `evaluate_signal` nunca era chamado. O fast-path de acúmulo era **código morto**, não "estratégia rara". |
| 2026-08-24 | Watchlist unificada em `bot/config.py` (fonte de verdade única, commit `a390e09`). PAXG passa a ser avaliado de fato pela **primeira vez**. |
| 2026-08-28 | 1º sinal real de acúmulo → ordem executada. |
| 2026-08-31 | Stop-loss disparado. |
| 2026-09-01 | 2º sinal → ordem executada e **estopada no mesmo dia**. |
| 2026-09-04 | Remoção da watchlist + kill switch (este documento). |

---

## 2. Desempenho real (`state/positions.jsonl`)

| # | Abertura (UTC) | Entrada | SL | Fechamento | Status |
|---|---|---|---|---|---|
| 1 | 2026-08-28 20:09 | 4461.67 | 4401.85 | 2026-08-31 02:52 | `closed_sl` |
| 2 | 2026-09-01 12:01 | 4379.47 | 4342.77 | 2026-09-01 13:19 | `closed_sl` |

- Quantidade: 0.001 PAXG por ordem (notional ~$4.4, dentro do teto de $10).
- Win rate: **0%** (0/2). Perda por trade: ~1.3% e ~0.84% do notional.
- O OCO Guard funcionou nos dois casos: cancelou a perna de TP órfã (http 200).

Perda absoluta é irrelevante (centavos) — o valor aqui é **informacional**.

---

## 3. O achado que realmente decidiu: conflito de design

A estratégia de acúmulo foi especificada como **BUY-only, sem stop e sem alvo
de venda** (DCA inteligente em ativo de reserva de valor). Mas a camada de
execução tem `EXECUTION_TPSL_ENABLED = True`, que anexa **SL 2.5×ATR + TP RR
2.0 nativos na Gate.io a toda compra**, indistintamente.

Consequência: o "acúmulo sem stop" **nunca existiu em produção**. O que rodou
foi um swing trade de curtíssimo prazo com stop apertado — precisamente o
comportamento que a tese de DCA pretendia evitar. Os dois stops não são
necessariamente evidência de que a tese está errada; são evidência de que
**ela nunca foi testada**.

Duas saídas eram possíveis:

1. **Implementar exceção no executor** (`ACCUMULATION_SYMBOLS` → compra sem
   TP/SL) e reavaliar a tese de verdade.
2. **Remover o PAXG** e concentrar no que tem rota validada.

Decisão: **opção 2**, por coerência com o histórico — o PAXG já havia sido
reprovado em 3 backtests anteriores (mean-reversion, breakout e MACD), sem
edge em nenhum. Não há motivo para gastar complexidade no executor por um
ativo sem evidência favorável.

---

## 4. Estado após a mudança

| Ativo | Estratégia | Rota até ordem real |
|---|---|---|
| BTC | Maré Alta D1 | ✅ |
| SOL | Maré Alta D1 | ✅ |
| TRX | Maré Alta D1 | ✅ |
| BNB | Maré Alta D1 | ✅ |
| HYPE | Breakout/Tendência (lb=30, atr=2.5) | ✅ |
| ~~PAXG~~ | ~~Acúmulo RSI 4h~~ | ❌ removido |

`ACCUMULATION_SYMBOLS` foi **mantido no código** (com `ACCUMULATION_ENABLED =
False`) para preservar o rollback de 1 linha.

---

## 5. Rollback

```python
# bot/config.py
WATCHLIST = [..., "PAXG/USDT"]
ACCUMULATION_ENABLED = True
```

Se algum dia a tese de DCA for retomada, o pré-requisito é resolver o item 3:
o executor precisa saber comprar **sem** TP/SL para os símbolos de acúmulo.
Antes disso, religar o PAXG só reproduz o mesmo experimento inválido.

---

## 6. Ponta solta registrada

- `EXECUTION_TPSL_ENABLED` é **global**. Qualquer estratégia futura BUY-only
  (acúmulo, DCA, hold longo) vai sofrer o mesmo problema silenciosamente.
  Sugestão para o futuro: override por estratégia em `executor.build_order()`.
