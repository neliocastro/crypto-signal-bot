# 🧪 Backtest MACD Crossover — Modo Agressivo

- **Data:** 2026-05-21T01:10:46.700059+00:00
- **Horizonte:** 2160 candles (1h)
- **Saída:** SL 1.5×ATR · TP 3.0×ATR · timeout 48 barras
- **Filtros entrada:** MACD cross above · preço > EMA200 · 40 ≤ RSI ≤ 70

## 📊 Resultados por ativo

| Ativo | Trades | WinRate | PF | Expect | MaxDD | TP/SL/TO | Veredicto |
|---|---:|---:|---:|---:|---:|---|:---:|
| `BTC/USDT` | 18 | 33.3% | 0.98 | -0.01% | -2.7% | 6/12/0 | ❌ rejected |
| `ETH/USDT` | 11 | 36.4% | 0.95 | -0.03% | -2.8% | 4/7/0 | ❌ rejected |
| `SOL/USDT` | 12 | 41.7% | 1.24 | +0.15% | -2.6% | 5/7/0 | ❌ rejected |
| `XRP/USDT` | 12 | 33.3% | 1.04 | +0.02% | -3.1% | 4/7/1 | ❌ rejected |
| `TRX/USDT` | 17 | 35.3% | 1.03 | +0.01% | -1.8% | 6/11/0 | ❌ rejected |
| `BNB/USDT` | 11 | 54.5% | 2.47 | +0.50% | -1.4% | 6/5/0 | ⚠️ borderline |
| `LINK/USDT` | 12 | 66.7% | 3.26 | +0.98% | -2.5% | 7/4/1 | ⭐ approved |
| `HYPE/USDT` | 9 | 55.6% | 3.45 | +1.24% | -1.9% | 5/4/0 | ⭐ approved |
| `AAVE/USDT` | 9 | 33.3% | 0.79 | -0.22% | -4.5% | 3/6/0 | ❌ rejected |
| `PAXG/USDT` | 7 | 28.6% | 0.47 | -0.18% | -1.4% | 2/5/0 | ❌ rejected |

## 🌐 Agregado (todos os ativos)

- **Trades totais:** 118
- **Win rate:** 41.5%
- **Profit factor:** 1.44
- **Expectancy:** +0.228% por trade
- **Retorno total acumulado:** +26.86%
- **Drawdown máximo:** -4.54%

## ✅ Recomendação para perfil AGRESSIVO

- ⭐ **Aprovados** (PF≥1.5 & WR≥55%): `LINK/USDT`, `HYPE/USDT`
- ⚠️ **Limítrofes:** `BNB/USDT`
- ❌ **Rejeitados:** `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `XRP/USDT`, `TRX/USDT`, `AAVE/USDT`, `PAXG/USDT`

> Gerado automaticamente por `scripts/backtest_macd.py`. Reproduza via workflow `backtest.yml`.
