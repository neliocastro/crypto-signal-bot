# Memória do projeto — crypto-signal-bot

Histórico vivo de decisões e aprendizados. Só o que ajuda a continuidade, sem conversas e sem estado volátil
(P&L, posições e contagens ficam em `state/` e `docs/resultado_financeiro.md`; pendências e próximos passos, em
`docs/pendencias.md`).

**Convenções**
- IDs fixos: `D-` decisão aprovada, `R-` rejeitada, `P-` problema/lição. Nunca reutilize um ID.
- Decisão não se apaga: quando mudar, marque `SUBSTITUÍDA por D-0xx` e mova-a para `docs/memoria-arquivo.md`.
- Evidência detalhada (números, fills, IDs de ordem) fica em `docs/historico/`, citada no fim de cada item.
- Decisão nova **com trade-off real** ganha um arquivo `docs/decisoes/D-0xx-titulo.md` (contexto, alternativas,
  decisão, consequências; modelo em `docs/decisoes/TEMPLATE.md`). Aqui fica o resumo de 1 a 3 linhas com o link.
- Limite: ~250 linhas. Passou disso, arquive o que estiver substituído ou concluído.
- Datas em AAAA-MM-DD. Horários: UTC, salvo indicação.

---

## Decisões aprovadas

### Escopo e arquitetura
- **D-001 (2026-06-16)** Execução **real** na Gate.io spot, **só compra (LONG)**. Arquitetura cérebro/braço:
  o Python no GitHub Actions decide e assina com HMAC; o relay PHP no cPanel (IP fixo) envia as ordens.
- **D-002 (data não registrada)** **SHORT descartado em definitivo.** Não propor.
- **D-003 (2026-07-10)** **1 ativo = 1 trilho executor.** O scan intraday só emite sinal/ordem para os pares de
  `INTRADAY_EXEC_ALLOWLIST` (`bot/main.py`); o Maré Alta roda em bloco próprio. Motivo: o ETH foi comprado
  pelo trilho errado em 05/07. `historico/incidente_2026-07-10-tpsl-fantasma.md`
- **D-004 (2026-08-24)** **`bot/config.py` é a fonte única da `WATCHLIST`** (o runtime é ignorado). Efeito aceito:
  `/add` e `/rm` do Telegram ficaram inertes. `historico/watchlist_runtime_2026-08-24.md`
- **D-005 (2026-08-11)** **OCO emulado**: a Gate.io spot não tem OCO; o `oco_guard` + a ação `oco_sync` do relay
  cancelam a perna sobrevivente. `historico/gateio_limitacoes.md`
- **D-006 (2026-06-19)** **Compra sem TP/SL é recusada** (`REQUIRE_PROTECTION` no PHP) e o stop tem piso de
  0,8% do preço (`EXECUTION_MIN_STOP_PCT`; bug do TRX, ATR baixo).
- **D-007 (2026-10-09)** `SELF_DISPATCH_PAT`: token fine-grained, só este repo, Actions RW, **sem vencimento**
  (escolha do usuário). Vive em dois lugares: secret do GitHub e servidor (o local no servidor foi SUBSTITUÍDO pelo D-039: `.env` de
  segredos, não mais o crontab/script). O `main.yml` falha
  (exit 1) se o re-disparo não devolver HTTP 204. `historico/incidente_2026-10-08_stops_e_cadencia.md`

### Estratégias e universo
- **D-010 (2026-08-23)** Universo do **Maré Alta D1 = BTC, SOL, TRX, BNB**. ETH e XRP saíram (PF 0,43 e 0,55 no
  backtest fiel). `historico/decisao_stop_e_universo_2026-08-23.md`
- **D-011 (2026-08-24)** MACD-only, Integrada, Tendência MACD e Confluência **removidas do código**.
  `historico/limpeza_estrategias_2026-08-24.md`
- **D-012 (2026-09-04)** **PAXG fora da watchlist**, `ACCUMULATION_ENABLED = False` (lado Python). O cron do servidor
  `paxg_rsi_check.php` continua ativo (D-032). `historico/paxg_removido_2026-09-04.md`
- **D-013 (2026-10-13)** **Breakout HYPE desligado** (`BREAKOUT_ENABLED = False`; PF ao vivo ~0,78 em 12 trades).
  O HYPE segue escaneado, sem sinal nem ordem. Religar: `True`, só após reavaliação.
  `historico/decisao_2026-10-13_hype_desligado_e_paper.md`
- **D-014 (2026-06-14)** Cruzamento de MACD **abaixo de zero vale** como entrada (decisão consciente; hoje usado
  pelo Maré Alta).

### Execução e risco
- **D-020 (2026-08-23)** Stop inicial global **2,5×ATR** (ótimo do D1 em 5 de 6 ativos).
  `historico/decisao_stop_e_universo_2026-08-23.md`
- **D-021 (2026-09-16)** Override por símbolo: **HYPE 3,0×ATR** (`EXECUTION_ATR_MULT_SL_BY_SYMBOL`).
  `historico/override_stop_por_simbolo.md`
- **D-022 (2026-08-23)** **Trava de concentração**: no máximo 1 posição viva e 2 ordens/dia por ativo. A contagem
  lê `state/positions.jsonl` (qualquer status `open*` conta). `historico/trava_concentracao_2026-08-23.md`
- **D-023 (2026-09-16)** `open_positions` do `execution_guard.json` é **só espelho**; não "consertar".
  `historico/prioridade1_2026-09-16.md`
- **D-024 (2026-08-12; reafirmada em 2026-09-16 e 2026-10-08)** **Teto US$ 10 por ordem.** Degrau US$ 20 só com
  **20 trades fechados abertos desde 2026-09-04**, **P&L > 0** e **PF ≥ 1** nessa janela. Ao subir: mudar Python e PHP
  juntos e reavaliar `EXECUTION_DAILY_LOSS_STOP`. `historico/reauditoria_degrau_2026-10-08.md`
- **D-025 (2026-09-16)** O bot **nunca cancela ordem que não criou**: ordens manuais do usuário ficam fora do OCO guard.
  `historico/prioridade1_2026-09-16.md`
- **D-026 (2026-10-15)** Trailing do Maré Alta **só com vela D1 fechada** (`MARE_ALTA_TRAILING_CLOSED_ONLY`).
  `historico/trailing_vela_fechada_2026-10-15.md`
- **D-027 (2026-10-15)** **Saída do Maré Alta = a validada**: TP1 +10% vende 50% → SL do restante no breakeven
  (preço de entrada) → trailing 3×ATR só depois do TP1; antes, stop fixo. `MARE_ALTA_PARTIAL_TP_ENABLED = True`
  após o deploy conferido do PHP FIX 10 (sha256 `6e3da8cb…`). `historico/saida_tp1_breakeven_2026-10-15.md`
- **D-033 (2026-10-15)** **SL renovado antes de expirar**: os gatilhos da Gate expiram em 30 dias e, antes do TP1, nada
  recriava o stop (posição nua no dia 30). Com 25 dias ou mais (`SL_RENEW_AFTER_DAYS`, idade por `sl_set_at`, senão
  `opened_at`), o bot recria o SL no **mesmo preço e qty** via `update_trailing`, sem mudar o PHP (`SL_RENEW_ENABLED`).
  O `oco_guard` alerta 1x se o SL ou o TP1 pendente vierem `expired/cancelled/failed` (`SL_EXPIRED_ALERT_ENABLED`).
  O TP1 **não** é renovado (exigiria ação nova no PHP).
- **D-034 (2026-10-15)** **Placar gravado no fechamento**: o `oco_guard` grava `exit_price` (preço do gatilho executado,
  `exit_basis: gatilho_est`), `exit_qty` e `pnl_usdt_est`/`pnl_pct_est` (taxa 0,1% por ponta), somando a perna do TP1
  parcial (`EXIT_RECORD_ENABLED`). A compra grava `strategy`. `scripts/placar.py` monta o placar só lendo o
  `positions.jsonl` (linhas antigas: preço da perna, estratégia inferida com `*`). O fill real fica para depois (PHP).
- **D-035 (2026-10-15)** **Trava de perda diária ligada de fato**: até aqui `EXECUTION_DAILY_LOSS_STOP` era inerte
  (nada alimentava `realized_loss_today`). Agora a perda do dia é derivada do `positions.jsonl`: `max(0, −soma do
  pnl_usdt_est)` das posições fechadas no dia UTC (`EXECUTION_DAILY_LOSS_FROM_POSITIONS`). Só bloqueia novas compras.
  Limite mantido em US$ 20 (inalcançável no degrau de US$ 10; reavaliar ao subir o degrau, D-024). P&L é estimativa
  pelo gatilho (D-034): a trava pode disparar um pouco depois do limite exato.
- **D-036 (2026-10-15)** **Whitelist do PHP = universo atual + PAXG**: `$SYMBOL_WHITELIST` passa a aceitar só BTC, SOL,
  TRX, BNB, HYPE e PAXG (este pelo cron do servidor, D-032); saem ETH, XRP, LINK e AAVE (D-010, R-005).
  `tests/test_whitelist_php.py` falha se a whitelist divergir de `WATCHLIST ∪ MARE_ALTA_UNIVERSE ∪ {PAXG}`.
  Deployada em 2026-10-15 (commit `8298f20d`, sha256 `4ec3b375…`, HTTP 401 conferido; backup `execute.php.bak-20261015b`).
- **D-037 (2026-10-15)** **Watchdog externo no servidor** (`server/watchdog_scan.php`, crontab do `ineocom`, de hora em
  hora): lê `state/runtime_config.json` do `main` e alerta no Telegram se `last_scan_utc` passar de 60 min (DND: +30),
  repetindo a cada 3 h e avisando a volta; também alerta `FALHA na compra` nova no `paxg_cron.log`. Fora do GitHub
  Actions e do `SELF_DISPATCH_PAT`. Só lê e avisa. Exige `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` no `.env` de segredos do
  servidor. Pausa: `.watchdog_pause`. Instalado em 2026-10-16 e conferido pelo cron em 2026-10-19/20.
- **D-039 (2026-10-20)** **Disparo do scan pelo servidor = `trigger_scan.php` versionado** (`server/`, instalado em
  `/home/ineocom/cryptosignals/bin/`, fora da pasta pública; crontab a cada 5 min). Lê o `SELF_DISPATCH_PAT` do `.env`
  de segredos, só conta HTTP 204 como sucesso e alerta no Telegram após 3 falhas seguidas (repete a cada 3 h; avisa a
  volta). Substitui o `trigger_scan.sh` (token no script, sem checar HTTP, caminho errado: P-18). Pausa: `.trigger_pause`.
  Instalado em 2026-10-20 (sha256 `05846d95…`): HTTP 204 a cada 5 min conferido no log; no GitHub, 200 scans sem falha
  e intervalo máximo de 5,2 min. Enquanto a corrente vive, os disparos do servidor aparecem como `cancelled` (normal).
- **D-040 (2026-10-20)** **Pela web, a pasta `public_html/cryptosignals/` só expõe o `execute.php`**: `.htaccess` com
  `Require all denied` + exceção para o relay (P-19). Scripts de compra (`gerar_teste_*.php`), logs e estado ficam
  bloqueados (HTTP 403); os crons rodam pelo terminal e não são afetados. Conferido: relay 401, demais 403.
  Fonte versionada: `server/cryptosignals.htaccess`.
- **D-042 (2026-10-21)** **Agente acessa o servidor só por SSH restrito e só leitura**: chave gerada no Mac do usuário,
  autorizada no `ineocom` com `restrict,command=` apontando para `server/agent_gate.php` (menu fixo: `help`, `status`,
  `hashes`, `crontab`, `env-keys`, `http`; saída com máscara de segredos; log de cada chamada). Nunca como `root`.
  Deploy, crontab e `.env` continuam com o usuário. `docs/decisoes/D-042-acesso-do-agente-ao-servidor.md`
  Instalado em 2026-10-21 (sha256 `58516b29…`; host key do servidor `SHA256:YcHODEy6…daf8` conferida dos dois lados).
  Contenção testada: pedidos fora do menu, `-tt`, `scp` e túnel recusados.
- **D-028 (2026-10-13)** As posições-papel XRP (23/08) e PAXG (28/08) em `state/paper_positions.json` são
  **obsoletas e ignoradas** (não são ordens reais).

### Processo e documentação
- **D-038 (2026-10-19)** Estrutura de documentação (substitui o D-030): `CLAUDE.md` (índice, regras, fluxo,
  emergência) + `memoria.md` (decisões e lições) + `docs/pendencias.md` (estado volátil) + `docs/decisoes/` (ADR só
  para decisão nova com trade-off) + `docs/{arquitetura, estrategias, operacao, resultado_financeiro}.md` +
  `docs/historico/` (evidência, sem edição) + `.agent-work/` (journal local de tarefa) + memória do agente (preferências
  do usuário, fora do repo; trecho AJUSTADO pelo D-041) + `.gitignore`. `docs/decisoes/D-038-estrutura-documentacao.md`
- **D-041 (2026-10-21)** **Preferências de trabalho do usuário no `CLAUDE.md`** (bloco "Como trabalhar com o usuário"),
  em texto neutro, para irem junto com o repositório em qualquer máquina. O repositório é **público** (conferido em
  2026-10-21): nada pessoal ou sensível em arquivo versionado. A memória local do agente fica só para o que não for
  regra de trabalho. Ajusta o item 7 do D-038.
- **D-032 (2026-10-15)** **O cron de acumulação do PAXG no servidor permanece ATIVO**, por decisão explícita do
  usuário: deve continuar comprando PAXG quando o RSI 4h ficar abaixo de 30 (`server/paxg_rsi_check.php`, crontab do
  `ineocom`, de hora em hora). É uma exceção ao D-012: essa compra fica fora do bot (sem `positions.jsonl`, sem OCO
  guard, sem trava de concentração, sem alerta próprio no Telegram) e o usuário aceita esse risco. Parâmetros
  conforme a documentação do cron (confirmar no servidor, pois `gerar_teste_paxg.php` não está no repositório):
  RSI 14 em 4h, limiar < 30, cooldown 12 h, US$ 10 por compra, SL −15%, sem TP.
  Para pausar: `touch .paxg_pause` no servidor (`docs/operacao.md`, seção 4).
- **D-031** Toda feature nova tem kill-switch booleano e rollback de 1 linha; mudanças aditivas; imports opcionais
  com degradação segura.

---

## Decisões rejeitadas
- **R-001** "Usar OCO nativo da Gate.io": **não existe** no spot. (2026-07-27)
- **R-002** Subir o teto para US$ 20: reprovado em 23/08, 16/09 e 08/10 (P&L e PF negativos).
- **R-003** Reaproveitar trades de configuração antiga para justificar o degrau. Só conta o regime atual.
- **R-004** Stop global 3,0×ATR (piora o D1); resolvido com override só para o HYPE (D-021). (2026-08-23)
- **R-005** Reentrar ETH, XRP, LINK, AAVE no Maré Alta; XRP, AAVE e BTC no breakout; MACD-only nos majors
  (reprovados em backtest/OOS). `historico/backtest_2026-06-validacao-oos.md`, `historico/backtest_2026-07-mare-alta-d1.md`
- **R-006** Exceção no executor para PAXG comprar sem TP/SL; optou-se por remover o PAXG. (2026-09-04)
- **R-007** Automatizar o OCO de ordens manuais (exigiria cancelar ordens que o bot não criou). (2026-09-16)
- **R-008** Religar o HYPE só porque o bloqueio acidental sumiu. (2026-10-13)

---

## Problemas e lições
Formato: problema → causa → regra que ficou.

- **P-01 (07/10)** TP/SL "fantasma" → em MARKET BUY o `amount` da Gate vem em **quote**; gatilhos vendiam ~4,99 ETH.
  Regra: base = `filled_total / fill_price`; HTTP 201 na criação **não** prova proteção (FIX 7).
- **P-02 (06/30)** Gatilhos sumiam após 24h → `expiration` 86400. Hoje 30 dias (2592000); o SL é renovado (D-033).
- **P-03 (06/30)** Cron PHP falhava com HTTP 500 → `/usr/bin/php` é CGI. Regra: em crontab use `/usr/local/bin/php`.
- **P-04 (07/27)** "O SL sumiu" era falso → a tela do app mostra só ordens **abertas**. Regra: consultar
  `GET /spot/price_orders/{id}` e `/spot/my_trades` antes de afirmar que algo sumiu.
- **P-05 (07/26)** YAML inválido no `main.yml` parou o bot; `EXECUTION_DRY_RUN` divergia do `$DRY_RUN` do PHP (o PHP
  ignora a flag do payload). Regra: conferir os dois lados. `historico/auditoria_2026-07-26.md`
- **P-06 (08/20)** Typo `'sspot'` no servidor recusou todas as compras por 9 dias → **fix commitado ≠ fix deployado**;
  o `execute.php` tem histórico de corrupção de bytes. Regra: conferir bytes/hash e varrer typos após cada deploy.
  Para medir alcance, usar `state/orders_executed.csv`, não o log rotacionado do servidor.
  `historico/incidente_2026-08-20-sspot-deploy.md`
- **P-07 (08/23)** Contador incremental de posições travava compras → derivar sempre de `positions.jsonl`.
- **P-08 (08/24)** Watchlist com dupla fonte deixou o PAXG como código morto. Regra: ao validar escrita em `state/`,
  conferir `_updated_at_utc` antes de concluir (leitura velha ≠ sobrescrita).
- **P-09 (09/14→10/09)** Token expirado derrubou a cadência por 24 dias sem alerta → `curl -s` retorna 0 com HTTP 401.
  Regra: **run verde ≠ passo funcionou**; conferir código HTTP e falhar alto.
- **P-10 (08/23→10/11)** Registro legado com status `open*` bloqueou 17 sinais do HYPE via trava de concentração.
  Regra: reconciliar `positions.jsonl` com a exchange; registro obsoleto bloqueia em silêncio.
- **P-11 (10/08)** Trailing usava a vela D1 em formação; stops subiam com picos intradia (BTC teria sobrevivido) → D-026.
- **P-12 (10/15)** A saída executada divergia da saída validada no backtest → D-027. Regra: conferir que a execução
  real é a estratégia que foi testada.
- **P-13 (08/23)** `grep -c` contou linhas, não ocorrências, e gerou alarme falso. Regra: comandos de verificação
  também precisam ser verificados com evidência independente.
- **P-14 (10/15)** Logado como `root` no servidor, `~` é `/root`. Regra: usar caminhos absolutos
  (`/home/ineocom/...`) e `chown ineocom:ineocom` em arquivo criado como root.
- **P-15 (07/24)** Um commit sobrescreveu o diário `docs/strategy_decisions.md` (hoje `historico/strategy_decisions_2026-05a06.md`) com uma linha de lixo (413 linhas perdidas;
  restaurado em 10/13). Regra: revisar o diff de docs antes de commitar.
- **P-16 (10/15)** O cron PAXG decidia comprar (RSI < 30), mas toda compra falhava com HTTP 500 → o crontab chama
  `/usr/local/bin/php`, porém o script interno roda o comprador com `exec('php …')`, que no PATH do cron é o CGI.
  O log tinha 1 compra OK e 308 linhas FALHA (cada falha gera 2 linhas), sem nenhum alerta. Fix: `$PHP_BIN` absoluto em `paxg_rsi_check.php`.
  Regra: P-03 vale também para `exec()` dentro do PHP; cron que falha precisa avisar alto.
- **P-17 (10/15)** O cron do GitHub é muito irregular: o `commander.yml` (`*/2`) rodou 6 vezes em 15/10, com intervalos
  de 3 a 5,5 h. Regra: **comandos do Telegram (`/pausar` etc.) podem levar horas**; para parar rápido, desabilitar o
  `main.yml` no GitHub. Nada que precise de prazo pode depender do cron do GitHub.
- **P-18 (10/09→10/20)** O cron do servidor chamava `/home/ineocom/Cryptosignas/trigger_scan.sh` (pasta com typo,
  inexistente) e falhou em silêncio, provavelmente desde a troca do token em 2026-10-09; a cadência dependia só da corrente do `main.yml`, que parou 80 min
  com um HTTP 500 do GitHub em 2026-10-19 23:30 UTC. O script real também não checava HTTP e tinha token de junho.
  Regra: todo script de servidor fica versionado no repo, confere o código HTTP e avisa quando falha; ao mexer no
  crontab, conferir que o caminho existe (`ls -la <caminho>`) antes de salvar.
- **P-20 (10/21)** Teste de contenção do D-042 abriu ~9 conexões SSH em segundos e o servidor bloqueou a porta 22
  para o IP do Mac por ~1 min (proteção de excesso de conexões; web, cPanel e relay seguiram no ar). Regra: espaçar as
  chamadas ao `cryptosignals-gate` (no máximo algumas por minuto) e preferir menos conexões.
- **P-19 (10/20)** A pasta pública do servidor expunha pela web scripts que compram de verdade (`gerar_teste_paxg.php`,
  sem trava de terminal: `foreach ($argv …)` só gera aviso e segue) e os logs de ordens. Sem evidência de acesso
  (logs de acesso não conferidos de forma conclusiva). Revisão em 2026-10-21: o `error_log` mostra o script morrendo
  na linha 103 (`STDERR` indefinido) quando roda fora do terminal, antes de enviar a ordem; pela web a compra
  provavelmente falharia (não testado). Os logs estavam expostos de fato. Regra: na web root só o que precisa ser acessível; script de
  servidor tem `PHP_SAPI === 'cli'` e fica fora de `public_html` sempre que possível → D-040.
