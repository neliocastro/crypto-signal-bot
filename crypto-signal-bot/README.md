# Crypto Signal Bot 🤖

Bot serverless que escaneia mercados cripto a cada 15 minutos e envia sinais qualificados ao Telegram.

## Stack
- **ccxt** (Gate.io, agnóstico)
- **pandas-ta** (RSI, MACD, EMA, ATR)
- **GitHub Actions** (cron grátis)

## Estratégia ativa
MACD + EMA200 no timeframe 1H, perfil Moderado (Conf ≥ 6, R:R ≥ 1:2).

## Adicionar moedas
Edite `bot/config.py` → `WATCHLIST` → `git push`.