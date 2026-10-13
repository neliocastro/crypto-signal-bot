# Indice da documentacao - crypto-signal-bot

> **Revisado em 2026-10-13** (HEAD `de5e4f5a` + este commit).
> Os nomes dos arquivos **nao mudam**: o codigo, os workflows e o teste canario
> citam caminhos de `docs/`. Para organizar, use este indice, nao renomeie.

Os documentos estao em tres grupos:

1. **Vivos** - descrevem o estado atual. Precisam estar certos hoje.
2. **Registros datados** - decisoes, auditorias, incidentes e backtests. Valem
   para a data do titulo. **Nao reescreva**; se algo mudou, crie um registro novo
   e aponte para ele.
3. **Superados** - mantidos so como historico. Cada um tem um aviso no topo
   dizendo o que o substitui.

Em divergencia entre doc e codigo, **o codigo vence** (`bot/config.py` e a fonte
unica de verdade de watchlist, kill-switches e execucao).

---

## 1. Documentos vivos (manter atualizados)

| Documento | O que cobre | Ultima revisao |
|---|---|---|
| [`estado_atual.md`](estado_atual.md) | Roteamento, kill-switches, camada de execucao, posicoes manuais, placar resumido | 2026-10-13 |
| [`mapa_estrategias.md`](mapa_estrategias.md) | 1 ativo = 1 trilho; allowlist do `main.py` (lido pelo teste canario) | 2026-10-13 |
| [`resultado_financeiro.md`](resultado_financeiro.md) | Placar real do bot (baseline 12/08 + secoes datadas) | 2026-10-11 |
| [`runbook_btc_manual.md`](runbook_btc_manual.md) | Posicao MANUAL de BTC do usuario (fora do bot) | 2026-10-11 |
| [`gateio_limitacoes.md`](gateio_limitacoes.md) | O que a Gate.io spot nao faz (OCO, condicionais, precisao) | 2026-08-11 (permanente) |
| [`troubleshooting.md`](troubleshooting.md) | Problemas recorrentes e como diagnosticar | 2026-07-01 |
| [`glossario.md`](glossario.md) | Indicadores e termos, sem jargao | 2026-06-14 (conceitual) |
| [`../CLAUDE.md`](../CLAUDE.md) | Regras e armadilhas para o Claude Code | 2026-10-13 |

### Quando atualizar cada um (no MESMO commit da mudanca)

| Se voce mudar... | Atualize |
|---|---|
| Kill-switch, `WATCHLIST`, `MARE_ALTA_UNIVERSE`, `BREAKOUT_*`, `ACCUMULATION_*` | `estado_atual.md` + `mapa_estrategias.md` |
| `INTRADAY_EXEC_ALLOWLIST` ou o nome de uma estrategia | `mapa_estrategias.md` + `tests/test_roteamento_strings.py` + `strategies.py` |
| Qualquer `EXECUTION_*` (com aprovacao do usuario) | `estado_atual.md` (tabela da execucao) + `mapa_estrategias.md` (secao 7) |
| Status em `state/positions.jsonl` a mao (reconciliacao) | registro datado novo + `estado_atual.md` |
| Placar recalculado | `resultado_financeiro.md` (secao nova datada) + resumo em `estado_atual.md` |
| Ordens manuais do usuario | `runbook_btc_manual.md` |
| Uma decisao nova | registro datado novo (ver modelo abaixo) + linha neste indice |

Ao revisar um documento vivo, troque a data "Ultima revisao" aqui e no topo dele.

---

## 2. Registros datados (historico, nao reescrever)

### Decisoes e mudancas de configuracao

| Data | Documento | Resumo |
|---|---|---|
| 2026-10-13 | [`decisao_2026-10-13_hype_desligado_e_paper.md`](decisao_2026-10-13_hype_desligado_e_paper.md) | HYPE desligado (`BREAKOUT_ENABLED = False`); 2 posicoes-papel obsoletas ignoradas |
| 2026-10-11 | [`reconciliacao_2026-10-11.md`](reconciliacao_2026-10-11.md) | Lote legado de HYPE fechado; BTC manual; placar por fills reais |
| 2026-10-08 | [`reauditoria_degrau_2026-10-08.md`](reauditoria_degrau_2026-10-08.md) | Degrau $10 -> $20 reprovado (congelado) |
| 2026-09-16 | [`prioridade1_2026-09-16.md`](prioridade1_2026-09-16.md) | Decisoes de execucao (cita `..._OVERRIDES`; o nome real e `EXECUTION_ATR_MULT_SL_BY_SYMBOL`) |
| 2026-09-16 | [`backlog_prioridade_1_2026-09-16.md`](backlog_prioridade_1_2026-09-16.md) | Backlog de 4 itens (status atual: ver `estado_atual.md`) |
| 2026-09-16 | [`override_stop_por_simbolo.md`](override_stop_por_simbolo.md) | Stop do HYPE 3.0x ATR |
| 2026-09-16 | [`degrau_notional_auditoria.md`](degrau_notional_auditoria.md) | Regra do degrau de capital |
| 2026-09-04 | [`paxg_removido_2026-09-04.md`](paxg_removido_2026-09-04.md) | PAXG fora da watchlist; acumulo desligado |
| 2026-08-24 | [`limpeza_estrategias_2026-08-24.md`](limpeza_estrategias_2026-08-24.md) | MACD-only e caminho legado removidos do codigo |
| 2026-08-24 | [`watchlist_runtime_2026-08-24.md`](watchlist_runtime_2026-08-24.md) | `config.py` como fonte unica da watchlist |
| 2026-08-23 | [`decisao_stop_e_universo_2026-08-23.md`](decisao_stop_e_universo_2026-08-23.md) | ETH/XRP fora do Mare Alta; stop global 2.5x |
| 2026-08-23 | [`trava_concentracao_2026-08-23.md`](trava_concentracao_2026-08-23.md) | 1 posicao viva + 2 ordens/dia por ativo |
| 2026-08-23 | [`ajuste_stop_2026-08.md`](ajuste_stop_2026-08.md) | Backtest de 180d do stop do HYPE |
| 2026-08-23 | [`revisao_ativos_2026-08.md`](revisao_ativos_2026-08.md) | Desempenho real por ativo |

### Auditorias e incidentes

| Data | Documento |
|---|---|
| 2026-10-08 | [`incidente_2026-10-08_stops_e_cadencia.md`](incidente_2026-10-08_stops_e_cadencia.md) - 3 stops simultaneos; token expirado derrubou a cadencia |
| 2026-08-20 | [`incidente_2026-08-20-sspot-deploy.md`](incidente_2026-08-20-sspot-deploy.md) + [`incidente_2026-08-20-fechamento.md`](incidente_2026-08-20-fechamento.md) - typo `sspot` no servidor |
| 2026-07-26 | [`auditoria_2026-07-26.md`](auditoria_2026-07-26.md) - YAML invalido parou o bot |
| 2026-07-10 | [`incidents/2026-07-10-tpsl-fantasma.md`](incidents/2026-07-10-tpsl-fantasma.md) - TP/SL fantasma |

### Backtests

| Data | Documento |
|---|---|
| 2026-07-10 | [`backtests/2026-07-mare-alta-d1.md`](backtests/2026-07-mare-alta-d1.md) - AAVE e LINK no Mare Alta D1 |
| 2026-06-21 | [`backtests/2026-06-validacao-oos.md`](backtests/2026-06-validacao-oos.md) - validacao out-of-sample |
| 2026-06-20 | [`backtests/2026-06-estrategia.md`](backtests/2026-06-estrategia.md) - backtests de estrategia |

### Diarios de bordo antigos (mai-jun/2026)

| Documento | Periodo |
|---|---|
| [`strategy_decisions.md`](strategy_decisions.md) | 28/05 a 27/06 (PAXG, HYPE promovido, MACD-only, bugs do go-live) |
| [`../strategy_decisions.md`](../strategy_decisions.md) | 16/06 a 17/06 (go-live real, TP/SL nativos) |

Os dois descrevem estrategias que **nao existem mais** (MACD-only, PAXG). O formato
"diario unico" foi substituido por um registro datado por decisao.

---

## 3. Superados (so historico)

| Documento | Substituido por |
|---|---|
| [`strategy_map.md`](strategy_map.md) | `mapa_estrategias.md` |
| [`README_BACKTEST.md`](README_BACKTEST.md) | MACD-only removido em 24/08 (`limpeza_estrategias_2026-08-24.md`) |
| [`backtest_report.md`](backtest_report.md) | idem; o arquivo e reescrito pelo workflow `backtest.yml` |

### A confirmar (status desconhecido pelo repositorio)

| Documento | Duvida |
|---|---|
| [`paxg_acumulacao_automatica.md`](paxg_acumulacao_automatica.md) | Descreve um **cron no servidor** (`server/paxg_rsi_check.php`) que compra $10 de PAXG com RSI 4h < 30, **independente do Python**. A remocao de 04/09 (`paxg_removido_2026-09-04.md`) desligou so o lado Python (`ACCUMULATION_ENABLED = False`) e nao cita o cron. `server/execute.php` ainda aceita `PAXG/USDT`. Conferir no servidor: `crontab -l \| grep paxg`, existencia de `.paxg_pause` e `tail paxg_cron.log`. Depois, registrar o resultado e mover este doc para "Superados" ou "Vivos". |

---

## 4. Gerados pelo bot (nao editar a mao)

- `docs/data/latest.json` - dashboard, reescrito a cada scan.
- `docs/backtest_report.md` - reescrito por `scripts/backtest_macd.py` quando o workflow de backtest roda.

---

## 5. Modelo de registro datado

Nome: `docs/<tema>_AAAA-MM-DD.md`. ASCII, em portugues. Secoes minimas:

```
# <Tema> - AAAA-MM-DD
## Contexto
## Evidencia      (arquivos, commits, runs, fills - com fuso UTC ou BRT explicito)
## Decisao        (quem decidiu; o que mudou; commit)
## Rollback       (1 linha)
```

Depois: adicione a linha na secao 2 deste indice e atualize os documentos vivos afetados.
