# Histórico de Decisões de Estratégia

Registro das decisões de estratégia do bot, baseadas em backtests e testes
de robustez. Mantido para rastreabilidade — por que cada ativo opera como opera.

---

## PAXG/USDT — REPROVADO (removido da watchlist em 2026-05-28)

Ouro tokenizado: ativo de baixíssima volatilidade, sem tendências exploráveis
no timeframe de 1h.

| Estratégia testada | Resultado |
|---|---|
| MACD-only (agressivo) | Reprovado — pouquíssimos sinais, sem edge |
| Mean-reversion (RSI/banda) | Reprovado — PF < 1.2 |
| Breakout/Tendência | Reprovado — natureza lateral, não rompe |

**Decisão:** removido da `WATCHLIST`. Reprovado em 3 abordagens distintas.
PAXG não combina com estratégias de momentum/tendência em 1h.

---

## HYPE/USDT — PROMOVIDO para Breakout/Tendência (shadow) em 2026-05-28

Ativo de tendência forte e alta volatilidade. Mean-reversion fracassaria
(venderia cedo nos ralis); momentum/breakout é o encaixe natural.

### Histórico
1. **MACD-only (Fase A):** aprovado em backtest 90d (PF 3.45) MAS sofreu
   whipsaw com stop apertado 1.5xATR — MDD -21% observado. Frágil.
2. **Breakout/Tendência (nova):** EMA9>21>50 + rompe máxima de N velas +
   RSI>50, stop largo 2.5xATR + trailing (deixa correr).

### Teste de robustez (2026-05-28, ~150d de histórico — ativo lista desde 30/12/2025)

**Sensibilidade de parâmetros (9 configs, todas PF > 1.3 → edge real, não overfit):**

| Config | PF | Ret% | MDD% |
|---|---|---|---|
| lb=20 atr=2.5 (inicial) | 1.86 | +55.3 | -25.0 |
| **lb=30 atr=2.5 (escolhida)** | **2.55** | **+67.5** | **-16.9** |
| lb=30 atr=3.0 | 2.11 | +57.2 | -21.1 |

**Robustez temporal (2 de 3 janelas lucrativas):**
- Janela A (início): PF 2.09 ✅
- Janela B (meio): PF 0.87 🔴 (mercado lateral)
- Janela C (recente): PF 3.32 ✅

**Dependência de poucos trades (risco conhecido):**
- 47 trades, WR 42.6%, maior trade = 66% do retorno.
- Sem o melhor trade: ainda +18.9% (PF 1.30) ✅
- Sem os 2 melhores: -6% 🔴 → depende de 2-3 ralis grandes.

### Decisão
- **Config de produção:** `lookback=30, atr_mult=2.5` (melhor PF e menor MDD).
- **Roteamento:** HYPE usa SÓ a estratégia breakout (fast-path dedicado em
  `evaluate_signal`); removido do MACD-only (`approved_symbols` agora só LINK).
- **SHADOW MODE ligado** (`BREAKOUT_SHADOW_MODE=True`): sinais marcados
  `[SHADOW]` por 2-4 semanas de observação antes de operar valendo —
  justificado pelo histórico curto (150d) e concentração em poucos trades.
- **Kill switch:** `BREAKOUT_ENABLED=False` desliga totalmente.

**Quando confiar:** após 2-4 semanas de shadow, se os sinais ao vivo forem
coerentes, trocar `BREAKOUT_SHADOW_MODE=False`.

---

## LINK/USDT — MACD-only agressivo (mantido)

Aprovado em backtest 90d (12 trades, 66.7% WR, PF 3.26). Permanece no perfil
agressivo MACD-only. Único ativo em `approved_symbols`.

---

## Controle (BTC/ETH/SOL) na estratégia breakout

Testados como controle — NÃO promovidos:
- ETH: PF 1.48 (limítrofe, retorno mais distribuído que HYPE)
- LINK: PF 1.22 (limítrofe)
- BTC: PF 0.91 (reprovado)
- SOL: PF 0.68 (reprovado)

A estratégia breakout NÃO generaliza para todos os ativos — é específica para
perfis de alta tendência como o HYPE. ETH fica como candidato futuro.
