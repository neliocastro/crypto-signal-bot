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

### ✅ O caminho válido: emular OCO do nosso lado

Como não existe OCO nativo, a exclusividade mútua precisa ser feita por nós:

- Guardar `tp_order_id` **e** `sl_order_id` no `state/positions.jsonl`.
- Ao detectar que um lado executou, **cancelar o outro** via
  `DELETE /api/v4/spot/price_orders/{id}` (o `gate_delete()` do PHP já faz
  isso no fluxo de trailing).
- Reconciliar contra a corretora (`GET /api/v4/spot/price_orders?status=open`)
  antes de agir — nunca confiar apenas no estado local do repo.

---

## 2. Caso real — 27/07/2026: os SL do HYPE desapareceram 🔴

### O que aconteceu

Duas compras REAIS de HYPE (\$5 cada), estratégia Breakout/Tendência:

| signal_id | hora (UTC) | fill | qty | TP | SL |
|---|---|---|---|---|---|
| `7e16ccd261b86c35` | 04:03 | 59.99 | 0.082 | 61.34 ✅ existe | 59.22 🔴 desapareceu |
| `4dbd732719211751` | 05:09 | 60.40 | 0.081 | 61.72 ✅ existe | 59.45 🔴 desapareceu |

### A resposta do relay dizia que o SL nasceu

Log do `state/paper_trades.jsonl`:

```json
"tpsl": {
  "enabled": true,
  "tp": { "http": 201, "id": 2081607963629322240, "err": null, "price": "61.72" },
  "sl": { "http": 201, "id": 2081607968662487040, "err": null, "price": "59.45" },
  "rules_source": "api",
  "base_qty": "0.081"
}
```

**HTTP 201, id gerado, `err: null`** nos dois lados. A Gate.io aceitou o SL.

### Por que NÃO foi o bug de precisão

Descartado com evidência:

- `rules_source: "api"` → o `pair_rules()` leu a Gate.io com sucesso; **não**
  caiu na tabela de fallback.
- HYPE_USDT tem `precision = 2`; os preços enviados (`59.45`, `61.72`) têm
  exatamente 2 casas. ✅ corretos.
- O **TP**, com o mesmo formato e a mesma `base_qty`, funcionou e **está**
  nas ordens abertas da corretora.

### Consequência financeira

O preço caiu abaixo dos dois gatilhos (mínima 24h **57.17**, ambos os SL em
~59.4) e **nada foi vendido** — não havia stop na corretora.

```
Posição: 0.163 HYPE · custo $9.81
Preço em 27/07 ~17:50 UTC: 57.18  ->  valor $9.32
Prejuízo aberto: -$0.49 (-5.0%)
Se os SL tivessem disparado: ~-$0.15 (-1.5%)
Perda extra atribuível à falha: ~-$0.34
```

O teto de \$5/ordem limitou o dano. O **mecanismo**, porém, falhou: a
proteção existia no log e não na corretora.

### Causa raiz: NÃO DETERMINADA ⚠️

Não há evidência suficiente para concluir. Hipóteses ainda abertas:

- O SL disparou, a ordem de mercado resultante falhou e a Gate.io removeu a
  condicional sem registrar venda.
- `expiration: 2592000` interpretado de forma diferente do esperado.
- Cancelamento manual involuntário.
- Alguma regra da Gate.io sobre condicionais de venda com `account: normal`.

**⛔ Não inventar causa.** Duas consultas fecham a questão (exigem a chave
privada, portanto rodam no relay):

```
GET /api/v4/spot/price_orders/2081591195686928384   # SL da 1a compra
GET /api/v4/spot/price_orders/2081607968662487040   # SL da 2a compra
```

O campo `status` retorna `open` | `finish` | `cancelled` | `failed`, e
`reason` explica o motivo.

---

## 3. Referência cruzada — o que funcionou

A posição **ETH** (`consolidated_eth_0710`) foi a única que fechou
corretamente, no lucro: TP executado em 26/07 20:07:49 a **1957.54**
(entrada 1709.66 → **+14.5%**, ~+\$1.44).

Detalhe relevante: essa posição foi **consolidada manualmente** por
Nélio numa estrutura de proteção única (SL 1545 / TP 1957) — não pelo
fluxo automático de duas condicionais independentes.

---

## 4. Checklist antes de mexer em TP/SL

- [ ] Confirmei que **não** estou propondo OCO nativo (não existe).
- [ ] O fluxo cancela o lado oposto quando um dispara?
- [ ] O `positions.jsonl` guarda `tp_order_id` **e** `sl_order_id`?
- [ ] Há reconciliação contra `GET /spot/price_orders?status=open` antes de agir?
- [ ] A precisão vem de `pair_rules()` (`rules_source: api`) e não do fallback?
- [ ] Existe verificação **pós-criação** de que a ordem realmente ficou aberta?

---

_Registrado em 2026-07-27 por solicitação de Nélio Castro, após proposta
incorreta de "OCO nativo" ter sido repetida. Atualizar este documento quando
a causa raiz do item 2 for determinada._
