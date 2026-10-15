# Operação, deploy e diagnóstico

> Revisado em 2026-10-15. Runbooks práticos. Caminhos e componentes em `arquitetura.md`.
> Fusos: `execution_log.jsonl` em UTC; Telegram e o usuário em America/Bahia (UTC−3). Converta antes de correlacionar.

## 1. Saúde do sistema (auditoria rápida)

| Pergunta | Como verificar |
|---|---|
| A cadência está normal? | `gh run list --workflow main.yml` → runs `workflow_dispatch` a cada ~5 min. Sem dispatch há horas = token ou cron do servidor com problema |
| O scan rodou de verdade? | log do passo **Run bot**: "Scan AUTORIZADO … Scan finalizado" ("PULADO" = dentro do intervalo, normal) |
| O relay está no ar? | `curl -s -w " HTTP %{http_code}\n" https://ineo.com.br/cryptosignals/execute.php` → `assinatura invalida` + **401** |
| Houve compra? | `state/paper_trades.jsonl` (`relay_response` com `status: filled`) e `state/orders_executed.csv` |
| Por que não comprou? | recalcular a regra com velas reais; conferir `mare_alta_state.json`, `last_signals.json` (cooldown) e bloqueios `blocked_by_guard` |
| Placar do bot? | `python scripts/placar.py` (total, por estratégia e por ativo); `--desde 2026-09-04` filtra pela data de abertura (regra D-024); `--degrau` mostra os critérios do degrau com e sem os trades de cadência degradada. Valores estimados pelo preço do gatilho (D-034) |
| Posições vivas? | `state/positions.jsonl`: status `open*` (qualquer um conta na trava de concentração) |
| O código passa? | workflow `checks` verde (php -l + testes) |

Comandos locais antes de todo commit:
```bash
python -m py_compile bot/*.py
python tests/test_roteamento_strings.py
python tests/test_saida_tp1.py
python tests/test_renovacao_sl.py
python tests/test_placar.py
python tests/test_trava_perda_diaria.py
```

## 2. Deploy do relay (`server/execute.php`)

O relay **não** é deployado pelo Git. Fix commitado ≠ fix deployado (P-06).

1. Workflow `checks` verde no commit.
2. No servidor (como root, use caminhos absolutos):
   ```bash
   cd /home/ineocom/public_html/cryptosignals && cp -p execute.php execute.php.bak-AAAAMMDD
   curl -fsSL https://raw.githubusercontent.com/neliocastro/crypto-signal-bot/<SHA_DO_COMMIT>/server/execute.php -o execute.php.new
   wc -c -l execute.php.new && sha256sum execute.php.new      # comparar com o arquivo do commit
   ```
3. Só se bater:
   ```bash
   mv execute.php.new execute.php && chown ineocom:ineocom execute.php && chmod 644 execute.php
   curl -s -w " HTTP %{http_code}\n" https://ineo.com.br/cryptosignals/execute.php     # esperado 401
   ```
4. Se der HTTP 500: `cp -p execute.php.bak-AAAAMMDD execute.php`.
5. Se a mudança depende de uma flag no Python, **ligar a flag só depois** do deploy conferido.

Paridade servidor × Git e varredura de corrupção (o arquivo tem histórico de bytes trocados):
```bash
F=/home/ineocom/public_html/cryptosignals/execute.php
php -l $F; wc -c -l $F; sha256sum $F
grep -nP "'ss[a-z]" $F                          # typos da família 'sspot' (vazio = ok)
grep -nP "[\x00-\x08\x0B\x0C\x0E-\x1F]" $F      # bytes de controle (exit 1 = limpo)
```
Hash local: `shasum -a 256 server/execute.php`.

Versões do relay em produção: FIX 10 (TP parcial), deployado em 2026-10-15, sha256 `6e3da8cb…`, backup
`execute.php.bak-20261015`.

## 3. Token `SELF_DISPATCH_PAT`
- Fica em **dois lugares**: secret do GitHub **e** crontab do `ineocom`. Troque sempre nos dois.
- Sintoma de token inválido: passo **Re-arm next scan** vermelho com HTTP 401 (403 = falta Actions RW; 404 = repo
  não selecionado no token).
- Troca no crontab: backup `~/crontab.bak-*` (chmod 600) e histórico do shell desligado.
- **Nunca** cole token, secret ou HMAC em chat, log, print ou commit. Se vazar: revogar na hora e trocar.

## 4. Cron PAXG no servidor (`paxg_rsi_check.php`)
Ativo, de hora em hora, por decisão do usuário (D-032). Compra US$ 10 de PAXG com SL −15% quando o RSI 4h < 30,
**fora do bot** (sem `positions.jsonl`, OCO guard ou trava de concentração). Parâmetros do `paxg_rsi_check.php`
conferidos no repositório (RSI 14, limiar 30, cooldown 12 h); valor e SL estão em `gerar_teste_paxg.php`, que só existe
no servidor (conferido em 2026-10-15: US$ 10, SL −15%, sem TP; sha256 `df762466…`).
O comprador é chamado por `exec()` com `$PHP_BIN = '/usr/local/bin/php'`. Com `'php'` do PATH, o cron usa o CGI e toda
compra falha com HTTP 500 (P-16). Para checar falhas: `grep -c 'FALHA na compra' $B/paxg_cron.log`.
Versão em produção: deployada em 2026-10-15, sha256 `0e3624f6…`, 5397 bytes, backup `paxg_rsi_check.php.bak-20261015`.
```bash
B=/home/ineocom/public_html/cryptosignals
crontab -l -u ineocom | grep -i paxg               # agendamento
tail -n 20 $B/paxg_cron.log                         # decisões
/usr/local/bin/php $B/paxg_rsi_check.php --dry      # testar sem comprar
touch $B/.paxg_pause && chown ineocom:ineocom $B/.paxg_pause   # PAUSAR
rm -f $B/.paxg_pause                                # REATIVAR
```
Em crontab use sempre `/usr/local/bin/php` (CLI). `Content-type: text/html` ou `Status: 500` no log = binário CGI.

## 5. Ordens e reconciliação com a exchange
- **Antes de afirmar que uma ordem sumiu**, consulte a API: `GET /spot/price_orders/{id}` (campos `status`, `reason`,
  `ftime`, `fired_order_id`) e `GET /spot/my_trades`. A tela do app só lista ordens abertas.
- Venda nascida de gatilho tem `text` = `ao-<id da condicional>` em `/spot/my_trades`.
- Registro obsoleto com status `open*` em `positions.jsonl` bloqueia compras do ativo (trava de concentração).
  Ao reconciliar à mão: mudar para `closed_manual`, registrar `closed_at`/`exit_price` e o motivo em `note`,
  **sem apagar** a linha; registrar a decisão em `memoria.md`.
- Órfãs antigas: `php ~/gate_cleanup.php orphans` (dry-run) e `cancel-orphans`.

Script de consulta assinada (servidor, jailshell: `/tmp` é noexec — grave em `~/` e rode com `bash ~/script.sh`):
```bash
ENV="/home/ineocom/cryptosignals/secrets/.env"
KEY=$(grep -E '^GATE_API_KEY' "$ENV" | head -1 | cut -d= -f2- | tr -d ' "')
SECRET=$(grep -E '^GATE_API_SECRET' "$ENV" | head -1 | cut -d= -f2- | tr -d ' "')
gate_get() {
  path="$1"; query="${2:-}"; ts=$(date +%s)
  bh=$(printf '' | openssl dgst -sha512 -hex | awk '{print $NF}')
  ss=$(printf 'GET\n/api/v4%s\n%s\n%s\n%s' "$path" "$query" "$bh" "$ts")
  sg=$(printf '%s' "$ss" | openssl dgst -sha512 -hmac "$SECRET" -hex | awk '{print $NF}')
  url="https://api.gateio.ws/api/v4$path"; [ -n "$query" ] && url="$url?$query"
  curl -s -H "KEY: $KEY" -H "Timestamp: $ts" -H "SIGN: $sg" "$url"; echo
}
gate_get "/spot/price_orders/<ID>"
gate_get "/spot/my_trades" "currency_pair=BTC_USDT&limit=20"
```

## 6. Posições manuais do usuário (fora do bot)
BTC e PAXG manuais **não** estão em `positions.jsonl`, **não** entram no P&L do bot e **não** são cobertas pelo OCO
guard (D-025). Situação em 2026-10-11: 0,0031756 BTC sem ordens de proteção; PAXG 0,0529.
Ferramenta: `php ~/btc_tp.php` (`--list`, `--sl QTD --live`, `--cancel ID`). Ao listar, use `tail -n +2` antes do JSON
e conte ordens com `grep -o '"id"' | wc -l` (o `grep -c` conta linhas e dá falso alarme, P-13).
`BTC_USDT`: preço com 1 casa, quantidade com 6.

## 7. Armadilhas recorrentes
- Run verde ≠ passo funcionou: confira códigos HTTP.
- O log do relay usa `"event":"execute"` (não `"order"`): confirme o nome real do campo antes de concluir por ausência.
- Para medir alcance de incidente, use `state/orders_executed.csv` (versionado), não o `execution_log.jsonl` (rotacionado).
- O cooldown de 4h vive no repositório (`last_signals.json`), não no servidor.
- Logado como `root`: `~` é `/root`; arquivo criado como root precisa de `chown ineocom:ineocom`.
- `tail -n 0` (não `tail -0`) no jailshell.
