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
WATCHLIST = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "TRX/USDT",
    "BNB/USDT",
    "LINK/USDT",
    "HYPE/USDT",
    "AAVE/USDT",
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

# ============ PERFIS DE RISCO (Fase A — MACD-only candidato) ============
# Default: "balanceado" = comportamento atual (zero mudanca).
# Para ativar modo agressivo (MACD-only nos ativos validados pelo backtest 90d):
#   ACTIVE_PROFILE = "agressivo"
# E faca git push. Para reverter, troque de volta para "balanceado".
#
# Validacao backtest 90d (2026-05-21):
#   LINK/USDT: 12 trades, 66.7% WR, PF 3.26  (approved)
#   HYPE/USDT:  9 trades, 55.6% WR, PF 3.45  (approved)
RISK_PROFILES = {
    "balanceado": {
        "macd_cross_enough": False,
        "approved_symbols":  None,
        "min_confidence":    6,
    },
    "agressivo": {
        "macd_cross_enough": True,
        # None = TODOS os ativos da watchlist usam MACD-only.
        # Excecoes ja sao interceptadas ANTES no evaluate_signal:
        #   HYPE -> Breakout (fast-path 1)  |  PAXG -> Acumulacao (fast-path 2)
        # Alem disso, MACD_ONLY_EXCLUDE garante que PAXG nunca caia aqui.
        "approved_symbols":  None,
        "min_confidence":    5,
    },
    "conservador": {
        "macd_cross_enough": False,
        "approved_symbols":  None,
        "min_confidence":    8,
    },
}
ACTIVE_PROFILE = "agressivo"   # "agressivo" = MACD-only em TODOS (exceto exclusoes); "balanceado" reverte

# Ativos que NUNCA usam MACD-only mesmo com approved_symbols=None.
# PAXG e ouro digital: estrategia propria de Acumulacao RSI 4h (compra-only).
MACD_ONLY_EXCLUDE = {"PAXG/USDT"}


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
BREAKOUT_ENABLED = True
BREAKOUT_SHADOW_MODE = False
BREAKOUT_SYMBOLS = {
    "HYPE/USDT": {"lookback": 30, "atr_mult": 2.5},
}


# ============ ACUMULACAO (PAXG - ouro digital) ============
# Estrategia de ACUMULO por sobrevenda (BUY only, sem stop nem alvo de venda).
# Dispara quando o RSI CRUZA p/ baixo do threshold no timeframe definido
# (entrada na zona de sobrevenda). Cooldown evita spam enquanto o RSI fica
# preso na zona. Pensado p/ ativo de reserva de valor: DCA inteligente.
#   rsi_extreme -> destaque "sobrevenda extrema" (oportunidade rara).
# ACCUMULATION_ENABLED=False -> kill switch (PAXG fica sem sinal de acumulo).
ACCUMULATION_ENABLED = True
ACCUMULATION_SYMBOLS = {
    "PAXG/USDT": {
        "timeframe":      "4h",
        "rsi_threshold":  30.0,
        "rsi_extreme":    20.0,
        "cooldown_hours": 24,
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
EXECUTION_DRY_RUN       = False      # GO-LIVE MINIMO: ordens REAIS (teto $5, stop $10/dia)
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
EXECUTION_MAX_NOTIONAL_USDT = 5.0    # nunca envia ordem acima de $5
EXECUTION_MIN_NOTIONAL_USDT = 3.0    # piso: Gate.io rejeita ordem < $3 (too small)
EXECUTION_MAX_OPEN          = 2      # no maximo 2 posicoes live ao mesmo tempo
EXECUTION_MAX_TRADES_DAY    = 6      # no maximo 6 ordens/dia
EXECUTION_DAILY_LOSS_STOP   = 10.0   # kill-switch: para tudo se perder $10 no dia
EXECUTION_STATE_FILE        = "state/execution_guard.json"  # contadores diarios

# Arquivo da "intencao" (lado cerebro). O HMAC secret vem de env
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
