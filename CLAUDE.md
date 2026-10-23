# CLAUDE.md — crypto-signal-bot

Bot de sinais e **execução real** de cripto spot na Gate.io (só compra), rodando no GitHub Actions, com relay PHP
num servidor cPanel. Dono: Nélio Castro. Fuso: **America/Bahia (UTC−3)**. Responda em **português do Brasil**.

> ⚠️ **Opera com DINHEIRO REAL.** Qualquer mudança que toque ordem, stop, TP, sizing ou o relay exige kill-switch,
> rollback de 1 linha, testes e aprovação explícita do usuário.

## Memória e documentos
@memoria.md

| Documento | Quando ler |
|---|---|
| `memoria.md` | sempre (carregado acima): decisões D-/R- (o porquê) e lições P- |
| `docs/pendencias.md` | início de toda sessão: o que falta fazer e o que acompanhar (estado volátil) |
| `docs/decisoes/` | ADR de decisão nova com trade-off (`TEMPLATE.md`); o resumo e o índice ficam no `memoria.md` |
| `docs/arquitetura.md` | stack, módulos, relay, cadência, workflows, `state/`, servidor, limites da Gate.io |
| `docs/estrategias.md` | o que cada ativo opera, cenários QUANDO/ENTÃO com o teste de cada um, kill-switches, parâmetros |
| `docs/operacao.md` | runbooks: auditoria, deploy do relay, token, cron PAXG, reconciliação, watchdog |
| `docs/resultado_financeiro.md` | placar real (datado); `python scripts/placar.py` gera o atual |
| `docs/historico/` | evidência original das decisões; não editar, só consultar |
| `.agent-work/<tarefa>.md` | journal local (fora do Git) de tarefa em andamento; ler ao retomar |

**Autoridade:** valores = código (`bot/config.py` é a fonte única). Porquês = decisões aprovadas e datadas no
`memoria.md`, que prevalecem sobre os outros docs. Os docs descrevem. Se código, memória e docs divergirem,
**pare e avise**: não escolha um lado sozinho.

## Regras de trabalho
1. **Se algum pedido meu contradisser uma decisão registrada em @memoria.md ou qualquer outro doc relevante, pare e
   me avise antes de realizar qualquer alteração. Explique qual decisão seria afetada e pergunte se desejo
   substituí-la.**
2. Antes de qualquer alteração relevante, releia as seções **Decisões aprovadas** e **Decisões rejeitadas** do
   `memoria.md`.
3. Não altere a stack técnica sem minha autorização (`docs/arquitetura.md`).
4. Não remova uma decisão aprovada silenciosamente: marque como substituída e arquive.
5. Não invente informações técnicas sobre o projeto. Verifique o repositório real e o código antes de afirmar;
   diga o que não conseguiu verificar.
6. Antes de uma mudança grande, apresente um plano resumido.
7. Depois de uma decisão importante aprovada, atualize o `memoria.md` (e o doc técnico afetado) no mesmo commit.

## Fluxo de trabalho
1. Ler `docs/pendencias.md` e, se houver, o journal da tarefa em `.agent-work/`.
2. Mudança relevante: plano resumido → aprovação do usuário → implementação.
3. Rodar os checks abaixo e **mostrar o diff antes de commitar**; commitar só com aprovação.
4. Commit **só dos arquivos listados** (`git -c core.fileMode=false add <arquivos>`: o SSD é exFAT e marca tudo como
   modificado), mensagem em português, direto no `main`; `pull --rebase` antes do push (o bot commita `state/` sem
   parar); depois do push, conferir o workflow `checks`.
5. Mudança no servidor: roteiro com o SHA do commit **já preenchido**, conferência de bytes e hash, backup antes,
   `chown ineocom:ineocom`, e só então registrar o deploy em `operacao.md`/`memoria.md`.
6. Tarefa que atravessa sessões ou espera o usuário agir no servidor: abrir `.agent-work/<tarefa>.md` com objetivo,
   feito, próximo passo e bloqueios; ao concluir, levar o que precisa durar para o doc certo e apagar o journal.
7. Fim da sessão: atualizar `docs/pendencias.md`.

## Como trabalhar com o usuário
- Quem muda o servidor é o usuário (como `root`), colando a saída no chat. O agente **só lê**, e só por
  `ssh cryptosignals-gate <ação>` (D-042/D-045: `help`, `status`, `hashes`, `crontab`, `env-keys`, `http`, `resumo`;
  prefira `resumo`, que junta as conferências numa conexão só, P-20). Conferência que o
  porteiro cobre, o agente faz sozinho em vez de pedir ao usuário.
- Comando de servidor: um bloco por passo, com valores **já preenchidos** (SHA, sha256, bytes, caminhos absolutos),
  o resultado esperado e o rollback. Nunca deixar placeholder (`<SHA>`, `<token>`) num comando executável.
- Todo comando para o servidor vem dentro da trava de hostname, para não rodar no Mac por engano (o `!` do Claude
  Code executa no Mac):
  `if hostname | grep -q '^dedi-15131000'; then <comandos>; else echo "PARE: comando do SERVIDOR."; fi`
- Conferir a saída de cada passo contra o esperado antes de passar o próximo.
- Crontab: gerar o arquivo novo, mostrar o `diff` e instalar com `crontab -u ineocom <arquivo>`, com backup. Se for
  preciso usar o vi, dar a instrução tecla a tecla, incluindo como sair sem salvar.
- Segredo: o usuário edita com `nano`; para conferir, mostrar só nomes de chaves ou tamanho, nunca o valor.
- Aprovação vale para uma etapa só (plano, implementação, commit, deploy).
- Avaliações e propostas: críticas e sugestões numeradas por prioridade, cada uma com recomendação explícita
  (adotar / adotar em parte / não adotar) e o motivo.

## Emergência: parar o bot já
- **Scan e ordens novas:** GitHub → Actions → `main.yml` → *Disable workflow* (imediato). O `/pausar` do Telegram
  vale no próximo scan, ~5 min (D-046). Stops e TPs já criados seguem ativos na Gate.
- **Cron PAXG:** `touch /home/ineocom/public_html/cryptosignals/.paxg_pause`.
- **Trigger do servidor:** `touch /home/ineocom/cryptosignals/bin/.trigger_pause` (senão ele alerta falhas de disparo
  enquanto o `main.yml` estiver desligado).
- **Watchdog:** `touch /home/ineocom/public_html/cryptosignals/.watchdog_pause`.
- **Relay:** restaurar o backup do `execute.php` (`docs/operacao.md`, seção 2).
- **Acesso do agente:** apagar a linha `agente-cryptosignals-leitura` do `/home/ineocom/.ssh/authorized_keys`.

## Regras de engenharia
- Mudanças **aditivas**; não renomeie símbolos existentes; mantenha aliases (`SYMBOLS = WATCHLIST`,
  `evaluate = evaluate_signal`).
- Toda feature nova tem **kill-switch booleano** e rollback de 1 linha. Imports opcionais com `try/except`:
  uma feature nova nunca derruba o scan.
- Antes de commitar: `python -m py_compile bot/*.py`, `python tests/test_roteamento_strings.py`,
  `python tests/test_saida_tp1.py`, `python tests/test_renovacao_sl.py`, `python tests/test_placar.py`,
  `python tests/test_trava_perda_diaria.py`, `python tests/test_whitelist_php.py`, `python tests/test_telegram_mensagens.py`,
  `python tests/test_backtests.py`, `python tests/test_dca.py`,
  `php tests/test_watchdog_scan.php`, `php tests/test_trigger_scan.php`, `php tests/test_agent_gate.php` (se houver PHP local);
  mexeu em workflow: `python scripts/check_workflows.py` (precisa de PyYAML; o `checks` roda). O workflow `checks` roda `php -l` no relay e os testes no GitHub.
- `server/execute.php` exige **deploy manual** conferido por bytes e hash (`docs/operacao.md`). Flag que dependa do
  PHP só se liga depois do deploy.
- Mensagens de commit em português; o `.gitignore` cobre `__pycache__`, `._*` e segredos: não force a inclusão.

## Proibido sem aprovação explícita
- Alterar `EXECUTION_*`, stops, TP/SL, sizing ou `server/execute.php`.
- Subir o degrau de capital (hoje US$ 10/ordem) fora da regra D-024.
- Propor ou implementar SHORT (D-002).
- Reativar estratégia desligada ou mudar a watchlist fora de `bot/config.py`.
- Dar ao bot poder de cancelar ordens que ele não criou (D-025).
- Colar token, secret ou HMAC em chat, log, print ou commit.
- Acessar o servidor de outro jeito que não o `ssh cryptosignals-gate`, ou pedir acesso como `root` ou sem restrição (D-042).

## Para lembrar sempre
- Run verde ≠ passo funcionou. Fix commitado ≠ fix deployado. Tela do app ≠ status real da ordem (use a API).
- Qualquer registro com status `open*` em `state/positions.jsonl` conta como posição viva.
- No servidor, use caminhos absolutos (`/home/ineocom/...`); logado como root, `~` é `/root`.
- **O repositório é público:** nada pessoal ou sensível em arquivo versionado (D-041).
