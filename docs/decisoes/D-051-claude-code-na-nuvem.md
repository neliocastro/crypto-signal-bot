# D-051 — Claude Code na nuvem sem segredos e sem acesso ao servidor

> Status: aprovada em 2026-10-27 | ajusta: D-038 (journal) e o fluxo de commit do `CLAUDE.md` | substituída por: —

## Contexto
O usuário quer trabalhar de máquinas diferentes com sessões do Claude Code na nuvem, com o GitHub como fonte do
código e sem clonar o repositório em cada uma. O bot opera dinheiro real, o repositório é público (D-041) e os
segredos vivem no `.env` do servidor e nos Secrets do GitHub Actions. Três regras do projeto supunham o agente no
Mac: commit direto no `main`, journal local em `.agent-work/` (D-038) e acesso ao servidor pela chave do porteiro
(D-042).

Auditoria de 2026-10-27: nenhum `.env` no índice nem no histórico (18.897 commits); nenhum token real no código.
O único achado com formato de token são valores fictícios de `tests/test_agent_gate.php`.

## Alternativas
| Opção | Prós | Contras |
|---|---|---|
| A (escolhida) Nuvem sem segredos: rede **Trusted**, sem variáveis, sem network secrets, sem acesso ao servidor | A sessão não consegue assinar ordem, falar com a Gate ou com o Telegram; nada sensível sai do servidor | Testes de integração e conferências do servidor seguem só no Mac |
| B Cadastrar `EXECUTION_HMAC_SECRET`/Telegram como network secrets | A nuvem poderia testar o relay e mandar mensagem | A sessão passa a poder **usar** o segredo, e quem tem o HMAC assina ordem real |
| C Levar a chave do `cryptosignals-gate` para a nuvem | Conferências de servidor de qualquer lugar | Fere o D-042 (chave só no Mac do usuário); chave fora do controle dele |
| D Versionar `.agent-work/` | O journal atravessa máquinas | Repositório público: risco de vazar dado pessoal (D-041) |

## Decisão
1. Ambiente de nuvem com **Network access = Trusted**, **sem variáveis de ambiente** e **sem network secrets**. O
   setup só instala `requirements.txt` e PyYAML. Os nomes das variáveis, sem valor, ficam em `.env.example`.
2. Mudança relevante (código, workflow, relay, flags, docs de decisão) vai por **branch + PR**, com merge só pelo
   usuário depois do `checks` verde. Ajuste trivial de doc pode seguir direto no `main`, como antes.
3. O estado de tarefa entre sessões fica em `docs/pendencias.md` (seção "Em andamento") ou na descrição do PR. O
   `.agent-work/` continua local, só como rascunho.
4. A sessão na nuvem não acessa o servidor (D-042 intacto). Conferência de servidor é feita no Mac ou com o usuário
   colando a saída.

Rollback: apagar o ambiente de nuvem e desinstalar o Claude GitHub App; o fluxo local continua igual.

## Consequências
- O que exige servidor, Gate ou Telegram não dá para validar na nuvem; isso é de propósito.
- O GitHub proxy não restringe para quais branches a sessão faz push: a proteção do `main` é recomendada
  (`CLOUD_SETUP.md`, checklist), sem bloquear os commits de `state/` do bot.
- Reavaliar se surgir uma tarefa de nuvem que precise de uma API externa: vira decisão nova antes de qualquer
  network secret.

## Referências
`CLOUD_SETUP.md`, `.env.example`, `.gitignore`; D-038, D-041, D-042; documentação oficial: Use Claude Code in the
cloud e Configure cloud environments (code.claude.com, conferida em 2026-10-27).
