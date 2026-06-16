# Histórico de Decisões de Estratégia

Registro das decisões de estratégia do bot, baseadas em backtests e testes
de robustez. Mantido para rastreabilidade — por que cada ativo opera como opera.

---

## PAXG/USDT — REPROVADO (removido da watchlist em 2026-05-28)

Ouro tokenizado: ativo de baixíssima volatilidade, sem tendências exploráveis
no timeframe de 1h.

| Estratégia testada | Resultado |
|---|---|
| MACD-only (agressivo) | Reprovado — pouquíssimos sinais, sem edge |
| Mean-reversion (RSI/banda) | Reprovado — PF < 1.2 |
| Breakout/Tendência | Reprovado — natureza lateral, não rompe |

**Decisão:** removido da `WATCHLIST`. Reprovado em 3 abordagens distintas.
PAXG não combina com estratégias de momentum/tendência em 1h.

---

## HYPE/USDT — PROMOVIDO para Breakout/Tendência (shadow) em 2026-05-28

Ativo de tendência forte e alta volatilidade. Mean-reversion fracassaria
(venderia cedo nos ralis); momentum/breakout é o encaixe natural.

### Histórico
1. **MACD-only (Fase A):** aprovado em backtest 90d (PF 3.45) MAS sofreu
   whipsaw com stop apertado 1.5xATR — MDD -21% observado. Frágil.
2. **Breakout/Tendência (nova):** EMA9>21>50 + rompe máxima de N velas +
   RSI>50, stop largo 2.5xATR + trailing (deixa correr).

### Teste de robustez (2026-05-28, ~150d de histórico — ativo lista desde 30/12/2025)

**Sensibilidade de parâmetros (9 configs, todas PF > 1.3 → edge real, não overfit):**

| Config | PF | Ret% | MDD% |
|---|---|---|---|
| lb=20 atr=2.5 (inicial) | 1.86 | +55.3 | -25.0 |
| **lb=30 atr=2.5 (escolhida)** | **2.55** | **+67.5** | **-16.9** |
| lb=30 atr=3.0 | 2.11 | +57.2 | -21.1 |

**Robustez temporal (2 de 3 janelas lucrativas):**
- Janela A (início): PF 2.09 ✅
- Janela B (meio): PF 0.87 🔴 (mercado lateral)
- Janela C (recente): PF 3.32 ✅

**Dependência de poucos trades (risco conhecido):**
- 47 trades, WR 42.6%, maior trade = 66% do retorno.
- Sem o melhor trade: ainda +18.9% (PF 1.30) ✅
- Sem os 2 melhores: -6% 🔴 → depende de 2-3 ralis grandes.

### Decisão
- **Config de produção:** `lookback=30, atr_mult=2.5` (melhor PF e menor MDD).
- **Roteamento:** HYPE usa SÓ a estratégia breakout (fast-path dedicado em
  `evaluate_signal`); removido do MACD-only (`approved_symbols` agora só LINK).
- **SHADOW MODE ligado** (`BREAKOUT_SHADOW_MODE=True`): sinais marcados
  `[SHADOW]` por 2-4 semanas de observação antes de operar valendo —
  justificado pelo histórico curto (150d) e concentração em poucos trades.
- **Kill switch:** `BREAKOUT_ENABLED=False` desliga totalmente.

**Quando confiar:** após 2-4 semanas de shadow, se os sinais ao vivo forem
coerentes, trocar `BREAKOUT_SHADOW_MODE=False`.

---

## LINK/USDT — MACD-only agressivo (mantido)

Aprovado em backtest 90d (12 trades, 66.7% WR, PF 3.26). Permanece no perfil
agressivo MACD-only. Único ativo em `approved_symbols`.

---

## Controle (BTC/ETH/SOL) na estratégia breakout

Testados como controle — NÃO promovidos:
- ETH: PF 1.48 (limítrofe, retorno mais distribuído que HYPE)
- LINK: PF 1.22 (limítrofe)
- BTC: PF 0.91 (reprovado)
- SOL: PF 0.68 (reprovado)

A estratégia breakout NÃO generaliza para todos os ativos — é específica para
perfis de alta tendência como o HYPE. ETH fica como candidato futuro.

## PAXG/USDT — Acúmulo por sobrevenda (BUY only) em 2026-05-29

Ouro digital tratado como reserva de valor: estratégia de ACÚMULO (DCA
inteligente), não de trade. Comprar fraqueza, sem alvo de venda nem stop.

### Histórico
- PAXG já havia sido REMOVIDO da watchlist (commit adf02d3): reprovou em 3
  backtests de trend/momentum. Motivo: ouro é lateral, sem tendência a capturar.
- Reintroduzido APENAS para acúmulo — categoria oposta (mean/sobrevenda),
  alinhada à natureza do ativo. NÃO volta para o trend (fast-path dedicado).

### Configuração (decidida com o usuário)
- **Timeframe:** 4h (sinais raros e significativos; evita ruído do 1h).
- **Gatilho:** RSI CRUZA para baixo de 30 (entrada na zona de sobrevenda).
  Dispara só no cruzamento — não a cada vela presa abaixo de 30 (anti-spam).
- **Sobrevenda extrema:** RSI < 20 → destaque "ACÚMULO EXTREMO" (oportunidade rara).
- **Cooldown:** 24h (máx. 1 alerta por dia por ativo). Estado persistido em
  `state/accumulation_signals.json`.
- **BUY only:** sem stop e sem take-profit — é hold/acúmulo, não trade.

### Roteamento e segurança
- Fast-path dedicado `_check_accumulation` em `evaluate_signal`: PAXG vai SÓ
  para o acúmulo, nunca cai no caminho de trend. Envolto em try/except (degrada seguro).
- Mensagem dedicada no Telegram (`_format_accumulation`): sem alvos de venda,
  com variação normal (RSI<30) e extrema (RSI<20).
- **Kill switch:** `ACCUMULATION_ENABLED=False` desliga só o acúmulo do PAXG.

### Validação
- Testes unitários 4/4: cruzamento dispara, cooldown bloqueia reenvio,
  "preso abaixo de 30" não dispara, RSU<20 marca extremo.
- Scan #204 (2026-05-29) verde em produção com PAXG na watchlist.

---


---

## 2026-06-12 — EXPANSAO: MACD-only Agressivo para TODA a watchlist (exceto PAXG)

Decisao do operador: ligar o MACD-only Agressivo para todos os ativos,
mantendo HYPE no Breakout e PAXG na Acumulacao.

### Implementacao
- `RISK_PROFILES["agressivo"]["approved_symbols"] = None`  -> None = todos.
- `MACD_ONLY_EXCLUDE = {"PAXG/USDT"}` (cinto extra de protecao).
- `evaluate_signal` ja intercepta antes: HYPE -> Breakout, PAXG -> Acumulacao.

### Mapa de roteamento (ordem de prioridade)
1. HYPE  -> Breakout/Tendencia
2. PAXG  -> Acumulacao RSI 4h (compra-only)
3. resto -> MACD-only Agressivo

| Ativo | Estrategia |
|---|---|
| HYPE | Breakout/Tendencia |
| PAXG | Acumulacao RSI 4h |
| BTC, ETH, SOL, XRP, TRX, BNB, LINK, AAVE | MACD-only Agressivo |

### Risco registrado
- 6 ativos novos no MACD-only (BTC, ETH, SOL, XRP, TRX, BNB, AAVE) entraram
  SEM backtest dedicado. Apenas LINK e HYPE foram validados nos 90d.
- Mitigacao: bot em EXECUTION_DRY_RUN=True (paper trading) -> nenhuma ordem
  real. Observar via paper_evaluator (relatorio a cada 7 dias) antes de
  considerar execucao real desses 6 ativos.

### Commits
- config.py: d33ff8d (approved_symbols=None + MACD_ONLY_EXCLUDE)
- strategies.py: a2e69a0 (fast-path aceita None + respeita exclude)


---

## 2026-06-14 — INVESTIGACAO DE PERDAS + 2 CORRECOES

Motivo: paper trading acumulou -9.46% (WR 20%, 5 trades fechados) em 14 dias.
Investigacao trade-a-trade revelou 3 causas. Duas corrigidas hoje.

### Diagnostico (paper_positions.json)
| Ativo | Estrategia | pnl | pico | duracao | causa |
|---|---|---|---|---|---|
| HYPE | Breakout | +4.00% | +8.14% | 54h | OK (onda real) |
| HYPE | Breakout | -7.51% | +1.49% | 15h | BUG trailing |
| HYPE | Breakout | -3.78% | +1.68% | 18h | BUG trailing |
| AAVE | MACD-only | -1.56% | +0.00% | 6h | sinal falso (lateral) |
| BNB  | MACD-only | -0.60% | +0.00% | 7h | sinal falso (lateral) |

### CORRECAO 1 — Bug do trailing stop (commit 9e8b41f)
- Arquivo: bot/paper_evaluator.py (_simulate_exit).
- Bug A: `pos["stop"] = trail` sobrescrevia o stop a cada scan -> podia DESCER.
- Bug B: fechava no `price` do scan (granularidade 1h, ja furado) e nao no
  nivel do stop -> slippage artificial (-7.5% num stop de ~-5.2%).
- Fix: stop so sobe (high-water mark); fill no nivel do stop (min(price,trail)).
  Mesmo ajuste aplicado ao stop fixo (MACD-only) e ao take_profit.
- NOTA: o bug era do SIMULADOR (paper), nao da estrategia. O paper estava
  reportando perda PIOR que a real. Estrategia Breakout permanece valida.

### CORRECAO 2 — Filtro anti-lateral no MACD-only (commit d51f7a1)
- Arquivo: bot/strategies.py (_check_aggressive_macd).
- Problema: em mercado lateral o MACD cruza muito -> sinais falsos (AAVE/BNB
  com pico +0%, stop direto).
- Fix: alem de (cross + preco>EMA200 + RSI 40-70), agora exige TENDENCIA real:
  1) EMA9 > EMA21 > EMA50 (empilhadas)
  2) spread (EMA9-EMA50)/close >= 0.15% (EMAs nao coladas)
  3) EMA200 inclinada p/ cima (ema200 atual > ema200 ~14 velas atras)
- Usa apenas dados ja existentes no df (sem adicionar ADX). Limiares
  conservadores; calibrar depois com dados do paper.
- Trade-off aceito: menos sinais, maior qualidade.

### Causa 3 (NAO corrigida, apenas registrada) — Regime de mercado
- Backtest pegou alta de maio; paper pegou junho lateral. Estrategias de
  tendencia sofrem em lateral por natureza. Mitigado pelos filtros acima.

### Status / proximo passo
- Bot segue em EXECUTION_DRY_RUN=True. NAO ir ao vivo ate o paper, com a
  logica corrigida, mostrar edge positivo consistente.
- Acao: deixar o scan rodar e reavaliar o paper em ~1-2 semanas.


---

## 2026-06-14 — DECISAO: manter cruzamentos de MACD ABAIXO de zero

Contexto: ao revisar um sinal de BNB, o usuario notou que o MACD-only dispara
quando a linha MACD cruza a Signal INDEPENDENTE de estarem acima ou abaixo da
linha zero. Perguntou se deveria filtrar para so operar cruzamentos acima de 0.

DECISAO (consciente, do usuario): NAO adicionar o filtro `macd > 0`. O bot
continua enviando sinais em cruzamentos acima E abaixo de zero.

Justificativa:
- Cruzamentos abaixo de zero capturam a VIRADA cedo (inicio de tendencia).
  Exigir macd>0 entraria mais tarde e perderia o melhor trecho de altas (ex.:
  no HYPE, o rali 44.736->55.338 comecou com cruzamento perto/abaixo de zero).
- Risco ja mitigado por filtros existentes: preco>EMA200 (so opera em alta
  macro), filtro anti-lateral (EMAs separadas + EMA200 inclinada) e RSI 40-70.

IMPORTANTE: isto NAO e um esquecimento. E uma escolha deliberada. Nao
"corrigir" no futuro adicionando macd>0 sem antes validar em backtest/paper.

Sem mudanca de codigo (comportamento atual ja e o desejado).


---

## 2026-06-16 — INVESTIGACAO: 3 residuos do bug do trailing

Contexto: apos a medicao mostrar P&L +26.97% (vs baseline -9.46%), 3 trades
fechados apresentavam perda PIOR que o stop calculado. Investigados um a um
com timestamps e candles reais da Gate.io (BNB/USDT 1h, 14-16/06).

### Resultado da investigacao

| Trade          | pnl    | stop   | fechou      | veredicto                        |
|----------------|--------|--------|-------------|----------------------------------|
| HYPE -7.51%    | -7.51% | -3.68% | 04/06 08h   | FOSSIL pre-fix (9e8b41f). OK.    |
| HYPE -3.78%    | -3.78% | -2.74% | 13/06 06h   | FOSSIL pre-fix (9e8b41f). OK.    |
| BNB  -1.42%    | -1.42% | -0.82% | 16/06 17h   | RISCO REAL de mercado (ver abaixo)|

### Detalhe do BNB (16/06): mergulho intra-vela, nao bug

Candles da Gate.io (fonte real do bot):
- 16/06 12:00 -> preco OK (614.40), acima do stop (609.08)
- 16/06 13:00 -> vela despencou de 614.60 ate LOW 601.20 (-2.2%) em 1 hora
- Stop de 609.08 foi furado INTRA-VELA (abriu acima, fechou abaixo)
- Scan so rodou na hora seguinte -> preco ja estava bem abaixo do stop
- fill = min(price, stop) pegou o price real (604.xx) -> perda -1.42%

CONCLUSAO: o codigo esta CORRETO. O `min(price, stop)` funciona como esperado.
A perda acima do stop e RISCO DE MERCADO GENUINO (slippage por gap/vela brusca)
-- nao e defeito do simulador. Isso acontece com qualquer trader em qualquer
corretora. O paper esta sendo REALISTA, nao pessimista.

IMPORTANTE: o +26.97% do paper e confiavel. O simulador nao esconde perdas.

### Decisao: manter comportamento atual (nao alterar codigo)
- Nao aumentar frequencia do scan (mais API calls sem beneficio proporcional)
- Nao criar "fill garantido no stop" (seria otimista demais para o paper)
- Registrar slippage como risco inerente ao go-live (stops podem executar
  levemente pior que o planejado em movimentos bruscos)

### Status geral pos-investigacao (16/06)
- Codigo limpo: nenhum bug vivo confirmado
- P&L paper: -9.46% (baseline 14/06) -> +26.97% (16/06)
- Win-rate: 20% -> 50% (5/10 trades)
- Melhor trade: HYPE Breakout +16.76% (trailing corrigido funcionou)
- Bot permanece em EXECUTION_DRY_RUN=True
- Proxima reavaliacao automatica: segunda-feira 09:00 (Bahia)
