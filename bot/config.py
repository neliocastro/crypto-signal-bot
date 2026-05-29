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
        "approved_symbols":  ["LINK/USDT"],  # HYPE migrado p/ estrategia Breakout/Tendencia
        "min_confidence":    5,
    },
    "conservador": {
        "macd_cross_enough": False,
        "approved_symbols":  None,
        "min_confidence":    8,
    },
}
ACTIVE_PROFILE = "agressivo"   # troque para "agressivo" para ativar LINK+HYPE em MACD-only ou volte para "balanceado"


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
BREAKOUT_SHADOW_MODE = True
BREAKOUT_SYMBOLS = {
    "HYPE/USDT": {"lookback": 30, "atr_mult": 2.5},
}


# ============ DASHBOARD (Fase C2) ============
# Kill switch para gerar docs/data/latest.json a cada scan.
DASHBOARD_ENABLED = False
