# 🧪 Backtest MACD Crossover — Modo Agressivo

- **Data:** 2026-05-21T00:55:53.697723+00:00
- **Horizonte:** 720 candles (1h)
- **Saída:** SL 1.5×ATR · TP 3.0×ATR · timeout 48 barras
- **Filtros entrada:** MACD cross above · preço > EMA200 · 40 ≤ RSI ≤ 70

## 📊 Resultados por ativo

| Ativo | Trades | WinRate | PF | Expect | MaxDD | TP/SL/TO | Veredicto |
|---|---:|---:|---:|---:|---:|---|:---:|
| `BTC/USDT` | 9 | 33.3% | 0.94 | -0.03% | -2.3% | 3/6/0 | ❌ rejected |
| `ETH/USDT` | 7 | 42.9% | 1.07 | +0.04% | -2.8% | 3/4/0 | ❌ rejected |
| `SOL/USDT` | 7 | 42.9% | 1.22 | +0.15% | -2.6% | 3/4/0 | ❌ rejected |
| `XRP/USDT` | 7 | 28.6% | 0.93 | -0.04% | -3.1% | 2/5/0 | ❌ rejected |
| `TRX/USDT` | 14 | 35.7% | 1.06 | +0.02% | -1.8% | 5/9/0 | ❌ rejected |
| `BNB/USDT` | 7 | 57.1% | 2.48 | +0.50% | -1.4% | 4/3/0 | ⭐ approved |
| `LINK/USDT` | 9 | 77.8% | 5.91 | +1.51% | -1.5% | 7/2/0 | ⭐ approved |
| `HYPE/USDT` | 8 | 62.5% | 4.89 | +1.56% | -1.9% | 5/3/0 | ⭐ approved |
| `AAVE/USDT` | 7 | 42.9% | 1.19 | +0.18% | -2.2% | 3/4/0 | ❌ rejected |
| `PAXG/USDT` | 6 | 33.3% | 0.58 | -0.14% | -1.4% | 2/4/0 | ❌ rejected |

## 🌐 Agregado (todos os ativos)

- **Trades totais:** 81
- **Win rate:** 45.7%
- **Profit factor:** 1.81
- **Expectancy:** +0.382% por trade
- **Retorno total acumulado:** +30.97%
- **Drawdown máximo:** -5.08%

## ✅ Recomendação para perfil AGRESSIVO

- ⭐ **Aprovados** (PF≥1.5 & WR≥55%): `BNB/USDT`, `LINK/USDT`, `HYPE/USDT`
- ⚠️ **Limítrofes:** — nenhum
- ❌ **Rejeitados:** `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `XRP/USDT`, `TRX/USDT`, `AAVE/USDT`, `PAXG/USDT`

> Gerado automaticamente por `scripts/backtest_macd.py`. Reproduza via workflow `backtest.yml`.
