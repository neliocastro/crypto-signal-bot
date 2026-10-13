# CLAUDE.md — crypto-signal-bot

Bot de sinais e **execução real** de cripto spot na Gate.io (só compra/LONG), rodando no GitHub Actions.
Dono: Nélio Castro. Fuso: **America/Bahia (UTC-3)**. Responda em **português do Brasil**.

> ⚠️ **O bot opera com DINHEIRO REAL** (`EXECUTION_DRY_RUN = False`). Qualquer mudança que
> toque ordem, stop, sizing ou o relay exige kill-switch, rollback de 1 linha e aprovação do usuário.

## O que este arquivo NÃO contém (de propósito)
P&L, número de trades, posições abertas e pendências mudam a cada scan. **Não confie em memória nem
neste arquivo para o estado atual.** Leia sempre:
- `state/positions.jsonl` — fonte da verdade das posições do bot
- `state/paper_trades.jsonl` — ordens enviadas e bloqueios de guarda
- `docs/estado_atual.md`, `docs/resultado_financeiro.md` — estado consolidado (datados)
- `docs/README.md` — índice: o que é doc vivo, registro datado ou superado
- `bot/config.py` — **fonte única de verdade** de watchlist, kill-switches e execução

## Arquitetura (cérebro / braço)
- **Cérebro:** Python no GitHub Actions (`bot/`). Escaneia, decide, calcula sizing e **assina com HMAC**.
  Persiste estado em `state/` e commita a cada scan (`chore: update signal state + dashboard [skip ci]`).
- **Braço:** `server/execute.php` num servidor cPanel com IP fixo. Valida HMAC + whitelist de IP,
  roda sanity checks e envia para a Gate.io API v4. Log em `execution_log.jsonl` (**UTC**).
- **Roteamento "1 token = 1 trilho":** cada ativo tem uma só estratégia que executa. Maré Alta D1
  (`bot/mare_alta.py`) para BTC/SOL/TRX/BNB; Breakout 1h (`bot/strategies.py`) para HYPE.
  **Desde 13/10 o Breakout está desligado** (`BREAKOUT_ENABLED = False`): o HYPE é escaneado mas não opera.
  O filtro de `bot/main.py` casa por string exata da estratégia: o teste canário protege isso.
- **OCO emulado:** a Gate.io spot não tem OCO nativo. TP e SL são ordens independentes e o
  `bot/oco_guard.py` reconcilia os pares. Só cobre ordens **criadas pelo bot**.
- **Cadência:** cron do servidor + self-chain do `main.yml` (ambos dependem do secret
  `SELF_DISPATCH_PAT`) + cron `*/15` do GitHub (best-effort, na prática 4-5×/dia).

## Comandos
```bash
pip install -r requirements.txt
python tests/test_roteamento_strings.py      # canário de roteamento (sem pytest); exit 0 = ok
python -m py_compile bot/*.py                # antes de TODO commit
python -c "import bot.main"                  # teste de import
```
Backtests em `scripts/` (sob demanda; ver também `.github/workflows/backtest.yml`).

## Regras de engenharia
1. **Mudanças aditivas.** Não renomeie símbolos existentes (evita `ImportError`); mantenha aliases
   (`SYMBOLS = WATCHLIST`, `evaluate = evaluate_signal`).
2. **Toda feature nova tem kill-switch booleano** e rollback de 1 linha documentado.
3. Imports opcionais com `try/except` → degradação segura. Feature nova nunca derruba o scan.
4. **Antes de commitar:** `py_compile`, teste de import e execução com mock. Rode o canário.
5. **Verifique o repositório real** antes de afirmar algo sobre estado. Ausência de evidência não é
   evidência de ausência: confirme o nome real do campo antes de concluir "vazio".
6. **Fusos:** `execution_log` em UTC, Telegram e o usuário em UTC-3. Converta antes de correlacionar.
7. Cada decisão relevante vira um `.md` em `docs/` (evidência + decisão + rollback).
8. Docs e commits seguem o estilo do repo (ASCII nos `.md` de `docs/`, mensagens em português).

## Proibido sem aprovação explícita do usuário
- Alterar `EXECUTION_*`, `EXECUTION_MAX_NOTIONAL_USDT`, stops, TP/SL ou o relay `server/execute.php`.
- **Subir o degrau de capital** (hoje US$ 10/ordem). Só com os critérios do degrau atendidos em amostra
  do **regime atual**; nunca reaproveite trades de configuração antiga. Ver `docs/reauditoria_*.md`.
- **Propor ou implementar SHORT.** Decisão definitiva do usuário: descartado.
- Reativar estratégias desligadas (PAXG acúmulo, etc.) ou mudar a watchlist fora de `bot/config.py`.
- Dar poder ao bot de cancelar ordens que ele não criou (posições manuais ficam fora do guard).

## Armadilhas já vividas (leia antes de debugar)
- **Fix commitado ≠ fix deployado.** `server/execute.php` exige deploy manual no cPanel; confira bytes
  e linhas no servidor (typo `'sspot'`, 20/08).
- **Run verde ≠ passo funcionou.** `curl -s` retorna 0 mesmo com HTTP 401. Em workflows, confira o
  código HTTP e falhe alto (`exit 1`). O token expirado derrubou a cadência por 24 dias (14/09–09/10).
- **`SELF_DISPATCH_PAT` vive em dois lugares** (secret do GitHub + crontab do servidor): troque sempre
  nos dois. **Nunca cole token, secret ou HMAC em chat, log, print ou commit.**
- **A tela "Ordem" da Gate só mostra ordens ABERTAS.** Ordem sumida ≠ ordem inexistente: consulte
  `GET /spot/price_orders/{id}` e `GET /spot/my_trades`.
- Condicionais não reservam saldo: a soma de TP+SL pode passar do saldo e a perna sobrevivente vira órfã.
- **`open_positions` do `execution_guard.json` é só espelho.** O contador real lê `positions.jsonl`.
  Não "conserte". Consequência: **qualquer registro com status começando em `open` conta como posição
  viva** e dispara a trava de concentração (1 posição + 2 ordens/dia por ativo). Registro obsoleto bloqueia
  compras sem aviso (o HYPE ficou bloqueado de 23/08 a 11/10 por isso).
- Dois parâmetros parecidos no HYPE: `atr_mult` (do **sinal**) ≠ `EXECUTION_ATR_MULT_SL_BY_SYMBOL` (stop da **ordem**).
  Em divergência doc × código, **confie no código**.
- O cooldown de 4h vive em `state/last_signals.json`. 🟢 PRONTO no Telegram não significa que houve ordem.
- Precisão por par: consulte `/spot/currency_pairs/{PAR}`; casas a mais retornam HTTP 400.
- `state/paper_positions.json` tem 2 posições-papel obsoletas (XRP 23/08, PAXG 28/08) que nunca fecham
  porque os ativos saíram do scan. **Ignore**: não são ordens reais (decisão do usuário, 13/10).

## Documentação (`docs/`)
- **Não renomeie nem mova** arquivos de `docs/`: código, workflows e o teste canário citam os caminhos.
- `docs/README.md` classifica cada doc. **Vivos** (`estado_atual`, `mapa_estrategias`,
  `resultado_financeiro`, `runbook_btc_manual`) se atualizam no MESMO commit da mudança que os afeta,
  com a data de revisão no topo e no índice. **Registros datados** não se reescrevem: crie um novo.
- Toda decisão nova: `docs/<tema>_AAAA-MM-DD.md` (contexto, evidência, decisão, rollback) + linha no índice.
- `docs/data/latest.json` e `docs/backtest_report.md` são gerados por automação: não edite à mão.

## Servidor (jailshell do cPanel)
`/tmp` é `noexec`: grave scripts em `~/` e rode com `bash ~/script.sh`. Use `tail -n 0` (não `tail -0`).
Segredos ficam em `/home/ineocom/cryptosignals/secrets/.env`, fora da web root. Entregue comandos de
terminal prontos, com caminhos reais (`/home/ineocom/...`).

## Posições manuais do usuário (fora do bot)
BTC e PAXG manuais e outros saldos legados **não são gerenciados pelo bot** nem pelo `oco_guard`.
Não os inclua no P&L do bot. Runbook em `docs/runbook_btc_manual.md` (confira a data do estado descrito).
