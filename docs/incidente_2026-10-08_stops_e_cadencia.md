# Incidente 2026-10-08 — 3 stops simultaneos + cadencia degradada desde 14/09

## Resumo

| Item | Conclusao |
|---|---|
| 3 stops de 08/10 17:40 UTC (SOL, BNB, BTC) | Queda correlacionada do mercado. **A protecao funcionou** (TP/SL nativos executaram). |
| Causa raiz da lentidao | `SELF_DISPATCH_PAT` **expirou/foi revogado em 14/09/2026** -> HTTP 401 |
| Ultimo `workflow_dispatch` antes da falha | **2026-09-14 21:13:08 UTC** (run #21956) |
| Duracao | **~24 dias** (14/09 21:13 -> 09/10 01:02 UTC) |
| Cadencia real no periodo | **~4-5 scans/dia** (so o cron best-effort `*/15` do GitHub), em vez de 1 a cada ~5 min |
| Correcao | Token novo gerado em 09/10 (fine-grained, so este repo, **Actions: RW**, **sem vencimento**), trocado no cron do servidor e no secret `SELF_DISPATCH_PAT` |
| Primeiro dispatch apos a troca | **2026-10-09 01:02:36 UTC** (run 37867809407) |

## Por que ficou invisivel por 24 dias

O cron do servidor (`ineocom`) e o self-chain do `main.yml` usam o **mesmo token**.
Quando ele expirou, os dois pararam juntos. O passo `Re-arm next scan` usava
`curl -s ... && echo ok || echo falha`: o `curl` retorna 0 mesmo com HTTP 401,
entao o run ficava **verde** e nada alertava. Restou so o cron do GitHub, que
na pratica dispara poucas vezes por dia.

## Correcao no `main.yml` (este commit)

O passo de re-disparo agora captura o HTTP (`-w "%{http_code}"`) e:

- **204** -> segue normal;
- **qualquer outro** -> emite `::error` com a dica (401 token expirado / 403 permissao /
  404 repo nao selecionado) e **sai com codigo 1** -> run **vermelho** no Actions
  (e e-mail de falha do GitHub).

O scan e o commit de estado ja rodaram antes desse passo, entao a falha nao
perde dados — so torna o problema visivel.

## Impacto na reauditoria do degrau (`docs/reauditoria_degrau_2026-10-08.md`)

Os **6 trades da janela "desde 04/09"** (0 wins, -$2.41) foram, em sua maioria,
abertos/fechados **com o bot em cadencia degradada** (entradas e saidas
potencialmente atrasadas em ate horas). O placar mistura desempenho da
estrategia com falha de infraestrutura.

Decisao: a decisao de **manter $10** nao muda (ela so ficaria mais conservadora).
Para a proxima reauditoria, marcar os trades abertos entre **14/09 21:13 UTC e
09/10 01:02 UTC** como `cadencia_degradada` e reportar o resultado **com e sem**
esses trades.

## Seguranca do token novo

- Escopo minimo: so `crypto-signal-bot`, **Actions: Read and write** (+ Metadata RO).
  Nao le nem altera codigo nem secrets.
- **Sem vencimento** por escolha do usuario: elimina a recorrencia deste incidente;
  em troca, se vazar (log, print, chat), **revogar imediatamente** e repetir a troca.
- O token nunca foi colado no chat; a troca no cron foi feita com backup
  (`~/crontab.bak-*`, chmod 600) e com o historico do shell desligado.

## Verificacao pendente

- Confirmar que voltaram runs `workflow_dispatch` a cada ~5 min (servidor + self-chain).
- Confirmar que o primeiro run com este `main.yml` termina com o passo de re-disparo
  em **HTTP 204**.

## Rollback

`git revert` deste commit restaura o passo antigo (silencioso). Nao recomendado.
