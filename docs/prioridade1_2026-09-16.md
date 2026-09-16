# Prioridade 1 — decisoes de 2026-09-16

Revisao das pendencias abertas no codigo de execucao. Uma mudanca de comportamento
(implementada), tres decisoes explicitas (documentadas, sem mexer em producao).

---

## 1. IMPLEMENTADO — stop por simbolo (`EXECUTION_ATR_MULT_SL_OVERRIDES`)

**Pendencia (registrada em 2026-08-23):** "O otimo do HYPE (3.0x) exigiria um
override por simbolo no `executor.build_order()` - commit isolado, ainda nao feito."

**Problema:** um unico multiplo global (`EXECUTION_ATR_MULT_SL = 2.5`) servia dois
trilhos com otimos diferentes, entao um deles sempre operava fora do seu otimo:

| Trilho | Ativos | Otimo medido | O que rodava |
|---|---|---|---|
| Mare Alta D1 | BTC, SOL, TRX, BNB | **2.5x** (supera 3.0x em 5 dos 6 ativos) | 2.5x ✔ |
| Breakout 1h | HYPE | **3.0x** (PF 1.50 vs 1.31 em 2.5x, 180d) | 2.5x ✘ |

**Solucao:** `build_order()` agora consulta um dict de override por simbolo antes
de calcular o risco. Simbolo ausente -> usa o global.

```python
EXECUTION_ATR_MULT_SL = 2.5              # default global (Mare Alta D1)
EXECUTION_ATR_MULT_SL_OVERRIDES = {
    "HYPE/USDT": 3.0,                    # otimo do breakout 1h
}
```

**Propriedades:**
- **Aditivo:** se a chave nao existir no `config.py`, vale `{}` -> comportamento
  identico ao anterior.
- **Degradacao segura:** valor invalido/erro -> cai no global (`try/except`).
- **Auditavel:** a ordem passa a registrar `atr_mult_sl` (multiplo efetivo) em
  `state/paper_trades.jsonl`.
- **ROLLBACK de 1 linha:** `EXECUTION_ATR_MULT_SL_OVERRIDES = {}`.

**Efeito pratico:** o stop do HYPE fica ~20% mais largo (3.0x em vez de 2.5x do
ATR). Nao muda o teto por ordem ($10) nem nenhuma trava de capital. O piso
`EXECUTION_MIN_STOP_PCT = 0.8` continua valendo por cima.

**Atencao (limite honesto):** o trailing D1 (`MARE_ALTA_SL_ATR_MULT = 3.0`) e a
saida do breakout continuam com seus proprios parametros — este override afeta
apenas o **stop inicial** anexado a compra.

---

## 2. DECIDIDO — degrau de $20 CONGELADO (teto segue $10)

Criterio combinado em 12/08: subir de $10 -> $20 **so no 20o trade** com **P&L > 0**
e **PF >= 1 ex-ETH**.

| Criterio | Exigido | Auditoria 23/08 | Status 16/09 |
|---|---|---|---|
| Trades | >= 20 | 14 | nao atingido |
| P&L (ex-ETH) | > 0 | -$0.23 | nao atingido |
| PF (ex-ETH) | >= 1 | 0.60 | nao atingido |

**Decisao:** MANTER $10. Nenhum dos 3 criterios foi atingido; nada mudou a favor
desde a auditoria anterior. Reavaliar somente quando o 20o trade fechar.

---

## 3. DECIDIDO — nao "consertar" o `open_positions` do `execution_guard.json`

O campo e **monotonico por design** desde o bugfix de 23/08: ele virou apenas um
**espelho informativo**. Quem decide a trava e `_open_count_total()`, que le a
fonte da verdade (`state/positions.jsonl`). Trocar o espelho por um contador
incremental reintroduziria exatamente o bug que travava todas as compras.

**Decisao:** manter como espelho. O comentario no codigo ja explica; nao ha acao.

---

## 4. DECIDIDO — ordens MANUAIS seguem fora do OCO guard

O `oco_guard` so reconcilia pares TP/SL registrados em `state/positions.jsonl`
(ordens criadas pelo bot). A posicao propria de BTC do usuario, protegida via
`~/btc_tp.php`, **nao e coberta**.

Automatizar exigiria varrer as `open_orders` da conta no relay PHP — ou seja, dar
ao bot a capacidade de **cancelar ordens que ele nao criou**. Risco de dano muito
maior que o beneficio.

**Decisao:** nao automatizar. Reconciliacao manual, documentada em
`docs/runbook_btc_manual.md`. Gap registrado no comentario do `config.py`.

---

## Resumo do commit

| Arquivo | Mudanca |
|---|---|
| `bot/executor.py` | override de stop por simbolo + `atr_mult_sl` na ordem |
| `bot/config.py` | `EXECUTION_ATR_MULT_SL_OVERRIDES` + reauditoria do degrau + gap do OCO |
| `docs/estado_atual.md` | tabela de execucao atualizada |
| `docs/prioridade1_2026-09-16.md` | este documento |

Nenhum kill-switch foi ligado ou desligado. Nenhuma trava de capital foi afrouxada.
