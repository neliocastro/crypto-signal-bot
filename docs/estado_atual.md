# Estado Atual do Bot — Consolidado (jul/2026)

> Documento de referencia. Sem mudanca de codigo — apenas registro de decisoes
> e do roteamento vigente no `main`. Proxima etapa: avaliar sinais no Telegram.

## Roteamento por ativo (produção)

| Ativo | Estrategia | Observacao |
|---|---|---|
| BTC | Mare Alta D1 | validado no walk-forward |
| ETH | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| SOL | Mare Alta D1 | validado no walk-forward |
| XRP | Mare Alta D1 | **incluido por decisao consciente** (reprovado no WF original) |
| TRX | Mare Alta D1 | validado no walk-forward |
| BNB | Mare Alta D1 | validado no walk-forward |
| LINK | Mare Alta D1 + MACD-only | **incluido no Mare Alta**; ainda gera sinal MACD-only 1h |
| HYPE | Breakout/Tendencia (lb=30/atr=2.5) | fast-path dedicado; nao passa pelo Mare Alta nem MACD-only |
| PAXG | Acumulacao RSI (BUY-only) | fora do trailing (nao registra stop) |

## Mare Alta D1 — universo atual

```python
MARE_ALTA_UNIVERSE = ["BTC/USDT", "ETH/USDT", "SOL/USDT",
                      "XRP/USDT", "TRX/USDT", "BNB/USDT", "LINK/USDT"]
```

- 7 ativos = **todos menos PAXG e HYPE**.
- Entrada (D1, vela fechada): MACD cruza acima do sinal + EMA9>EMA21.
- Saida: stop 2.5xATR -> TP1 +10% (50%) -> breakeven + trailing 3.0xATR.
- Commit: `6b1c8d5`.

### Nota de risco (ETH/XRP)
ETH e XRP foram **reprovados no walk-forward original** da estrategia e entraram
por decisao de negocio. Acompanhar de perto na avaliacao dos sinais.

### Ponta solta (LINK)
LINK esta no Mare Alta D1 **e** ainda no `approved_symbols` do MACD-only 1h,
entao pode gerar sinal pelos dois caminhos. Decisao pendente: tornar exclusivo
do Mare Alta (remover do MACD-only) ou manter os dois.

## Trailing (Mare Alta ATR / mare_alta_trailing.py)

- `MARE_ALTA_SYMBOLS = []` -> mira **todos** os ativos com posicao registrada.
- PAXG fica de fora por arquitetura (acumulacao BUY-only, sem stop p/ trailar).

## Camada de execucao Gate.io (Fase 1 — dry-run)

Cinto triplo de seguranca ativo:

| Flag | Valor | Efeito |
|---|---|---|
| `EXECUTION_DRY_RUN` | `True` | cerebro nunca envia ordem real |
| `EXECUTION_RELAY_URL` | `""` | nao ha destino p/ ordem real |
| `DRY_RUN` (PHP) | `true` | braco tambem so loga |
| `MAX_NOTIONAL_USDT` (PHP) | `20` | teto rigido no servidor |

- Modulos: `bot/executor.py`, `server/execute.php`, `bot/paper_evaluator.py`.
- Logs nascem no 1o sinal BUY: `state/paper_trades.jsonl`, `state/execution_log.jsonl`.

### Bugs conhecidos do execute.php (a corrigir em sessao dedicada)
1. `pair_rules()` falha -> fallback `precision=6` -> trigger com casas demais -> HTTP 400.
2. `ATR=0` -> compra sem TP/SL. Fix: pular sinal quando ATR=0.

## Relatorio semanal (Telegram/e-mail)

- Segunda 09:00 (America/Bahia). Consolida:
  - Parte 1: estrategia HYPE (breakout producao).
  - Parte 2: dry-run da execucao (P&L hipotetico, win-rate, slippage medio).

## Proximos passos

- [ ] Avaliar sinais e mensagens que chegam no Telegram.
- [ ] Decidir exclusividade do LINK (Mare Alta vs MACD-only).
- [ ] Monitorar ETH/XRP no Mare Alta (reprovados no WF).
- [ ] Corrigir `execute.php` (precision + ATR=0) antes da Fase 2 real.
