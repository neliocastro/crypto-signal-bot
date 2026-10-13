# Crypto Signal Bot 🤖

Bot de sinais e **execução real** de cripto spot na Gate.io (só compra/LONG), rodando no GitHub Actions.
O Python decide e assina com HMAC; o relay PHP (`server/execute.php`, servidor com IP fixo) envia as ordens.

> ⚠️ Opera com **dinheiro real**. Leia [`CLAUDE.md`](CLAUDE.md) antes de mudar qualquer coisa.

## Estratégias (resumo em 13/10/2026)
- **Maré Alta D1** — BTC, SOL, TRX, BNB (único trilho que hoje pode gerar ordem).
- **Breakout 1h** — HYPE, **desligado** desde 13/10 (`BREAKOUT_ENABLED = False`).

O detalhe vigente fica em [`docs/estado_atual.md`](docs/estado_atual.md) e
[`docs/mapa_estrategias.md`](docs/mapa_estrategias.md). Este resumo pode envelhecer; aqueles são
revisados a cada mudança.

## Documentação
Índice completo em [`docs/README.md`](docs/README.md) (documentos vivos, registros datados e superados).

## Mudar a watchlist
`bot/config.py` é a fonte única de verdade (`WATCHLIST`). O universo do Maré Alta é
`MARE_ALTA_UNIVERSE` em `bot/mare_alta.py`. Atualize `docs/estado_atual.md` no mesmo commit.

## Verificar antes de commitar
```bash
python -m py_compile bot/*.py
python tests/test_roteamento_strings.py
```
