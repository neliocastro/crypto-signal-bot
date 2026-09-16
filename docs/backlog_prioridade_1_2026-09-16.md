# Backlog — Prioridade 1 (4 itens)

> Documento de **registro**, criado em **2026-09-16**. Nenhuma linha de codigo de
> producao foi alterada neste commit. O bot segue exatamente como esta no `main`.
> Objetivo: travar por escrito o que esta pendente, com evidencia, plano,
> criterio de aceite e rollback — para implementar depois com calma.
>
> Contexto vigente: ver `docs/estado_atual.md`.
> **ATENCAO: o bot envia ORDENS REAIS** (`EXECUTION_DRY_RUN = False`,
> teto $10/ordem, stop $20/dia, max 10/dia).

## Resumo

| # | Item | Onde | Toca ordem real? | Esforco |
|---|---|---|---|---|
| 1 | Override de stop por simbolo (HYPE 3.0xATR) | `bot/executor.py` + `bot/config.py` | **SIM** | medio |
| 2 | Registrar auditoria do degrau $20 (NAO subir) | `bot/config.py` + doc | nao | baixo |
| 3 | Limpar residuo do PAXG no estado | `state/last_signals.json` | nao | baixo |
| 4 | OCO Guard nao cobre ordens manuais (BTC) | `bot/oco_guard.py` + runbook | **SIM** | alto |

---

## 1. Override de stop por simbolo — HYPE a 3.0xATR

**Status:** pendente (assumido explicitamente no proprio codigo).

**Evidencia (comentario em `bot/config.py`, bloco `EXECUTION_ATR_MULT_SL`):**

> "Escolha: 2.5x melhora os DOIS trilhos. O otimo do HYPE (3.0x) exigiria um
> override por simbolo no executor.build_order() - **commit isolado, ainda nao
> feito**."

Backtest de referencia (ver `docs/decisao_stop_e_universo_2026-08-23.md`):

| Trilho | 2.0x | 2.5x | 3.0x |
|---|---|---|---|
| HYPE 1h (180d) | PF 1.18 | PF 1.31 | **PF 1.50** |
| D1 (BTC/SOL/TRX/BNB) | — | **melhor em 5 de 6** | pior |

Hoje **um unico** `EXECUTION_ATR_MULT_SL = 2.5` serve os dois trilhos. O D1 esta
no seu otimo; o HYPE nao.

**Plano proposto (aditivo, com fallback seguro):**

```python
# bot/config.py — dict OPCIONAL. Ausente/vazio = comportamento atual.
EXECUTION_ATR_MULT_SL_BY_SYMBOL = {
    "HYPE/USDT": 3.0,
}
```

```python
# bot/executor.py, dentro de build_order():
# le o override; se nao houver, cai no global. NUNCA quebra se a chave faltar.
mult = EXECUTION_ATR_MULT_SL_BY_SYMBOL.get(symbol, EXECUTION_ATR_MULT_SL)
```

Seguir o padrao ja usado em `executor.py` para `EXECUTION_CONCENTRATION_GUARD`:
`try: from .config import ... / except Exception: <default>`.

**Criterio de aceite:**
- `py_compile` limpo.
- Proxima compra de HYPE registra em `paper_trades.jsonl` stop com **3.0x** ATR.
- Proxima compra de BTC/SOL/TRX/BNB continua com **2.5x** (nao regride).
- `EXECUTION_MIN_STOP_PCT = 0.8` continua sendo aplicado **depois** do override.

**Rollback:** remover a chave do dict (ou o dict inteiro) e dar push. 1 linha.

**Risco:** stop mais largo = perda maior por trade quando estopa. Com teto de
$10/ordem, a exposicao adicional e de centavos.

---

## 2. Degrau de $20 — auditoria reprovada, registrar formalmente

**Status:** decisao **ja tomada** (nao subir), mas registrada apenas num
comentario inline. Merece doc propria para nao se perder.

**Regra do degrau (em `EXECUTION_MAX_NOTIONAL_USDT`):** subir $10 -> $20 **so**
no 20o trade, com P&L > 0 e PF >= 1 ex-ETH.

**Auditoria de 2026-08-23 — 3 de 3 criterios FALHAM:**

| Criterio | Exigido | Real | Veredito |
|---|---|---|---|
| Trades | >= 20 | 14 | REPROVADO |
| P&L ex-ETH | > 0 | -$0.23 | REPROVADO |
| PF | >= 1 | 0.60 | REPROVADO |

**Decisao:** manter `EXECUTION_MAX_NOTIONAL_USDT = 10.0`. **Nao subir.**

**Acao pendente:** reauditar apos os 4 itens acima, com a serie pos-remocao do
PAXG e pos-ajuste de stop (a base de 14 trades esta contaminada por HYPE com
stop de 2.0x e por ativos ja removidos da watchlist).

**Nota de metodo:** so subir degrau com a amostra do **regime atual**. Reusar
trades de configuracao antiga para justificar aumento de tamanho e o erro
classico de aumentar aposta com base em dado que nao vale mais.

---

## 3. Residuo do PAXG no estado

**Status:** pendente (baixo impacto, higiene).

O PAXG foi removido em 2026-09-04 (`ACCUMULATION_ENABLED = False` + fora da
`WATCHLIST`, ver `docs/paxg_removido_2026-09-04.md`), mas os arquivos de estado
podem ainda carregar entradas antigas dele:

- `state/last_signals.json` — chaves de cooldown de simbolo fora do universo.
- `state/accumulation_signals.json` — estado de uma estrategia desligada.

**Efeito real:** nenhum sinal ou ordem e gerado (o ativo nao entra no scan). O
problema e **diagnostico**: o estado sugere um universo que nao existe mais, e
foi exatamente esse tipo de divergencia silenciosa que gerou o incidente da
dupla fonte de verdade da watchlist em 2026-08-24.

**Plano:** remover as chaves de simbolos que nao estao na `WATCHLIST` atual.
Idealmente **automatizar**: no load do estado, descartar chave cujo simbolo nao
esteja no universo vigente (self-healing, evita repetir a limpeza manual a cada
remocao de ativo).

**Criterio de aceite:** apos um scan, `last_signals.json` contem apenas simbolos
da `WATCHLIST` vigente.

**Rollback:** irrelevante — o arquivo e regravado a cada scan.

---

## 4. OCO Guard nao cobre ordens manuais (posicao BTC do usuario)

**Status:** pendente. **Maior risco dos quatro.**

**Limite documentado (`bot/config.py` e `docs/gateio_limitacoes.md` secao 7):**
o `oco_guard` so reconcilia pares TP<->SL registrados em
`state/positions.jsonl` — isto e, **ordens criadas pelo bot**. Ordens **manuais**
criadas na corretora **nao sao cobertas**.

**Exposicao concreta:** a posicao propria de BTC (~0.00527384 BTC, PM ~$60.749,8),
protegida por ordens manuais via `~/btc_tp.php`:

| Perna | Preco | Qtd |
|---|---|---|
| TP1 | 85.000 | 0.0021 |
| TP2 | 95.000 | 0.0019 |
| SL | 69.200 | 0.0040 |
| Runner | livre | 0.00127384 |

A Gate.io **nao tem OCO nativo no spot**: TP e SL sao `price_orders`
independentes e nao reservam saldo. Se o **SL de 0.0040 disparar**, os TPs de
0.0021 e 0.0019 continuam `open` sobre base ja vendida e vao terminar em
`BALANCE_NOT_ENOUGH` / `expired` — exatamente o padrao ja observado (TPs orfaos
do HYPE em 27/07 e SL do ETH em 11/08).

**Cenario inverso, mais grave:** se **TP1 e TP2 dispararem** (total 0.0040), o SL
de 0.0040 fica cobrindo base que nao existe mais — e o **runner de 0.00127384
fica sem stop nenhum**, sem ninguem avisar.

**Plano proposto (2 fases):**

1. **Observar antes de agir** (risco zero): estender o `oco_sync` para
   **listar e reportar** pares manuais via `GET /spot/price_orders?status=open`,
   sem cancelar nada. Alerta no Telegram quando detectar perna orfa.
2. **Somente depois**, com allowlist explicita de `order_id`, permitir o cancelamento
   automatico da perna sobrevivente.

**Regra de metodo obrigatoria** (licao de 27/07/2026): a tela "Ordem" do app
Gate.io mostra **somente ordens abertas** — condicionais com status
`finish`/`failed`/`expired`/`cancelled` **desaparecem da lista**. Ausencia na tela
**nao** prova que a ordem nao existiu. Antes de afirmar que algo sumiu ou que a
posicao esta desprotegida, consultar sempre
`GET /api/v4/spot/price_orders/{id}` e `GET /api/v4/spot/my_trades`; os campos
decisivos sao `status`, `reason`, `ftime` e `fired_order_id`.

**Criterio de aceite (fase 1):** o guard reporta as 3 pernas manuais do BTC a
cada scan, sem emitir nenhum `DELETE`.

**Rollback:** `OCO_GUARD_ENABLED = False` (kill-switch ja existente).

**Risco de nao fazer:** o runner de BTC pode ficar descoberto silenciosamente.
**Risco de fazer errado:** cancelar por engano uma protecao manual valida da
posicao pessoal — por isso a fase 1 e somente leitura.

---

## Ordem de execucao recomendada

1. **Item 3** (residuo PAXG) — risco zero, higiene de estado.
2. **Item 2** (registrar auditoria do degrau) — so documentacao/comentario.
3. **Item 1** (override de stop do HYPE) — aditivo, rollback de 1 linha.
4. **Item 4** (OCO manual) — fase 1 somente leitura; fase 2 depois de observar.

Racional: comecar pelo que **nao toca ordem real** e terminar pelo que mexe na
protecao de capital proprio.

## Nao fazer agora

- Subir o teto para $20 (item 2: reprovado 3 de 3).
- Reentrar ETH, XRP, LINK, SOL-breakout, AAVE ou PAXG (todos reprovados em
  backtest; ver `docs/estado_atual.md`).
- Cancelar ordens manuais do BTC automaticamente antes da fase 1 do item 4.
