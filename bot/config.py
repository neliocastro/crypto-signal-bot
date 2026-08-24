"""
Configuração central do bot.
Para adicionar/remover moedas: edite WATCHLIST e dê git push.
"""

# ============ EXCHANGE ============
# Agnóstico: troque por 'binance', 'kraken', 'okx', 'bybit', etc.
# A sintaxe ccxt é idêntica para todas.
EXCHANGE_ID = "gateio"

# ============ WATCHLIST ============
# Formato ccxt: BASE/QUOTE
#
# FONTE DE VERDADE UNICA (2026-08-24): esta lista define o universo de scan.
# Antes state/runtime_config.json sobrescrevia isto e vencia - mas ele e um
# ARTEFATO GERADO (o job commita state/ por cima a cada scan), entao watchlist
# editada la se perdia em ~5min. Pior: o PAXG havia sumido do runtime e o
# fast-path de acumulo virou codigo morto silencioso por ~2 meses.
# runtime_config._static_watchlist() agora forca esta lista.
# Ver docs/watchlist_runtime_2026-08-24.md
#
# ETH e XRP REMOVIDOS (2026-08-24): fora do universo do Mare Alta D1 desde
# 2026-08-23 (PF 0.43 e 0.55 no backtest fiel) e sem fast-path proprio ->
# nenhuma rota ate ordem real. Ficavam so para diagnostico MTF no Telegram, ao
# custo de ~6 fetches/scan. Trade-off assumido: perde-se a visibilidade deles
# no resumo. ROLLBACK: reinserir as duas linhas aqui e dar push.
WATCHLIST = [
    "BTC/USDT",
    "SOL/USDT",
    "TRX/USDT",
    "BNB/USDT",
    "HYPE/USDT",       # breakout / tendencia (fast-path)
    "PAXG/USDT",       # acumulo RSI 4h (ouro digital) - sem alvo de venda
]

# ============ TIMEFRAME ============
TIMEFRAME = "1h"
CANDLES_LIMIT = 300  # histórico suficiente para EMA200 + buffer

# ============ PERFIL DE RISCO ============
PROFILE = {
    "nome": "Moderado",
    "confianca_minima": 6,        # 1-10
    "rr_minimo": 2.0,             # Risco/Retorno 1:2
    "atr_multiplier_sl": 1.5,     # Stop = 1.5 * ATR
    "tp1_rr": 2.0,                # TP1 em R:R 1:2
    "tp2_rr": 3.0,                # TP2 em R:R 1:3
}

# ============ INDICADORES ============
INDICATORS = {
    "ema_curto": 9,
    "ema_medio": 21,
    "ema_longo": 50,
    "ema_tendencia": 200,
    "rsi_periodo": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_periodo": 14,
}

# ============ MULTI-TIMEFRAME (Fase 2b) ============
# True = aplica filtros 4h (tendencia) + 15m (pullback) no evaluate_signal
# False = comportamento legado (so 1h). Kill switch seguro.
MTF_ENABLED = True
# Fase 2c.1: paralelizacao dos 3 timeframes via ThreadPoolExecutor.
# Reduz tempo de fetch_multi_tf de ~15s para ~5-6s por ativo.
# Desligue (False) se observar rate-limit ou bugs intermitentes.
MTF_PARALLEL_FETCH = True

# ============ SCAN PARALELO (Fase D) ============
# Paraleliza o scan dos ATIVOS (nao so dos timeframes). Maior ganho de
# velocidade: scan de ~3min (10+ ativos sequenciais) cai p/ ~30-45s.
# SCAN_PARALLEL=False -> volta ao loop sequencial (kill switch seguro).
# SCAN_MAX_WORKERS    -> ativos simultaneos. Cuidado: cada ativo dispara
#   ate 3 fetches (MTF), entao workers altos podem gerar rate-limit na
#   exchange. 5 e um equilibrio seguro p/ a watchlist atual.
SCAN_PARALLEL = True
SCAN_MAX_WORKERS = 5

# ============ ANTI-SPAM ============
# Não reenvia o mesmo sinal antes desse cooldown (em horas).
SIGNAL_COOLDOWN_HOURS = 4

# ============ ARQUIVOS DE ESTADO ============
STATE_FILE = "state/last_signals.json"

# ============ ALIASES DE COMPATIBILIDADE ============
SYMBOLS          = WATCHLIST
EXCHANGE         = EXCHANGE_ID
CANDLE_LIMIT     = CANDLES_LIMIT
INTERVAL         = TIMEFRAME          # caso main use INTERVAL
COOLDOWN_HOURS   = SIGNAL_COOLDOWN_HOURS
RISK_PROFILE     = PROFILE
INDICATOR_CONFIG = INDICATORS

# ============ PERFIS DE RISCO — REMOVIDO em 2026-08-24 ============
# RISK_PROFILES / ACTIVE_PROFILE / MACD_ONLY_EXCLUDE foram REMOVIDOS junto com
# a estrategia MACD-only (_check_aggressive_macd) e o caminho legado
# (Integrada / Tendencia MACD / Confluencia) em bot/strategies.py.
#
# MOTIVO: o perfil "agressivo" (approved_symbols=None) fazia BTC/ETH/SOL/XRP/
# TRX/BNB rodarem MACD-only a cada scan, e 100% desses sinais eram descartados
# pelo INTRADAY_EXEC_ALLOWLIST do main.py. Custo de CPU e rate-limit sem
# nenhuma ordem possivel. O caminho legado, por sua vez, era inalcancavel.
#
# ROTEAMENTO ATUAL (unico):
#   Mare Alta D1 (bot/mare_alta.py) -> BTC, SOL, TRX, BNB
#   Breakout / Tendencia            -> HYPE (BREAKOUT_SYMBOLS)
#   Acumulo (RSI sobrevenda)        -> PAXG (ACCUMULATION_SYMBOLS)
#   Demais ativos no scan 1h        -> apenas diagnostico no Telegram
#
# Ver docs/limpeza_estrategias_2026-08-24.md. Rollback: git revert do commit.

# ============ BREAKOUT / TREND-FOLLOWING (HYPE) ============
# Estrategia de tendencia validada por teste de robustez (2026-05-28):
#   HYPE/USDT lb=30 atr=2.5 -> PF 2.55, +67% em ~150d, MDD -16.9%.
#   Robusto a parametros (9/9 configs PF>1.3); 2/3 janelas lucrativas.
#   Risco: retorno concentrado em 2-3 trades grandes (natureza trend-following).
# Entrada: EMA9>EMA21>EMA50 + rompe maxima de `lookback` velas + RSI>50.
# Saida: stop largo atr_mult*ATR + trailing stop manual (deixa correr).
#
# BREAKOUT_SHADOW_MODE=True -> sinal marcado [SHADOW] para observacao
#   (2-4 semanas) antes de confiar 100%. Troque para False para operar valendo.
# BREAKOUT_ENABLED=False    -> kill switch: desliga o breakout (HYPE fica sem sinal).
#
# DESEMPENHO REAL (2026-08-23, state/positions.jsonl): 12 trades, WR 25%,
#   PF 0.60 - MUITO abaixo do backtest (2.55). Diagnostico: o stop de 2.0xATR
#   aplicado pelo executor estava dentro do ruido intraday. Ver mudanca em
#   EXECUTION_ATR_MULT_SL abaixo e docs/ajuste_stop_2026-08.md.
BREAKOUT_ENABLED = True
BREAKOUT_SHADOW_MODE = False
BREAKOUT_SYMBOLS = {
    "HYPE/USDT": {"lookback": 30, "atr_mult": 2.5},
}

# REAVALIACAO DE REENTRADA (2026-08-12) - LINK e SOL REPROVADOS:
#   Backtest 165d (01/03-13/08, 3961 candles 1h, fee 0.1% i/v, split de robustez):
#     SOL  breakout PF 0.44 (-25.7%) | MACD PF 0.79 (-10.8%) -> sem edge em nenhuma
#     LINK breakout PF 0.77 (-9.8%)  | MACD PF 1.08 total, MAS decaiu: H1 2.24 -> H2 0.60
#   O edge historico do LINK (PF 3.26 no backtest de maio) MORREU na metade recente.
#   Controle HYPE breakout: PF 1.49 total, positivo nas 2 metades (1.64/2.06).
#   Decisao do usuario: NAO reentrar nenhum dos dois; concentrar no que tem edge.

# ============ ACUMULACAO (PAXG - ouro digital) ============
# Estrategia de ACUMULO por sobrevenda (BUY only, sem stop nem alvo de venda).
# Dispara quando o RSI CRUZA p/ baixo do threshold no timeframe definido
# (entrada na zona de sobrevenda). Cooldown evita spam enquanto o RSI fica
# preso na zona. Pensado p/ ativo de reserva de valor: DCA inteligente.
#   rsi_extreme -> destaque "sobrevenda extrema" (oportunidade rara).
# ACCUMULATION_ENABLED=False -> kill switch (PAXG fica sem sinal de acumulo).
#
# CORRIGIDO (2026-08-24): a nota anterior dizia "ZERO disparos em ~2 meses (o
# RSI 4h nao cruzou 30). Mantido: e uma estrategia rara por design." ERRADO -
# o PAXG estava FORA da watchlist efetiva (runtime), entao evaluate_signal
# nunca era chamado para ele e este fast-path era INALCANCAVEL. Nao era
# raridade estatistica, era codigo morto. Com a watchlist unificada em
# config.py, a estrategia passa a ser avaliada de fato pela primeira vez.
# ATENCAO: acumulo compra SEM stop-loss (BUY only). Travas de capital abaixo
# (teto $10/ordem, max 10/dia, stop $20/dia) continuam valendo.
ACCUMULATION_ENABLED = True
ACCUMULATION_SYMBOLS = {
    "PAXG/USDT": {
        "timeframe":      "4h",
        "rsi_threshold":  30.0,
        "rsi_extreme":    20.0,
        "cooldown_hours": 12,
    },
}
ACCUMULATION_STATE_FILE = "state/accumulation_signals.json"

# ============ DASHBOARD (Fase C2) ============
# Kill switch para gerar docs/data/latest.json a cada scan.
DASHBOARD_ENABLED = False

# ============ EXECUCAO (Fase 1 - DRY-RUN / paper trading) ============
# Camada de execucao agnostica de estrategia. Em Fase 1 NADA e executado de
# verdade: executor.py monta a "intencao", assina com HMAC e (se houver relay)
# envia ao PHP, que tambem esta em dry-run. Sem relay configurado, so registra
# a intencao em state/paper_trades.jsonl. Cinto duplo de seguranca:
#   EXECUTION_DRY_RUN=True  +  EXECUTION_RELAY_URL vazio  -> ordem real impossivel.
#
# Kill switches:
#   EXECUTION_ENABLED       -> liga/desliga a camada inteira (False = inerte).
#   EXECUTION_DRY_RUN       -> True na Fase 1 (jamais envia ordem real).
#   EXECUTION_PCT           -> fracao do saldo USDT por ordem (0.10 = 10%).
#   EXECUTION_RELAY_URL     -> URL https do braco PHP (vazio = so loga local).
#   EXECUTION_PAPER_BALANCE -> saldo USDT assumido p/ dimensionar no dry-run.
EXECUTION_ENABLED       = True
EXECUTION_DRY_RUN       = False     # GO-LIVE: ordens REAIS (teto $10/ordem, stop $20/dia, max 10/dia)
EXECUTION_PCT           = 0.02   # go-live minimo: 2% do saldo por ordem
EXECUTION_RELAY_URL     = "https://ineo.com.br/cryptosignals/execute.php"  # relay live (HMAC+IP whitelist)
EXECUTION_PAPER_BALANCE = 1000.0    # USDT hipoteticos (sizing do paper trading)

# ============ PROTECOES DE CAPITAL (go-live minimo / canario) ============
# Travas RIGIDAS aplicadas no executor.py ANTES de qualquer envio ao relay.
# Pensadas para "testar o mundo real" com perda insignificante.
#   EXECUTION_MAX_NOTIONAL_USDT -> teto absoluto por ordem (igual ao do PHP).
#   EXECUTION_MAX_OPEN          -> maximo de posicoes live simultaneas.
#   EXECUTION_MAX_TRADES_DAY    -> maximo de ordens enviadas por dia (UTC).
#   EXECUTION_DAILY_LOSS_STOP   -> se a perda do dia (USDT) atingir isto, PARA.
EXECUTION_MAX_NOTIONAL_USDT = 10.0   # DEGRAU 2 (2026-08-12): $5 -> $10 apos infra provada em 9 trades; proximo degrau ($20) SO no 20o trade com P&L>0 e PF>=1 ex-ETH. AUDITORIA 23/08: 3 de 3 criterios FALHAM (14 trades, P&L -$0.23 ex-ETH, PF 0.60) -> NAO subir.
EXECUTION_MIN_NOTIONAL_USDT = 3.0    # piso: Gate.io rejeita ordem < $3 (too small)
# --- Saida automatica (TP/SL nativos na Gate.io, anexados a cada compra) ---
#
# EXECUTION_ATR_MULT_SL: 2.0 -> 2.5 em 2026-08-23. DUAS razoes:
#   (a) ALINHAMENTO: o mare_alta.py sempre documentou stop de 2.5xATR, mas quem
#       calcula o stop da ordem REAL e este parametro (que estava em 2.0). O D1
#       operava mais apertado que a estrategia validada. Agora bate.
#   (b) EVIDENCIA: backtest fiel (stop + TP1 +10% 50% + BE + trailing 3xATR),
#       ~1400 candles D1 por ativo -> 2.5x supera 3.0x em 5 dos 6 ativos
#       (BTC 1.28 vs 1.07 | SOL 4.51 vs 3.77 | TRX 2.21 vs 2.13 | BNB 2.15 vs 1.79).
#       No HYPE 1h (180d): PF 1.18 (2.0x) -> 1.31 (2.5x) -> 1.50 (3.0x).
#   Escolha: 2.5x melhora os DOIS trilhos. O otimo do HYPE (3.0x) exigiria um
#   override por simbolo no executor.build_order() - commit isolado, ainda nao
#   feito. Ver docs/decisao_stop_e_universo_2026-08-23.md.
#   ROLLBACK: volte para 2.0.
EXECUTION_ATR_MULT_SL = 2.5    # Stop-Loss = entrada - (mult * ATR)
EXECUTION_TP_RR       = 2.0    # Take-Profit = entrada + (RR * risco). RR 2.0 = alvo 2x o risco
EXECUTION_TPSL_ENABLED = True  # kill-switch: False = volta a comprar sem TP/SL
EXECUTION_MIN_STOP_PCT = 0.8   # piso de afastamento do stop (% do preco). Bug TRX: ATR baixo (0.25%) gerava stop coladissimo (-0.5%) -> ruido estopava
EXECUTION_MAX_OPEN          = 10      # no maximo 10 posicoes live ao mesmo tempo
EXECUTION_MAX_TRADES_DAY    = 10      # no maximo 10 ordens/dia
EXECUTION_DAILY_LOSS_STOP   = 20.0   # kill-switch: para tudo se perder $20 no dia
EXECUTION_STATE_FILE        = "state/execution_guard.json"  # contadores diarios

# Arquivo da "intencao" (lado cerebrod). O HMAC secret vem de env
# (GitHub Secret EXECUTION_HMAC_SECRET); NUNCA fica no codigo.
PAPER_TRADES_FILE = "state/paper_trades.jsonl"

# ============ AVALIACAO DO DRY-RUN (paper_evaluator) ============
# Mede o que TERIA acontecido (P&L hipotetico, win-rate, slippage) ESPELHANDO
# a estrategia de cada sinal. Relatorio automatico no Telegram a cada N dias.
#   PAPER_EVAL_ENABLED         -> kill switch da avaliacao.
#   PAPER_REPORT_INTERVAL_DAYS -> cadencia do relatorio (dias).
PAPER_EVAL_ENABLED         = True
PAPER_REPORT_INTERVAL_DAYS = 7
PAPER_POSITIONS_FILE       = "state/paper_positions.json"

# ============ MARE ALTA - TRAILING D1 (bot/mare_alta_trailing.py) ============
# Trailing sintetico por ATR no diario: sobe o stop (CATRACA, nunca rebaixa)
# via acao "update_trailing" no relay PHP (cria novo stop -> confirma -> deleta
# o antigo; se falhar, o antigo e MANTIDO). Ligado em 2026-07-04.
MARE_ALTA_TRAILING_ENABLED = True   # kill-switch do trailing D1
MARE_ALTA_SL_ATR_MULT      = 3.0    # stop = close_D1 - 3.0 * ATR(D1)
MARE_ALTA_ATR_PERIOD       = 14     # periodo do ATR diario
MARE_ALTA_SYMBOLS          = []     # vazio = qualquer posicao aberta registrada

# ============ OCO GUARD - emulacao de OCO (bot/oco_guard.py) ============
# A Gate.io NAO tem OCO nativo no spot: TP e SL sao price_orders INDEPENDENTES,
# e quando uma perna dispara a outra fica orfa (casos reais: TPs do HYPE 27/07,
# SL do ETH 11/08). O guard reconcilia pares TP<->SL a cada scan via acao
# "oco_sync" do relay: consulta o status REAL na API e, se uma perna disparou
# (finish) e a oposta segue open, cancela a sobrevivente e fecha a posicao
# local (closed_tp/closed_sl). EM PRODUCAO desde 2026-08-11, validado por
# smoke test (ver docs/gateio_limitacoes.md, secao 7).
# LIMITE: so reconcilia pares registrados em state/positions.jsonl (ordens do
# bot). Ordens MANUAIS criadas na corretora NAO sao cobertas.
# Degradacao segura: falha nunca derruba o scan; nunca cria ordem.
OCO_GUARD_ENABLED = True   # kill-switch do OCO emulado
