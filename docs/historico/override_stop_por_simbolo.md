# Override de stop por símbolo (2026-09-16)

## O que mudou

Novo parâmetro **`EXECUTION_ATR_MULT_SL_BY_SYMBOL`** em `bot/config.py`, lido por
`bot/executor.py` através da função `_atr_mult_for(symbol)`.

```python
EXECUTION_ATR_MULT_SL_BY_SYMBOL = {
    "HYPE/USDT": 3.0,
}
```

O global `EXECUTION_ATR_MULT_SL = 2.5` continua valendo para **todos** os outros
ativos (os 4 do Mare Alta D1: BTC, SOL, TRX, BNB). Nada neles muda.

## Por que

Esta mudança **fecha uma pendência explicitamente registrada** no comentário do
`config.py` desde 2026-08-23:

> "O ótimo do HYPE (3.0x) exigiria um override por símbolo no
> `executor.build_order()` - commit isolado, ainda não feito."

### Evidência

| Trilho | 2.0x | 2.5x | 3.0x |
|---|---|---|---|
| HYPE/USDT 1h (180d) | PF 1.18 | PF 1.31 | **PF 1.50** |
| BTC/USDT D1 (backtest fiel) | — | **1.28** | 1.07 |
| SOL/USDT D1 | — | **4.51** | 3.77 |
| TRX/USDT D1 | — | **2.21** | 2.13 |
| BNB/USDT D1 | — | **2.15** | 1.79 |

Os dois trilhos têm ótimos **diferentes**: 2.5x para o D1, 3.0x para o HYPE 1h.
Um único valor global obrigava a escolher um perdedor. O override resolve isso.

### Diagnóstico de suporte

Dos 17 registros de `state/positions.jsonl`, 13 são HYPE (76%) e **os 9 stops são
TODOS dele**. O stop apertado ficava dentro do ruído intraday do ativo — mesmo
diagnóstico que já justificou a subida de 2.0x → 2.5x em 2026-08-23.

## Implementação (aditiva e degradação segura)

`bot/executor.py`:

```python
try:
    from .config import EXECUTION_ATR_MULT_SL_BY_SYMBOL
except Exception:
    EXECUTION_ATR_MULT_SL_BY_SYMBOL = {}
```

- Se a chave **não existir** no `config.py`, o dict fica vazio e **nada muda**
  (todos os ativos seguem no global). Comportamento antigo preservado.
- `_atr_mult_for()` valida a **faixa [0.5, 6.0]**: valor fora disso é tratado
  como erro de digitação, loga `warning` e cai no global. Nunca gera stop absurdo.
- Qualquer exceção → global. A função nunca levanta.
- A ordem enviada ao relay passa a carregar o campo **`atr_mult_sl`** com o
  multiplicador *efetivo* usado — auditabilidade em `paper_trades.jsonl`.

## Interação com as travas existentes

- **`EXECUTION_MIN_STOP_PCT = 0.8`** continua sendo aplicado DEPOIS: o piso de
  afastamento (0.8% do preço) segue valendo. Um stop de 3.0xATR só é usado se
  for mais largo que o piso — nunca mais apertado.
- Nada muda em `EXECUTION_TP_RR = 2.0`: o TP é derivado do risco, então um stop
  mais largo no HYPE gera automaticamente um **TP proporcionalmente mais
  distante**. Consequência esperada: menos stops por ruído, alvos mais longe,
  win-rate potencialmente menor com payoff maior (natureza trend-following).
- **Sizing NÃO muda**: `notional` continua vindo de `EXECUTION_PCT` com clamp em
  `[MIN_NOTIONAL, MAX_NOTIONAL]`. O stop mais largo, portanto, aumenta o risco em
  $ por trade do HYPE (~+20% do risco anterior), ainda dentro do teto de $10/ordem.

## Rollback

Uma linha em `bot/config.py`:

```python
EXECUTION_ATR_MULT_SL_BY_SYMBOL = {}
```

Ou `git revert` do commit. Nenhuma migração de estado é necessária — o parâmetro
só afeta ordens **novas**; posições já abertas mantêm seus stops.

## O que observar

Próximos trades do HYPE em `state/orders_executed.csv` / `state/positions.jsonl`:
se a proporção de `closed_sl` cair em relação aos 9 stops históricos, a hipótese
do "stop dentro do ruído" se confirma. Amostra mínima honesta: **8-10 trades**.
Antes disso, qualquer leitura é anedótica.
