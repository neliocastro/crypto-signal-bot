# Crypto Signal Bot 🤖

Bot de sinais e **execução real** de cripto spot na Gate.io (só compra). O Python roda no GitHub Actions, decide e
assina as ordens; um relay PHP num servidor com IP fixo as envia à exchange.

> ⚠️ Opera com **dinheiro real**. Antes de mudar qualquer coisa, leia [`CLAUDE.md`](CLAUDE.md) e [`memoria.md`](memoria.md).

## Documentação
| Documento | Conteúdo |
|---|---|
| [`memoria.md`](memoria.md) | decisões aprovadas e rejeitadas, lições, pendências |
| [`docs/arquitetura.md`](docs/arquitetura.md) | stack, módulos, relay, cadência, estado, servidor |
| [`docs/estrategias.md`](docs/estrategias.md) | o que cada ativo opera e com quais parâmetros |
| [`docs/operacao.md`](docs/operacao.md) | auditoria, deploy, diagnóstico, posições manuais |
| [`docs/resultado_financeiro.md`](docs/resultado_financeiro.md) | placar real |
| [`docs/historico/`](docs/historico/) | evidência original (incidentes, auditorias, backtests) |

## Verificar antes de commitar
```bash
python -m py_compile bot/*.py
python tests/test_roteamento_strings.py
python tests/test_saida_tp1.py
```
