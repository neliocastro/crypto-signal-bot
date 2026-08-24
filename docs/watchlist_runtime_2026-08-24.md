# Watchlist: fonte de verdade movida para config.py (2026-08-24)

> Achado ao tratar a "ponta solta" do ETH/XRP da auditoria de estrategias.
> O diagnostico inicial estava incompleto, e a primeira correcao FALHOU.
> Este doc registra os dois erros e a solucao que ficou.

## 1. O achado: PAXG era codigo morto silencioso

`bot/main.py` (antes):

```python
runtime_watchlist = cfg.get("watchlist") or []
effective_symbols = list(runtime_watchlist) if runtime_watchlist else list(SYMBOLS)
```

`cfg` vem de `state/runtime_config.json`, que tinha **7 ativos sem PAXG**.
`bot/config.py` WATCHLIST tinha 8 **com** PAXG. O runtime vencia.

| Fonte | PAXG presente? |
|---|---|
| `bot/config.py` WATCHLIST | sim |
| `state/runtime_config.json` | **nao** |
| Universo real do scan | **nao** |

Resultado: `ACCUMULATION_ENABLED = True` e `ACCUMULATION_SYMBOLS` com PAXG,
mas `evaluate_signal` **nunca era chamado para PAXG** - o fast-path de acumulo
era inalcancavel.

O comentario em `config.py` registrava:

> "ZERO disparos em ~2 meses (o RSI 4h nao cruzou 30). Mantido: e uma
> estrategia rara por design."

**Diagnostico errado.** Nao era raridade estatistica: o ativo nao entrava no
loop. Mesmo genero de achado da auditoria de estrategias (codigo declarado
ative mas inalcancavel), so que este morava em `state/` e por isso sobreviveu
a limpeza. Nao ha registro de decisao de remover o PAXG - foi **drift**.

## 2. A primeira correcao FALHOU (licao principal)

Commit `0a3e9d5` editou `state/runtime_config.json` diretamente via API.
A releitura do `main` minutos depois mostrou o arquivo **de volta aos 7
ativos**, com `_updated_by: "scan"`.

A justificativa usada para prever que sobreviveria estava errada:

> ~~`mark_scan_ran()` faz `load() -> save()`, entao a lista commitada e
> preservada.~~

Isso vale **dentro do processo**, mas ignora o passo anterior: o runner do
GitHub Actions faz **checkout do repo antes do commit existir**, roda o scan
com a watchlist antiga em memoria e no fim commita `state/` por cima
(`chore: update signal state [skip ci]`).

**`state/runtime_config.json` e um ARTEFATO GERADO, nao configuracao
versionada.** Edita-lo via API e uma corrida perdida a cada ~5 minutos.

## 3. Solucao aplicada

### `bot/runtime_config.py` (commit b25b092)

Novo `_static_watchlist()`, aplicado nos **3 caminhos de retorno** de `load()`:

```python
def _static_watchlist(cfg):
    try:
        from .config import WATCHLIST as _cfg_wl
        cfg["watchlist"] = list(_cfg_wl)
    except Exception as e:
        log.warning("config.WATCHLIST indisponivel (%s) - watchlist do runtime mantida", e)
    return cfg
```

`DEFAULTS["watchlist"]` virou lista vazia (placeholder). O que o scan gravar
em `runtime_config.json` passa a ser **irrelevante** para a watchlist: a
proxima leitura sobrescreve com o valor do codigo.

O `main.py` **nao foi tocado** - a expressao `cfg.get("watchlist") or []`
continua valida, so que agora `cfg["watchlist"]` ja vem de `config.py`.

### `bot/config.py` (commit a390e09)

Watchlist de 8 para **6 ativos**:

```
BTC, SOL, TRX, BNB, HYPE, PAXG
```

- **PAXG mantido** - agora efetivamente escaneado. O acumulo passa a ser
  avaliado pela primeira vez. **Atencao: acumulo e compra sem stop-loss**
  (BUY only, sem alvo de venda). Se o RSI 4h cruzar 30, havera ordem real
  (teto $10, dentro das travas de capital).
- **ETH e XRP removidos** - sem rota ate ordem desde 2026-08-23 (saida do
  universo do Mare Alta D1, PF 0.43 e 0.55 no backtest fiel). Economiza ~6
  fetches por scan.

### Trade-off assumido no ETH/XRP

`config.py` documentava que os dois ficavam **de proposito**, para o
diagnostico MTF no Telegram. Essa funcao **se perde**: eles deixam de aparecer
no resumo de scan. Trocou-se visibilidade por custo de rede.

## 4. Custo da solucao

Os comandos de watchlist do **Telegram Commander** (`/add`, `/rm`) ficam
**inertes**: continuam gravando no JSON, mas a alteracao e ignorada na leitura
seguinte. Isso e coerente com o que ja acontecia na pratica (o scan
sobrescrevia tudo), so que agora e explicito em vez de silencioso.

Para mudar o universo: **editar `WATCHLIST` em `bot/config.py` e dar push.**

Os demais campos do runtime (`paused`, `scan_interval_min`, DND,
`last_scan_utc`) seguem funcionando normalmente pelo Telegram.

## 5. Rollback

- Voltar o comportamento antigo: `git revert b25b092`.
- Voltar so os ativos: reinserir `ETH/USDT` e `XRP/USDT` na WATCHLIST.
- Desligar so o acumulo: `ACCUMULATION_ENABLED = False`.

## 6. Verificacao

No log do proximo scan deve aparecer:

```
Iniciando scan | symbols=['BTC/USDT', 'SOL/USDT', 'TRX/USDT', 'BNB/USDT', 'HYPE/USDT', 'PAXG/USDT']
```

Se PAXG nao aparecer, ou se ETH/XRP ainda aparecerem, o `_static_watchlist`
nao esta sendo aplicado - investigar o import de `.config` dentro de
`runtime_config.py`.

## 7. Licao de metodo

Distinguir **arquivo versionado** de **artefato gerado** antes de commitar
qualquer correcao. Se um job de CI escreve no caminho, um commit via API nao
sobrevive - e o "sucesso" do commit nao prova nada. Sempre reler o arquivo
apos o ciclo seguinte do job, nao logo apos o commit.
