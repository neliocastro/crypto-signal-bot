# Arquitetura e stack

> Revisado em 2026-10-15. Descreve **como o sistema é montado**. O que cada ativo opera está em
> `estrategias.md`; como operar e diagnosticar, em `operacao.md`. Em divergência com o código, o código vence.

## Visão geral (cérebro / braço)

```
GitHub Actions (Python) "CÉREBRO"                    Servidor ineocom, cPanel (PHP) "BRAÇO"
scan → sinal → sizing → SL/TP → assina HMAC  ──POST──►  valida HMAC → sanity checks → Gate.io API v4
grava state/*.jsonl e commita no repo        ◄───────  resultado / fill / ids de TP e SL
Telegram (sinais, ordens, alertas)                      execution_log.jsonl (UTC)
```

- **Dados de mercado:** Gate.io, com fallback para Binance e Bybit (`bot/data_fetcher.py`).
- **Execução:** só Gate.io spot, só compra (LONG).
- **Estado:** versionado no próprio repositório (`state/`), commitado a cada scan
  (`chore: update signal state + dashboard [skip ci]`).

## Stack

| Camada | Tecnologia |
|---|---|
| Cérebro | Python 3.11 no GitHub Actions (`ubuntu-latest`) |
| Bibliotecas | `ccxt 4.4.50`, `pandas 2.2.3`, `numpy 1.26.4`, `ta 0.11.0`, `requests 2.32.3` (`requirements.txt`) |
| Braço | PHP (cPanel, IP fixo na whitelist da Gate.io), `server/execute.php` |
| Exchange | Gate.io API v4 spot; TP/SL como `price_orders` (gatilhos condicionais) |
| Notificação | Telegram (bot próprio) |
| Sentimento | Fear & Greed (alternative.me, sem chave) |

Mudar qualquer item desta tabela exige autorização do usuário (`CLAUDE.md`).

## Módulos (`bot/`)

| Módulo | Papel |
|---|---|
| `main.py` | entrypoint do scan: diagnóstico dos ativos, roteamento, executor, Maré Alta, trailing, OCO, relatórios |
| `config.py` | **fonte única** de watchlist, kill-switches e parâmetros de execução |
| `strategies.py` | `evaluate_signal`: fast-path Breakout (HYPE) e Acúmulo (PAXG); demais ativos → `None` |
| `mare_alta.py` | estratégia Maré Alta D1 (scan próprio, universo próprio) |
| `executor.py` | sizing, SL/TP, travas de capital, assinatura HMAC e envio ao relay |
| `mare_alta_trailing.py` | registro de posições (`positions.jsonl`) e trailing D1 por ATR |
| `oco_guard.py` | OCO emulado (ação `oco_sync`) e TP1 → breakeven |
| `data_fetcher.py`, `indicators.py`, `sentiment.py` | dados, indicadores e Fear & Greed |
| `telegram_sender.py`, `commander.py`, `runtime_config.py` | mensagens, comandos do Telegram e config de runtime |
| `paper_evaluator.py` | paper trading (simulação, não afeta ordens reais) |
| `watchdog.py` | alerta de intervalo longo entre scans (> 20 min) |
| `dashboard_writer.py` | dashboard (`DASHBOARD_ENABLED = False`) |
| `reports/daily_summary.py` | resumo diário no Telegram |

`server/`: `execute.php` (relay), `paxg_rsi_check.php` (cron PAXG), `gate_cleanup.php` (limpeza manual de órfãs).
`scripts/`: backtests sob demanda. `tests/`: testes standalone (sem pytest).

## Relay PHP (`server/execute.php`)

Ações, todas exigindo assinatura HMAC-SHA256 do corpo (`X-Signature`):

| Ação | O que faz |
|---|---|
| (padrão) compra | market buy (`ioc`) + TP e SL como `price_orders`; base = `filled_total / fill_price`; aceita `tp_frac` (TP parcial) |
| `update_trailing` | cria o novo SL → confirma → deleta o antigo (falhou = antigo mantido) |
| `oco_sync` | lê o status real de cada perna; cancela a sobrevivente; com `tp_partial` devolve `tp1_hit` sem cancelar o SL |

Travas próprias do PHP: `$MAX_NOTIONAL_USDT = 10.0`, `$REQUIRE_PROTECTION = true`, `$SYMBOL_WHITELIST` (BTC, SOL, TRX,
BNB, HYPE + PAXG do cron D-032; D-036, sincronia vigiada por `tests/test_whitelist_php.py`),
idempotência por `signal_id` (`seen_signals.json`), precisão por par via `/spot/currency_pairs` com tabela de fallback.
**Qualquer mudança neste arquivo exige deploy manual** (`operacao.md`).

## Cadência do scan

| Disparador | Frequência | Depende de `SELF_DISPATCH_PAT`? |
|---|---|---|
| Cron do servidor ineocom → `workflow_dispatch` | ~5 min | sim |
| Self-chain: último passo do `main.yml` espera 240 s e re-dispara | ~5 min | sim |
| Cron do GitHub `*/15` | best-effort (na prática poucas vezes por dia) | não |

O intervalo mínimo entre scans vem de `state/runtime_config.json` (`scan_interval_min`, hoje 5; comando `/intervalo`).
Runs fora do intervalo terminam com "Scan PULADO". Concorrência: `scan-${ref}`, enfileira sem cancelar.

## Workflows (`.github/workflows/`)

| Workflow | Gatilho | Função |
|---|---|---|
| `main.yml` | cron `*/15` + `workflow_dispatch` | scan, commit de `state/`, re-disparo (falha se ≠ HTTP 204) |
| `checks.yml` | push em `server/`, `bot/`, `tests/` | `php -l` no relay + `py_compile` + testes |
| `commander.yml` | cron `*/2` (na prática a cada 3–5 h, P-17) | lê comandos do Telegram (`/status`, `/pausar`, `/retomar`, `/intervalo`, `/forcar`, `/dnd`…) |
| `daily_summary.yml` | cron 12:00 UTC (09:00 BRT) | resumo diário |
| `backtest.yml` | manual | roda um script de `scripts/`; o `backtest_macd` grava `docs/backtest_report.md` (artefato gerado, não versionar à mão) |

**Secrets do GitHub:** `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `EXECUTION_HMAC_SECRET`, `SELF_DISPATCH_PAT`.

## Estado (`state/`)

| Arquivo | Conteúdo | Fonte da verdade de |
|---|---|---|
| `positions.jsonl` | posições do bot (`open`, `closed_tp`, `closed_sl`, `closed_manual`) | posições vivas e trava de concentração |
| `paper_trades.jsonl` | intenção, bloqueio de trava e resposta do relay de cada ordem | o que foi enviado |
| `orders_executed.csv` | uma linha por operação (legível) | alcance de incidentes |
| `execution_guard.json` | contadores do dia (UTC); `open_positions` é só espelho | limite diário |
| `last_signals.json` | cooldown de 4h por `símbolo|estratégia` | supressão de sinais repetidos |
| `mare_alta_state.json` | última vela D1 alertada por ativo | anti-duplicata do Maré Alta |
| `runtime_config.json` | intervalo de scan, DND, pausa | cadência (a watchlist daqui é ignorada) |
| `paper_positions.json` | posições-papel (simulação) | — |

## Servidor (ineocom)

| Item | Caminho / valor |
|---|---|
| Conta / SSH | `ineocom@dedi-15131000` (jailshell); também acessado como `root` |
| Relay | `/home/ineocom/public_html/cryptosignals/execute.php` |
| Log do relay | `/home/ineocom/public_html/cryptosignals/execution_log.jsonl` (UTC, campo `"event":"execute"`) |
| Idempotência | `/home/ineocom/public_html/cryptosignals/seen_signals.json` |
| Cron PAXG | `/home/ineocom/public_html/cryptosignals/paxg_rsi_check.php` + `paxg_cron.log`, pausa `.paxg_pause` |
| Segredos | `/home/ineocom/cryptosignals/secrets/.env` (fora da web root): `GATE_API_KEY`, `GATE_API_SECRET`, `EXECUTION_HMAC_SECRET` |
| Endpoint | `https://ineo.com.br/cryptosignals/execute.php` (HTTP 401 sem assinatura = correto) |
| Watchdog externo | `/home/ineocom/public_html/cryptosignals/watchdog_scan.php` + `watchdog_cron.log`, estado `.watchdog_state.json`, pausa `.watchdog_pause` (D-037) |
| Script manual BTC | `~/btc_tp.php` (home do `ineocom`) |
| PHP para cron | `/usr/local/bin/php` (CLI); `/usr/bin/php` é CGI e falha |

Não existe `/home/nelio/...` (caminho inventado no passado).

## Limites da Gate.io que moldam o projeto
- **Sem OCO nativo no spot.** TP e SL são `price_orders` independentes e **não reservam saldo**; quem cancela a perna
  sobrevivente é o bot (`oco_sync`).
- Gatilhos têm `expiration` obrigatória (hoje 30 dias).
- Em `/spot/orders` o campo é `account: spot`; em `/spot/price_orders` é `put.account: normal`.
- Precisão por par (`/spot/currency_pairs/{PAR}`): casas a mais retornam HTTP 400. Mínimo de ordem ~US$ 3.
- Em MARKET BUY o `amount` da resposta vem em **quote** (USDT), não em base.
- O app só mostra ordens **abertas**; status real via `GET /spot/price_orders/{id}` e `/spot/my_trades`
  (a API grafa `canceled`).
