# Watchlist efetiva mora no runtime, nao no config.py (2026-08-24)

> Achado encontrado ao tratar a "ponta solta" do ETH/XRP apontada na
> auditoria de estrategias. O diagnostico inicial estava incompleto.

## O mecanismo

`bot/main.py`:

```python
runtime_watchlist = cfg.get("watchlist") or []
effective_symbols = list(runtime_watchlist) if runtime_watchlist else list(SYMBOLS)
```

`cfg` vem de `state/runtime_config.json`. Portanto **`bot/config.py` WATCHLIST
e apenas fallback**: so vale se a lista do runtime estiver vazia ou ausente.
Editar `config.py` para mudar o universo de scan e um **no-op** enquanto o
runtime tiver conteudo.

`runtime_config.save()` faz `DEFAULTS + dados do arquivo`, e `mark_scan_ran()`
faz `load() -> save()` a cada scan. Logo a lista commitada aqui **sobrevive**
aos ciclos seguintes (o scan so atualiza `last_scan_utc` e metadados).

## O bug silencioso: PAXG nunca foi escaneado

| Fonte | PAXG presente? |
|---|---|
| `bot/config.py` WATCHLIST | sim |
| `state/runtime_config.json` (antes) | **nao** |
| Universo real do scan | **nao** |

Consequencia: `ACCUMULATION_ENABLED = True` e `ACCUMULATION_SYMBOLS` com
PAXG, mas `evaluate_signal` **nunca era chamado para PAXG** — o fast-path de
acumulo era inalcancavel.

O comentario em `config.py` registrava:

> "ZERO disparos em ~2 meses (o RSI 4h nao cruzou 30). Mantido: e uma
> estrategia rara por design."

**Esse diagnostico estava errado.** Nao era raridade estatistica: o ativo nao
entrava no loop. Mesmo genero de achado da auditoria de estrategias (codigo
declarado ativo mas inalcancavel), so que este morava em `state/`, nao em
`bot/`, e por isso sobreviveu a limpeza de 2026-08-24.

Nao ha registro de decisao de remover o PAXG do runtime — trata-se de **drift
acidental**, provavelmente de uma edicao manual da watchlist via runtime.

## Mudanca aplicada

Watchlist efetiva passa de 7 para **6 ativos**:

```
BTC, SOL, TRX, BNB, HYPE, PAXG
```

- **PAXG reposto** — corrige o bug. O acumulo volta a ser avaliado de fato.
  Atencao: acumulo e **compra sem stop-loss** (BUY only, sem alvo de venda).
  Se o RSI 4h cruzar 30, havera ordem real (teto $10, dentro das travas).
- **ETH e XRP removidos** — sem rota ate ordem desde 2026-08-23 (saida do
  universo do Mare Alta D1). Economiza ~6 fetches por scan.

### Trade-off assumido no ETH/XRP

`config.py` documentava que os dois ficavam **de proposito**, para o
diagnostico MTF no Telegram. Essa funcao **se perde** com a remocao: eles
deixam de aparecer no resumo de scan. A decisao foi trocar visibilidade por
custo de rede.

## Divergencia remanescente (proposital)

`bot/config.py` WATCHLIST segue com 8 ativos (incluindo ETH/XRP). Nao foi
alterado: ele e o fallback de emergencia, e mante-lo completo evita que uma
perda do `runtime_config.json` deixe o bot sem universo. **A fonte de verdade
do que e escaneado e `state/runtime_config.json`.**

## Rollback

Reinserir os simbolos em `state/runtime_config.json`. Para desligar so o
acumulo sem mexer na watchlist: `ACCUMULATION_ENABLED = False`.

## Verificacao

Apos o proximo scan, conferir no log:

```
Iniciando scan | symbols=['BTC/USDT', 'SOL/USDT', 'TRX/USDT', 'BNB/USDT', 'HYPE/USDT', 'PAXG/USDT']
```

Se PAXG nao aparecer, o commit foi sobrescrito por um scan em voo — refazer.
