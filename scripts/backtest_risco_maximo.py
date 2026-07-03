#!/usr/bin/env python3
"""
backtest_risco_maximo.py — Backtest da estrategia "RISCO MAXIMO" (LONG-only).

TESE (definida com o Nelio):
  Comprar na VIRADA de momentum: quando a linha MACD cruza a linha de sinal
  PRA CIMA (bullish crossover), VALIDO mesmo com MACD ainda NEGATIVO (abaixo
  do zero) — captura a largada da tendencia. Filtro estrutural: EMA9 > EMA21.
  Alvo longo de +6% (TP). Stop: comparamos ATR vs minima do cruzamento.

ENTRADA (compra) — regra exata:
  1. GATILHO: MACD (12,26) cruza a linha de sinal (9) PRA CIMA
             -> valido mesmo com MACD < 0 (nao exige estar positivo)
  2. FILTRO : EMA9 > EMA21 no momento do cruzamento (obrigatorio)
             -> NAO precisam cruzar na mesma vela; a EMA ja pode estar cruzada
  Entrada na ABERTURA da vela seguinte ao sinal (sem lookahead).

SAIDA:
  - TP fixo: +TP_PCT% (default 6%)
  - Stop   : dois modos, escolhidos por --stop
       atr : entry - ATR_MULT*ATR   (default 2.5x)
       min : minima das ultimas 2 velas do sinal
  - Timeout: TIMEOUT_BARS velas (saida a mercado)
  Prioridade conservadora: se a vela toca STOP e TP, conta STOP.

Custos: FEE por lado (ida+volta) descontado do PnL.

Uso:
  python -m scripts.backtest_risco_maximo
  python -m scripts.backtest_risco_maximo --compare        # ATR vs MIN lado a lado
  python -m scripts.backtest_risco_maximo --stop atr --atr 2.5 --tp 6
  python -m scripts.backtest_risco_maximo --symbols HYPE/USDT,BTC/USDT
"""
from __future__ import annotations
import argparse, sys, time
from dataclasses import dataclass, field
from typing import List

try:
    import ccxt, pandas as pd, numpy as np
except ImportError as e:
    print(f"[ERRO] dependencia ausente: {e}. pip install ccxt pandas numpy"); sys.exit(1)

DEFAULT_SYMBOLS = ["BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","TRX/USDT",
                   "BNB/USDT","LINK/USDT","AAVE/USDT","HYPE/USDT"]
TIMEFRAME, DEFAULT_DAYS = "1h", 99
EXCHANGES = ["gateio","binance","bybit"]
TP_PCT_DEF, ATR_MULT_DEF = 6.0, 2.5
TIMEOUT_BARS = 240              # ate 10 dias (alvo longo de 6%)
FEE = 0.001                     # 0.1% por lado -> ida+volta 0.2%
WARMUP, MS_H = 220, 3600*1000


def ema(s, span): return s.ewm(span=span, adjust=False).mean()

def macd_lines(close):
    macd = ema(close, 12) - ema(close, 26)
    signal = ema(macd, 9)
    return macd, signal

def atr(df, p=14):
    h, l, c = df["high"], df["low"], df["close"]; pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False, min_periods=p).mean()

def enrich(df):
    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["macd"], df["signal"] = macd_lines(df["close"])
    df["atr"] = atr(df)
    # cruzamento de alta: MACD cruza a sinal pra cima (vale mesmo com MACD<0)
    prev_below = df["macd"].shift(1) <= df["signal"].shift(1)
    now_above = df["macd"] > df["signal"]
    df["cross_up"] = prev_below & now_above
    return df

def fetch_ohlcv(symbol, days):
    needed = days*24 + WARMUP
    for ex_name in EXCHANGES:
        try:
            ex = getattr(ccxt, ex_name)({"enableRateLimit": True}); ex.load_markets()
            if symbol not in ex.markets: continue
            cursor = ex.milliseconds() - needed*MS_H
            rows = []; last = None; stalls = 0; guard = 0
            while len(rows) < needed and guard < 20:
                guard += 1
                b = ex.fetch_ohlcv(symbol, TIMEFRAME, since=cursor, limit=1000)
                if not b: break
                rows += b
                if last is not None and b[-1][0] <= last:
                    stalls += 1
                    if stalls >= 2: break
                else:
                    stalls = 0
                last = b[-1][0]; cursor = b[-1][0] + MS_H
                time.sleep(ex.rateLimit/1000)
            seen = set(); uniq = []
            for rr in rows:
                if rr[0] not in seen: seen.add(rr[0]); uniq.append(rr)
            uniq.sort(key=lambda x: x[0])
            if len(uniq) < 250: continue
            df = pd.DataFrame(uniq, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            span = (uniq[-1][0]-uniq[0][0])/MS_H/24
            print(f"  [{symbol}] {len(df)} candles via {ex_name} (~{span:.0f}d)"); return df
        except Exception as e:
            print(f"  [{symbol}] {ex_name} falhou: {str(e)[:60]}"); continue
    print(f"  [{symbol}] SEM DADOS"); return None


@dataclass
class Trade:
    pnl_pct: float = 0.0; outcome: str = ""; exit_i: int = -1; bars: int = 0

@dataclass
class Result:
    symbol: str; stop_mode: str = "atr"; trades: List[Trade] = field(default_factory=list)
    @property
    def n(self): return len(self.trades)
    @property
    def wins(self): return sum(1 for t in self.trades if t.pnl_pct > 0)
    @property
    def win_rate(self): return 100*self.wins/self.n if self.n else 0.0
    @property
    def gw(self): return sum(t.pnl_pct for t in self.trades if t.pnl_pct > 0)
    @property
    def gl(self): return abs(sum(t.pnl_pct for t in self.trades if t.pnl_pct < 0))
    @property
    def pf(self): return self.gw/self.gl if self.gl > 0 else float("inf")
    @property
    def total(self): return sum(t.pnl_pct for t in self.trades)
    @property
    def exp(self): return self.total/self.n if self.n else 0.0
    @property
    def best(self): return max((t.pnl_pct for t in self.trades), default=0.0)
    @property
    def avg_bars(self): return sum(t.bars for t in self.trades)/self.n if self.n else 0.0
    @property
    def rr(self):
        avg_w = (self.gw/self.wins) if self.wins else 0.0
        losses = self.n - self.wins
        avg_l = (self.gl/losses) if losses else 0.0
        return avg_w/avg_l if avg_l > 0 else float("inf")
    @property
    def mdd(self):
        eq = peak = mdd = 0.0
        for t in self.trades:
            eq += t.pnl_pct; peak = max(peak, eq); mdd = min(mdd, eq-peak)
        return mdd


def run_bt(df, symbol, stop_mode, atr_mult, tp_pct):
    res = Result(symbol=symbol, stop_mode=stop_mode); i = 60; n = len(df)
    while i < n-1:
        row = df.iloc[i]
        valid = (bool(row["cross_up"]) and not pd.isna(row["ema9"]) and not pd.isna(row["ema21"])
                 and row["ema9"] > row["ema21"] and not pd.isna(row["atr"]) and row["atr"] > 0)
        if not valid:
            i += 1; continue
        entry = float(df.iloc[i+1]["open"])        # entra na abertura da vela seguinte
        a0 = float(row["atr"])
        if stop_mode == "atr":
            stop = entry - atr_mult*a0
        else:  # min do cruzamento (minima das ultimas 2 velas ate o sinal)
            stop = float(min(df.iloc[i]["low"], df.iloc[i-1]["low"]))
        target = entry*(1 + tp_pct/100.0)
        t = Trade(); j = i+1; end = min(n-1, i+TIMEOUT_BARS); exit_price = None
        while j <= end:
            lo = float(df.iloc[j]["low"]); hi = float(df.iloc[j]["high"])
            if lo <= stop:                                   # stop primeiro (conservador)
                exit_price = stop; t.outcome = "STOP"; t.exit_i = j; break
            if hi >= target:
                exit_price = target; t.outcome = "TP"; t.exit_i = j; break
            j += 1
        if exit_price is None:
            t.exit_i = end; exit_price = float(df.iloc[end]["close"]); t.outcome = "TIMEOUT"
        gross = (exit_price/entry - 1)
        t.pnl_pct = (gross - 2*FEE)*100                      # desconta custos (ida+volta)
        t.bars = t.exit_i - i
        res.trades.append(t); i = t.exit_i + 1
    return res


def verdict(r):
    if r.n < 5: return "INSUFICIENTE"
    if r.pf >= 1.5 and r.win_rate >= 35: return "APROVADO"
    if r.pf >= 1.2: return "LIMITROFE"
    return "REPROVADO"

def table(results, stop_mode, atr_mult, tp_pct):
    print(f"\n{'='*98}")
    print(f'RISCO MAXIMO | MACD cruza^ (mesmo <0) & EMA9>EMA21 | TP {tp_pct:.0f}% | stop={stop_mode.upper()}'
          + (f' {atr_mult}xATR' if stop_mode=='atr' else ' (min cruzamento)') + ' | c/custos')
    print('='*98)
    print(f"{'Ativo':<11}{'Trades':>7}{'WR%':>7}{'PF':>8}{'R:R':>7}{'Exp%':>8}{'Ret%':>9}{'MDD%':>8}{'Best%':>8}  Veredito")
    print("-"*98)
    port = Result(symbol="CARTEIRA", stop_mode=stop_mode)
    for r in sorted(results, key=lambda x: x.pf, reverse=True):
        port.trades += r.trades
        pf = "inf" if r.pf == float("inf") else f"{r.pf:.2f}"
        rr = "inf" if r.rr == float("inf") else f"{r.rr:.2f}"
        print(f"{r.symbol:<11}{r.n:>7}{r.win_rate:>7.1f}{pf:>8}{rr:>7}{r.exp:>8.3f}{r.total:>9.2f}{r.mdd:>8.2f}{r.best:>8.2f}  {verdict(r)}")
    print("-"*98)
    pf = "inf" if port.pf == float("inf") else f"{port.pf:.2f}"
    rr = "inf" if port.rr == float("inf") else f"{port.rr:.2f}"
    print(f"{port.symbol:<11}{port.n:>7}{port.win_rate:>7.1f}{pf:>8}{rr:>7}{port.exp:>8.3f}{port.total:>9.2f}{port.mdd:>8.2f}{port.best:>8.2f}  {verdict(port)}")
    return port


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--stop", type=str, default="atr", choices=["atr","min"])
    p.add_argument("--atr", type=float, default=ATR_MULT_DEF)
    p.add_argument("--tp", type=float, default=TP_PCT_DEF)
    p.add_argument("--compare", action="store_true", help="roda ATR e MIN lado a lado")
    a = p.parse_args()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()]
    print(f"\nBACKTEST RISCO MAXIMO — {a.days}d — {TIMEFRAME} — TP {a.tp:.0f}% | fee {FEE*100:.1f}%/lado")

    # baixa uma vez, reutiliza
    data = {}
    for s in syms:
        df = fetch_ohlcv(s, a.days)
        if df is not None and len(df) >= 250:
            data[s] = enrich(df)

    modes = ["atr","min"] if a.compare else [a.stop]
    ports = {}
    for mode in modes:
        res = [run_bt(data[s], s, mode, a.atr, a.tp) for s in data]
        ports[mode] = table(res, mode, a.atr, a.tp)

    if a.compare:
        print(f"\n{'#'*70}\nVEREDITO STOP: ATR({a.atr}x) vs MINIMA DO CRUZAMENTO (carteira)\n{'#'*70}")
        for m in ("atr","min"):
            pr = ports[m]; pf = "inf" if pr.pf==float("inf") else f"{pr.pf:.2f}"
            print(f"  {m.upper():4} -> PF {pf} | WR {pr.win_rate:.1f}% | R:R {pr.rr:.2f} | Ret {pr.total:.1f}% | MDD {pr.mdd:.1f}% | {pr.n} trades")
        best = max(ports.values(), key=lambda x: x.pf)
        print(f"\n  >> Melhor PF: STOP={best.stop_mode.upper()}")

if __name__ == "__main__":
    main()
