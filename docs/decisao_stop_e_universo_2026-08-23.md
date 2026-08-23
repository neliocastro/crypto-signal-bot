# Decisao final — universo do Mare Alta e multiplicador do stop (2026-08-23)

> Fecha a sequencia de 4 tarefas de auditoria desta sessao. Duas mudancas
> aplicadas em producao, ambas com evidencia e rollback de uma linha.

## Mudanca 1 — ETH e XRP saem do Mare Alta D1 ✅ APLICADO

`bot/mare_alta.py`: `MARE_ALTA_UNIVERSE` passa de 6 para **4 ativos**
(BTC, SOL, TRX, BNB).

Tres evidencias independentes convergiram:

| Evidencia | ETH | XRP | Metodo |
|---|---|---|---|
| Walk-forward original (jul/2026) | reprovado | reprovado | validacao da estrategia |
| Backtest simplificado 3,8 anos | PF 0,56 | PF 0,47 | stop + TP RR2 |
| **Backtest FIEL (com trailing)** | **PF 0,43** | **PF 0,55** | stop + TP1 +10% 50% + BE + trailing 3xATR |

Os 4 mantidos, no mesmo teste fiel (stop 2,5x):
BTC 1,28 | SOL 4,51 | TRX 2,21 | BNB 2,15.

**Descoberta relevante:** o trailing AMPLIFICA quem tem tendencia real
(SOL 1,81 -> 4,51) e NAO salva quem serpenteia (ETH 0,56 -> 0,43). A hipotese
de que o modelo simplificado estava penalizando ETH/XRP injustamente foi
**refutada** — com o modelo fiel eles pioraram.

**Ressalvas:** XRP tem apenas 6 trades em 3,8 anos e ETH ~10 — amostras
pequenas. Backtest nao e futuro. Rollback: reinserir os dois na lista.

## Mudanca 2 — Stop: 2,0x -> **2,5x** (e NAO 3,0x global)

`bot/config.py`: `EXECUTION_ATR_MULT_SL = 2.5`.

### Por que 2,5 e nao 3,0

O 3,0x foi o pico no backtest do **HYPE 1h** (PF 1,18 -> 1,50). Mas o teste
nos ativos do **D1 com o modelo fiel** mostrou o contrario: com trailing ativo,
**2,5x supera 3,0x em 5 dos 6 ativos** (BTC 1,28 vs 1,07; SOL 4,51 vs 3,77;
TRX 2,21 vs 2,13; BNB 2,15 vs 1,79). O trailing ja cumpre o papel de "dar
espaco"; alargar o stop inicial vira redundancia e aumenta a perda por trade.

`EXECUTION_ATR_MULT_SL` e um parametro **global da camada de execucao** — vale
para todo ativo. Escolha: o valor que melhora os DOIS trilhos.

| Multiplicador | HYPE 1h (PF) | Carteira D1 fiel |
|---|---|---|
| 2,0 (anterior) | 1,18 | pior em todos |
| **2,5 (aplicado)** | **1,31** | **melhor em 5/6** |
| 3,0 | 1,50 | pior que 2,5 em 5/6 |

2,5x melhora o HYPE (1,18 -> 1,31) **e** e o otimo do D1. Ganho parcial no HYPE
em troca de nao degradar 4 ativos — troca deliberada.

### Consequencia colateral positiva

O `mare_alta.py` sempre documentou stop de **2,5xATR**, mas quem calcula o stop
da ordem real e o `executor.py`, que usava 2,0x. Ou seja, o D1 operava com um
stop **mais apertado do que a estrategia validada**. Esta mudanca **alinha a
execucao com a estrategia** — corrige uma divergencia silenciosa.

### Pendencia opcional (nao aplicada)

Para o HYPE capturar seu otimo (3,0x, PF 1,50) sem afetar o D1, seria preciso
um **override por simbolo** no `executor.py`:

```python
# em config.py
EXECUTION_ATR_MULT_SL_BY_SYMBOL = {"HYPE/USDT": 3.0}
# em executor.build_order(), antes de calcular `risco`:
_mult = EXECUTION_ATR_MULT_SL_BY_SYMBOL.get(signal.get("symbol"),
                                            EXECUTION_ATR_MULT_SL)
```

NAO aplicado nesta rodada: mexe na funcao que monta TODA ordem real. Merece
commit isolado e revisao propria. Ganho estimado: PF 1,31 -> 1,50 no HYPE.

## Efeito pratico esperado

- Menos trades (o stop de 2,0x estopava ~1/3 das entradas por ruido).
- Perda por trade maior em % (~-1,8% -> ~-2,2%), compensada por menos perdas.
- TP mais distante (RR 2,0 sobre risco maior).
- Piso `EXECUTION_MIN_STOP_PCT = 0.8%` permanece ativo (protege TRX, ATR baixo).

## Reavaliacao

Revisar ao atingir **10 trades fechados** com a nova config. Sucesso: WR >= 33%
e PF >= 1. Se o HYPE seguir com PF < 1, a hipotese do ruido estara descartada e
o proximo passo e voltar o HYPE para shadow.

**Rollback completo:** `EXECUTION_ATR_MULT_SL = 2.0` + reinserir ETH/XRP.

---

_Fontes: `docs/revisao_ativos_2026-08.md` (desempenho real),
`docs/ajuste_stop_2026-08.md` (backtest HYPE 180d), backtests D1 de 3,8 anos
com dados publicos da Gate.io._
