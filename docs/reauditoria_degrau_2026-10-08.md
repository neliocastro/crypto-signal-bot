# Reauditoria do degrau de teto ($10 -> $20) — 2026-10-08

## Contexto

Regra combinada em 12/08 (`config.py`, `docs/degrau_notional_auditoria.md`):
subir `EXECUTION_MAX_NOTIONAL_USDT` de $10 para $20 **so no 20o trade**, com
**P&L > 0** e **PF >= 1 sem o ETH**. As auditorias de 23/08 e 16/09 reprovaram
por falta de amostra. O 20o trade fechou e hoje ha **22 trades fechados**, entao
esta e a primeira reauditoria em que o criterio de amostra pode ser avaliado.

## Evidencia (`state/positions.jsonl`, HEAD `84388d2`)

Estimativa com fee 0.1% ida e volta; detalhe trade a trade em `docs/resultado_financeiro.md` (secao 5).

| Criterio | Exigido | 16/09 | **08/10** | Status |
|---|---|---|---|---|
| Trades fechados | >= 20 | 14 | **22** | ✅ atingido |
| P&L total | > 0 | — | **-$1.28** | ❌ reprovado |
| P&L sem ETH | > 0 | -$0.23 | **-$2.70** | ❌ reprovado |
| PF sem ETH | >= 1 | 0.60 | **~0.37** | ❌ reprovado |

Recorte do universo atual (desde 04/09): **6 trades, 0 wins, -$2.41**. Todos no stop.

## Decisao

**MANTER $10. Degrau de $20 segue CONGELADO.** O criterio de amostra foi atingido, mas
os criterios de resultado pioraram desde 16/09. Nenhuma mudanca em `config.py` ou no PHP.

## Regra de reauditoria (daqui em diante)

Pelo principio 10 do projeto (so subir com amostra do regime atual), a proxima
reauditoria **nao reaproveita trades de configuracao antiga**:

1. Janela: trades abertos **a partir de 04/09/2026** (universo de 5 ativos + override do HYPE).
2. Gatilho: quando essa janela tiver **20 trades fechados**.
3. Criterios: P&L > 0 **e** PF >= 1 na janela.
4. Hoje: 6 de 20.

## Pendencias que NAO sao decididas aqui

- Investigar os 3 stops simultaneos de 08/10 17:40 UTC (SOL, BNB, BTC) no `execution_log.jsonl`.
- Revisao de estrategia (filtro de regime, pausar trilhos ou seguir coletando): decisao separada, com evidencia propria.

## Rollback

Este documento nao alterou codigo. Nada a reverter.
