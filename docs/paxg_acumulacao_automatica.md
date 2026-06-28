# 🥇 Acumulação Automática do PAXG (Ouro Digital)

> **Status:** ✅ ATIVO em produção desde 2026-06-28
> **Tipo:** Acumulação (DCA) automática via cron no servidor — independente do scan Python.

---

## 📌 Resumo executivo

O servidor compra **$10 de PAXG/USDT** automaticamente sempre que:

1. **RSI 4h(14) < 30** (sobrevenda), **E**
2. Passaram **≥ 12h** desde a última compra automática (cooldown).

É **acumulação pura**: **sem take-profit** (nunca vende no lucro). Há apenas um
**stop-loss largo de −15%** que funciona como *circuit-breaker* de catástrofe
(na prática nunca dispara em flutuação normal do ouro).

---

## 🏗️ Arquitetura (isolada do cérebro Python)

Diferente das estratégias do bot (que rodam no GitHub Actions em dry-run), a
acumulação do PAXG roda **100% no servidor**, via cron, usando o "braço" PHP
que já estava validado:

```
crontab (de hora em hora)
   │
   ▼
paxg_rsi_check.php  ── "cérebro" leve ───────────────┐
   │  1. busca candles 4h do PAXG na Gate.io (cURL)   │
   │  2. calcula RSI(14) de Wilder                     │
   │  3. checa cooldown (.paxg_last_buy)               │
   │  4. SE RSI<30 E cooldown ok → dispara:            │
   ▼                                                   │
gerar_teste_paxg.php  ── monta a ordem ───────────────┤
   │  - notional $10, SL largo -15%, SEM TP            │
   │  - assina com HMAC-SHA256                          │
   │  - POST para execute.php                           │
   ▼                                                   │
execute.php  ── "braço" (IP fixo na whitelist Gate.io) ┘
   │  - valida HMAC + whitelist + teto ($10)
   │  - compra a mercado na Gate.io
   │  - cria SL nativo (sem TP)
   ▼
execution_log.jsonl  (registro auditável de cada compra)
paxg_cron.log        (registro de cada decisão do cron)
```

---

## ⚙️ Parâmetros (onde mexer)

| Parâmetro | Valor | Arquivo | Linha/var |
|---|---|---|---|
| Gatilho RSI | **< 30** | `paxg_rsi_check.php` | `$RSI_LIMIAR = 30.0` |
| Período RSI | 14 | `paxg_rsi_check.php` | `$RSI_PERIOD = 14` |
| Timeframe | 4h | `paxg_rsi_check.php` | candlesticks `interval=4h` |
| Cooldown | **12h** | `paxg_rsi_check.php` | `$COOLDOWN_H = 12` |
| Valor/compra | **$10** | `gerar_teste_paxg.php` | `$NOTIONAL_USDT = 10.0` |
| Stop-loss largo | **−15%** | `gerar_teste_paxg.php` | `$SL_PCT = 15.0` |
| Take-profit | **nenhum** | `gerar_teste_paxg.php` | `$tp_price = 0.0` (envia `null`) |
| Teto de notional | **$10** | `execute.php` | `$MAX_NOTIONAL_USDT = 10.0` |
| Whitelist | inclui `PAXG/USDT` | `execute.php` | `$SYMBOL_WHITELIST` |

> ⚠️ **Atenção ao alterar o valor da compra:** se subir o `$NOTIONAL_USDT` no
> `gerar_teste_paxg.php`, suba **também** o `$MAX_NOTIONAL_USDT` no `execute.php`,
> senão a ordem é rejeitada por estourar o teto.

---

## 🗂️ Arquivos no servidor

Caminho base: `/home/ineocom/public_html/cryptosignals/`

| Arquivo | Papel |
|---|---|
| `paxg_rsi_check.php` | Cron: calcula RSI 4h, checa cooldown, decide comprar |
| `gerar_teste_paxg.php` | Monta a ordem de acúmulo ($10, SL -15%, sem TP) e assina (HMAC) |
| `execute.php` | Braço de execução (valida e envia à Gate.io) |
| `.paxg_last_buy` | Timestamp epoch da última compra (controla cooldown) |
| `.paxg_pause` | **Kill-switch**: se existir, o cron não compra nada |
| `paxg_cron.log` | Log de cada decisão do cron |
| `execution_log.jsonl` | Log auditável de cada ordem executada |

---

## ⏰ Cron instalado

```cron
0 * * * * /usr/bin/php /home/ineocom/public_html/cryptosignals/paxg_rsi_check.php >> /home/ineocom/public_html/cryptosignals/paxg_cron.log 2>&1
```

Roda de hora em hora (minuto 0). PHP do servidor: `8.2.31`.

---

## 🛑 Como pausar / controlar

```bash
BASE=/home/ineocom/public_html/cryptosignals

# PAUSAR (kill-switch) — cria o arquivo de pausa:
touch $BASE/.paxg_pause

# REATIVAR — remove o arquivo de pausa:
rm -f $BASE/.paxg_pause

# ZERAR o cooldown (permitir compra imediata no próximo RSI<30):
rm -f $BASE/.paxg_last_buy

# TESTAR a seco (mostra RSI e decisão, NÃO compra):
php $BASE/paxg_rsi_check.php --dry

# VER o histórico de decisões do cron:
tail -n 20 $BASE/paxg_cron.log

# VER a última compra registrada:
tail -n 1 $BASE/execution_log.jsonl
```

---

## ✅ Validação (2026-06-28)

| Teste | Resultado |
|---|---|
| Cálculo de RSI 4h (vs Gate.io ao vivo) | ✅ confere (ex: RSI 51.x em zona neutra) |
| `--dry` com RSI 51 (>30) | ✅ decisão = NÃO compra (correto) |
| Compra real $5 (manual, validação inicial) | ✅ filled, order_id 1090800700419, SL 3464.04 |
| Compra real $10 (via cron, limiar forçado a 60) | ✅ filled, order_id 1090809438021, SL 3466.12, **TP null** |
| Cooldown armado após compra | ✅ `.paxg_last_buy` gravado |
| Sintaxe (`php -l`) dos 3 arquivos | ✅ sem erros |

---

## 🧠 Decisões de design (por quê é assim)

- **Por que cron no servidor, e não no scan Python?**
  O scan Python está em dry-run (cinto triplo de segurança) e tinha o bug
  histórico do `execute.php` (precision). A acumulação do PAXG reaproveita o
  caminho manual já validado, isolado e seguro, sem reativar execução real no
  cérebro Python.

- **Por que SL largo de −15% e não "sem SL"?**
  O `execute.php` tem o guard anti-posição-nua (FIX 3): recusa compra **sem TP
  E sem SL**. O SL de −15% satisfaz o guard sem descaracterizar o acúmulo —
  só dispara num colapso extremo do ouro (cenário de seguro, não de trade).

- **Por que sem take-profit?**
  PAXG é tese de acumulação/hold (ouro digital). Não há teto de venda.

---

## 📝 Histórico

| Data | Evento |
|---|---|
| 2026-06-27 | Validação do braço com TRX (TP/SL nativos, fix allow_url_fopen + account:normal) |
| 2026-06-28 | PAXG adicionado à whitelist; `gerar_teste_paxg.php` criado (SL largo, sem TP) |
| 2026-06-28 | Primeira compra real de PAXG ($5) validada |
| 2026-06-28 | `paxg_rsi_check.php` + cron criados; teto subido p/ $10; automação no ar |
