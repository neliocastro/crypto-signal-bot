# Saida validada do Mare Alta (TP1 50% + breakeven) - 2026-10-15

> Implementacao **aprovada pelo usuario em 15/10/2026** (item 1 de
> `docs/trailing_vela_fechada_2026-10-15.md`). Entra **DESLIGADA**:
> `MARE_ALTA_PARTIAL_TP_ENABLED = False` ate o `execute.php` (FIX 10) estar no servidor.

## Contexto

O backtest fiel que aprovou BTC/SOL/TRX/BNB (`docs/decisao_stop_e_universo_2026-08-23.md`)
usa: stop 2.5x ATR -> **TP1 +10% vendendo 50%** -> **stop no breakeven** -> trailing 3x ATR
no restante. A execucao real fazia outra coisa: TP unico em 2.0x o risco (~+23%) para 100%
da base + trailing desde o primeiro dia. O script do backtest fiel nao esta no repositorio;
a regra abaixo segue a descricao de `bot/mare_alta.py` e dos docs.

## Regra implementada (com a flag ligada, so sinais `MARE_ALTA_D1`)

| Fase | Stop | TP |
|---|---|---|
| Compra | `ref - 2.5 x ATR` (piso 0.8%), base inteira - **inalterado** | `ref x 1.10`, so **50%** da base |
| Antes do TP1 | **fixo** (trailing nao mexe) | aberto |
| TP1 dispara | novo SL no **preco de entrada (fill)** so com o restante; o antigo e deletado | - |
| Depois do TP1 | trailing 3x ATR em vela D1 fechada, piso = breakeven (catraca) | nenhum |

HYPE / outros trilhos e posicoes abertas antes da flag: comportamento antigo.

Breakeven = preco medio do fill (sem somar taxas): saida no breakeven custa ~0.2% de taxa.

## Como funciona

1. `executor.build_order`: com a flag, TP vira +10% e o pedido leva `tp_frac = 0.5`.
2. `execute.php` FIX 10: cria o TP so com `floor(base x 0.5)`, se as duas metades respeitam
   `min_base`; senao cai no TP da base inteira e devolve `tp_frac_note`. Responde
   `tpsl.tp_frac_applied` e `tpsl.tp.qty`.
3. `main.py`: so marca a posicao como `tp_partial` se o PHP confirmou (`tp_frac_applied`).
   Se o pedido tinha `tp_frac` e o PHP nao aplicou, avisa no Telegram (PHP antigo).
4. `oco_guard` manda `tp_partial` no `oco_sync`. FIX 10: TP1 `finish` **nao cancela o SL**;
   devolve `tp1_hit`. O Python chama `update_trailing` (cria o SL no breakeven com
   `base_qty - tp1_qty` -> confirma -> deleta o SL antigo). Falhou? O SL antigo fica e
   tenta de novo no proximo scan (aviso no Telegram uma vez).
5. `mare_alta_trailing`: pula posicoes `tp_partial` antes do TP1; depois anda com a qty restante.

Campos novos em `state/positions.jsonl`: `tp_partial`, `tp1_qty`, `tp1_done`, `tp1_hit_at`,
`tp1_order_id`, `tp1_price`. Apos o TP1 `base_qty` passa a ser o restante.

**Janela conhecida:** entre o TP1 disparar e o proximo scan (~5 min) o SL antigo ainda e da
base inteira. Se o preco cair do +10% ate o stop nesse intervalo, a venda do SL falha por saldo
e o proximo scan cria o SL do restante. Risco aceito (queda de >15% em minutos).

## Testes

`tests/test_saida_tp1.py` (sem rede, relay simulado): build_order com/sem flag e HYPE;
ciclo completo compra -> stop fixo -> TP1 -> breakeven -> trailing -> closed_sl; falha no
breakeven (SL antigo mantido, 1 aviso); TP1 e SL no mesmo intervalo; posicao antiga.
`php -l`: workflow `.github/workflows/checks.yml` (roda em push de `server/`, `bot/`, `tests/`).

## Deploy (ordem obrigatoria)

1. Conferir o workflow **checks** verde no GitHub (lint do PHP + testes).
2. Pasta do relay: **`/home/ineocom/public_html/cryptosignals/`** (caminho absoluto; logado como
   `root`, `~` e `/root`). Backup: `cp -p execute.php execute.php.bak-20261015`.
   Versao em producao antes do deploy (conferida 15/10): 18344 bytes / 232 linhas, sha256
   `2926114e...` = commit `4b78f981d` + os 2 hotfixes manuais de 20/08 (`sspot`->`spot`, teto 10.0).
   Fora comentarios, identica ao `99aecc3ab`: o upload nao perde nada que so existia no servidor.
   Baixar a versao fixada no commit, conferir o hash e so entao substituir:
   `curl -fsSL https://raw.githubusercontent.com/neliocastro/crypto-signal-bot/b1b0f8fb82a2eca3732aa2086c3c49c2cec33df1/server/execute.php -o execute.php.new`
3. Conferir (fix commitado != fix deployado): `execute.php.new` com **20996 bytes / 262 linhas** e
   sha256 `6e3da8cb72252d362a99d0abd4129bd2943aa3b9668e04212eaf482385499c23`. Depois
   `mv execute.php.new execute.php && chown ineocom:ineocom execute.php && chmod 644 execute.php`
   (arquivo de root pode dar HTTP 500 no PHP da conta) e `curl` no endpoint: esperado HTTP 401.
4. So entao: `MARE_ALTA_PARTIAL_TP_ENABLED = True` em `bot/config.py` (commit proprio).

Ordem inversa (flag antes do PHP): o PHP antigo ignora `tp_frac` e cria o TP de +10% na base
inteira; o bot avisa no Telegram e a posicao segue o modo antigo.

## Rollback

- Python: `MARE_ALTA_PARTIAL_TP_ENABLED = False` (posicoes ja abertas em modo parcial seguem
  o ciclo ate fechar, porque o estado fica gravado na posicao).
- PHP: `cp execute.php.bak-20261015 execute.php`. Sem `tp_frac`/`tp_partial` o FIX 10 e inerte.

## Ainda nao tratado (pre-existente)

- Gatilhos da Gate expiram em 30 dias (`expiration` 2592000 no PHP). Trade do Mare Alta que
  dure mais que isso perde TP/SL; o trailing recria o SL ao subir, mas o TP1 nao.
- Fechamentos `closed_sl` nao gravam `exit_price`; com TP1 parcial, o placar precisa somar a
  perna do TP1 (`tp1_price` x `tp1_qty`) a do stop.
