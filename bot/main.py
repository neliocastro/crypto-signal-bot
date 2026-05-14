"""
Orquestrador principal — executado pelo GitHub Actions a cada 15 min.
"""
import json
import os
import traceback
from datetime import datetime, timezone, timedelta

from . import config
from .data_fetcher import fetch_ohlcv
from .indicators import enrich
from .strategies import evaluate
from .sentiment import fear_and_greed
from .telegram_sender import send, format_signal

# Liga/desliga heartbeat (mensagem quando NÃO há sinais).
# Para a fase de testes, deixe True. Depois mude para False.
SEND_HEARTBEAT = True

def load_state():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def should_send(symbol: str, side: str, candle_ts: str, state: dict) -> bool:
    """Evita reenviar o mesmo sinal dentro do cooldown."""
    key = f"{symbol}:{side}"
    last = state.get(key)
    if not last:
        return True
    last_time = datetime.fromisoformat(last["sent_at"])
    if datetime.now(timezone.utc) - last_time < timedelta(hours=config.SIGNAL_COOLDOWN_HOURS):
        return False
    return True

def mark_sent(symbol: str, side: str, candle_ts: str, state: dict):
    key = f"{symbol}:{side}"
    state[key] = {
        "candle": candle_ts,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

def run():
    print(f"=== Scan iniciado: {datetime.now(timezone.utc).isoformat()} ===")
    state = load_state()
    fg = fear_and_greed()
    signals_found = 0
    checked = 0

    for symbol in config.WATCHLIST:
        try:
            print(f"→ {symbol}")
            df = fetch_ohlcv(symbol)
            df = enrich(df)
            sig = evaluate(symbol, df)
            checked += 1

            if sig and should_send(symbol, sig.side, sig.timestamp, state):
                msg = format_signal(sig, fg)
                if send(msg):
                    mark_sent(symbol, sig.side, sig.timestamp, state)
                    signals_found += 1
                    print(f"  ✅ Sinal {sig.side} enviado (conf {sig.confidence}/10)")
            elif sig:
                print(f"  ⏸ Sinal {sig.side} em cooldown")
            else:
                print(f"  · Sem setup")
        except Exception as e:
            print(f"  ❌ Erro em {symbol}: {e}")
            traceback.print_exc()

    save_state(state)

    if SEND_HEARTBEAT and signals_found == 0:
        from .telegram_sender import send_heartbeat
        send_heartbeat(checked, signals_found, fg)

    print(f"=== Fim: {signals_found}/{checked} sinais ===")

if __name__ == "__main__":
    run()