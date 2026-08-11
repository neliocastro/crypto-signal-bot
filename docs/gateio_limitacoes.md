# Limitações da Gate.io (spot) — conhecimento permanente

> **Leia antes de propor qualquer mecanismo de proteção de posição.**
> Este documento existe para evitar retrabalho e propostas tecnicamente
> inválidas que já foram descartadas.
>
> **STATUS (2026-08-11): caso ENCERRADO.** As órfãs foram canceladas e a
> emulação de OCO está EM PRODUÇÃO e validada. Ver seção 7.

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

### ✅ O caminho válido: emular OCO do nosso lado — **IMPLEMENTADO (seção 7)**

Como não existe OCO nativo, a exclusividade mútua precisa ser feita por nós:

- Guardar `tp_order_id` **e** `sl_order_id` no `state/positions.jsonl`. ✅
- Ao detectar que um lado executou, **cancelar o outro** via
  `DELETE /api/v4/spot/price_orders/{id}`. ✅ (ação `oco_sync` do relay)
- Reconciliar contra a corretora (`GET /api/v4/spot/price_orders/{id}`)
  antes de agir — nunca confiar apenas no estado local do repo. ✅

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

Esses dois TP (total 0.163 HYPE) apontavam para uma base **que já foi vendida**.
(Resolvido — ver seção 7.)

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
Já corrigido, mas as ordens antigas seguiam penduradas.

### ✅ Ações que decorreram deste caso — TODAS CONCLUÍDAS (2026-08-11)

1. ~~Cancelar os 2 TP órfãos~~ ✅ resolvidos: `2081591191043833856` cancelado
   manualmente; `2081607963629322240` finalizado pela própria exchange.
2. ~~Cancelar os 2 TP antigos de 4.99~~ ✅ mortos (failed/expired na exchange).
3. ~~Implementar a emulação de OCO~~ ✅ **EM PRODUÇÃO** — ver seção 7.
4. ~~Registrar fechamentos no `positions.jsonl`~~ ✅ reconciliado (posições do
   HYPE marcadas `closed_sl`; ETH `closed_tp`); o `oco_guard` agora faz isso
   automaticamente a cada scan.

**Caso adicional (mesma classe):** em 11/08 o `gate_cleanup.php` detectou um
**SL órfão do ETH** (`2081738667730141184`, SELL 0.0058 ETH ≤ 1785.43, saldo
real 0.00007570 — déficit 98,7%): o espelho do caso HYPE (TP disparou, SL
ficou órfão). Cancelado via `cancel-orphans` (HTTP 200). Prova de que o
problema era **recorrente e bidirecional** — daí o OCO emulado ser necessário.

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
Mesmo problema de reconciliação: o repo seguiu com `status: open`
(hoje já marcado `closed_tp` e coberto pelo `oco_guard`).

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
cleanup tool ....... ~/gate_cleanup.php (orphans = dry-run; cancel-orphans)
                     log em ~/gate_cleanup_log.jsonl
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

⚠️ Grafia da API: a Gate.io retorna **`canceled`** (1 "l", grafia americana)
no status de condicional cancelada — confirmado no smoke test de 11/08.

---

## 6. Checklist antes de mexer em TP/SL

- [x] Confirmei que **não** estou propondo OCO nativo (não existe).
- [x] Consultei a **API** antes de afirmar que uma ordem sumiu (não o app).
- [x] O fluxo cancela o lado oposto quando um dispara? → `oco_sync`/`oco_guard`.
- [x] O `positions.jsonl` guarda `tp_order_id` **e** `sl_order_id`? → sim,
      desde o `register_position` atualizado (fills novos).
- [x] Há reconciliação contra a API antes de agir? → `oco_sync` consulta o
      status real de cada perna a cada scan.
- [ ] A precisão vem de `pair_rules()` (`rules_source: api`) e não do fallback?
- [ ] O `amount` do TP/SL está em **BASE** (não em quote)? — bug FIX 7.
- [ ] Existe verificação **pós-criação** de que a ordem ficou aberta?

---

## 7. ✅ RESOLUÇÃO — OCO emulado em PRODUÇÃO (2026-08-11)

O buraco descrito na seção 1 foi fechado ponta a ponta. Circuito completo:

```
COMPRA → register_position() grava tp_order_id + sl_order_id  (mare_alta_trailing.py)
SCAN   → oco_guard.sync() envia pares abertos ao relay        (bot/oco_guard.py)
RELAY  → oco_sync consulta status REAL de cada perna na API   (server/execute.php)
       → perna disparou (finish) + oposta open? DELETE na sobrevivente
PYTHON → posição vira closed_tp/closed_sl + aviso no Telegram
```

### Peças e características

| Peça | Onde | Nota |
|---|---|---|
| `register_position(..., tp_price, tp_order_id)` | `bot/mare_alta_trailing.py` + 2 pontos do `main.py` | aditivo, retrocompatível |
| Ação `oco_sync` | `server/execute.php` (deployado 11/08) | read-mostly; NUNCA cria ordem; máx. 20 pares/chamada |
| `oco_guard.sync()` | `bot/oco_guard.py`, plugado no scan após o trailing | kill-switch `OCO_GUARD_ENABLED` (default True); falha nunca derruba o scan |

### Smoke test (validação em produção, 11/08 ~12h BRT)

Usando o par já morto do HYPE (leitura pura, nada a cancelar):

```json
HTTP 200
{"status":"oco_synced","pairs":[{"signal_id":"7e16ccd261b86c35",
  "tp":{"id":"2081591191043833856","status":"canceled","ftime":1785207869},
  "sl":{"id":"2081591195686928384","status":"finish",
        "fired_order_id":1105451750524,"ftime":1785161204},
  "closed_by":"sl","cancel":null}],"checked":1}
```

- `sl.fired_order_id 1105451750524` bate com a venda auto-order auditada em
  `/spot/my_trades` (27/07) → lookup correto. ✅
- `closed_by: "sl"` → decisão correta. ✅
- `cancel: null` → TP não estava `open`, nada a cancelar → sem ação
  desnecessária. ✅

### Retrocompatibilidade

Posições antigas só têm `sl_order_id`: o guard ainda detecta SL `finish` e
fecha a posição (apenas não há TP a cancelar — o PHP responde `absent`).
Fills novos nascem com o par completo.

### Limpeza executada

- 27/07: TP órfãos do HYPE — 1 cancelado manualmente, demais finalizados pela
  exchange (BALANCE_NOT_ENOUGH/expired).
- 11/08: SL órfão do ETH `2081738667730141184` cancelado via
  `php ~/gate_cleanup.php cancel-orphans` (HTTP 200). Reconciliação contra a
  API confirmou: **zero órfãs restantes**.

---

_Criado em 2026-07-27 por solicitação de Nélio Castro, após proposta incorreta
de "OCO nativo" ter sido repetida. Atualizado no mesmo dia com a causa raiz
confirmada por diagnóstico na API. **Encerrado em 2026-08-11**: órfãs
canceladas e emulação de OCO em produção, validada por smoke test._
