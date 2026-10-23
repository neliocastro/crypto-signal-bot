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
python tests/test_whitelist_php.py
python tests/test_telegram_mensagens.py
python tests/test_backtests.py
python tests/test_dca.py
php tests/test_watchdog_scan.php        # no GitHub (o checks roda); local só com PHP instalado
php tests/test_trigger_scan.php
php tests/test_agent_gate.php
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
grep -nP "'ss[a-z]" $F | grep -vE ':\s*(\*|//)'   # typos da família 'sspot' fora de comentário (vazio = ok)
grep -nP "[\x00-\x08\x0B\x0C\x0E-\x1F]" $F      # bytes de controle (exit 1 = limpo)
```
Hash local: `shasum -a 256 server/execute.php`.

Versões do relay em produção: **FIX 11 (DCA sem TP/SL, D-049)**, deployado em 2026-10-23 a partir do commit
`e08f5d35`, sha256 `945b2015…`, 21772 bytes, backup `execute.php.bak-20261023` (= D-036). Anteriores: D-036
(whitelist), sha256 `4ec3b375…`, backup `execute.php.bak-20261015b` (= FIX 10); FIX 10 (TP parcial), sha256
`6e3da8cb…`.

## 3. Token `SELF_DISPATCH_PAT`
- Fica em **dois lugares**: secret do GitHub **e** `.env` de segredos do servidor (`SELF_DISPATCH_PAT=`, lido pelo
  `trigger_scan.php`, D-039). Troque sempre nos dois.
- Sintoma de token inválido: passo **Re-arm next scan** vermelho com HTTP 401 (403 = falta Actions RW; 404 = repo
  não selecionado no token). Erro passageiro (5xx, 429, sem resposta) é tentado de novo até 3 vezes (D-043): um
  aviso amarelo "nova tentativa" com HTTP 204 no fim é normal.
- Troca no servidor: backup do `.env` (chmod 600) e edição com `nano`, nunca com `echo` (o histórico guardaria o token).
  Depois: `/usr/local/bin/php /home/ineocom/cryptosignals/bin/trigger_scan.php --dry` mostra se o token está presente.
- **Nunca** cole token, secret ou HMAC em chat, log, print ou commit. Se vazar: revogar na hora e trocar.

## 4. Cron PAXG no servidor (`paxg_rsi_check.php`)
**Pausado em 2026-10-23 e substituído pelo DCA semanal (D-049).** A linha do crontab sai quando o DCA estiver no ar.
O texto abaixo descreve como ele funcionava. Era ativo, de hora em hora, por decisão do usuário (D-032). Compra US$ 10 de PAXG com SL −15% quando o RSI 4h < 30,
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
- Comandos do Telegram (`/pausar`, `/status`…) valem no próximo scan, ~5 min (D-046); antes levavam horas (P-17).
  Para parar já: desabilitar o `main.yml` em Actions.
- O log do relay usa `"event":"execute"` (não `"order"`): confirme o nome real do campo antes de concluir por ausência.
- Para medir alcance de incidente, use `state/orders_executed.csv` (versionado), não o `execution_log.jsonl` (rotacionado).
- O cooldown de 4h vive no repositório (`last_signals.json`), não no servidor.
- Logado como `root`: `~` é `/root`; arquivo criado como root precisa de `chown ineocom:ineocom`.
- `tail -n 0` (não `tail -0`) no jailshell.

## 8. Watchdog externo (`watchdog_scan.php`, D-037)
A cada 15 min no crontab do `ineocom` (D-044). Alerta no Telegram se o scan parar por mais de 30 min (repete a cada 3 h, avisa
a volta) e se surgir `FALHA na compra` nova no `paxg_cron.log`. Só lê e avisa; não toca em ordens.

Instalação (uma vez):
1. No `/home/ineocom/cryptosignals/secrets/.env`, adicionar `TELEGRAM_TOKEN=` e `TELEGRAM_CHAT_ID=` com os mesmos valores
   dos secrets do GitHub. **Editar com o editor, nunca com `echo` no shell** (o histórico guardaria o token).
2. Deploy conferido por hash, como na seção 2 (arquivo `server/watchdog_scan.php`), com `chown ineocom:ineocom`.
3. Testar: `/usr/local/bin/php $B/watchdog_scan.php --test-telegram` (deve chegar a mensagem) e `--dry`.
4. Crontab do `ineocom` (`crontab -e -u ineocom`), sempre com o CLI:
   `*/15 * * * * /usr/local/bin/php /home/ineocom/public_html/cryptosignals/watchdog_scan.php >> /home/ineocom/public_html/cryptosignals/watchdog_cron.log 2>&1`

```bash
B=/home/ineocom/public_html/cryptosignals
tail -n 20 $B/watchdog_cron.log                     # decisões ("scan: ok", "telegram ok=SIM")
touch $B/.watchdog_pause && chown ineocom:ineocom $B/.watchdog_pause   # PAUSAR
rm -f $B/.watchdog_pause                            # REATIVAR
```

## 9. Trigger do scan pelo servidor (`trigger_scan.php`, D-039)
A cada 5 min no crontab do `ineocom`. Dispara o `main.yml` e só conta HTTP 204 como sucesso. Após 3 falhas seguidas,
alerta no Telegram (repete a cada 3 h; avisa a volta). É a perna da cadência que não depende do próprio `main.yml`.

```bash
B=/home/ineocom/cryptosignals/bin
tail -n 5 $B/trigger_scan.log                       # "dispatch HTTP 204" a cada 5 min (no GitHub, metade vira `cancelled`: normal)
/usr/local/bin/php $B/trigger_scan.php --dry        # token presente? Telegram configurado? (não dispara)
touch $B/.trigger_pause && chown ineocom:ineocom $B/.trigger_pause   # PAUSAR (faça junto ao desligar o main.yml)
rm -f $B/.trigger_pause                             # REATIVAR
```
Linha do crontab: `*/5 * * * * /usr/local/bin/php /home/ineocom/cryptosignals/bin/trigger_scan.php >> /home/ineocom/cryptosignals/bin/trigger_scan.log 2>&1`

## 10. Pasta pública do servidor (`.htaccess`, D-040)
Pela web, só o `execute.php` responde. A fonte do arquivo é `server/cryptosignals.htaccess` (sem segredo; 15 linhas,
428 bytes, sha256 `93b1e4ef…`). Paridade servidor × Git: `sha256sum /home/ineocom/public_html/cryptosignals/.htaccess`.
Para recriar: `curl -fsSL https://raw.githubusercontent.com/neliocastro/crypto-signal-bot/<SHA>/server/cryptosignals.htaccess
-o /home/ineocom/public_html/cryptosignals/.htaccess`, conferir o hash, `chown ineocom:ineocom` e `chmod 644`.
Conferir depois de qualquer mudança na pasta:
```bash
U=https://ineo.com.br/cryptosignals; curl -s -w " HTTP %{http_code}\n" $U/execute.php; for f in watchdog_scan.php paxg_cron.log execution_log.jsonl error_log; do echo "$f -> $(curl -s -o /dev/null -w '%{http_code}' $U/$f)"; done
```
Esperado: `execute.php` 401; os demais 403. **Nunca** testar abrindo um `gerar_teste_*.php`: ele compra de verdade.
Rollback: `rm -f /home/ineocom/public_html/cryptosignals/.htaccess`.

## 11. Acesso do agente ao servidor (`agent_gate.php`, D-042)
O agente só lê, e só por `ssh cryptosignals-gate <ação>`. A chave do agente fica no Mac do usuário
(`~/.ssh/cryptosignals_agent`) e, no servidor, é autorizada com comando forçado: qualquer conexão com ela executa o
`agent_gate.php`, que aceita só `help`, `status`, `hashes`, `crontab`, `env-keys`, `http` e `resumo` (status + hashes + http
numa conexão só; D-045). O `status` mostra também o `agent_gate.log` e a lista de arquivos da pasta pública.

- Entrada no `~/.ssh/config` do Mac:
  `Host cryptosignals-gate` / `HostName ineo.com.br` / `User ineocom` / `IdentityFile ~/.ssh/cryptosignals_agent` /
  `IdentitiesOnly yes` / `UseKeychain yes` / `AddKeysToAgent yes`.
- Linha no `/home/ineocom/.ssh/authorized_keys` (chave pública em uma linha só):
  `restrict,command="/usr/local/bin/php /home/ineocom/cryptosignals/bin/agent_gate.php" ssh-ed25519 AAAA… agente-cryptosignals-leitura`
- Teste de contenção: `ssh cryptosignals-gate status` responde; `ssh cryptosignals-gate 'cat /etc/passwd'` é recusado.
- Auditoria: `tail /home/ineocom/cryptosignals/bin/agent_gate.log` (data, IP, pedido, ok/RECUSADO).
- **Revogar:** apagar a linha `agente-cryptosignals-leitura` do `authorized_keys`. Efeito imediato.
- **Limite de conexões (P-20):** ~9 conexões em poucos segundos bloqueiam a porta 22 para o IP de origem por ~1 min.
  Espaçar as chamadas. Web, cPanel e relay não são afetados pelo bloqueio.
- Instalado em 2026-10-21: `agent_gate.php` sha256 `58516b29…` (6880 bytes); backup do `authorized_keys` em
  `/home/ineocom/.ssh/authorized_keys.bak-20261021`.

## 12. DCA semanal (`bot/dca.py`, D-049)
Compra US$ 10 por semana de BTC e de PAXG, sem TP/SL, no primeiro scan a partir de segunda 13:00 UTC.
1. **Pré-requisito:** o `execute.php` com o FIX 11 no servidor (seção 2), conferido por hash.
2. **Ligar:** `DCA_ENABLED = True` no `config.py` (commit e push). Desligar: `False`.
3. **Conferir a 1ª compra:** mensagem "🧺 DCA semanal" no Telegram, linha `filled` em `state/dca.jsonl`, linha no
   `state/orders_executed.csv` e, na Gate, a compra sem gatilho de TP/SL.
4. **Falhou numa semana:** o Telegram avisa e não há nova tentativa até a semana seguinte (proteção contra compra
   dobrada). Para comprar na mão naquela semana, use a Gate.
5. **Placar:** `python scripts/placar.py` mostra a seção do DCA (compras, investido, quantidade e custo médio).

