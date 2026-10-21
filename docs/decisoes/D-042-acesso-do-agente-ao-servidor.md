# D-042 — Acesso do agente ao servidor por SSH, só leitura, via porteiro

> Status: aprovada em 2026-10-21 | substitui: — | substituída por: —

## Contexto
Toda conferência no servidor (hashes, logs, crontab, testes HTTP) dependia de o usuário copiar comandos do chat,
rodar no terminal web do cPanel e colar a saída de volta. Isso custa idas e voltas e já gerou enganos de digitação
(placeholder literal, comando sem espaço). O servidor guarda as chaves da Gate, o HMAC e os tokens, e o relay envia
ordens com dinheiro real: um acesso amplo do agente seria um risco desproporcional. A porta 22 aceita conexões
(OpenSSH 9.9, conferido em 2026-10-21).

## Alternativas
| Opção | Prós | Contras |
|---|---|---|
| **A. SSH com chave restrita a um porteiro só de leitura (escolhida)** | o agente confere sozinho; a chave só executa ações de um menu fixo; nada de shell, escrita ou segredo; rollback = apagar 1 linha | exige criar e instalar o porteiro; deploy e mudanças continuam manuais |
| B. SSH normal com a conta `ineocom` | o agente faz tudo, inclusive deploy | acesso ao `.env` e a qualquer arquivo; um erro ou uma instrução maliciosa vira dano real |
| C. SSH como `root` | sem limites | risco máximo; descartado |
| D. Manter copiar e colar | zero risco novo | lento e sujeito a erro humano |

## Decisão
Opção A. A chave do agente nasce no Mac do usuário (`~/.ssh/cryptosignals_agent`, ed25519, com senha guardada no
Keychain) e é autorizada no `authorized_keys` do `ineocom` com `restrict,command="/usr/local/bin/php
/home/ineocom/cryptosignals/bin/agent_gate.php"`. Toda conexão com essa chave cai no `server/agent_gate.php`, que
aceita só `help`, `status`, `hashes`, `crontab`, `env-keys` e `http`, com nome exato, sem argumentos. Toda saída
passa por uma máscara de segredos e toda chamada é registrada em `agent_gate.log`. O agente usa só
`ssh cryptosignals-gate <ação>`. Rollback: apagar a linha da chave no `authorized_keys`.

## Consequências
- O agente faz sozinho as conferências de paridade (hash), logs, crontab e HTTP; o usuário só age para mudar algo.
- Deploy, crontab e `.env` continuam com o usuário (fase 2, deploy controlado, é decisão separada).
- `env-keys` mostra só nomes de chaves; o porteiro nunca lê valor de segredo para exibir.
- O `.env` continua legível pela conta `ineocom` (o porteiro roda como ela): a proteção é o menu fixo, não a
  permissão de arquivo. Mudar o menu é mudar código versionado, com teste e revisão.
- Chave antiga `id_rsa.1781635343` segue autorizada no cPanel com origem não registrada: revisar à parte.

## Referências
`server/agent_gate.php`, `tests/test_agent_gate.php`, `docs/operacao.md` (seção 11), `CLAUDE.md`.
