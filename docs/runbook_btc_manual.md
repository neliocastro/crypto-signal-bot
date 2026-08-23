# Runbook — ordens MANUAIS de BTC (fora do bot)

> Posicao **manual** do usuario na Gate.io. NAO foi criada pelo bot, NAO esta em
> `state/positions.jsonl` e **NAO e coberta pelo OCO Guard** (que so reconcilia
> pares registrados pelo bot). Reconciliacao e 100% manual.

## Posicao e ordens vigentes (22/08/2026)

| Perna | Gatilho | Preco limite | Qtd (BTC) | ID |
|---|---|---|---|---|
| TP1 | `>=` 85000.0 | 84950.0 | 0.00210 | 2091210227331366912 |
| TP2 | `>=` 95000.0 | 94900.0 | 0.00190 | 2091210236151988224 |
| SL  | `<=` 69200.0 | 69000.0 | 0.00400 | 2091210244972609536 |

Saldo: 0.00527384 BTC | custo medio $60.749,8 (~$320,38) | runner sem TP: 0.00127384 BTC.

A soma das 3 ordens (0.0080) excede o saldo e isso funciona porque condicionais
**nao reservam saldo** — mas cria a necessidade do runbook de reconciliacao abaixo.

---

## ✅ CHECK SEMANAL — versao CORRETA

```bash
php ~/btc_tp.php --list | tail -n +2 | grep -o '"id"' | wc -l    # deve retornar 3
```

Visao completa (id + status + gatilho de cada perna):

```bash
php ~/btc_tp.php --list | tail -n +2 | python3 -m json.tool \
  | grep -E '"id"|"status"|"price"|"rule"'
```

O `tail -n +2` e obrigatorio: o script imprime `http=200` antes do JSON e o
`json.tool` quebra sem isso.

## ❌ CHECK ERRADO (documentado por engano em 22/08 — NAO usar)

```bash
php ~/btc_tp.php --list | tail -n +2 | grep -c '"id"'    # ERRADO
```

**Por que falha:** `grep -c` conta **LINHAS que casam**, nao ocorrencias. O
`--list` devolve o JSON compactado em **uma unica linha**, entao o comando
retorna `1` mesmo com as 3 ordens abertas. Diferenca: `-c` conta linhas, `-o`
imprime cada ocorrencia (e o `wc -l` entao as conta).

### Falso alarme real (2026-08-23)

O check errado retornou `1` e sugeriu que 2 ordens teriam sumido. O check
correto retornou `3` e o `json.tool` confirmou as tres `open`. Nada havia
acontecido. Sinais que ja contradiziam o alarme **antes** de qualquer comando:

- BTC ~$76,9k: longe dos dois gatilhos (85.000 e 69.200) — nenhuma perna podia
  ter disparado;
- saldo `0,00527384` intacto e congelado `0,00`: se o TP1 tivesse disparado,
  0,0021 BTC teriam saido.

**Licao:** comandos de verificacao tambem precisam ser verificados. Mesma
familia do falso positivo do `grep -nP "'ss[a-z]|=>'s[a-z]+'"`, que casava com
`'side'=>'sell'` (ver `docs/incidente_2026-08-20-sspot-deploy.md`). Antes de
declarar incidente, cruze o resultado do comando com evidencia independente.

---

## Runbook de reconciliacao (obrigatorio quando o check nao der 3)

Primeiro descubra QUAL perna disparou:

```bash
php ~/btc_tp.php --list | tail -n +2 | python3 -m json.tool
```

**Se o TP1 disparou** (vendeu 0,0021 → restam 0,00317384 BTC): o SL de 0,0040
virou orfao e falharia com `BALANCE_NOT_ENOUGH`. Cancele e recrie no tamanho certo:

```bash
php ~/btc_tp.php --cancel 2091210244972609536
php ~/btc_tp.php --sl 0.00317384 --live
```

**Se o SL disparou:** cancele os dois TPs.

```bash
php ~/btc_tp.php --cancel 2091210227331366912
php ~/btc_tp.php --cancel 2091210236151988224
```

## Regras da API que custaram caro

1. `BTC_USDT`: `precision = 1` (preco com **1 casa decimal**) e
   `amount_precision = 6`. Preco com mais casas → HTTP 400.
2. Em `POST /api/v4/spot/price_orders` o campo `put.account` e **`normal`**
   (aceita `normal|margin|cross_margin`) — **nao** `spot`. Semantica diferente
   de `/spot/orders`, onde `account` e `spot`. Primo direto do typo `sspot`.
3. A Gate.io nao tem OCO nativo no spot: TP e SL sao ordens independentes.
