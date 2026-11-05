---
name: auditoria-crypto-bot
description: Auditoria do crypto-signal-bot (só leitura) com resultado das últimas operações e P&L. Use sempre que o usuário pedir auditoria, conferência, "está tudo certo?", saúde do bot, placar, P&L, resultado, últimas operações/trades/compras, DCA ou situação do bot. Também para /auditoria-crypto-bot.
---

# Auditoria do Crypto Bot

Objetivo: dizer ao usuário **se está tudo certo** com o bot e **quais foram as últimas operações e o P&L**.
É uma auditoria **só de leitura**: não altere `state/`, código, flags nem o servidor; não commite; não envie ordem.
Responda em português do Brasil, horários em UTC e, quando ajudar, também em America/Bahia (UTC−3).

## 0. Preparar
1. Estar na raiz do `crypto-signal-bot` (tem `bot/config.py`). Se a sessão não tiver o repositório, clone o público
   só para leitura: `git clone --depth 300 https://github.com/neliocastro/crypto-signal-bot.git`.
2. Garantir estado recente: `git pull --ff-only` (o bot commita `state/` a cada ~5 min). Se o clone for raso demais para
   7 dias de histórico, `git fetch --shallow-since=<hoje-8d> origin main`.
3. Ler `docs/pendencias.md` (o que já é conhecido, para não alarmar à toa) e ter em mente as decisões do `memoria.md`.

## 1. Coleta automática
```bash
python .claude/skills/auditoria-crypto-bot/scripts/coleta.py --dias 7 --ultimas 8
```
O script só lê. Cobre: compilação e todos os `tests/test_*.py` e `.php`, `check_workflows`, frequência do scan
(último scan + lacunas nos commits de `state/`), flags do `bot/config.py`, posições vivas, últimos fechamentos e
ordens, DCA (com P&L aberto se a API pública da Gate responder), `scripts/placar.py` e `--degrau`.
Marcadores: `[OK]`, `[ATENCAO]`, `[FALHA]`, `[NAO VERIFICADO]`.

## 2. Conferências que exigem julgamento
- **Config × decisões:** compare as flags com o `memoria.md` (ex.: teto US$ 10 do D-024, `BREAKOUT_ENABLED=False`
  do D-013, `PAPER_EVAL_ENABLED=False` do D-046, DCA do D-049). **Divergência entre código, memória e docs: pare e
  avise; não escolha um lado** (regra do `CLAUDE.md`).
- **Posição viva sem `sl_order_id`** ou registro `open*` antigo: destacar (P-10, trava de concentração).
- **Fechamento novo:** ler a linha em `state/positions.jsonl`; dizer se o P&L é `fill_real` ou estimado, e o
  slippage de entrada (`orders_executed.csv`: fill × ref). Vários stops no mesmo minuto: anotar como “a confirmar”.
- **DCA:** cada semana desde `DCA_START_DATE` deve ter `filled` para BTC e PAXG (a partir de segunda 13:00 UTC).
- **Pendências:** se a auditoria resolver um item de `docs/pendencias.md` (ex.: primeiro `fill_real`), **sugerir**
  a atualização; não editar sem o usuário pedir.

**Não são problema (não alarmar):** `open_positions` do `execution_guard.json` diferente da contagem real (espelho,
D-023); `state/paper_positions.json` com XRP/PAXG antigos (D-028); `docs/data/latest.json` parado
(`DASHBOARD_ENABLED=False`); PAXG do DCA abaixo de US$ 10 (passo de 0,001 da Gate, já em `pendencias.md`);
posições manuais do usuário fora do placar (D-025).

## 3. Fontes externas (se disponíveis)
- **GitHub Actions:** `gh run list -R neliocastro/crypto-signal-bot --workflow main.yml --limit 30` e o workflow
  `checks`. Na nuvem sem credencial o `gh` dá 403: marcar NÃO VERIFICADO e usar a frequência pelos commits.
- **Servidor:** só no Mac, só `ssh cryptosignals-gate resumo` (uma conexão, P-20; D-042/D-045). Conferir relay 401,
  hashes iguais aos registrados em `docs/operacao.md`, crontab com trigger (5 min) e watchdog (15 min). **Na nuvem não
  há acesso ao servidor (D-051): não tente outro caminho**; liste como NÃO VERIFICADO.
- **Gate.io autenticada:** fora do escopo do agente; reconciliação de ordens é com o usuário (`docs/operacao.md` §5).

## 4. Relatório (formato fixo)
Comece pela conclusão em 1–2 linhas (“tudo certo” ou o problema principal), depois:

1. **Auditoria**: tabela Item | Resultado (✅/⚠️/❌), com código/testes, frequência do scan, pausado?, posições
   vivas, config × decisões, DCA, e o que mudou desde a última pendência. Em seguida, **pontos de atenção**
   numerados por prioridade, cada um com recomendação (adotar / adotar em parte / não adotar) quando houver ação.
2. **Últimas operações**: tabela Data (UTC) | Operação | Resultado (fechamentos + compras, mais recente primeiro).
3. **P&L**: tabela de recortes do placar (Todos, sem cadência degradada, por estratégia); critério do degrau D-024
   (janela do D-053, desde 2026-10-15: trades, P&L, PF, aprovado?); tabela do DCA (investido, custo médio e, se houver preço, P&L aberto).
   Deixar claro que o placar é estimativa (D-034), exceto linhas `fill_real`.
4. **O que não consegui conferir**: Gate, Actions, servidor, posições manuais (não reprecificadas), com o motivo e
   como conferir (ex.: `ssh cryptosignals-gate resumo` no Mac).

Termine dizendo que nada foi alterado. Nunca coloque token, secret, HMAC ou dado pessoal no relatório.
