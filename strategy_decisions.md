# Strategy Decisions — Diario de Bordo do crypto-signal-bot

Registro cronologico de decisoes de estrategia e correcoes tecnicas.
Evita que decisoes conscientes sejam revertidas por engano no futuro.

---

## 2026-06-16 — GO-LIVE REAL CONCLUIDO (Fase 2) 🎉

### Marco historico
- **Primeira ordem REAL executada na Gate.io.**
- `order_id`: **1083985954152** | BTC/USDT buy market | $2,96 USDT @ $65.770,20 | status: filled/closed.
- Ordem de TESTE manual (strategy=MANUAL_TEST). Sera vendida manualmente na plataforma Gate.io.

### Decisoes de estrategia
1. **Cruzamentos de MACD abaixo de zero: MANTIDOS.** Decisao consciente (NAO e descuido).
   Razao: capturar viradas de tendencia cedo. Risco mitigado por preco>EMA200 + filtro anti-lateral + RSI 40-70.
2. **Estrategia MACD-only ativa** com 4 filtros: cruzamento MACD x Signal (acima OU abaixo de zero),
   preco > EMA200, RSI 40-70, filtro anti-lateral (EMAs separadas + EMA200 inclinada).

### Correcoes tecnicas (caca aos bugs do go-live)
1. **HMAC alinhado** entre GitHub Secret, execute.php e script de teste (era a 1a barreira: "assinatura invalida").
2. **PHP em modo real**: $DRY_RUN = false no execute.php (Fase 2).
3. **time_in_force = 'ioc'** no payload da Gate.io (execute.php $bodyArr).
   BUG: Gate.io rejeita ordem market com 'gtc' (default quando ausente). Market spot exige ioc/fok.
   Erro original: "TimeInForce gtc is not support for market order".
4. **Sizing com piso minimo**: EXECUTION_MIN_NOTIONAL_USDT = 3.0 (config.py + executor.py build_order).
   BUG: Gate.io rejeita ordem < $3 ("Your order size is too small. The minimum is 3 USDT").
   Regra final de sizing: notional = clamp(2% do saldo, MIN $3, MAX $5).

### Proteçoes de capital ativas (inalteradas)
- Teto por ordem: $5 (EXECUTION_MAX_NOTIONAL_USDT) | Piso: $3 (EXECUTION_MIN_NOTIONAL_USDT)
- Max posicoes simultaneas: 2 | Max ordens/dia: 6 | Kill-switch: perda de $10/dia para tudo.

### Ponto de atencao registrado
- Com piso de $3 e EXECUTION_PCT=2%, ordens so atingem 2% "reais" do saldo a partir de ~$150.
  Em saldos menores, o piso de $3 eleva o risco relativo por trade (limitacao imposta pela Gate.io).

### Infra de disparo (jornada anterior, ja resolvida)
- Atraso de scan resolvido: cron confiavel do servidor (ineocom) via workflow_dispatch + self-scheduling.
- Watchdog ativo. Relay live com HMAC + IP whitelist.

### Commits desta sessao
- config.py: EXECUTION_MIN_NOTIONAL_USDT=3.0 (commit 2fc293f)
- executor.py: piso $3 em build_order (commit c4b6740)

---

## 2026-06-17 — SAIDA AUTOMATICA (TP/SL nativos na Gate.io) IMPLEMENTADA 🎯

### Marco
- Toda compra agora NASCE PROTEGIDA: alem da ordem market, o relay anexa
  Take-Profit e Stop-Loss como ordens price-triggered nativas na Gate.io.
- Validado em teste real: compra order_id 1084748113878 (BTC @ $64.593,80, ~$3)
  + TP id 2067427661151469568 (>= $72.000) + SL id 2067427666172051456 (<= $62.000),
  todas HTTP 201. (Posicao de teste — gerenciar/vender manualmente.)

### Design da saida (ATR-based, configuravel)
- SL = entrada - (EXECUTION_ATR_MULT_SL * ATR)   -> default 2.0x
- TP = entrada + (EXECUTION_TP_RR * risco)        -> default 2.0 (R:R 1:2)
- ATR(14) ja calculado em indicators.py e propagado no sinal (main.py).
- Parametros em config.py, com kill-switch EXECUTION_TPSL_ENABLED.
- Decisao do multiplicador: 2.0x (configuravel). Nota: breakout HYPE usa 2.5x
  (validado em backtest); 1.5x foi considerado apertado demais p/ timeframe 1h.

### CONFIRMADO: Gate.io SPOT nao tem OCO nativo atomico
- TP e SL sao ordens INDEPENDENTES (/spot/price_orders). A corretora NAO cancela
  a irma quando uma executa. Mitigacao atual: expiration=86400s (24h) mata o orfao.

### PENDENCIA TECNICA (proximo passo planejado): OCO emulado pelo bot
- Falta: a cada scan, o bot listar price_orders na Gate.io, detectar gatilho orfao
  (1 lado executou, outro pendente) e cancelar o restante.
- Exige 2 novos endpoints no execute.php (listar + cancelar price_orders) + logica
  de pareamento TP<->SL por compra. Risco do orfao hoje e baixo (ordens $3-5,
  expiration 24h, Gate.io rejeita orfao por saldo). Implementar com servidor disponivel p/ teste.

### Commits desta etapa
- config.py: EXECUTION_ATR_MULT_SL=2.0, EXECUTION_TP_RR=2.0, EXECUTION_TPSL_ENABLED (commit e72bbc5)
- executor.py: sl_price/tp_price por ATR no build_order (commit af41cc5)
- execute.php (no servidor, fora do GitHub): bloco price_orders apos compra filled.
- test_relay.php (servidor): atualizado com sl_price/tp_price + resumo TP/SL.

---

## 2026-06-17 — ESTADO FINAL DO GO-LIVE (Fase 2 concluida) ✅

### Decisao consciente: OCO emulado ADIADO (nao e esquecimento)
- Motivo: ordens de $3-5 -> risco de gatilho orfao e minimo.
- Mitigacao vigente e SUFICIENTE: expiration=86400s (24h) mata o orfao;
  Gate.io tende a rejeitar orfao por saldo insuficiente.
- GATILHO p/ implementar OCO emulado: quando aumentar o tamanho das ordens
  (ex.: notional > ~$20) ou aumentar EXECUTION_MAX_OPEN. AI o orfao passa a importar.

### Roadmap do OCO emulado (quando for a hora) — 3 etapas testaveis
- Etapa A: 2 endpoints novos no execute.php -> list_price_orders + cancel_price_order.
- Etapa B: executor.py registra pares TP<->SL por compra em state/oco_pairs.json.
- Etapa C: reconciliacao no scan (main.py) -> se 1 lado executou, cancela o irmao.
- Obs: o bot hoje e "fire-and-forget" (maybe_execute -> send_order, sem follow-up).
  O OCO emulado introduz o 1o subsistema de acompanhamento pos-ordem.

### Limpeza de posicoes de TESTE (feita manualmente pelo usuario na Gate.io)
- BTC teste #1: order_id 1083985954152 (~$3 @ $65.770) — vender manual.
- BTC teste #2: order_id 1084748113878 (~$3 @ $64.593) + gatilhos
  TP 2067427661151469568 / SL 2067427666172051456 — cancelar gatilhos + vender manual.

### CHECKLIST OPERACIONAL (estado atual do sistema em producao)
- [x] Scan automatico confiavel (cron servidor + self-scheduling, intervalo 5min).
- [x] Watchdog ativo.
- [x] HMAC alinhado GitHub <-> PHP <-> teste.
- [x] Modo real ($DRY_RUN=false). Ping dry-run continua disponivel p/ diagnostico.
- [x] Sizing: 2% saldo, piso $3, teto $5 (clamp rigido).
- [x] Travas: max 2 posicoes, max 6 ordens/dia, kill-switch $10/dia.
- [x] time_in_force=ioc (market spot Gate.io).
- [x] Saida automatica: TP/SL nativos por ATR 2.0x (configuravel) anexados a cada compra.
- [ ] OCO emulado (orfao) — ADIADO conscientemente (ver acima).

### Estrategias ativas (recap)
- MACD-only (cruzamento incl. abaixo de zero, decisao consciente) + EMA200 + RSI 40-70 + anti-lateral.
- Breakout HYPE (lookback 30, atr_mult 2.5) — SHADOW_MODE=False (valendo).
- Acumulacao PAXG (DCA por sobrevenda, BUY only, sem stop).
- Multi-timeframe (4h tendencia + 15m pullback) — kill switch disponivel.

### Snapshot do mercado no fechamento (2026-06-17 ~23:08 BRT)
- Fear & Greed: 23 (Extreme Fear). Scan: 9 ativos, 0 sinais -> bot aguardando (correto).
- HYPE/USDT H1: tendencia de alta (preco ~55.338, EMA9>EMA21, MACD+, RSI 55).
