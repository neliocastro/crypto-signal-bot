# 🧪 Backtest MACD Crossover

Script: [`scripts/backtest_macd.py`](../scripts/backtest_macd.py)
Workflow: [`.github/workflows/backtest.yml`](../.github/workflows/backtest.yml)

## Para que serve

Testa, contra histórico real (~30 dias), o sinal de **MACD cross above signal** como entrada candidata ao perfil **agressivo** do bot. Responde:

> "Se a única regra de entrada fosse o MACD cruzando acima, qual o win rate, profit factor e drawdown nos meus 10 ativos?"

## Como rodar

1. GitHub → **Actions** → **backtest** → **Run workflow** → branch `main`.
2. Aguarde ~3-5 min.
3. Veja o resultado em [`docs/backtest_report.md`](backtest_report.md).
4. JSON detalhado em [`state/backtest_results.json`](../state/backtest_results.json).

## Critérios de classificação por ativo

| Categoria | WinRate | Profit Factor |
|---|---|---|
| ⭐ Aprovado | ≥ 55% | ≥ 1.5 |
| ⚠️ Limítrofe | ≥ 50% | ≥ 1.2 |
| ❌ Rejeitado | < 50% | < 1.2 |
| — Sem dados | < 5 trades | — |

## Parâmetros (modo rápido AAA)

- Horizonte: **30 dias** (720 candles 1h)
- Entrada: MACD cross above + preço > EMA200 + 40 ≤ RSI ≤ 70
- Saída: SL 1.5×ATR · TP 3.0×ATR · timeout 48 barras
- Fonte: Gate.io (via `bot.data_fetcher.fetch_ohlcv`)

## Próximo passo

Se o agregado for **PF≥1.5 e WR≥55% em pelo menos 5 ativos**, o sistema de **perfis** (Fase A) será implementado, restringindo o modo agressivo aos ativos aprovados.
