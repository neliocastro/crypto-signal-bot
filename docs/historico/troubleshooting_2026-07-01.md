# Troubleshooting — crypto-signal-bot

Registro de incidentes de producao e suas correcoes, para rastreabilidade.

---

## INC-001 — Cron de acumulacao do PAXG nao comprava (HTTP 500)

**Data:** 2026-06-30 / 2026-07-01
**Severidade:** Alta (perda de oportunidade de compra)
**Componente:** `paxg_rsi_check.php` (cron de acumulacao, servidor)

### Sintoma
O RSI 4h do PAXG mergulhou abaixo de 30 em **2026-06-30 00:00 UTC** (atingiu 24,4),
mas **nenhuma compra automatica foi executada**. O fluxo de acumulacao (exclusivo do PAXG)
deveria ter disparado uma ordem de compra.

### Investigacao
Comandos rodados no servidor:

```bash
# 1) O cron esta agendado?
crontab -l | grep paxg
# -> 0 * * * * /usr/bin/php .../paxg_rsi_check.php >> .../paxg_cron.log 2>&1  (AGENDADO)

# 2) Ha pausa ativa?
ls -la .../.paxg_pause   # -> sem pausa

# 3) O que o log do cron mostra?
tail -n 20 .../paxg_cron.log
# -> repetido, toda hora:
#    Content-type: text/html; charset=UTF-8
#    Status: 500 Internal Server Error

# 4) Rodando o script A MAO:
php .../paxg_rsi_check.php --dry
# -> RSI4h=35.31 (limiar<30) | ult.compra ha 9999.0h (cooldown 12h) | dispara=NAO  (FUNCIONA!)
```

### Causa raiz
O servidor tem **dois binarios PHP**:

| Binario | Contexto | Resultado |
|---|---|---|
| `/usr/bin/php` | usado pelo **cron** | PHP-CGI/FastCGI -> imprime `Content-type` + `Status: 500` e quebra |
| `/usr/local/bin/php` | usado no **shell** (comando `php`) | PHP-CLI -> funciona corretamente |

O crontab estava usando `/usr/bin/php`, que roda em modo **CGI** (nota a saida
`Content-type: text/html` e `Status: 500 Internal Server Error`, tipica de PHP web,
nao de CLI). Ele falhava com HTTP 500 **antes** de calcular o RSI, em toda execucao
horaria. Por isso o cron nunca comprava, mesmo com o RSI cruzando abaixo de 30.

Quando rodado a mao, o shell usa `/usr/local/bin/php` (CLI), que funciona — mascarando
o problema.

### Correcao
Trocar o binario PHP do crontab para o CLI correto:

```bash
crontab -l > /tmp/ct.bak && \
crontab -l | sed 's#/usr/bin/php #/usr/local/bin/php #' | crontab - && \
crontab -l | grep paxg
```

Crontab resultante (correto):
```
0 * * * * /usr/local/bin/php /home/ineocom/public_html/cryptosignals/paxg_rsi_check.php >> /home/ineocom/public_html/cryptosignals/paxg_cron.log 2>&1
```

### Verificacao (pos-fix)
```bash
/usr/local/bin/php .../paxg_rsi_check.php --dry
# -> RSI4h=35.09 (limiar<30) | ult.compra ha 9999.0h (cooldown 12h) | dispara=NAO   (SEM erro 500)

tail -n 3 .../paxg_cron.log
# -> 2026-07-01T02:48:05+00:00  skip: RSI4h=35.09 (limiar<30) | ... | dispara=NAO
#    Log LIMPO, sem 'Status: 500'.
```

### Impacto
- A compra referente ao mergulho de RSI de 2026-06-30 00:00 UTC (RSI 24,4) foi **perdida**
  (o cron estava quebrado naquele momento).
- A partir do fix, o cron calcula o RSI e dispara corretamente no proximo cruzamento < 30.

### Prevencao
- **Sempre** usar caminho absoluto do **PHP CLI** (`/usr/local/bin/php`) em crontab, nunca `/usr/bin/php`.
- Confirmar com `php -v` qual binario o shell usa e com `which -a php` os disponiveis.
- Se o log de um cron PHP mostrar `Content-type: text/html` ou `Status: 500`, e sinal
  de que esta rodando em modo CGI (binario errado), nao CLI.
- Backup do crontab salvo em `/tmp/ct.bak` antes da alteracao.

---

## Referencia rapida — operacao do PAXG (acumulacao)

```bash
BASE=/home/ineocom/public_html/cryptosignals

touch  $BASE/.paxg_pause                       # PAUSAR a acumulacao
rm -f  $BASE/.paxg_pause                       # REATIVAR
/usr/local/bin/php $BASE/paxg_rsi_check.php --dry   # testar sem comprar
tail -n 20 $BASE/paxg_cron.log                 # ver decisoes do cron
crontab -l | grep paxg                         # conferir agendamento
```

**Parametros de acumulacao (config.py):** timeframe 4h, rsi_threshold 30, rsi_extreme 20, cooldown_hours 12.

---

## INC-002 — Ordens TP/SL desapareciam apos 24h

**Data:** 2026-06-30 / 2026-07-01
**Severidade:** Alta (posicao ficava sem protecao apos 1 dia)
**Componente:** `execute.php` (braco de execucao, servidor) — linhas 193 e 206

### Sintoma
As ordens de Take-Profit (TP) e Stop-Loss (SL) eram criadas com sucesso
(`http:201` no log, com IDs retornados pela Gate.io), mas **desapareciam
apos ~24 horas**. Posicoes que nao batiam o gatilho no primeiro dia ficavam
**desprotegidas** (sem TP e sem SL) a partir do 2o dia.

### Investigacao
```bash
grep -n "price_orders\|expiration\|trigger\|put_type\|86400" \
  /home/ineocom/public_html/cryptosignals/execute.php
# -> 186: $ppath = '/api/v4/spot/price_orders';
# -> 193: $tpBody = ['trigger'=>['price'=>$tp_s,'rule'=>'>=','expiration'=>86400], ...
# -> 206: $slBody = ['trigger'=>['price'=>$sl_s,'rule'=>'<=','expiration'=>86400], ...
```

### Causa raiz
O TP e o SL sao **price-triggered orders** (ordens condicionais, endpoint
`/api/v4/spot/price_orders`). Cada uma tem o campo obrigatorio `expiration`
(tempo de vida em segundos) — quanto tempo a ordem-gatilho fica "viva"
esperando o preco tocar o trigger.

O valor estava fixado em **`expiration => 86400`** = exatamente **24 horas**.
Passadas 24h sem o preco atingir o gatilho, a Gate.io **cancela
automaticamente** a ordem condicional. Por isso o TP/SL "sumia" apos 1 dia.

A Gate.io **exige** `expiration > 0` (nao existe valor "infinito"/perpetuo).

### Correcao
Aumentar o `expiration` de 24h para 30 dias (2592000s) nas duas linhas:

```bash
BASE=/home/ineocom/public_html/cryptosignals
cp $BASE/execute.php $BASE/execute.php.bak-expiration
sed -i "s/'expiration'=>86400/'expiration'=>2592000/g" $BASE/execute.php
grep -n "expiration" $BASE/execute.php
# -> 193: ... 'expiration'=>2592000 ...
# -> 206: ... 'expiration'=>2592000 ...
```

Equivalencias uteis: 86400=1d · 604800=7d · **2592000=30d** · 31536000=365d.

### Verificacao (pos-fix)
`grep` confirmou as linhas 193 e 206 com `'expiration'=>2592000` (30 dias).
Backup salvo em `execute.php.bak-expiration`.

### Impacto
- **Futuro:** toda nova compra passa a criar TP/SL validos por 30 dias.
- **Passado:** posicoes ja abertas cujos TP/SL ja haviam expirado ficaram
  temporariamente nuas; foram **reprotegidas manualmente** pelo operador.
  O fix NAO recria ordens ja canceladas — apenas as novas nascem com 30 dias.

### Prevencao
- Nunca usar `expiration` curto (24h) em price_orders de TP/SL de swing/trend,
  cujos trades podem levar dias/semanas para resolver.
- Ao alterar `execute.php`, sempre validar via `grep -n "expiration"` que as
  DUAS linhas (TP e SL) ficaram com o valor correto.
- Considerar (melhoria futura) um cron de "re-arme" que verifica posicoes
  abertas e recria TP/SL antes de qualquer expiracao.
