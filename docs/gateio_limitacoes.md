# Limitações da Gate.io (spot) — conhecimento permanente

> **Leia antes de propor qualquer mecanismo de proteção de posição.**
> Este documento existe para evitar retrabalho e propostas tecnicamente
> inválidas que já foram descartadas.

---

## 1. A Gate.io NÃO tem OCO nativo no spot ⛔

Esta é a limitação mais importante da arquitetura de execução.

| | Situação |
|---|---|
| OCO nativo (One-Cancels-the-Other) no spot | ❌ **NÃO EXISTE** |
| Endpoint para vincular duas ordens | ❌ Não existe |
| O que existe | ✅ `POST /api/v4/spot/price_orders` (price-triggered orders) |

### O que são as price-triggered orders

É o que o `server/execute.php` usa (linha ~150). Cada uma é uma ordem
**condicional independente**:

```php
$ppath = '/api/v4/spot/price_orders';
// TP
$tpBody = ['trigger'=>['price'=>$tp_s,'rule'=>'>=','expiration'=>2592000],
           'put'=>['type'=>'market','side'=>'sell','amount'=>$base_qty_s,
                   'account'=>'normal','time_in_force'=>'ioc'],'market'=>$pair];
// SL
$slBody = ['trigger'=>['price'=>$sl_s,'rule'=>'<=', ...] ...];
```

Características:

- 🔗 **Não há vínculo entre TP e SL.** São dois objetos separados na exchange.
- 💰 **NÃO reservam saldo.** A condicional só existe como gatilho; a ordem
  de mercado nasce quando o `trigger.price` é atingido.
- ⚠️ **Consequência:** se o TP disparar e vender a base, o SL continua vivo
  na corretora apontando para uma quantidade que não existe mais — e
  vice-versa. **Nós** temos que cancelar o outro lado.

### ❌ Hipóteses ERRADAS já descartadas

Registradas aqui justamente para não voltarem:

1. ~~"Usar OCO nativo da Gate.io"~~ → **não existe no spot.** Proposta inválida.
2. ~~"O TP reservou o saldo e o SL ficou órfão por saldo insuficiente"~~ →
   price-triggered orders **não reservam saldo**. Não há disputa.
3. ~~"Os SL do HYPE de 27/07 nunca nasceram / desapareceram"~~ → **falso.**
   Nasceram, dispararam e executaram. Ver seção 2.

### ✅ O caminho válido: emular OCO do nosso lado

Como não existe OCO nativo, a exclusividade mútua precisa ser feita por nós:

- Guardar `tp_order_id` **e** `sl_order_id` no `state/positions.jsonl`.
- Ao detectar que um lado executou, **cancelar o outro** via
  `DELETE /api/v4/spot/price_orders/{id}` (o `gate_delete()` do PHP já faz
  isso no fluxo de trailing).
- Reconciliar contra a corretora (`GET /api/v4/spot/price_orders?status=open`)
  antes de agir — nunca confiar apenas no estado local do repo.

---

## 2. Caso real — 27/07/2026: os SL do HYPE FUNCIONARAM ✅

> **CAUSA RAIZ CONFIRMADA** via `GET /spot/price_orders/{id}` executado no
> servidor em 27/07/2026 16:51 BRT. A hipótese de "SL desapareceu" era
> **FALSA**. Os stops fizeram exatamente o trabalho para o qual foram criados.

### As duas compras e seus stops

| # | signal_id | compra (BRT) | fill | qty | SL gatilho | SL disparou (BRT) | status |
|---|---|---|---|---|---|---|---|
| 1 | `7e16ccd261b86c35` | 27/07 01:03 | 59.99 | 0.082 | 59.22 | **27/07 11:06** | `finish` ✅ |
| 2 | `4dbd732719211751` | 27/07 02:09 | 60.40 | 0.081 | 59.45 | **27/07 10:16** | `finish` ✅ |

Resposta da API para o SL #1:

```json
{ "market": "HYPE_USDT",
  "trigger": { "price": "59.22", "rule": "<=", "expiration": 2592000 },
  "put": { "type": "market", "side": "sell", "amount": "0.082",
           "account": "normal", "time_in_force": "ioc" },
  "id": 2081591195686928384,
  "ctime": 1785124989, "ftime": 1785161204,
  "fired_order_id": 1105451750524,
  "status": "finish" }
```

### A venda confirmada em `/spot/my_trades`

```json
{ "id": "30908769", "currency_pair": "HYPE_USDT", "side": "sell",
  "role": "taker", "amount": "0.082", "price": "59.2",
  "order_id": "1105451750524", "fee": "0.0048544",
  "fee_currency": "USDT", "deal": "4.8544",
  "text": "ao-2081591195686928384" }
```

O campo `text` começa com `ao-` (auto order) seguido do **id da condicional** —
é a prova documental de que a venda nasceu do SL, não de uma ação manual.

### P&L real — o stop protegeu

```
Trade 1: compra 0.082 @ 59.99 = $4.9192  ->  venda @ 59.20 = $4.8544
         fee $0.0048544                  ->  liquido $4.8495
         P&L  -$0.0696  (-1.42%)

Trade 2: compra 0.081 @ 60.40 = $4.8924  ->  venda ~@ 59.40 (aprox)
         P&L  ~-$0.0858  (-1.75%)

TOTAL  : investido $9.8116 | recuperado ~$9.6561
         P&L -$0.1554  (-1.58%)
```

🎯 **Sem os stops**, a posição teria seguido até a mínima de 57.17
(≈5% de prejuízo). Os SL cortaram em -1.58%. **O mecanismo funcionou.**

### 🔴 O BUG REAL: TP órfãos (exatamente o previsto na seção 1)

Depois de o SL disparar e vender a base, os **TP continuaram abertos**:

```json
[ { "trigger": {"price":"61.72"}, "put": {"amount":"0.081"},
    "id": 2081607963629322240, "status": "open" },
  { "trigger": {"price":"61.34"}, "put": {"amount":"0.082"},
    "id": 2081591191043833856, "status": "open" } ]
```

Esses dois TP (total 0.163 HYPE) apontam para uma base **que já foi vendida**.
Se o preço subir até 61.34/61.72, eles vão disparar e **falhar**.

### Prova histórica: 4 ordens já falharam assim

O histórico de finalizadas mostra o destino inevitável do órfão:

| ctime (BRT) | gatilho | amount | status | reason |
|---|---|---|---|---|
| 03/07 03:06 | ≤ 65.732 | 4.99 | `failed` | **BALANCE_NOT_ENOUGH** |
| 03/07 03:06 | ≥ 70.519 | 4.99 | `failed` | **BALANCE_NOT_ENOUGH** |
| 29/06 15:05 | ≤ 64.422 | 4.99 | `failed` | **BALANCE_NOT_ENOUGH** |
| 29/06 15:05 | ≥ 70.265 | 4.99 | `expired` | — |

⚠️ Note o `amount: 4.99` — esse é o rastro do **bug FIX 7** (documentado no
cabeçalho do `execute.php`): `$gate['amount']` em MARKET BUY vem em **QUOTE**
(USDT), não em base. Tentava vender 4.99 HYPE (≈$300) tendo 0.08.
Já corrigido, mas as ordens antigas seguem penduradas.

### ✅ Ações que decorrem deste caso

1. Cancelar os 2 TP órfãos (`2081591191043833856`, `2081607963629322240`).
2. Cancelar os 2 TP antigos de 4.99 (≥74.92 e ≥75.01) — falha garantida.
3. Implementar a emulação de OCO da seção 1 (cancelar o lado oposto).
4. Registrar o fechamento no `state/positions.jsonl` — o repo não soube que
   as posições foram encerradas, e o trailing Maré Alta seguiu gerenciando
   posição inexistente.

---

## 3. 🧭 Lição DE MÉTODO (a mais importante deste caso)

> **A tela "Ordem (8)" do app Gate.io mostra SOMENTE ordens ABERTAS.**
> Condicionais com `status = finish` / `failed` / `expired` **desaparecem**
> dessa lista.

Eu (assistente) concluí que "o SL desapareceu / a posição está desprotegida"
porque não vi o SL nos prints do app. **Ausência na tela ≠ ordem inexistente.**
A conclusão gerou alarme falso de posição nua e duas hipóteses técnicas erradas.

**Regra:** antes de afirmar que uma ordem sumiu, consultar
`GET /api/v4/spot/price_orders/{id}` e `GET /api/v4/spot/my_trades`.
O `status` e o `fired_order_id` são a única fonte de verdade.

Corolário: **não inventar causa raiz.** Duas consultas de 10 segundos
substituíram três teorias erradas.

---

## 4. Referência cruzada — o que funcionou

A posição **ETH** (`consolidated_eth_0710`) fechou no lucro: TP executado em
26/07 20:07:49 a **1957.54** (entrada 1709.66 → **+14.5%**, ≈+\$1.44).

Foi uma posição **consolidada manualmente** por Nélio numa estrutura de
proteção única (SL 1545 / TP 1957) — não pelo fluxo automático.
Mesmo problema de reconciliação: o repo seguiu com `status: open`.

---

## 5. 🖥️ Caminhos reais da infraestrutura (servidor ineocom)

Para **não chutar caminho** em scripts de diagnóstico:

```
.env (segredos) .... /home/ineocom/cryptosignals/secrets/.env
                     (FORA da web root; lido via parse_ini_file)
variáveis .......... GATE_API_KEY
                     GATE_API_SECRET
                     EXECUTION_HMAC_SECRET
relay (web root) ... /home/ineocom/public_html/cryptosignals/execute.php
logs do relay ...... execution_log.jsonl  (mesmo dir do execute.php)
                     seen_signals.json    (idempotência por signal_id)
endpoint público ... https://ineo.com.br/cryptosignals/execute.php
                     (HTTP 401 sem assinatura HMAC — comportamento correto)
usuário SSH ........ ineocom @ dedi-15131000  (cPanel / jailshell)
```

⚠️ **Peculiaridades do shell (jailshell):**

- `/tmp` é montado com **noexec** → `chmod +x /tmp/script.sh` dá
  `Permission denied`. Gravar scripts no **home** (`~/`).
- Chamar sempre com `bash ~/script.sh` (não `./script.sh`).
- Heredoc longo pode embaralhar no eco do terminal; usar delimitador
  distinto (`<<'ENDOFSCRIPT'`) e conferir com `cat`.
- ❌ **NÃO existe** `/home/nelio/secrets/.env` — caminho inventado, já falhou.

### Script de diagnóstico que funcionou

```bash
ENV="/home/ineocom/cryptosignals/secrets/.env"
KEY=$(grep -E '^GATE_API_KEY'    "$ENV" | head -1 | cut -d= -f2- | tr -d ' "')
SECRET=$(grep -E '^GATE_API_SECRET' "$ENV" | head -1 | cut -d= -f2- | tr -d ' "')

gate_get() {                       # assinatura HMAC-SHA512 da Gate.io v4
  path="$1"; query="${2:-}"
  ts=$(date +%s)
  bh=$(printf '' | openssl dgst -sha512 -hex | awk '{print $NF}')
  ss=$(printf 'GET\n/api/v4%s\n%s\n%s\n%s' "$path" "$query" "$bh" "$ts")
  sg=$(printf '%s' "$ss" | openssl dgst -sha512 -hmac "$SECRET" -hex | awk '{print $NF}')
  url="https://api.gateio.ws/api/v4$path"; [ -n "$query" ] && url="$url?$query"
  curl -s -H "KEY: $KEY" -H "Timestamp: $ts" -H "SIGN: $sg" "$url"; echo
}

gate_get "/spot/price_orders/<ID>"
gate_get "/spot/price_orders" "status=open&market=HYPE_USDT"
gate_get "/spot/my_trades"    "currency_pair=HYPE_USDT&limit=20"
```

Campos que importam no retorno: **`status`** (`open`/`finish`/`cancelled`/
`failed`/`expired`), **`reason`**, **`ftime`** (quando finalizou) e
**`fired_order_id`** (se disparou, o id da ordem de mercado gerada).

---

## 6. Checklist antes de mexer em TP/SL

- [ ] Confirmei que **não** estou propondo OCO nativo (não existe).
- [ ] Consultei a **API** antes de afirmar que uma ordem sumiu (não o app).
- [ ] O fluxo cancela o lado oposto quando um dispara?
- [ ] O `positions.jsonl` guarda `tp_order_id` **e** `sl_order_id`?
- [ ] Há reconciliação contra `GET /spot/price_orders?status=open` antes de agir?
- [ ] A precisão vem de `pair_rules()` (`rules_source: api`) e não do fallback?
- [ ] O `amount` do TP/SL está em **BASE** (não em quote)? — bug FIX 7.
- [ ] Existe verificação **pós-criação** de que a ordem ficou aberta?

---

_Criado em 2026-07-27 por solicitação de Nélio Castro, após proposta incorreta
de "OCO nativo" ter sido repetida. **Atualizado no mesmo dia** com a causa
raiz confirmada por diagnóstico na API: os SL funcionaram; o bug real são os
TP órfãos por falta de emulação de OCO._
