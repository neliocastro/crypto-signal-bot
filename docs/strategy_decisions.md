# Histu00f3rico de Decisu00f5es de Estratu00e9gia

Registro das decisu00f5es de estratu00e9gia do bot, baseadas em backtests e testes
de robustez. Mantido para rastreabilidade u2014 por que cada ativo opera como opera.

---

## PAXG/USDT u2014 REPROVADO (removido da watchlist em 2026-05-28)

Ouro tokenizado: ativo de baixu00edssima volatilidade, sem tendu00eancias exploru00e1veis
no timeframe de 1h.

| Estratu00e9gia testada | Resultado |
|---|---|
| MACD-only (agressivo) | Reprovado u2014 pouqu00edssimos sinais, sem edge |
| Mean-reversion (RSI/banda) | Reprovado u2014 PF < 1.2 |
| Breakout/Tendu00eancia | Reprovado u2014 natureza lateral, nu00e3o rompe |

**Decisu00e3o:** removido da `WATCHLIST`. Reprovado em 3 abordagens distintas.
PAXG nu00e3o combina com estratu00e9gias de momentum/tendu00eancia em 1h.

> NOTA (2026-05-29): PAXG foi REINTRODUZIDO com estratu00e9gia DIFERENTE
> (Acu00famulo por sobrevenda RSI 4h, BUY only) u2014 ver secu00e7u00e3o abaixo.

---

## HYPE/USDT u2014 PROMOVIDO para Breakout/Tendu00eancia em 2026-05-28

Ativo de tendu00eancia forte e alta volatilidade. Momentum/breakout u00e9 o encaixe
natural. Validado por teste de robustez (9/9 configs PF>1.3). Stop largo
2.5xATR + trailing (deixa correr). Shadow mode desligado u2014 opera valendo.

---

## LINK/USDT u2014 MACD-only agressivo (mantido)

Backtest 90d: 12 trades, 66.7% WR, PF 3.26. Aprovado.

---

## 2026-06-12 u2014 EXPANSAO: MACD-only Agressivo para TODA a watchlist (exceto PAXG)

MACD-only (cruzamento incluindo abaixo de zero, decisu00e3o consciente) aplicado
a BTC, ETH, SOL, XRP, TRX, BNB, LINK, AAVE. HYPE usa Breakout; PAXG usa Acu00famulo.

---

## 2026-06-14 u2014 INVESTIGACAO DE PERDAS + 2 CORRECOES

CORRECAO 1: bug do trailing stop (commit 9e8b41f).
CORRECAO 2: filtro anti-lateral no MACD-only (commit d51f7a1) u2014 barra entradas
em mercado lateral (EMAs coladas). Foi este filtro que barrou o AAVE 4h em 19/06
("QUASE Lu00c1": RSI 50.3, MACD -0.34, EMAs indecisas).

---

## 2026-06-14 u2014 DECISAO: manter cruzamentos de MACD ABAIXO de zero

Decisu00e3o consciente: MACD-only aceita cruzamento mesmo com MACD < 0 (setup
clu00e1ssico de recuperau00e7u00e3o). O filtro anti-lateral protege contra os falsos.

---

## 2026-06-16 u2014 INVESTIGACAO: 3 residuos do bug do trailing (resolvidos/registrados)

Mantido comportamento atual. BNB 16/06 foi mergulho intra-vela, nu00e3o bug.

---

## 2026-06-19 u2014 BUG CRITICO: ordem REAL saia SEM SL/TP (ATR nao propagado) + piso de volatilidade

### Sintoma
Compra real do TRX/USDT (~$3) executou na Gate.io, mas **sem stop-loss nem
take-profit anexados** u2014 posiu00e7u00e3o nasceu desprotegida. Mesmo com
`EXECUTION_TPSL_ENABLED = True`.

### Causa raiz (cadeia completa)
1. `main.py` calcula o ATR do candle e o expu00f5e em `diag["atr"]` (linha ~113). OK.
2. `evaluate_signal()` (strategies.py) retorna um **dict de sinal SEM a chave `"atr"`**
   (todas as estratu00e9gias: MACD-only, Breakout, Acu00famulo).
3. `qualified_signals` usa apenas `d["signal"]` u2014 o ATR de `diag` **nunca era copiado**
   para o sinal.
4. `executor.build_order()` lia `signal.get("atr") or 0` -> **atr = 0**.
5. O bloco `if EXECUTION_TPSL_ENABLED and price and atr > 0:` ficava **False** ->
   `sl_price = tp_price = None` -> ordem enviada ao relay **sem proteu00e7u00e3o**.

### Causa secundaria (exposta na investigau00e7u00e3o do TRX)
O TRX u00e9 ativo de **baixu00edssima volatilidade**: ATR(14) 1h ~ 0.25% do preu00e7o.
Mesmo com o ATR propagado, `2 x ATR` geraria um stop **coladu00edssimo (~-0.51%)**,
estopado por ruu00eddo de mercado (spread + slippage) em minutos.

### Correcoes (commitadas direto no main, 2026-06-20 ~00:58 BRT)
1. **bot/main.py** (commit 7f3f759): apu00f3s montar `qualified_signals`, propaga
   `diag["atr"] -> sig["atr"]` para TODAS as estratu00e9gias de uma vez (loop
   type-safe: dict OU objeto), com log `[FIX-ATR]` e try/except que nunca
   derruba o scan.
2. **bot/executor.py** (commit d61b9b9):
   - leitura de ATR type-safe em `build_order` (aceita dict ou objeto);
   - **PISO DE VOLATILIDADE**: o stop nunca fica mais perto que
     `EXECUTION_MIN_STOP_PCT` (% do preu00e7o). Se `2 x ATR` < piso, usa o piso.
3. **bot/config.py** (commit 43b7e09): declara `EXECUTION_MIN_STOP_PCT = 0.8`
   (piso default de 0,8% do preu00e7o).

### Efeito pratico (TRX, fill ~0.32220)
| | Antes (bug) | Depois do fix |
|---|---|---|
| ATR chega ao executor | nao (0) | sim |
| SL gerado | None (nu) | sim, **-0,80%** (piso) em vez de -0,51% |
| TP gerado | None | sim (RR 2.0 sobre o risco do piso) |

### Acao manual (paralela)
O TRX ju00e1 em carteira foi **protegido manualmente** na Gate.io pelo usuu00e1rio
(SL ~0.3180 / TP ~0.3290, nu00edveis tu00e9cnicos mais largos que o ATR apertado).

### Pendencia (ainda NAO validada) u2014 ponta PHP
O bot agora **envia** `sl_price`/`tp_price`. A criau00e7u00e3o real dos gatilhos depende
do relay `execute.php` LER esses campos (bloco `price_orders` da Gate.io).
O `test_relay.php` atual **hardcoda o ATR**, o que mascarava o bug.
**Validar no pru00f3ximo sinal real** (ou em teste sem ATR hardcoded): conferir na
Gate.io se SL/TP nasce sozinho e procurar o log `[FIX-ATR]` no "Run bot".

### Kill-switch / ajustes
- `EXECUTION_TPSL_ENABLED = False` -> volta a comprar sem TP/SL (reverte tudo).
- `EXECUTION_MIN_STOP_PCT` -> ajustu00e1vel (subir = stop mais largo p/ baixa vol).
