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
