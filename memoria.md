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
- **D-006 (2026-06-19)** **Compra sem TP/SL é recusada** (`REQUIRE_PROTECTION` no PHP; exceção só para o DCA, D-049) e o stop tem piso de
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
  `paxg_rsi_check.php` ficou ativo pelo D-032, depois substituído pelo DCA (D-049). `historico/paxg_removido_2026-09-04.md`
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
  TRX, BNB, HYPE e PAXG (este hoje pelo DCA, D-049); saem ETH, XRP, LINK e AAVE (D-010, R-005).
  `tests/test_whitelist_php.py` falha se a whitelist divergir de `WATCHLIST ∪ MARE_ALTA_UNIVERSE ∪ {PAXG}`.
  Deployada em 2026-10-15 (commit `8298f20d`, sha256 `4ec3b375…`, HTTP 401 conferido; backup `execute.php.bak-20261015b`).
- **D-037 (2026-10-15)** **Watchdog externo no servidor** (`server/watchdog_scan.php`, crontab do `ineocom`, de hora em
  hora): lê `state/runtime_config.json` do `main` e alerta no Telegram se `last_scan_utc` passar de 60 min (DND: +30;
  limite e frequência AJUSTADOS pelo D-044),
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
  Fonte versionada: `server/cryptosignals.htaccess`. O `gerar_teste_trx.php` (compra manual de TRX de 2026-06, sem uso)
  sai da pasta pública para `/home/ineocom/cryptosignals/arquivo/` (decisão do usuário; feito e conferido em 2026-10-21).
  Os backups antigos da pasta também foram para lá; ficam só os 3 de rollback recentes (relay, cron PAXG, watchdog).
- **D-042 (2026-10-21)** **Agente acessa o servidor só por SSH restrito e só leitura**: chave gerada no Mac do usuário,
  autorizada no `ineocom` com `restrict,command=` apontando para `server/agent_gate.php` (menu fixo: `help`, `status`,
  `hashes`, `crontab`, `env-keys`, `http`; saída com máscara de segredos; log de cada chamada). Nunca como `root`.
  Deploy, crontab e `.env` continuam com o usuário. `docs/decisoes/D-042-acesso-do-agente-ao-servidor.md`
  Instalado em 2026-10-21 (sha256 `58516b29…`; host key do servidor `SHA256:YcHODEy6…daf8` conferida dos dois lados).
  Contenção testada: pedidos fora do menu, `-tt`, `scp` e túnel recusados.
- **D-043 (2026-10-21)** **Re-disparo do `main.yml` com novas tentativas**: até 3 (`REARM_ATTEMPTS`), esperando 30 s e
  60 s, só para erro passageiro (5xx, 429, sem resposta); 401/403/404/422 falham na hora. Um HTTP 500 único tinha
  parado a corrente em 2026-10-19 (P-18). O `checks` passa a validar o YAML e o `bash -n` de todos os workflows
  (`scripts/check_workflows.py`, P-05). Rollback: `REARM_ATTEMPTS: "1"`.
- **D-044 (2026-10-21)** **Watchdog externo mais rápido** (ajusta o D-037): limite 30 min (era 60) e crontab a cada
  15 min (era de hora em hora). Parada avisada em 30 a 45 min (antes, até ~2 h). Rollback: `max_gap_min` 60 e
  `30 * * * *`. Instalado em 2026-10-21 (sha256 `a9d73ea8…`); 1ª execução a cada 15 min às 02:15 UTC, `limite=30min`.
- **D-045 (2026-10-21)** **Porteiro com `resumo`** (ajuste do D-042): `status` + `hashes` + `http` numa conexão só (P-20),
  e o `status` passa a mostrar o `agent_gate.log` e a lista de arquivos da pasta pública (vigiar arquivo estranho, P-19).
  Continua só leitura. Instalado em 2026-10-21 (sha256 `6c0fc576…`), conferido pelo próprio `resumo`.
  Atualizado em 2026-10-26 (sha256 `50bc78a1…`): `hashes` sem os scripts do PAXG, arquivados (`docs/operacao.md`, seção 11).
- **D-046 (2026-10-21)** **Telegram só com eventos + comandos no scan** (Fases 0 e 1 do plano de mensagens): desliga o
  resumo a cada scan (`SCAN_SUMMARY_ENABLED`; eram ~288 msgs/dia com diagnóstico de MACD de estratégias removidas) e o
  paper trading (`PAPER_EVAL_ENABLED`, D-028); o resumo diário e o `/status` mostram estratégias ligadas/desligadas,
  posições e a trava real (D-035); `/add` e `/rm` respondem que a watchlist vem do `config.py` (D-004). Os comandos
  passam a ser lidos no início de cada scan (`TELEGRAM_COMMANDS_IN_SCAN`, ~5 min) e o `commander.yml` fica só manual.
- **D-047 (2026-10-23)** **"Maré Alta D1" passa a se chamar "Tendência Diária"** no que o usuário lê (Telegram e docs
  novos). O id interno continua `MARE_ALTA_D1` (executor do TP1, placar, `positions.jsonl`, testes); o módulo e as flags
  `MARE_ALTA_*` também ficam. Decisões e históricos antigos seguem citando "Maré Alta" (mesma estratégia). Outros nomes
  exibidos: "Rompimento 1h" (breakout), "Acúmulo na Queda" (RSI).
- **D-048 (2026-10-23)** **Acúmulo por RSI não aprovado e range trading arquivado**, pelos backtests com dados reais
  (2 anos; PAXG 581 dias). Acúmulo RSI 4h < 30 x DCA semanal: custo médio BTC −3,1% / −2,6% / +0,1% (inteiro / 1ª / 2ª
  metade), PAXG +2,9% / −0,3% / −2,6%: sem vantagem consistente, e até 78 dias sem comprar. O stop de −15% vendeu
  72 de 90 lotes de BTC (retorno −7,4% contra −2,2% sem stop). Range (só compra, ADX D1 < 20): 7 a 14 trades por
  ativo, nenhum com amostra mínima e saldo somado fora da amostra negativo (−13,2%; PAXG 5 stops em 6). Não
  implementar nenhum dos dois; não afrouxar regras para "fazer passar" (R-003, P-12). Se o usuário quiser acumular,
  o caminho é um DCA simples, com a decisão de proteção (D-006/R-006) ainda em aberto. O cron do PAXG (D-032), que é
  esse RSI com stop −15%, rendeu −2,2% no período contra +0,4% do DCA: rever com o usuário.
  `docs/backtests/acumulo_20261023.md`, `docs/backtests/range_20261023.md`
- **D-049 (2026-10-23)** **DCA semanal sem stop em BTC e PAXG** (US$ 10/semana cada, segunda 13:00 UTC; teto
  mensal US$ 50 por ativo). Substitui o D-032 (cron do PAXG, pausado já) e abre exceção ao D-006/R-006 só para
  `strategy == "DCA"` (relay FIX 11, `$DCA_NO_PROTECTION`). O DCA fica em `state/dca.jsonl`, fora do
  `positions.jsonl`: não conta na trava de posição viva (D-022) nem no trailing/OCO; convive com a Tendência Diária
  no BTC. Uma tentativa por semana, sem compra dobrada. FIX 11 deployado em 2026-10-23 (sha256 `945b2015…`, backup
  `execute.php.bak-20261023`) e `DCA_ENABLED` ligado em seguida; cron do PAXG pausado (`.paxg_pause`). 1ª compra em
  2026-10-26 (BTC e PAXG `filled`); o PAXG compra em passos de 0,001 PAXG da Gate, então o aporte fica abaixo de
  US$ 10 (hoje ~80%; pode cair mais com o preço menor). Em 2026-10-26 a linha do cron do PAXG saiu do crontab e `paxg_rsi_check.php` e
  `gerar_teste_paxg.php` foram arquivados em `/home/ineocom/cryptosignals/arquivo/` (`docs/operacao.md`, seção 4).
  `docs/decisoes/D-049-dca-semanal.md`
- **D-050 (2026-10-23)** **Fill real da saída e renovação do TP1** (relay FIX 12). (a) O `oco_sync` devolve o fill real
  da ordem disparada (`GET /spot/orders/{fired_order_id}`; usar `avg_deal_price`, pois o `fill_price` dessa resposta é o
  total em USDT); o `oco_guard` grava o P&L com ele (`exit_basis: fill_real`) e cai na estimativa se faltar
  (`$FILL_LOOKUP`). (b) Ação `renew_tp`: TP1 com 25 dias ou mais é renovado no mesmo preço e qty, só se estiver `open`,
  **apagando o antigo antes de criar o novo** (os dois vivos poderiam disparar juntos e vender saldo do DCA ou manual);
  se apagar e não criar, fica `tp_renew_pending` e o scan seguinte cria (`TP_RENEW_ENABLED`, ligar após o deploy).
  Conferido na Gate em 2026-10-23: gatilho executado = `finish`; a ordem de 15 dias atrás ainda é consultável.
  FIX 12 deployado em 2026-10-23 (sha256 `809cb3cc…`, backup `execute.php.bak-20261023b` = FIX 11) e
  `TP_RENEW_ENABLED` ligado em seguida.
- **D-028 (2026-10-13)** As posições-papel XRP (23/08) e PAXG (28/08) em `state/paper_positions.json` são
  **obsoletas e ignoradas** (não são ordens reais).

### Processo e documentação
- **D-038 (2026-10-19)** Estrutura de documentação (substitui o D-030): `CLAUDE.md` (índice, regras, fluxo,
  emergência) + `memoria.md` (decisões e lições) + `docs/pendencias.md` (estado volátil) + `docs/decisoes/` (ADR só
  para decisão nova com trade-off) + `docs/{arquitetura, estrategias, operacao, resultado_financeiro}.md` +
  `docs/historico/` (evidência, sem edição) + `.agent-work/` (journal local de tarefa; AJUSTADO pelo D-051: o estado
  vai para `pendencias.md`) + memória do agente (preferências do usuário, fora do repo; trecho AJUSTADO pelo D-041) +
  `.gitignore`. `docs/decisoes/D-038-estrutura-documentacao.md`
- **D-041 (2026-10-21)** **Preferências de trabalho do usuário no `CLAUDE.md`** (bloco "Como trabalhar com o usuário"),
  em texto neutro, para irem junto com o repositório em qualquer máquina. O repositório é **público** (conferido em
  2026-10-21): nada pessoal ou sensível em arquivo versionado. A memória local do agente fica só para o que não for
  regra de trabalho. Ajusta o item 7 do D-038.
- **D-051 (2026-10-27)** **Claude Code na nuvem sem segredos**: rede Trusted, sem variáveis nem network secrets, sem
  acesso ao servidor (D-042 intacto). Mudança relevante vai por PR com merge do usuário; o estado de tarefa entre
  sessões vai para `pendencias.md` ou para o PR (ajusta o journal do D-038). `CLOUD_SETUP.md`, `docs/decisoes/D-051-claude-code-na-nuvem.md`
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
- **R-006** Exceção no executor para PAXG comprar sem TP/SL; optou-se por remover o PAXG. (2026-09-04) Revertido
  em 2026-10-23 só para compras DCA (D-049).
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
  `main.yml` no GitHub. Nada que precise de prazo pode depender do cron do GitHub. (Comandos: resolvido pelo D-046.)
- **P-18 (10/09→10/20)** O cron do servidor chamava `/home/ineocom/Cryptosignas/trigger_scan.sh` (pasta com typo,
  inexistente) e falhou em silêncio, provavelmente desde a troca do token em 2026-10-09; a cadência dependia só da corrente do `main.yml`, que parou 80 min
  com um HTTP 500 do GitHub em 2026-10-19 23:30 UTC. O script real também não checava HTTP e tinha token de junho.
  Regra: todo script de servidor fica versionado no repo, confere o código HTTP e avisa quando falha; ao mexer no
  crontab, conferir que o caminho existe (`ls -la <caminho>`) antes de salvar.
- **P-21 (10/23)** Os relatórios dos backtests não foram gravados: um único `git add` com um caminho inexistente
  (`docs/backtest_report.md`) faz o Git cancelar o comando inteiro, e o `2>/dev/null || true` escondeu o erro.
  Regra: um `git add` por caminho, conferindo se existe; não silenciar erro de passo que precisa funcionar.
- **P-20 (10/21)** Teste de contenção do D-042 abriu ~9 conexões SSH em segundos e o servidor bloqueou a porta 22
  para o IP do Mac por ~1 min (proteção de excesso de conexões; web, cPanel e relay seguiram no ar). Regra: espaçar as
  chamadas ao `cryptosignals-gate` (no máximo algumas por minuto) e preferir menos conexões.
- **P-19 (10/20)** A pasta pública do servidor expunha pela web scripts que compram de verdade (`gerar_teste_paxg.php`,
  sem trava de terminal: `foreach ($argv …)` só gera aviso e segue) e os logs de ordens. Sem evidência de acesso
  (logs de acesso não conferidos de forma conclusiva). Revisão em 2026-10-21: o `error_log` mostra o script morrendo
  na linha 103 (`STDERR` indefinido) quando roda fora do terminal, antes de enviar a ordem; pela web a compra
  provavelmente falharia (não testado). Os logs estavam expostos de fato. Logs de acesso (2026-10-21): o Apache
  guarda só outubro/2026 (`/var/log/apache2/domlogs/` + `/home/ineocom/logs/*-Oct-2026.gz`); nesse período, nenhum
  acesso externo a `gerar_teste_*` nem aos logs do bot, só os testes feitos do próprio servidor. Jun a set: sem log. Regra: na web root só o que precisa ser acessível; script de
  servidor tem `PHP_SAPI === 'cli'` e fica fora de `public_html` sempre que possível → D-040.
