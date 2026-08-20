# Fechamento do incidente `sspot` — 2026-08-20

Apêndice de [`incidente_2026-08-20-sspot-deploy.md`](incidente_2026-08-20-sspot-deploy.md).
Registra o que foi apurado DEPOIS do fix, com os dados de `state/`.

---

## 1. Alcance revisado: 9 ordens perdidas (não 6)

O diagnóstico inicial usou o `execution_log.jsonl` do servidor, que é rotacionado.
O `state/orders_executed.csv` (versionado no Git) mostra que o bug era mais
antigo — as rejeições começaram em **18/08**, não em 20/08:

| ts_utc | BRT | Par | Notional | ref_price | status |
|---|---|---|---|---|---|
| 18/08 07:04:30 | 04:04 | HYPE/USDT | $10 | 59,99 | rejected_by_exchange |
| 19/08 16:09:58 | 13:09 | HYPE/USDT | $10 | 61,87 | rejected_by_exchange |
| 19/08 20:14:41 | 17:14 | HYPE/USDT | $10 | 70,25 | rejected_by_exchange |
| 20/08 00:00:42 | 21:00 (19/08) | ETH/USDT | $10 | 2.253,24 | rejected_by_exchange |
| 20/08 00:00:45 | 21:00 (19/08) | BNB/USDT | $10 | 627,60 | rejected_by_exchange |
| 20/08 09:03:15 | 06:03 | HYPE/USDT | $10 | 73,08 | rejected_by_exchange |

Todas com `reason = INVALID_REQUEST_BODY`, modo `REAL`, `fill_price` vazio.
Somando as rejeições anteriores vistas no log do servidor: **9 ordens perdidas**.

> 🔑 Lição: para medir ALCANCE, usar `state/orders_executed.csv` (histórico
> completo versionado) e não o `execution_log.jsonl` do servidor.

## 2. Efeito colateral: `execution_guard.json` congelado

```json
{"day": "2026-08-10", "trades_today": 2, "open_positions": 2, "realized_loss_today": 0.0}
```

`_register_sent_order()` só incrementa quando o status é `filled/accepted/ok`.
Como TODA ordem foi rejeitada desde 10/08, o guard nunca mais foi gravado.
Não é bug: é sintoma. Volta a atualizar na primeira ordem que passar.

Consequência menor: `open_positions: 2` diverge do OCO Guard, que rastreia
**1** par vivo. Sem risco (teto = 10 posições). Autocorrige.

## 3. TP órfãos de 27/07: ENCERRADOS

Os 4 TP condicionais com `amount 4.99` (rastro do FIX 7) **não existem mais** na
Gate.io, confirmado pela tela de ordens abertas do usuário em 20/08.
Desfecho previsto em `gateio_limitacoes.md`: condicional apontando para base já
vendida termina em `BALANCE_NOT_ENOUGH` → `expired` → some da tela.
**Pendência encerrada, sem ação necessária.**

## 4. Estado das ordens abertas na Gate.io (20/08, 10:18 BRT)

| Ordem | Criada | Gatilho | Papel |
|---|---|---|---|
| TRX/USDT vender condicional | 09/08 21:04 | ≥ 0,3436 | Take-Profit |
| TRX/USDT vender condicional | 11/08 07:25 | ≤ 0,3275 | Stop-Loss |

Par OCO completo e saudável (15 TRX, `signal_id 4be19321e486ca99`,
TP id `2086604676907663360`). TRX em 0,3348 — entre os dois gatilhos.
A data mais recente do SL é assinatura do trailing D1 (cria novo → deleta antigo).
O `oco_sync` reporta `n_pairs: 1`, `status: oco_synced`, ambas as pernas `open`.
Bate 1:1 com a tela da exchange.

Saldo disponível: **468,59 USDT**.

## 5. Por que ainda não houve compra pós-fix

O cooldown de 4h venceu às 10:03 BRT, mas nenhum sinal novo foi qualificado:
`state/last_signals.json` continua com uma única chave, inalterada:

```
HYPE/USDT|Breakout / Tendência = 2026-08-20T09:03:11+00:00
```

Motivo: o HYPE **recuou** para ~71,79, ou seja **−1,77%** abaixo do entry de 73,08.
Sem romper a máxima de 30 velas, `_check_breakout_trend` não qualifica
(exige EMA9>EMA21>EMA50 + rompimento + RSI>50). **Não é falha do fix.**

Pipeline confirmado vivo: o GitHub Actions commitou `state/` às 14:17 UTC
(11:17 BRT) do mesmo dia.

> 💰 Nota: como o HYPE caiu após o sinal, a ordem morta às 06:03 teria fechado
> o dia em prejuízo. O custo REAL do incidente em 20/08 foi oportunidade
> perdida, não capital — o que não reduz a gravidade do bug.

## 6. Situação final

| Item | Estado |
|---|---|
| Typo `sspot` | ✅ corrigido no servidor e no Git |
| Pariedade servidor ↔ Git | ✅ código executável idêntico |
| TP órfãos 27/07 | ✅ expiraram |
| Par OCO TRX | 🟢 saudável, trailing ativo |
| Pipeline GitHub Actions | 🟢 ativo |
| Primeira compra pós-fix | ⏳ aguardando setup válido |
| `execution_guard.json` | ⚠️ congelado até a 1ª ordem aceita |

**Prova pendente:** uma linha em `state/orders_executed.csv` com
`status = filled` e `fill_price` preenchido.
