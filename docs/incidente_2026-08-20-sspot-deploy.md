# Incidente 2026-08-20 — `sspot`: 6 ordens recusadas pela Gate.io

**Severidade:** ALTA (sistema 100% incapaz de comprar)
**Duração:** de ~11/08 (deploy do FIX 8) até 20/08 09:20 BRT
**Causa raiz:** typo `'account'=>'sspot'` no `execute.php` do SERVIDOR
**Causa da causa:** falha de deploy — o FIX 9 estava commitado no Git mas nunca subiu ao servidor

---

## 1. Sintoma relatado

Sinais chegavam ao Telegram marcados `🟢 PRONTO PARA OPERAR (1)` para HYPE/USDT,
mas nenhuma compra acontecia. O header do próprio sinal mostrava
`🎯 Sinais qualificados: 0` — o que confundiu o diagnóstico inicial.

## 2. Causa raiz (provada por log)

`server/execute.php`, montagem do body da ordem de compra:

```php
$bodyArr = [... 'account'=>'sspot' ...];   // ERRADO
$bodyArr = [... 'account'=>'spot'  ...];   // CORRETO
```

A Gate.io só aceita `spot` | `margin` | `unified`. Com `sspot` a API devolve:

```json
{
  "status": "rejected_by_exchange",
  "http": 400,
  "detail": {
    "label": "INVALID_REQUEST_BODY",
    "message": "Request body not conforming to schema"
  }
}
```

Entrada real do `execution_log.jsonl` (HYPE, 20/08):

```json
{"event":"execute","order":{"signal_id":"227e953adbf190b2","symbol":"HYPE/USDT",
 "side":"buy","strategy":"Breakout / Tendência","notional_usdt":10,
 "ref_price":73.08,"sl_price":70.26574273,"tp_price":78.70851454,
 "dry_run":false,"ts":"2026-08-20T09:03:11+00:00"},
 "result":{"status":"rejected_by_exchange","http":400,
 "reason":"INVALID_REQUEST_BODY"}}
```

O `ref_price 73.08` bate exatamente com o Entry do sinal das 06:54 BRT.

## 3. Alcance — 6 ordens perdidas

| Ativo | Ordens | Notional |
|---|---|---|
| HYPE/USDT | 4 | $40 |
| ETH/USDT | 1 | $10 |
| BNB/USDT | 1 | $10 |

Não era específico do HYPE: **toda compra, de todos os ativos, em todos os
trilhos (Breakout e Maré Alta D1), estava sendo recusada.**

## 4. A causa da causa — deploy travado

| | Repositório | Servidor (antes do fix) |
|---|---|---|
| Bytes | 19.025 | 18.344 |
| Linhas | 241 | 232 |
| `'account'` | `'spot'` ✅ | `'sspot'` ❌ |
| Último FIX | **9** | **8** (11/08) |

Os 681 bytes / 9 linhas de diferença eram exatamente o bloco de comentário do
FIX 9. **O código correto existia no Git há dias — o servidor nunca recebeu.**

## 5. As DUAS barreiras (por que "qualificados: 0")

O diagnóstico exigiu separar dois bloqueios distintos e sequenciais:

| Hora local | Evento | Onde parou |
|---|---|---|
| 06:03 | ordem HYPE enviada ($10, ref 73.08) | ❌ `sspot` → HTTP 400 |
| 06:54 | Telegram 🟢 PRONTO, qualificados: 0 | 🚫 cooldown 4h |
| 07:05 | Telegram 🟢 PRONTO, qualificados: 0 | 🚫 cooldown 4h |

A falha REAL foi uma só, às 06:03. Ela carimbou
`HYPE|Breakout / Tendência` no `state/last_signals.json`, e o cooldown de 4h
(`SIGNAL_COOLDOWN_HOURS = 4`) suprimiu os sinais seguintes — comportamento
**correto**, não bug.

> ⚠️ A lista visual do Telegram é montada a partir do diagnóstico de TODOS os
> ativos, **independente** de `qualified_signals`. Por isso o HYPE aparece
> 🟢 PRONTO mesmo quando foi suprimido. Ver 🟢 no Telegram **não** significa
> que houve tentativa de ordem.

## 6. Correção aplicada

```bash
cd /home/ineocom/public_html/cryptosignals
cp -a execute.php execute.php.bak-$(date +%Y%m%d-%H%M%S)
sed -i "s/'account'=>'sspot'/'account'=>'spot'/g" execute.php
php -l execute.php
grep -c "sspot" execute.php        # 0
curl -s -o /dev/null -w "%{http_code}\n" https://ineo.com.br/cryptosignals/execute.php  # 401
```

Validação: `No syntax errors detected` · `'account'=>'spot'` = 1 ·
`sspot` = 0 · endpoint HTTP 401 (HMAC protegendo).

## 7. Verificação de paridade servidor ↔ Git (rodar antes de cada sessão)

```bash
cd /home/ineocom/public_html/cryptosignals
echo "=== servidor ===" && wc -c -l execute.php
echo "=== fixes presentes ===" && grep -n "FIX [0-9]" execute.php | cut -c1-110
echo "=== typos da familia ===" && grep -nP "'ss[a-z]|=>'s[a-z]+'" execute.php
echo "=== bytes de controle ===" && grep -nP "[\x00-\x08\x0B\x0C\x0E-\x1F]" execute.php
echo "=== ultimas execucoes ==="
grep '\"event\":\"execute\"' execution_log.jsonl | tail -3 | \
  grep -o '\"symbol\":\"[^\"]*\"\|\"status\":\"[^\"]*\"\|\"http\":[0-9]*'
```

Compare a contagem de `FIX N` com a do repositório. Se o servidor tiver menos,
ele está rodando código velho.

## 8. Lições

1. **FIX commitado ≠ FIX deployado.** O bug não estava no código do Git; estava
   na ponte entre Git e servidor. Sempre verificar paridade.
2. **O log usa `"event":"execute"`, não `"event":"order"`.** Um grep pelo campo
   errado devolveu vazio e levou a uma conclusão errada no meio da investigação
   ("a ordem sequer foi enviada"). Confirmar o nome real do campo antes de
   concluir por ausência de resultado.
3. **Ausência de evidência ≠ evidência de ausência** — mesma lição já registrada
   em `docs/gateio_limitacoes.md` (a tela da Gate.io só mostra ordens abertas).
4. **Esse arquivo tem histórico de corrupção de bytes:** FIX 8 removeu um byte de
   controle `0x1D`; havia também `'ssem TP nem SL'`. `sspot` é da mesma família.
   Varrer typos após cada edição manual.
5. **Fusos:** `execution_log.jsonl` é UTC; o Telegram é America/Bahia (−3h).
   Sempre converter antes de correlacionar eventos.

## 9. Estado de idempotência

Durante o diagnóstico o `seen_signals.json` foi zerado (58 → 0) e depois
restaurado, liberando apenas `227e953adbf190b2` (58 → 57). Backups em
`seen_signals.json.bak-*`.

O cooldown de 4h vive no **repositório** (`state/last_signals.json`), não no
servidor — zerar o `seen_signals.json` não o afeta.

## 10. Caminhos reais

| Item | Caminho |
|---|---|
| Relay | `/home/ineocom/public_html/cryptosignals/execute.php` |
| Segredos | `/home/ineocom/cryptosignals/secrets/.env` |
| Log | `/home/ineocom/public_html/cryptosignals/execution_log.jsonl` |
| Idempotência | `/home/ineocom/public_html/cryptosignals/seen_signals.json` |
| SSH | `ineocom@dedi-15131000` (jailshell, `/tmp` noexec) |
