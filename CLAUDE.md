# CLAUDE.md — crypto-signal-bot

Bot de sinais e **execução real** de cripto spot na Gate.io (só compra), rodando no GitHub Actions, com relay PHP
num servidor cPanel. Dono: Nélio Castro. Fuso: **America/Bahia (UTC−3)**. Responda em **português do Brasil**.

> ⚠️ **Opera com DINHEIRO REAL.** Qualquer mudança que toque ordem, stop, TP, sizing ou o relay exige kill-switch,
> rollback de 1 linha, testes e aprovação explícita do usuário.

## Memória e documentos
@memoria.md

| Documento | Quando ler |
|---|---|
| `memoria.md` | sempre (carregado acima): decisões D-/R-, lições, pendências |
| `docs/arquitetura.md` | stack, módulos, relay, cadência, workflows, `state/`, servidor, limites da Gate.io |
| `docs/estrategias.md` | o que cada ativo opera, regras de entrada/saída, kill-switches, parâmetros de execução |
| `docs/operacao.md` | auditoria, deploy do relay, token, cron PAXG, reconciliação, posições manuais |
| `docs/resultado_financeiro.md` | placar real (datado) |
| `docs/historico/` | evidência original das decisões; não editar, só consultar |

**Autoridade:** valores = código (`bot/config.py` é a fonte única). Porquês = decisões aprovadas e datadas no
`memoria.md`, que prevalecem sobre os outros docs. Os docs descrevem. Se código, memória e docs divergirem,
**pare e avise**: não escolha um lado sozinho.

## Regras de trabalho
1. **Se algum pedido meu contradisser uma decisão registrada em @memoria.md ou qualquer outro doc relevante, pare e
   me avise antes de realizar qualquer alteração. Explique qual decisão seria afetada e pergunte se desejo
   substituí-la.**
2. Antes de qualquer alteração relevante, releia as seções **Decisões aprovadas** e **Decisões rejeitadas** do
   `memoria.md`.
3. Não altere a stack técnica sem minha autorização (`docs/arquitetura.md`).
4. Não remova uma decisão aprovada silenciosamente: marque como substituída e arquive.
5. Não invente informações técnicas sobre o projeto. Verifique o repositório real e o código antes de afirmar;
   diga o que não conseguiu verificar.
6. Antes de uma mudança grande, apresente um plano resumido.
7. Depois de uma decisão importante aprovada, atualize o `memoria.md` (e o doc técnico afetado) no mesmo commit.

## Regras de engenharia
- Mudanças **aditivas**; não renomeie símbolos existentes; mantenha aliases (`SYMBOLS = WATCHLIST`,
  `evaluate = evaluate_signal`).
- Toda feature nova tem **kill-switch booleano** e rollback de 1 linha. Imports opcionais com `try/except`:
  uma feature nova nunca derruba o scan.
- Antes de commitar: `python -m py_compile bot/*.py`, `python tests/test_roteamento_strings.py`,
  `python tests/test_saida_tp1.py`, `python tests/test_renovacao_sl.py`. O workflow `checks` roda `php -l` no relay e os testes no GitHub.
- `server/execute.php` exige **deploy manual** conferido por bytes e hash (`docs/operacao.md`). Flag que dependa do
  PHP só se liga depois do deploy.
- Mensagens de commit em português; não commite `__pycache__`.

## Proibido sem aprovação explícita
- Alterar `EXECUTION_*`, stops, TP/SL, sizing ou `server/execute.php`.
- Subir o degrau de capital (hoje US$ 10/ordem) fora da regra D-024.
- Propor ou implementar SHORT (D-002).
- Reativar estratégia desligada ou mudar a watchlist fora de `bot/config.py`.
- Dar ao bot poder de cancelar ordens que ele não criou (D-025).
- Colar token, secret ou HMAC em chat, log, print ou commit.

## Para lembrar sempre
- Run verde ≠ passo funcionou. Fix commitado ≠ fix deployado. Tela do app ≠ status real da ordem (use a API).
- Qualquer registro com status `open*` em `state/positions.jsonl` conta como posição viva.
- No servidor, use caminhos absolutos (`/home/ineocom/...`); logado como root, `~` é `/root`.
