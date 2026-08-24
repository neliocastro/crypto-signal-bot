# Watchlist: onde ela mora de verdade (2026-08-24)

> Achado que comecou ao tratar a "ponta solta" do ETH/XRP e terminou numa
> mudanca de arquitetura. Este doc foi reescrito 3x no mesmo dia; a versao
> abaixo e a que bate com o codigo em `main`.

## Estado ATUAL (vale hoje)

**`bot/config.py` WATCHLIST e a fonte de verdade unica.**

`bot/runtime_config.py` tem `_static_watchlist(cfg)`, chamado em TODOS os
caminhos de `load()`:

```python
from .config import WATCHLIST as _cfg_wl
cfg["watchlist"] = list(_cfg_wl)
```

Entao a chave `"watchlist"` de `state/runtime_config.json` e um **placeholder
vestigial**: o que estiver la e sobrescrito em memoria a cada `load()`. O
`DEFAULTS` do proprio modulo ja traz `"watchlist": []` com essa nota.

Universo de scan hoje (6 ativos):

```
BTC, SOL, TRX, BNB, HYPE, PAXG
```

### Consequencia funcional a conhecer

Os comandos de watchlist do **Telegram Commander (`/add`, `/rm`) ficaram
inertes**. Eles escrevem no runtime, e o runtime nao manda mais. Para mudar o
universo: editar `WATCHLIST` em `bot/config.py` e dar push. Isso e uma
regressao real de usabilidade, aceita em troca de ter o universo em codigo
versionado e revisavel.

## O bug que originou tudo: PAXG era codigo morto

Na arquitetura anterior, `main.py` fazia:

```python
runtime_watchlist = cfg.get("watchlist") or []
effective_symbols = list(runtime_watchlist) if runtime_watchlist else list(SYMBOLS)
```

`config.py` listava PAXG, mas o runtime tinha 7 ativos **sem PAXG**. O runtime
vencia. Resultado: `evaluate_signal` **nunca era chamado para PAXG** e o
fast-path de acumulo (`ACCUMULATION_ENABLED = True`) era **inalcancavel**.

O comentario em `config.py` dizia:

> "ZERO disparos em ~2 meses (o RSI 4h nao cruzou 30). Estrategia rara por
> design."

**Errado.** Nao era raridade estatistica, era codigo morto. Mesmo genero de
achado da auditoria de estrategias, mas escondido em `state/` em vez de
`bot/` - por isso sobreviveu a limpeza.

## CORRECAO: a justificativa da mudanca estava errada

O docstring de `_static_watchlist()` e o cabecalho de `config.py` afirmam:

> "state/runtime_config.json e um ARTEFATO GERADO - o job faz checkout, roda o
> scan e commita state/ por cima. Qualquer watchlist editada ali e perdida no
> proximo ciclo (~5 min)."

**Isso e FALSO.** Foi uma hipotese minha, construida sobre uma leitura errada,
que acabou virando justificativa oficial no codigo.

O que o codigo realmente faz: `mark_scan_ran()` chama `load() -> save()`,
mexendo so em `last_scan_utc`, `fear_greed` e `last_signals_count`. A
watchlist e lida e regravada intacta.

**Evidencia:**

| Momento | Fonte | Watchlist |
|---|---|---|
| 01:04Z | commit `0a3e9d5` (manual, no runtime) | 6 ativos, com PAXG |
| 02:07Z | **scan** (`_updated_by: scan`) | 6 ativos, com PAXG |

O scan reescreveu o arquivo depois do commit e **preservou** a lista. Uma
watchlist editada no runtime NAO se perde em ~5 min.

### A decisao continua certa, pelo motivo certo

Centralizar em `config.py` **segue sendo bom** - mas o argumento valido nao e
"o runtime nao persiste" (nao e verdade). E:

- watchlist e **decisao de estrategia**, nao estado efemero de execucao;
- pertence a codigo versionado, revisavel em diff e com historico;
- **elimina a dupla fonte de verdade** que criou o bug do PAXG.

Esse motivo se sustenta sozinho. O outro deveria sair do docstring de
`_static_watchlist()` e do cabecalho de `config.py` numa proxima passada.

### Como o erro aconteceu (licao de metodo)

Na verificacao feita logo apos o commit `0a3e9d5`, o arquivo lido ainda
trazia a lista antiga **com `_updated_at_utc` = 00:55:46** - ou seja,
conteudo anterior ao commit, leitura velha. Foi interpretado como "o scan
reverteu".

**Regra:** ao validar uma escrita em `state/`, conferir o `_updated_at_utc`
ANTES de concluir. Timestamp anterior ao seu commit = leitura velha, nao
sobrescrita. Ausencia de evidencia nao e evidencia de ausencia - a mesma
licao ja registrada em `docs/gateio_limitacoes.md`.

## ETH e XRP fora do scan

Removidos: sem rota ate ordem desde 2026-08-23 (fora do universo do Mare Alta
D1, sem fast-path proprio). Economiza ~6 fetches/scan.

**Custo assumido:** eles ficavam de proposito para diagnostico MTF no
Telegram. Essa visibilidade se perde.

**Rollback:** reinserir as duas linhas em `bot/config.py` WATCHLIST e push.

## Proxima observacao

O PAXG entra no loop de scan pela primeira vez. O fast-path de acumulo nunca
foi exercitado em producao. Quando o RSI 4h cruzar 30, sera a estreia real de
`_check_accumulation -> executor.maybe_execute` - e acumulo e **compra sem
stop-loss** (BUY only). Travas de capital seguem valendo: teto $10/ordem,
max 10 ordens/dia, stop diario $20.

Para desligar so o acumulo sem mexer na watchlist:
`ACCUMULATION_ENABLED = False`.
