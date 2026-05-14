from datetime import datetime
from .config import SYMBOLS, TIMEFRAME, EXCHANGE_ID
from .data_fetcher import fetch_ohlcv
from .indicators import enrich
from .strategies import evaluate
from .sentiment import fear_and_greed
from .telegram_sender import send_message, format_signal, format_scan_summary

def run():
    fg = fear_and_greed()
    signals = []
    diagnostics = []

    for symbol in SYMBOLS:
        try:
            df = fetch_ohlcv(symbol, TIMEFRAME, limit=300)
            df = enrich(df)
            last = df.iloc[-1]

            # Diagnóstico do ativo (sempre coletado)
            diagnostics.append({
                "symbol": symbol,
                "price": float(last["close"]),
                "rsi": float(last.get("RSI_14", float("nan"))),
                "macd": float(last.get("MACD_12_26_9", float("nan"))),
                "macd_signal": float(last.get("MACDs_12_26_9", float("nan"))),
                "macd_hist": float(last.get("MACDh_12_26_9", float("nan"))),
                "ema200": float(last.get("EMA_200", float("nan"))),
            })

            # Avaliação de setup
            sig = evaluate(symbol, df)
            if sig:
                signals.append(sig)

        except Exception as e:
            diagnostics.append({"symbol": symbol, "error": str(e)})

    # Envia sinais (se houver)
    for sig in signals:
        send_message(format_signal(sig, fg))

    # Sempre envia o resumo diagnóstico
    send_message(
        format_scan_summary(
            diagnostics=diagnostics,
            signals_count=len(signals),
            fg=fg,
            timeframe=TIMEFRAME,
            exchange=EXCHANGE_ID,
        )
    )

if __name__ == "__main__":
    run()
