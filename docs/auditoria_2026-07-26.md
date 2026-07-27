# Auditoria 2026-07-26 21:30 BRT - crypto-signal-bot

## 1. BLOQUEADOR CRITICO (bot estava PARADO) - CORRIGIDO

O commit `dd38b87` ("Update main.yml", 00:17 UTC) deixou o YAML invalido:
`inputs:` ficou indentado como IRMAO de `workflow_dispatch:` dentro de `on:`,
virando um "trigger" inexistente. O GitHub rejeita o arquivo inteiro -> o run
30227100304 falhou com ZERO jobs (nem criou o job `scan`).

Enquanto isso durou, NENHUM scan rodou e nenhuma ordem pode ser enviada.
Os 2 ultimos runs verdes foram 00:10 e 00:16 UTC, logo antes da quebra.

**Fix:** `inputs:` reaninhado dentro de `workflow_dispatch:`.

## 2. INCOERENCIA Python x PHP (dinheiro real anunciado como simulado) - CORRIGIDO

| Camada | Flag | Efeito real |
|---|---|---|
| `bot/config.py` | `EXECUTION_DRY_RUN = True` | Telegram avisava "Ordem simulada" |
| `server/execute.php` L10 | `$DRY_RUN = false` | **enviava ordem REAL na Gate.io** |

O PHP usa a propria global (linha 10) e IGNORA o campo `dry_run` do payload.
Resultado: o dinheiro real ja saia, mas a notificacao dizia teste.

**Fix:** `EXECUTION_DRY_RUN = False` -> os dois lados coerentes (go-live).

## 3. TETO DESALINHADO - CORRIGIDO

- `bot/config.py`: `EXECUTION_MAX_NOTIONAL_USDT = 5.0`
- `server/execute.php` L13: `$MAX_NOTIONAL_USDT = 10.0` (o dobro)

O commit `a281e4b` (23/07) tinha alinhado para 5.0, mas o `98a803a` (24/07)
reverteu para 10.0. O "cinto duplo" virou cinto frouxo.

**Fix:** PHP volta para `5.0`.

## 4. TABELA DE PRECISAO DIVERGENTE DA GATE.IO - CORRIGIDO

Conferido em 2026-07-26 via `GET /api/v4/spot/currency_pairs/<PAR>`:

| Par | price (API) | tabela antiga | amount (API) | tabela antiga |
|---|---|---|---|---|
| BTC/ETH/SOL/XRP/BNB/LINK/AAVE | - | OK | - | OK |
| **TRX_USDT** | **4** | 5 (errado) | **1** | 2 (errado) |
| **HYPE_USDT** | **2** | 3 (errado) | **3** | 2 (errado) |

Se `pair_rules()` falhar (timeout/rate-limit), o fallback mandava casas demais
em TRX e HYPE -> HTTP 400 no TP/SL -> compra sem protecao. Este e exatamente o
bug observado em 21/06.

**Fix:** linhas 17-18 do `execute.php` atualizadas.

> ATENCAO: o `execute.php` roda no servidor (ineo.com.br), NAO no GitHub.
> O commit no repo e apenas a fonte de verdade - o arquivo precisa ser
> copiado para `/home/ineocom/.../cryptosignals/execute.php` para valer.

## 5. WATCHLIST EM TRES VERSOES (pendente de decisao)

```
bot/config.py           : BTC ETH SOL XRP TRX BNB HYPE PAXG   (8)
state/runtime_config.json: BTC ETH SOL XRP TRX BNB HYPE       (7)  <- manda no scan
server/execute.php      : os 8 + LINK + AAVE                  (10) <- whitelist permissiva
```

Nao quebra nada (o PHP so autoriza), mas LINK e AAVE sairam do bot e continuam
liberados no relay. Vale limpar.

## 6. ESTADO SAUDAVEL (verificado)

- Relay `https://ineo.com.br/cryptosignals/execute.php` -> HTTP 401 sem HMAC (vivo e protegido)
- `REQUIRE_PROTECTION` no PHP recusa compra nua se ATR=0 (bug de 19/06 fechado)
- FIX 7 presente: base do TP/SL derivada de `filled_total / fill_price` (nao de `amount`)
- Travas: teto $5 - piso $3 - max 10 ordens/dia - max 10 abertas - stop diario $20
- TP/SL nativos: SL 2.0xATR, TP RR 2.0, piso de stop 0.8%
- Mare Alta trailing D1 ativo - paper_evaluator ativo - Telegram Commander verde
- `state/execution_guard.json` esta em 2026-07-23 (trades_today=2, open_positions=1):
  contadores stale, sem impacto (limites sao 10/10), zeram na virada de dia UTC.
