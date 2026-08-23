# Trava de concentracao por ativo (2026-08-23)

> Implementada em `bot/executor.py` (commit `8a1d5bc`). Continua a sequencia de
> auditoria de 23/08 (ver `docs/decisao_stop_e_universo_2026-08-23.md`).

## O problema

O bot tinha teto GLOBAL de posicoes (`EXECUTION_MAX_OPEN = 10`) e teto GLOBAL de
ordens/dia (`EXECUTION_MAX_TRADES_DAY = 10`). Nenhum dos dois olhava PARA QUAL
ativo a ordem ia. Resultado real, medido em `state/positions.jsonl`:

| Ativo | Registros | % |
|---|---|---|
| **HYPE/USDT** | **13** | **76%** |
| ETH/USDT | 3 | 18% |
| TRX/USDT | 1 | 6% |

E a distribuicao por desfecho e ainda mais dura:

| Ativo | closed_sl | closed_tp | outros |
|---|---|---|---|
| HYPE | **9** | 3 | 1 aberta (legado protegido) |
| ETH | 0 | 1 | 2 manuais |
| TRX | 0 | 1 | - |

**Os 9 stops do historico inteiro sao TODOS do mesmo ativo.** O teto de 10
posicoes nunca segurou nada porque o bot nunca chegou perto de 10 ativos
DIFERENTES: ele reentrava no mesmo. Diversificacao no papel, aposta unica na
pratica.

## A mudanca

Duas travas novas em `check_guards()`, aplicadas ANTES de qualquer envio ao relay:

| Trava | Valor | O que impede |
|---|---|---|
| `EXECUTION_MAX_OPEN_PER_SYMBOL` | 1 | reentrar num ativo que ja tem posicao viva |
| `EXECUTION_MAX_TRADES_DAY_PER_SYMBOL` | 2 | martelar o mesmo ativo em serrote no mesmo dia |

Bloqueio gera `status=blocked_by_guard` com motivo explicito, entra em
`state/paper_trades.jsonl` e avisa no Telegram - mesmo caminho das travas
existentes. Nao cancela ordem, nao vende nada, so **deixa de comprar**.

## Detalhe que importa: de onde vem a contagem

`_open_count_for_symbol()` le **`state/positions.jsonl`** (status `open*`), a
mesma fonte que `oco_guard` e o trailing usam.

NAO usa `state/execution_guard.json`. Motivo: aquele contador so INCREMENTA
(`_register_sent_order`); **nada o decrementa quando o TP ou o SL fecha a
posicao**. Hoje ele esta congelado em `{"day":"2026-08-22","open_positions":1}`,
ou seja, ja nao descreve a realidade. Basear a trava nele seria construir sobre
numero errado.

> Pendencia registrada (nao corrigida aqui): `open_positions` do
> `execution_guard.json` deveria ser decrementado no fechamento, ou lido do
> `positions.jsonl` como aqui. Merece commit proprio.

`_sent_today_for_symbol()` conta `relay_response` do dia (UTC) por simbolo em
`state/paper_trades.jsonl` - eventos que so existem depois de passar as travas.

## Seguranca e rollback

- **Aditivo**: as chaves nao existem em `config.py`; o executor tem default
  proprio. Nada quebra por ImportError.
- **Degradacao segura**: qualquer falha de leitura retorna 0 -> nao bloqueia por
  engano. A trava so age com evidencia positiva.
- **Rollback de 1 linha** - adicione em `bot/config.py`:

```python
EXECUTION_CONCENTRATION_GUARD = False
```

- **Afrouxar em vez de desligar** (tambem em `bot/config.py`):

```python
EXECUTION_MAX_OPEN_PER_SYMBOL       = 2
EXECUTION_MAX_TRADES_DAY_PER_SYMBOL = 3
```

## Efeito esperado

- Menos trades no HYPE; o capital do dia sobra para BTC/SOL/TRX/BNB (Mare Alta D1).
- Se um ativo entrar em serrote, ele custa no maximo 2 tentativas/dia em vez de
  consumir todo o orcamento de risco.
- Nao melhora o edge de nenhuma estrategia. E controle de **risco**, nao de
  retorno: reduz a variancia de ter 76% do resultado dependendo de um ativo.

## Ressalva honesta

A amostra e pequena (17 registros). A concentracao em HYPE tem causa conhecida e
legitima - era o unico ativo do trilho breakout 1h, que dispara muito mais que o
D1. A trava nao afirma que "HYPE e ruim"; afirma que **nenhum ativo isolado deve
carregar a carteira**. Reavaliar junto com os 10 trades fechados previstos em
`docs/decisao_stop_e_universo_2026-08-23.md`.
