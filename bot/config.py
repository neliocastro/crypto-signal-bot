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
