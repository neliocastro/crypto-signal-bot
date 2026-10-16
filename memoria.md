# Memória do projeto — crypto-signal-bot

Histórico vivo de decisões e aprendizados. Só o que ajuda a continuidade, sem conversas e sem estado volátil
(P&L, posições e contagens ficam em `state/` e `docs/resultado_financeiro.md`).

**Convenções**
- IDs fixos: `D-` decisão aprovada, `R-` rejeitada, `P-` problema/lição. Nunca reutilize um ID.
- Decisão não se apaga: quando mudar, marque `SUBSTITUÍDA por D-0xx` e mova-a para `docs/memoria-arquivo.md`.
- Evidência detalhada (números, fills, IDs de ordem) fica em `docs/historico/`, citada no fim de cada item.
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
  (escolha do usuário). Vive em dois lugares (secret do GitHub + crontab do servidor). O `main.yml` falha
  (exit 1) se o re-disparo não devolver HTTP 204. `historico/incidente_2026-10-08_stops_e_cadencia.md`

### Estratégias e universo
- **D-010 (2026-08-23)** Universo do **Maré Alta D1 = BTC, SOL, TRX, BNB**. ETH e XRP saíram (PF 0,43 e 0,55 no
  backtest fiel). `historico/decisao_stop_e_universo_2026-08-23.md`
- **D-011 (2026-08-24)** MACD-only, Integrada, Tendência MACD e Confluência **removidas do código**.
  `historico/limpeza_estrategias_2026-08-24.md`
- **D-012 (2026-09-04)** **PAXG fora da watchlist**, `ACCUMULATION_ENABLED = False` (lado Python). O cron do servidor
  `paxg_rsi_check.php` continua ativo: ver pendências. `historico/paxg_removido_2026-09-04.md`
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
  Vale no servidor só após o deploy conferido por hash (`docs/operacao.md`, seção 2).
- **D-028 (2026-10-13)** As posições-papel XRP (23/08) e PAXG (28/08) em `state/paper_positions.json` são
  **obsoletas e ignoradas** (não são ordens reais).

### Processo e documentação
- **D-030 (2026-10-15)** Estrutura de documentação: `CLAUDE.md` (regras) + `memoria.md` (este arquivo) +
  `docs/{arquitetura, estrategias, operacao, resultado_financeiro}.md` + `docs/historico/` (evidência, sem edição).
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
- **P-02 (06/30)** Gatilhos sumiam após 24h → `expiration` 86400. Hoje 30 dias (2592000); ainda expiram (pendência).
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

---

## Pendências
- **Cron PAXG no servidor: decidido manter (D-032).** Confirmado no servidor em 2026-10-15 (`gerar_teste_paxg.php`,
  sha256 `df762466…`): US$ 10, SL −15%, sem TP, `signal_id` único por compra. As compras falhavam (P-16); o fix
  foi deployado em 2026-10-15 (commit `8dc5668a`, sha256 `0e3624f6…`, backup `paxg_rsi_check.php.bak-20261015`),
  mas ainda falta ver o primeiro `COMPRA OK` no log e o SL na Gate. Ainda em aberto: registrar essas compras em
  `positions.jsonl` (2026-10-15: o usuário manteve o D-032 por enquanto; se mudar, o trailing precisa pular o PAXG,
  pois `MARE_ALTA_SYMBOLS = []` trocaria o SL −15% por `close − 3×ATR`) e alertar no Telegram quando o cron falhar. A whitelist do PHP **precisa** manter
  PAXG enquanto o D-032 valer.
- **Gatilhos expiram em 30 dias**: o SL passou a ser renovado (D-033). Falta: renovar o TP1 (ação nova no PHP +
  deploy) e confirmar na API da Gate o nome do status de gatilho expirado (o alerta cobre `expired/cancelled/failed`).
- **Placar**: resolvido por estimativa (D-034). Falta o fill real da saída (o `oco_sync` do PHP consultar a ordem
  executada; exige deploy). A trava de perda diária foi ligada em D-035.
- **Próxima reauditoria do degrau**: `python scripts/placar.py --degrau` já marca `cadencia_degradada` (abertos entre
  2026-09-14 21:13 e 2026-10-09 01:02 UTC) e reporta com e sem eles. Em 2026-10-15: 6/20 trades (−US$ 2,41, PF 0);
  sem os degradados, 3/20 (−US$ 1,15, PF 0). Reprovado nos dois recortes; reauditar ao chegar a 20.
- **Whitelist do PHP**: corrigida no Git (D-036); falta o **deploy manual** do `execute.php` conferido por hash.
- **Tabelas de precisão de fallback divergem** entre PHP (`$SAFE_PRICE_PREC`: TRX 4, HYPE 2) e Python
  (`_SAFE_PRICE_PREC`: TRX 5, HYPE 3). Só valem se `/spot/currency_pairs` falhar; conferir na Gate e alinhar.
- **Watchdog** (`bot/watchdog.py`) só alerta quando um scan volta a rodar; não cobre parada total de disparos.
- **BTC manual do usuário** (0,0031756 BTC) sem ordens de proteção desde 21/09: decisão do usuário.

## Próximos passos
1. Decidir o cron PAXG.
2. Acompanhar a primeira compra com TP1 parcial (mensagens "TP1 parcial NAO aplicado" ou "🎯 TP1" no Telegram).
3. Revisar estratégia só com amostra limpa (pós-2026-10-09): Maré Alta 0/6 desde 04/09, parte em cadência degradada.
