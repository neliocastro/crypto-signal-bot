# Estratégias, roteamento e parâmetros de execução

> Revisado em 2026-10-15. Descreve **o que o bot opera hoje** e com quais parâmetros. Valores conferidos em
> `bot/config.py` e `bot/mare_alta.py`; em divergência, o código vence. O porquê de cada escolha está em
> `memoria.md` (IDs D-/R-). Ao mudar roteamento, kill-switch ou parâmetro, atualize este arquivo no mesmo commit.

## Resposta curta

```
Maré Alta D1  -> BTC  SOL  TRX  BNB   (diário)   ÚNICO trilho que hoje pode gerar ordem real
Breakout 1h   -> HYPE                 DESLIGADO desde 2026-10-13 (D-013)
```

**Watchlist (scan intraday, 5):** BTC, SOL, TRX, BNB, HYPE (`WATCHLIST` em `bot/config.py`).
**Universo do Maré Alta (4):** `MARE_ALTA_UNIVERSE` em `bot/mare_alta.py`, independente da watchlist.

## Tendência Diária (antiga "Maré Alta D1"; id `MARE_ALTA_D1`, `bot/mare_alta.py`) — em produção

- **Entrada (vela D1 fechada):** MACD(12,26,9) cruza acima da linha de sinal (vale abaixo de zero, D-014) **e**
  EMA9 > EMA21. Um alerta por vela (`state/mare_alta_state.json`).
- **Saída (D-027, `MARE_ALTA_PARTIAL_TP_ENABLED = True`):**

| Fase | Stop | Alvo |
|---|---|---|
| Compra | `ref − 2,5×ATR` (piso 0,8%), posição inteira | TP1 = `ref × 1,10`, **50%** da posição |
| Antes do TP1 | fixo (sem trailing) | TP1 aberto |
| TP1 executa | novo SL no **preço de entrada**, só o restante | nenhum |
| Depois do TP1 | trailing `close_D1 − 3×ATR`, vela fechada, catraca (só sobe; piso = breakeven) | nenhum |

  Se o relay não aplicar o TP parcial (qty abaixo do mínimo), o TP sai na base inteira e o bot avisa no Telegram;
  essa posição segue o modo antigo (TP 2,0R + trailing desde o início).
- **Validação:** walk-forward jul/2026 (carteira PF 1,64; OOS PF 2,08). Backtest fiel com stop 2,5×:
  BTC 1,28 · SOL 4,51 · TRX 2,21 · BNB 2,15. O script desse backtest não está no repositório.
- Kill-switches: `MARE_ALTA_ENABLED`, `MARE_ALTA_SHADOW_MODE` (False = ordens reais), `MARE_ALTA_TRAILING_ENABLED`,
  `MARE_ALTA_TRAILING_CLOSED_ONLY`, `MARE_ALTA_PARTIAL_TP_ENABLED`.
- **Validade dos gatilhos (D-033):** a Gate expira TP e SL em 30 dias. Com 25 dias ou mais, o SL de qualquer posição
  aberta é recriado no mesmo preço e qty (`SL_RENEW_ENABLED`, `SL_RENEW_AFTER_DAYS = 25`), antes e depois do TP1.
  O TP1 não é renovado: se expirar, o Telegram avisa e a posição segue só com o stop fixo.

## Breakout / Tendência 1h (`bot/strategies.py`) — desligado

- `BREAKOUT_ENABLED = False` (D-013). Com o switch desligado, `evaluate_signal` devolve `None` para o HYPE.
- Regra (para quando religar): EMA9 > EMA21 > EMA50 + rompe a máxima de 30 velas + RSI > 50;
  `BREAKOUT_SYMBOLS = {"HYPE/USDT": {"lookback": 30, "atr_mult": 2.5}}`.
- **Dois parâmetros parecidos:** o `atr_mult` de `BREAKOUT_SYMBOLS` é do **sinal**; o stop da **ordem** vem de
  `EXECUTION_ATR_MULT_SL_BY_SYMBOL = {"HYPE/USDT": 3.0}`.
- `BREAKOUT_SHADOW_MODE = True` acrescenta `[SHADOW]` ao nome e, de propósito, quebra o match da allowlist (sem ordem).
- Desempenho ao vivo: PF ~0,78 em 12 trades (backtest original 2,55).

## Desligadas ou removidas
| Estratégia | Estado |
|---|---|
| Acúmulo RSI 4h (PAXG) | `ACCUMULATION_ENABLED = False` desde 2026-09-04 (código mantido). **O cron do servidor segue ativo por decisão do usuário (D-032)**; compra fora do bot |
| MACD-only, Integrada, Tendência MACD, Confluência | removidas do código em 2026-08-24 |
| SHORT | descartado em definitivo (D-002) |
| Acúmulo na Queda (RSI 4h < 30) em BTC e PAXG | testado em 2026-10-23: **não aprovado** contra um DCA simples (D-048) |
| Faixa Lateral (range, só compra) | testado em 2026-10-23: **arquivado** (amostra pequena, saldo negativo fora da amostra; D-048) |

## Roteamento (1 ativo = 1 trilho, D-003)

```
evaluate_signal(symbol, df, ...)                    # bot/strategies.py
  fast-path BREAKOUT -> só se BREAKOUT_ENABLED e símbolo em BREAKOUT_SYMBOLS
  fast-path ACÚMULO  -> só se ACCUMULATION_ENABLED
  demais             -> None

INTRADAY_EXEC_ALLOWLIST = {                          # bot/main.py
    ("HYPE/USDT", "Breakout / Tendência"),
    ("PAXG/USDT", "Acúmulo (RSI sobrevenda)"),       # inerte
}
```

A allowlist casa por **string exata, com acento**. Renomear o campo `strategy` em `strategies.py` faz o ativo parar de
operar em silêncio; o canário `tests/test_roteamento_strings.py` pega isso. Altere os dois arquivos no mesmo commit.
O Maré Alta roda **fora** dessa allowlist, em bloco próprio do `main.py`.

O Telegram recebe só **eventos** (sinal, ordem, TP/SL, TP1, trailing, falhas, alertas), o resumo diário e o `/status`
(D-046). O antigo resumo a cada scan, com "🟢 PRONTO / quase lá" baseado em MACD, foi desligado (`SCAN_SUMMARY_ENABLED`).

## Cenários (spec do comportamento, D-038)

O comportamento esperado, em cenários verificáveis. Cada um cita o teste que o prova
(`arquivo::função`). **Sem teste** = só descrito: é candidato a teste antes de mexer no código.
Mudou o comportamento? Atualize o cenário e o teste no mesmo commit.

| # | QUANDO | ENTÃO | Teste |
|---|---|---|---|
| C-01 | vela D1 fecha com MACD(12,26,9) cruzando acima do sinal e EMA9 > EMA21 | Maré Alta emite 1 sinal por vela e ativo | **sem teste** |
| C-02 | o executor monta a compra do Maré Alta com `MARE_ALTA_PARTIAL_TP_ENABLED` | SL = ref − 2,5×ATR; TP1 = ref × 1,10 com `tp_frac` 0,5 | `test_saida_tp1::test_build_order_flag_ligada_mare_alta` |
| C-03 | a flag está desligada, ou o trilho não é o Maré Alta | TP único 2,0R na base inteira, sem `tp_frac` | `test_saida_tp1::test_build_order_flag_desligada_ou_outro_trilho` |
| C-04 | a posição está aberta e o TP1 ainda não executou | o trailing não mexe no stop | `test_saida_tp1::test_ciclo_tp1_breakeven_trailing_fechamento` |
| C-05 | o TP1 executa | o SL vai para o preço de entrada só com o restante; depois o trailing 3×ATR sobe em catraca | `test_saida_tp1::test_ciclo_tp1_breakeven_trailing_fechamento` |
| C-06 | o relay não confirma o SL no breakeven | o SL antigo fica, o bot tenta de novo e avisa 1 vez | `test_saida_tp1::test_breakeven_falha_mantem_sl_e_avisa_uma_vez` |
| C-07 | TP1 e SL executam no mesmo intervalo | a posição fecha | `test_saida_tp1::test_tp1_e_sl_no_mesmo_intervalo_fecha_posicao` |
| C-08 | o relay não aplicou o TP parcial | a posição segue o modo antigo (trailing desde o início) | `test_saida_tp1::test_posicao_sem_tp_parcial_segue_modo_antigo` |
| C-09 | o SL de uma posição aberta tem 25 dias ou mais | é recriado no mesmo preço e qty; com menos de 25, nada | `test_renovacao_sl::test_renova_com_25_dias_mesmo_preco_e_qty`, `::test_nao_renova_antes_de_25_dias` |
| C-10 | a renovação do SL falha | o SL antigo fica e o bot avisa 1 vez por dia | `test_renovacao_sl::test_falha_mantem_sl_antigo_e_avisa_uma_vez_por_dia` |
| C-11 | o SL ou o TP1 pendente aparece `expired/cancelled/failed` | alerta 1 vez, sem fechar a posição nem mexer em ordem | `test_renovacao_sl::test_oco_alerta_sl_e_tp1_mortos_uma_vez` |
| C-12 | o OCO fecha uma posição | grava `exit_price`, `exit_qty` e `pnl_usdt_est` (somando a perna do TP1) | `test_placar::test_oco_grava_saida_no_fechamento`, `::test_pnl_tp1_e_depois_sl_no_breakeven` |
| C-13 | a perda líquida do dia UTC chega a US$ 20 | novas compras são recusadas; ganho no dia compensa | `test_trava_perda_diaria::test_bloqueia_quando_perda_do_dia_atinge_o_limite`, `::test_ganho_do_dia_compensa_perda` |
| C-14 | já há 1 posição viva ou 2 ordens no dia no mesmo ativo | a compra é recusada (D-022) | **sem teste** |
| C-15 | um sinal intraday não está na `INTRADAY_EXEC_ALLOWLIST` | não vira ordem; o Maré Alta não depende da allowlist | `test_roteamento_strings::test_allowlist_do_main_bate_com_o_contrato`, `::test_mare_alta_nao_depende_da_allowlist` |
| C-16 | o relay recebe compra de ativo fora do universo + PAXG | recusa (`symbol fora da whitelist`) | conteúdo da whitelist: `test_whitelist_php::test_whitelist_igual_ao_universo`; a recusa no PHP: **sem teste** |

## Parâmetros de execução (`bot/config.py`)

| Parâmetro | Valor | Nota |
|---|---|---|
| `EXECUTION_ENABLED` / `EXECUTION_DRY_RUN` | `True` / `False` | ordens **reais** |
| `EXECUTION_PCT` | 0,02 | 2% de `EXECUTION_PAPER_BALANCE` (1000) = US$ 20, limitado pelo teto: **na prática toda ordem é US$ 10** |
| `EXECUTION_MAX_NOTIONAL_USDT` | 10,0 | teto por ordem (D-024; espelhado no PHP) |
| `EXECUTION_MIN_NOTIONAL_USDT` | 3,0 | mínimo da Gate.io |
| `EXECUTION_ATR_MULT_SL` | 2,5 | stop inicial global (D-020) |
| `EXECUTION_ATR_MULT_SL_BY_SYMBOL` | `{"HYPE/USDT": 3.0}` | override (D-021) |
| `EXECUTION_MIN_STOP_PCT` | 0,8 | piso de distância do stop, % do preço |
| `EXECUTION_TP_RR` | 2,0 | TP = entrada + 2×risco (fora do Maré Alta com TP1 parcial) |
| `EXECUTION_TPSL_ENABLED` | `True` | TP/SL nativos em toda compra |
| `EXECUTION_MAX_OPEN` / `EXECUTION_MAX_TRADES_DAY` | 10 / 10 | limites globais (dia UTC) |
| `EXECUTION_DAILY_LOSS_STOP` | 20,0 | bloqueia **novas compras** quando a perda líquida do dia UTC chega a US$ 20; derivada do `pnl_usdt_est` do `positions.jsonl` (`EXECUTION_DAILY_LOSS_FROM_POSITIONS`, D-035). Inerte até 2026-10-15 |
| Trava de concentração | 1 posição viva + 2 ordens/dia por ativo | D-022; defaults no `executor.py` |
| `OCO_GUARD_ENABLED` | `True` | OCO emulado (D-005) |
| `SL_RENEW_ENABLED` / `SL_RENEW_AFTER_DAYS` | `True` / 25 | renova o SL antes dos 30 dias da Gate (D-033) |
| `EXIT_RECORD_ENABLED` / `EXIT_FEE_RATE` | `True` / 0,001 | grava saída e P&L estimados no fechamento (D-034) |
| `SL_EXPIRED_ALERT_ENABLED` | `True` | alerta 1x se SL ou TP1 pendente morrer sem executar (D-033) |
| `SIGNAL_COOLDOWN_HOURS` | 4 | cooldown por `símbolo|estratégia` |
| `REQUIRE_PROTECTION` (PHP) | `true` | compra sem TP nem SL é recusada (D-006) |

## Histórico do universo
| Data | Mudança |
|---|---|
| 2026-07-10 | AAVE e LINK fora (Maré Alta D1 PF 0,86 / 0,80) |
| 2026-08-23 | ETH e XRP fora do Maré Alta (backtest fiel PF 0,43 / 0,55) |
| 2026-08-24 | ETH e XRP fora da watchlist; estratégias mortas removidas |
| 2026-09-04 | PAXG fora; acúmulo desligado |
| 2026-09-16 | stop do HYPE 3,0×ATR |
| 2026-10-13 | Breakout HYPE desligado |
| 2026-10-15 | trailing com vela fechada; saída TP1 50% + breakeven ligada |
