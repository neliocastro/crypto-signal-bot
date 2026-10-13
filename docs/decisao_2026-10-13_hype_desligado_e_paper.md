# Decisao 2026-10-13 - HYPE desligado e posicoes-papel obsoletas

> Registro de decisao do usuario. Continua `docs/reconciliacao_2026-10-11.md`.
> Commits: `4c0a58b5` (reconciliacao + kill switch) e `de5e4f5a` (CLAUDE.md).

## 1. Breakout HYPE desligado

**Contexto.** A reconciliacao de 11/10 fechou o registro `legacy_hype_pre_bot`
(`closed_manual`). Esse registro "aberto" mantinha a trava de concentracao
ligada e bloqueou 17 sinais de HYPE entre 23/08 e 11/10. Fechado o registro,
o trilho Breakout HYPE voltaria a enviar ordens reais (teto $10).

**Evidencia contra religar.** HYPE ao vivo teve PF ~0.78 em 12 trades, muito
abaixo do backtest (PF 2.55). O bloqueio de 23/08 a 11/10 foi acidental, nao
uma decisao; religar so porque o bloqueio sumiu tambem nao seria.

**Decisao.** `BREAKOUT_ENABLED = False` em `bot/config.py`, no mesmo commit da
reconciliacao (`4c0a58b5`).

**Efeito verificado (run 38459227786, 13/10 20:00 UTC, HEAD `de5e4f5a`).**
- O HYPE continua na `WATCHLIST` e e escaneado, mas `evaluate_signal` devolve
  `None` (o fast-path do breakout so roda com o switch ligado).
- O Mare Alta nao cobre HYPE (`MARE_ALTA_UNIVERSE` = BTC, SOL, TRX, BNB).
- Resultado do scan: 5 ativos, 0 sinais, sem erro.
- `state/positions.jsonl`: nenhum registro com status `open*`.

**Rollback / religar.** `BREAKOUT_ENABLED = True`. Antes de religar, reavaliar
o HYPE com trades do regime atual (stop 3.0x ATR desde 16/09).

## 2. Posicoes-papel obsoletas em `state/paper_positions.json`

`state/paper_positions.json` lista 2 posicoes-papel "abertas":

| Ativo | Estrategia | Aberta em | Entrada |
|---|---|---|---|
| XRP/USDT | Tendencia MACD - Agressivo | 2026-08-23 | 1.4945 |
| PAXG/USDT | Acumulo (RSI sobrevenda) | 2026-08-28 | 4460.27 |

**Sao simulacao (paper trading), nao ordens reais.** O usuario confirmou em
13/10 que elas **nao existem mais**. Ficaram presas porque o
`paper_evaluator` so atualiza preco de ativos que ainda estao no scan: XRP saiu
em 24/08 e PAXG em 04/09, entao essas posicoes nunca fecham.

**Decisao.** Ignorar. O arquivo nao foi editado (o bot o reescreve a cada scan).

**Consequencias conhecidas (inofensivas):**
- O log do scan mostra `paper_evaluator: 2 aberta(s)`.
- O relatorio semanal do paper no Telegram conta essas 2 posicoes.
- Nao afetam ordens reais, a trava de concentracao nem o P&L do bot (o
  contador real le `state/positions.jsonl`).

**Se um dia quiser zerar:** remover as duas entradas de `open` em
`state/paper_positions.json` num commit proprio, entre dois scans.
