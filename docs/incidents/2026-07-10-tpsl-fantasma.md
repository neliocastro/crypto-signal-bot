# Post-mortem — TP/SL fantasma (02–10/jul/2026)

**Severidade:** alta (posições reais sem proteção na exchange)
**Perda financeira:** nenhuma (posições seguem abertas e em lucro)
**Status:** corrigido — commits `171c0bb` e `a703511` + deploy manual do `execute.php` no servidor (10/jul)

## Sintoma

Posições ETH compradas pelo bot (02/07 e 05/07) apareciam na Gate.io **sem TP/SL ativos**, embora o `execution_log`/`paper_trades.jsonl` registrasse a criação dos gatilhos com HTTP 201. Em 10/07 restava apenas 1 gatilho órfão (SL 1614,58 da compra de 02/07).

## Causa-raiz

Em **MARKET BUY** na Gate.io, o campo `amount` da resposta da ordem vem denominado em **QUOTE (USDT gastos)**, não em base. O `server/execute.php` usava:

```php
if (isset($gate['amount']) && (float)$gate['amount'] > 0) $base_raw = (float)$gate['amount'];   // BUG
elseif ($fill_price > 0) $base_raw = (float)($result['filled_total']) / $fill_price;             // correto, nunca alcançado
```

Como `amount` sempre vem preenchido, os gatilhos TP/SL eram criados para vender **~4,99 ETH** (o notional em USDT) em vez de **~0,0029 ETH**. A Gate.io aceita a criação do gatilho sem validar saldo; quando o trigger dispara, a venda falha por saldo insuficiente e **o gatilho é consumido silenciosamente**.

## Timeline

| Data | Evento |
|---|---|
| 02/07 | Compra ETH #1 (0,0030 @ 1.644,41) + TP 1.700,88 / SL 1.614,58 com qty errada (4,99) |
| 03/07 | Preço cruza o TP #1 → venda falha → gatilho some |
| 05/07 | Compra ETH #2 (0,0028 @ 1.779,58) + TP 1.817,61 / SL 1.760,56 com qty errada |
| ~07/07 | Máxima 1.849,54 cruza TP #2 → falha → some |
| 08/07 | Mínima ~1.743 cruza SL #2 → falha → some (posição nua) |
| 10/07 | Auditoria encontra o órfão de 02/07; reconstrução via `paper_trades.jsonl`; causa-raiz identificada no `execute.php` |

## Correções

1. **Camada 0 (manual, imediata):** TP/SL manual na Gate.io — trigger 1.957,54 / 1.552,00, qty 0,0059 (saldo real 0,005975 c/ staking) — cobrindo as 2 posições.
2. **Commit `171c0bb`:** `state/positions.jsonl` criado com as 2 posições reais → trailing D1 (3×ATR, catraca) as adota no próximo ciclo.
3. **Commit `a703511` (FIX 7):** `base_raw = filled_total / fill_price` sempre; sanity check `base×fill ≤ notional×1,05`, senão TP/SL não são criados e o motivo fica no `note` (fail-safe > fail-silent). **Deployado no servidor em 10/07.**
4. Roteamento por trilho (já em `bot/main.py`, 2026-07-10) elimina a duplicidade de executores que originou a 2ª compra de ETH pelo trilho intraday.

## Lições

- **HTTP 201 na criação de gatilho ≠ proteção real.** A exchange não valida saldo na criação de price-triggered orders; validar `base_qty` contra o fill é responsabilidade do cliente.
- **Fallback correto inalcançável = código morto perigoso.** O cálculo certo existia desde o início, atrás de um `if` que nunca deixava chegar nele.
- **Campos de API denominados em quote vs base** precisam de comentário explícito no código e teste de sanidade em runtime.
- Auditoria periódica: comparar posições em carteira × gatilhos ativos na exchange (candidato a check automático no watchdog).
