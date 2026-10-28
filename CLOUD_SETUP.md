# Claude Code na nuvem — crypto-signal-bot

> Criado em 2026-10-27 (D-051). Como trabalhar neste repositório com sessões do Claude Code na nuvem, de
> qualquer máquina, sem clonar o repositório e **sem levar segredo nenhum para a nuvem**.
> Termos e telas conferidos na documentação oficial em 2026-10-27:
> [Use Claude Code in the cloud](https://code.claude.com/docs/en/claude-code-on-the-web) e
> [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments). Se a tela mudar, a documentação vence.

## Em uma frase

O GitHub é a fonte do código; a sessão na nuvem só **lê, edita, roda testes e abre PR**. Ela não fala com a Gate.io,
com o relay, com o servidor nem com o Telegram, e não recebe nenhum segredo.

## 1. Conectar o repositório

1. Em [claude.ai/code](https://claude.ai/code), conclua o onboarding e autorize o **Claude GitHub App** no repositório
   `neliocastro/crypto-signal-bot`. O App também habilita o **Auto-fix** de PR.
   Alternativa: `/web-setup` no terminal (usa o token do `gh` local).
2. As credenciais do GitHub **não entram na VM**: o *GitHub proxy* as anexa do lado do servidor. O proxy recusa
   apagar branch e enviar tag, mas **não limita quais branches** recebem push. Por isso a seção 6 pede a proteção do `main`.

## 2. Ambiente de nuvem (uma vez)

No seletor de ambiente abaixo da caixa de mensagem: **New environment**. Preencha:

| Campo | Valor | Por quê |
|---|---|---|
| Nome | `crypto-signal-bot` | — |
| **Network access** | **Trusted** (padrão) | Libera PyPI, GitHub etc. Gate.io, Telegram e o servidor **não** estão na lista: a sessão não alcança o relay nem a exchange. Não use **Full**. |
| **Environment variables** | **vazio** | Os testes não precisam de variável. Quem usa o ambiente consegue ler esses valores: segredo nunca vai aqui. |
| **Network secrets** | **nenhum** | Ver seção 3. |
| **Setup script** | o bloco abaixo | Instala o que os checks do `CLAUDE.md` pedem. |

```bash
#!/bin/bash
# Roda como root no Ubuntu 24.04 antes do Claude iniciar. PHP 8.3 e Python 3 ja vem instalados.
pip install -r requirements.txt pyyaml || true
```

O setup roda **antes** das variáveis do ambiente existirem e fica em cache por cerca de 7 dias.

## 3. Variáveis e segredos: onde cada um fica

| Variável | (a) Ambiente de nuvem | (b) Network secret | (c) Onde fica |
|---|---|---|---|
| `GATE_API_KEY`, `GATE_API_SECRET` | não | **não** | só no `.env` do servidor |
| `EXECUTION_HMAC_SECRET` | não | **não** | `.env` do servidor + Secret do GitHub Actions |
| `SELF_DISPATCH_PAT` | não | **não** | `.env` do servidor + Secret do GitHub Actions |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | não | **não** | `.env` do servidor + Secret do GitHub Actions |
| `TELEGRAM_BOT_TOKEN` | não | **não** | Secret do GitHub Actions (alias) |

- **(a) Variáveis não sensíveis para a nuvem:** nenhuma é necessária hoje.
- **(b) Network secrets:** nenhum. Um network secret fica fora da VM, mas a sessão consegue **usá-lo**. Com o
  `EXECUTION_HMAC_SECRET`, por exemplo, ela poderia assinar ordens reais no relay. O trabalho na nuvem é código e
  testes; nada nele precisa chamar essas APIs.
- **(c) Só no servidor e no GitHub:** todas. Os nomes, sem valores, estão em [`.env.example`](.env.example).

Se um dia surgir um caso que precise de um network secret, ele vira decisão nova no `memoria.md` antes de ser cadastrado.

## 4. Começar numa máquina e continuar em outra

Nada fica preso a uma máquina: a sessão roda na nuvem e o código vive no GitHub.

- **Começar:** pelo navegador ([claude.ai/code](https://claude.ai/code)), pelo app Claude (aba **Code**), pelo app
  desktop (ambiente em **Cloud**) ou pelo terminal: `claude --cloud "tarefa"`. O terminal clona o **branch do GitHub**,
  não a cópia local: faça push antes.
- **Continuar em outra máquina:** abra a mesma sessão em claude.ai/code ou no app. Para mandar um recado sem abrir:
  `claude -p "mensagem" --cloud <id-da-sessão>`.
- **Trazer para um terminal com clone** (opcional): `claude --teleport` (ou `/teleport` dentro da sessão). Exige
  árvore limpa e o mesmo repositório. A cópia local vira uma sessão separada.
- **Estado da tarefa entre sessões:** vai em `docs/pendencias.md`, seção "Em andamento", ou na descrição do PR
  (D-051). O `.agent-work/` é local e não chega na nuvem.
- **Sessão parada por inatividade:** reabrir pelo claude.ai/code restaura a conversa. Comandos em segundo plano precisam
  ser rodados de novo.

## 5. Revisar e fazer o merge do PR

1. A sessão trabalha num branch próprio e, ao terminar, abre o PR. Para isso, peça a ela "abrir PR"
   (o PR também pode ser criado pelo cartão **Changes**).
2. Revise no cartão **Changes**: diff linha a linha, comentários por linha devolvidos ao Claude, **Compare against**.
3. Confira no GitHub:
   - o workflow `checks` verde no PR;
   - a lista de arquivos tocados;
   - nenhum valor parecido com token no diff.
4. Merge **só por você**, no GitHub. Depois do merge, confira de novo o `checks` no `main`.
5. Conflito com o `main`: o bot commita `state/` a cada scan. Se um PR conflitar, peça à sessão um rebase. Um PR
   não deve tocar em `state/`.
6. **Auto-fix** (menu **⋮** do PR no **Changes**) faz a sessão corrigir CI e responder comentários sozinha. As
   respostas saem com o **seu** usuário do GitHub. Use só em PR de código e testes.

Regras que continuam valendo (`CLAUDE.md`): ordem, stop, TP, sizing, `EXECUTION_*`, workflow e `server/execute.php`
exigem sua aprovação explícita. Merge de código não é deploy: o relay e os scripts do servidor seguem pelo roteiro
manual do `docs/operacao.md`.

## 6. O `.env` real fica só no servidor

- Caminho: `/home/ineocom/cryptosignals/secrets/.env`, fora da web root. Editado só por você (`nano`).
- O repositório nunca teve `.env` (auditoria de 2026-10-27: nada no índice nem nos 18.897 commits). O `.gitignore`
  bloqueia `.env` e `.env.*`, com exceção só para o `.env.example`.
- A sessão na nuvem **não acessa o servidor**: a chave do porteiro `cryptosignals-gate` (D-042) existe só no Mac e
  **nunca** vai para o ambiente de nuvem. Conferências de servidor (`resumo`, hashes, deploy) são feitas numa sessão
  local no Mac ou com você colando a saída no chat.

## 7. Checklist de segurança antes do primeiro uso

- [ ] O Claude GitHub App está instalado só neste repositório, ou só nos que você quiser.
- [ ] Ambiente com **Network access = Trusted**, **Environment variables vazio**, **Network secrets vazio**.
- [ ] O setup script é só o da seção 2, sem nenhum valor sensível (todo mundo que usa o ambiente consegue lê-lo).
- [ ] No GitHub, regra de proteção do `main`: o push direto fica para você e o bot. Exigir PR para os demais e o
      `checks` verde para o merge, se fizer sentido. Atenção: o bot commita `state/` no `main`; a regra não pode
      bloquear o `GITHUB_TOKEN` do workflow.
- [ ] Visibilidade das sessões em **Private** (conta Pro/Max). Não compartilhe sessões: o repositório é público,
      mas a conversa pode ter dados de operação.
- [ ] Primeira sessão: pedir `git ls-files | grep -E '(^|/)\.env'` (esperado: só `.env.example`) e rodar os checks
      do `CLAUDE.md`.
- [ ] Combinado: a sessão na nuvem **não** faz merge, deploy nem chamada à Gate, ao relay ou ao Telegram.

## Emergência

Igual ao `CLAUDE.md`, seção "Emergência". Para parar uma sessão na nuvem: pare ou arquive pelo claude.ai/code.
Para cortar o acesso da nuvem ao repositório: desinstale o Claude GitHub App no GitHub (Settings → Applications) e,
se tiver usado `/web-setup`, revogue o token do `gh`.
