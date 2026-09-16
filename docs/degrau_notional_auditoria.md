# Degrau de Tamanho de Ordem - Auditoria e Decisao

> Criado em **2026-09-16**. Registra formalmente a auditoria do degrau
> **$10 -> $20** por ordem, que antes vivia apenas num comentario inline em
> `bot/config.py`. **Nenhum parametro foi alterado neste commit.**
>
> Item 2 do `docs/backlog_prioridade_1_2026-09-16.md`.

## Valor vigente

```python
EXECUTION_MAX_NOTIONAL_USDT = 10.0   # INALTERADO
EXECUTION_MIN_NOTIONAL_USDT = 3.0    # piso da Gate.io (rejeita < $3)
```

## Historico de degraus

| Degrau | Data | Valor | Justificativa |
|---|---|---|---|
| 1 | go-live | $5 | canario: perda insignificante por design |
| 2 | 2026-08-12 | **$10** | infra provada em 9 trades (ordem, TP/SL, relay, HMAC) |
| 3 | *nao concedido* | $20 | criterios reprovados (abaixo) |

## Regra do degrau 3

Subir para $20 **somente** quando os TRES criterios forem satisfeitos ao mesmo
tempo:

1. **>= 20 trades** registrados
2. **P&L > 0** (excluindo ETH)
3. **PF >= 1** (excluindo ETH)

> O ETH e excluido porque foi removido da watchlist em 2026-08-24 (PF 0.43 no
> backtest fiel): manter seus trades na conta inflaria/deflacionaria uma serie
> que nao representa mais o sistema em producao.

## Auditoria de 2026-08-23 - REPROVADA (3 de 3)

| Criterio | Exigido | Real | Veredito |
|---|---|---|---|
| Trades | >= 20 | 14 | **REPROVADO** |
| P&L ex-ETH | > 0 | **-$0.23** | **REPROVADO** |
| Profit Factor | >= 1 | **0.60** | **REPROVADO** |

**Decisao: NAO subir.** Teto permanece em $10.

Nao houve "quase passou": falhou em **volume de amostra**, em **resultado** e em
**qualidade do resultado**. Sao tres falhas independentes, nao uma so vista de
tres angulos.

### Diagnostico do PF 0.60

O numero nao e aleatorio - tem causa identificada e ja corrigida:

- A serie e dominada pelo HYPE: **13 dos 17 registros** de
  `state/positions.jsonl` (76%) e **todos os 9 stops** eram dele.
- Esses trades rodaram com **stop de 2.0xATR**, que estava **dentro do ruido
  intraday** (ver `docs/ajuste_stop_2026-08.md`).
- Em 2026-08-23 o stop subiu para **2.5xATR** e entrou a **trava de
  concentracao** (max 1 posicao aberta e 2 ordens/dia por ativo).

## Por que a amostra de 14 trades esta INVALIDA para reauditoria

A base nao pode ser reaproveitada. Ela mistura tres regimes diferentes:

| Fator | Durante os 14 trades | Hoje |
|---|---|---|
| Stop | 2.0xATR | **2.5xATR** |
| Trava de concentracao | ausente | **ativa** |
| Universo | incluia ETH, XRP, PAXG | **5 ativos** |
| Contador de posicoes abertas | bugado (monotonico) | corrigido |

**Regra de metodo:** so contam para o degrau os trades executados sob a
configuracao **vigente**. Reaproveitar trades de configuracao antiga para
justificar aumento de tamanho e aumentar aposta com base em dado que ja nao
descreve o sistema - o erro classico que os degraus existem justamente para
evitar.

## Contador zerado - marco da nova serie

A contagem valida para o degrau 3 comeca **do zero** a partir de
**2026-09-04** (remocao do PAXG, ultima mudanca estrutural do universo).

Proxima reauditoria: quando a serie iniciada em 2026-09-04 acumular **20
trades**. Antes disso, qualquer avaliacao e ruido estatistico.

## Como reauditar (quando houver amostra)

Fonte de verdade: `state/positions.jsonl` (registros com `status` fechado) e
`state/paper_trades.jsonl` (eventos `relay_response`).

1. Filtrar `opened_at >= 2026-09-04`.
2. Excluir ETH (e qualquer ativo fora da `WATCHLIST` vigente).
3. Contar trades fechados; se **< 20**, PARAR - reprovado por amostra.
4. Somar P&L; calcular PF = soma dos ganhos / soma das perdas (absoluto).
5. Aprovar **somente** se os tres criterios passarem.

## Se algum dia for aprovado

Alterar **os dois lados** - Python e PHP:

- `bot/config.py`: `EXECUTION_MAX_NOTIONAL_USDT = 20.0`
- `server/execute.php`: o teto espelhado no relay (defesa em profundidade)

> **Licao do incidente `sspot` (2026-08-20): FIX COMMITADO != FIX DEPLOYADO.**
> Mudar so o `config.py` cria divergencia silenciosa - o Python autoriza $20 e o
> relay recusa. Sempre validar no servidor apos o deploy.

**Rollback:** voltar os dois para `10.0`.

## Travas que NAO mudam com o degrau

Subir o teto por ordem nao afrouxa nenhuma outra protecao:

| Trava | Valor |
|---|---|
| `EXECUTION_DAILY_LOSS_STOP` | $20/dia |
| `EXECUTION_MAX_TRADES_DAY` | 10/dia |
| `EXECUTION_MAX_OPEN` | 10 simultaneas |
| `EXECUTION_MAX_OPEN_PER_SYMBOL` | 1 |
| `EXECUTION_MAX_TRADES_DAY_PER_SYMBOL` | 2 |
| `REQUIRE_PROTECTION` (PHP) | compra sem TP/SL e recusada |

> Atencao ao interagir: com teto de $20 e stop diario de $20, **um unico trade
> perdedor pode consumir o stop do dia**. Se o degrau 3 for concedido, reavaliar
> `EXECUTION_DAILY_LOSS_STOP` na mesma ocasiao.
