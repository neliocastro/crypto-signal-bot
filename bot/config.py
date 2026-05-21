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
    "PAXG/USDT",
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
        "approved_symbols":  ["LINK/USDT", "HYPE/USDT"],
        "min_confidence":    5,
    },
    "conservador": {
        "macd_cross_enough": False,
        "approved_symbols":  None,
        "min_confidence":    8,
    },
}
ACTIVE_PROFILE = "agressivo"   # troque para "agressivo" para ativar LINK+HYPE em MACD-only ou volte para "balanceado"


# ============ DASHBOARD (Fase C2) ============
# Kill switch para gerar docs/data/latest.json a cada scan.
DASHBOARD_ENABLED = False
