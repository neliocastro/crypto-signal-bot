"""
MARE ALTA D1 - Estrategia validada em walk-forward (jul/2026). PRODUCAO (live).

Entrada (diario, vela FECHADA):
  - MACD(12,26,9) cruza ACIMA da linha de sinal (valido mesmo abaixo de zero)
  - EMA9 > EMA21 no fechamento do cruzamento
Saida (hibrida - referencia p/ acompanhamento):
  - Stop inicial: 2.5 x ATR(14)
  - TP1: +10% em 50% da posicao -> stop vai a breakeven
  - Restante: trailing 3.0 x ATR
Universo validado: BTC, SOL, TRX, BNB (ETH e XRP reprovados nesta logica).

Validacao (2022-09 -> 2026-07, custos 0.2%):
  carteira PF 1.64 / +240% | walk-forward 3/3 janelas positivas
  OOS cego: PF 2.08 / WR 76% | sobrevive sem os 5 melhores trades

Modulo AUTOCONTIDO: nao altera nenhuma estrategia existente.
Integracao no main.py (1 linha, envolta em try/except la):
    from bot.mare_alta import run_mare_alta
    run_mare_alta(notify=send_telegram)   # apos o scan normal
"""
import json
import os
from typing import Callable, Optional, Dict, Any, List

# ---------------- config / kill-switches ----------------
MARE_ALTA_ENABLED     = True    # False = desliga tudo
MARE_ALTA_SHADOW_MODE = False   # PRODUCAO: sinais vao ao executor (ordens reais)

# UNIVERSO (2026-08-23): ETH e XRP REMOVIDOS.
#   Tres evidencias independentes convergiram contra os dois:
#     1) walk-forward original (jul/2026): reprovados nesta logica
#     2) backtest simplificado 3.8 anos:   ETH PF 0.56 | XRP PF 0.47
#     3) backtest FIEL (stop + TP1 +10% 50% + breakeven + trailing 3xATR),
#        ~1400 candles D1 por ativo:       ETH PF 0.43 (-38%) | XRP PF 0.55 (-16%)
#   Os 4 mantidos, no mesmo teste fiel (stop 2.5x):
#        BTC PF 1.28 | SOL PF 4.51 | TRX PF 2.21 | BNB PF 2.15
#   O trailing AMPLIFICA quem tem tendencia real (SOL 1.81 -> 4.51) e nao
#   salva quem serpenteia (ETH 0.56 -> 0.43). Detalhes e ressalvas de amostra
#   (XRP tem apenas 6 trades no periodo) em docs/revisao_ativos_2026-08.md.
#   ROLLBACK: basta reinserir "ETH/USDT" e "XRP/USDT" na lista abaixo.
MARE_ALTA_UNIVERSE    = ["BTC/USDT", "SOL/USDT", "TRX/USDT", "BNB/USDT"]

MARE_ALTA_TIMEFRAME   = "1d"
MARE_ALTA_STOP_ATR    = 2.5
MARE_ALTA_TRAIL_ATR   = 3.0
MARE_ALTA_TP1_PCT     = 0.10    # +10%
MARE_ALTA_TP1_FRAC    = 0.5     # vende 50% no TP1

_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "state", "mare_alta_state.json"
)

# ---------------- indicadores (puros, sem dependencia externa) ----------------
def _ema(vals: List[float], n: int) -> List[float]:
    k = 2.0 / (n + 1.0)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out

def _atr(h: List[float], l: List[float], c: List[float], p: int = 14) -> List[float]:
    trs = [h[0] - l[0]]
    for i in range(1, len(c)):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1])))
    a = 1.0 / p
    out = [trs[0]]
    for t in trs[1:]:
        out.append(t * a + out[-1] * (1.0 - a))
    return out

# ---------------- estado (anti-duplicata entre scans) ----------------
def _load_state() -> Dict[str, Any]:
    try:
        with open(_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(st: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w") as f:
            json.dump(st, f, indent=2)
    except Exception:
        pass  # degradacao segura: nunca derruba o scan

# ---------------- nucleo do sinal ----------------
def check_mare_alta(ohlcv: List[List[float]]) -> Optional[Dict[str, Any]]:
    """Recebe OHLCV diario [[ts,o,h,l,c,v],...]; avalia a ULTIMA VELA FECHADA
    (indice -2). Retorna dict do sinal ou None."""
    if not ohlcv or len(ohlcv) < 40:
        return None
    closes = [r[4] for r in ohlcv]
    highs  = [r[2] for r in ohlcv]
    lows   = [r[3] for r in ohlcv]
    e9,  e21 = _ema(closes, 9),  _ema(closes, 21)
    e12, e26 = _ema(closes, 12), _ema(closes, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    sig  = _ema(macd, 9)
    atr  = _atr(highs, lows, closes, 14)

    i = len(closes) - 2  # ultima vela FECHADA
    cross_up = macd[i-1] <= sig[i-1] and macd[i] > sig[i]
    if not (cross_up and e9[i] > e21[i]):
        return None

    entry = closes[i]
    return {
        "strategy":  "MARE_ALTA_D1",
        "side":      "BUY",
        "candle_ts": int(ohlcv[i][0]),
        "timestamp": int(ohlcv[i][0]),  # compat executor._signal_id (idempotencia por vela D1)
        "entry_ref": entry,
        "price": entry,              # compat executor._ref_price
        "stop":      round(entry - MARE_ALTA_STOP_ATR * atr[i], 8),
        "tp1":       round(entry * (1.0 + MARE_ALTA_TP1_PCT), 8),
        "atr":       round(atr[i], 8),
        "macd_below_zero": macd[i] < 0,
        "shadow":    MARE_ALTA_SHADOW_MODE,
    }

def _format_msg(symbol: str, s: Dict[str, Any]) -> str:
    tag  = "[SHADOW] " if s["shadow"] else ""
    zero = " (MACD ainda <0: entrada antecipada)" if s["macd_below_zero"] else ""
    return (
        f"\U0001F30A [MARE ALTA D1] {tag}Sinal de COMPRA: {symbol}{zero}\n"
        f"Entrada ref (fech. D1): {s['entry_ref']}\n"
        f"Stop inicial (2.5xATR): {s['stop']}\n"
        f"TP1 +10% (vende 50%):   {s['tp1']}\n"
        f"Apos TP1: stop -> breakeven + trailing 3xATR no restante"
    )

# ---------------- entrypoint ----------------
def run_mare_alta(notify: Optional[Callable[[str], Any]] = None,
                  exchange=None) -> List[Dict[str, Any]]:
    """Roda o scan D1 da Mare Alta. Autocontido e com degradacao segura:
    qualquer erro e engolido (logado) para nunca derrubar o scan principal."""
    signals: List[Dict[str, Any]] = []
    if not MARE_ALTA_ENABLED:
        return signals
    try:
        if exchange is None:
            import ccxt
            exchange = ccxt.gateio({"enableRateLimit": True})
        state = _load_state()
        for symbol in MARE_ALTA_UNIVERSE:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, MARE_ALTA_TIMEFRAME, limit=60)
                sig = check_mare_alta(ohlcv)
                if sig is None:
                    continue
                key = symbol.replace("/", "_")
                if state.get(key) == sig["candle_ts"]:
                    continue  # ja alertado nesta vela
                state[key] = sig["candle_ts"]
                sig["symbol"] = symbol
                signals.append(sig)
                msg = _format_msg(symbol, sig)
                if notify is not None:
                    try:
                        notify(msg)
                    except Exception as e:
                        print(f"[MARE_ALTA] notify falhou: {e}")
                print(msg)
            except Exception as e:
                print(f"[MARE_ALTA] {symbol}: erro ignorado -> {e}")
        _save_state(state)
    except Exception as e:
        print(f"[MARE_ALTA] erro geral ignorado -> {e}")
    return signals

if __name__ == "__main__":
    run_mare_alta()
