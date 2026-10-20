# D-038 — Estrutura de documentação e contexto do agente

> Status: aprovada em 2026-10-19 | substitui: D-030 (2026-10-15) | substituída por: —

## Contexto
O D-030 organizou o projeto em `CLAUDE.md` + `memoria.md` + 4 docs + `docs/historico/`. Em 2026-10-19 o usuário trouxe
um framework de contexto para agentes (índice curto, ADRs, specs, runbooks, reference, incidents, journal de tarefa,
memória do agente, backlog, tríade CLAUDE/AGENTS/GEMINI) e pediu a comparação. A estrutura atual já cobria a maior
parte, mas havia buracos concretos:
- **não existia `.gitignore`**: 113 itens não rastreados (`._*` do exFAT, `__pycache__`) a um `git add -A` do commit;
- **o fluxo de trabalho não estava escrito** (plano → aprovação → checks → diff → commit só dos arquivos listados →
  deploy por hash), só praticado em conversa;
- **pendências voláteis dentro do `memoria.md`**, contra a regra do próprio arquivo ("sem estado volátil"); em
  2026-10-19 havia 2 itens desatualizados (cron PAXG "a decidir" já decidido; watchdog "a deployar" já instalado);
- **nenhum lugar para tarefa em andamento** (a instalação do watchdog ficou esperando uma conferência só na conversa);
- **memória do agente vazia**: preferências do usuário só valiam dentro da conversa;
- decisões registradas sem as **alternativas descartadas**, e o `memoria.md` crescendo (6 decisões só em 2026-10-15).

## Alternativas
| Opção | Prós | Contras |
|---|---|---|
| **A. Manter o D-030 e só fechar os buracos (escolhida)** | não quebra links nem citações em commits e decisões; mudança pequena | `memoria.md` continua sendo a fonte das decisões antigas (sem alternativas) |
| B. Adotar o framework inteiro (`docs/decisions`, `runbooks`, `reference`, `incidents`, `openspec`, tríade, backlog externo) | padrão replicável em outros projetos | 9 lugares para um projeto solo; renomear `operacao.md`/`arquitetura.md` quebra referências; openspec é ferramenta nova; backlog fora do repo exige conector; tríade exige manter 3 cópias iguais |
| C. Não mudar nada | zero custo | os buracos acima continuam (o do `.gitignore` é risco direto) |

## Decisão
Opção A. Ficam adotados do framework:
1. `.gitignore` (segredos, `__pycache__`, `._*`, `.DS_Store`, `.agent-work/`).
2. `CLAUDE.md` ganha os blocos **Fluxo de trabalho** e **Emergência**, e a tabela passa a listar onde vive cada coisa.
3. Pendências e próximos passos saem do `memoria.md` para `docs/pendencias.md`.
4. Journal de tarefa em `.agent-work/<tarefa>.md`, local e fora do Git, só para tarefa que atravessa sessões ou depende
   de o usuário agir no servidor.
5. ADR leve em `docs/decisoes/` só para decisão **nova** com trade-off real; o `memoria.md` continua sendo o índice e a
   autoridade dos porquês. As decisões antigas não são migradas.
6. Specs como cenários QUANDO/ENTÃO no `estrategias.md`, cada um ligado ao teste que o prova (sem openspec).
7. Memória do agente (fora do repo) só para preferências e correções do usuário, não para fatos do projeto.

Não adotados: tríade de agentes, backlog externo, pastas `incidents/`, `runbooks/` e `reference/` separadas, openspec.

## Consequências
- A regra de autoridade continua: código > `memoria.md` > docs; divergência = parar e avisar.
- O D-030 tinha descartado "um `.md` solto por decisão"; a diferença agora é que o ADR é exceção (só com trade-off),
  segue modelo fixo e o `memoria.md` continua sendo o índice único.
- `docs/pendencias.md` precisa ser atualizado a cada sessão; item resolvido sai de lá.
- Journal local se perde se a máquina ou o SSD falhar: por isso não guarda nada que precise durar (isso vai para
  `memoria.md`, `pendencias.md` ou `operacao.md` ao fim da tarefa).
- Reavaliar a tríade se outro agente (Codex, Gemini) passar a trabalhar no repositório.

## Referências
`docs/memoria-arquivo.md` (D-030), `CLAUDE.md`, `docs/pendencias.md`, `docs/estrategias.md` (cenários).
