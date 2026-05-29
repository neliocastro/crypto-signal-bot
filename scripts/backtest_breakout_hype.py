#!/usr/bin/env python3
"""
backtest_breakout_hype.py — Backtest BREAKOUT + TREND-FOLLOWING (LONG-only).

Tese: ativos de tendencia forte (ex.: HYPE) precisam MONTAR na tendencia
e DEIXAR CORRER. Cruzamento + stop apertado sofre whipsaw (HYPE: MDD -21%
no MACD-only). Solucao: breakout confirmado + stop largo + trailing.

ENTRADA (compra):
  1. EMA9 > EMA21 > EMA50                 (tendencia empilhada de alta)
  2. close > maxima das ultimas N velas   (breakout; N=lookback)
  3. RSI > 50                             (momentum; SEM teto -> deixa correr)

SAIDA (deixa o lucro correr):
  - Stop inicial : entry - ATR_MULT*ATR
  - Trailing stop: sobe com a maxima (topo - ATR_MULT*ATR)
  - Timeout      : TIMEOUT_BARS velas (saida a mercado)
  Sem TP fixo: captura tendencias longas.

Controle: BTC/ETH/SOL/LINK para ver se generaliza ou e especifico do HYPE.

Uso:
  python -m scripts.backtest_breakout_hype
  python -m scripts.backtest_breakout_hype --symbols HYPE/USDT --lookback 20 --atr 2.5
"""
from __future__ import annotations
import argparse, sys, time
from dataclasses import dataclass, field
from typing import List

try:
    import ccxt, pandas as pd, numpy as np
except ImportError as e:
    print(f"[ERRO] dependencia ausente: {e}. pip install ccxt pandas numpy"); sys.exit(1)

DEFAULT_SYMBOLS = ["HYPE/USDT","BTC/USDT","ETH/USDT","SOL/USDT","LINK/USDT"]
TIMEFRAME, DEFAULT_DAYS = "1h", 99
EXCHANGES = ["gateio","binance","bybit"]
BREAKOUT_LOOKBACK_DEF = 20
ATR_MULT_DEF, TIMEOUT_BARS = 2.5, 96
WARMUP, MS_H = 220, 3600*1000

def ema(s, span): return s.ewm(span=span, adjust=False).mean()

def rsi(s, p=14):
    d = s.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag = g.ewm(alpha=1/p, adjust=False, min_periods=p).mean()
    al = l.ewm(alpha=1/p, adjust=False, min_periods=p).mean()
    rs = ag / al.replace(0, np.nan); return 100 - (100 / (1 + rs))

def atr(df, p=14):
    h, l, c = df["high"], df["low"], df["close"]; pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False, min_periods=p).mean()

def enrich(df, lookback):
    df = df.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)
    df["hh"] = df["high"].rolling(lookback).max().shift(1)  # max N velas anteriores (sem lookahead)
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

def sig_breakout(r):
    try:
        if any(pd.isna(r[c]) for c in ("ema9","ema21","ema50","rsi","hh","close")): return False
        return (r["ema9"] > r["ema21"] > r["ema50"] and r["close"] > r["hh"] and r["rsi"] > 50.0)
    except (KeyError, TypeError):
        return False

@dataclass
class Trade:
    pnl_pct: float = 0.0; outcome: str = ""; exit_i: int = -1; bars: int = 0

@dataclass
class Result:
    symbol: str; trades: List[Trade] = field(default_factory=list)
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
    def mdd(self):
        eq = peak = mdd = 0.0
        for t in self.trades:
            eq += t.pnl_pct; peak = max(peak, eq); mdd = min(mdd, eq-peak)
        return mdd

def run_bt(df, symbol, atr_mult):
    res = Result(symbol=symbol); i = 60; n = len(df)
    while i < n-1:
        row = df.iloc[i]
        if not sig_breakout(row) or pd.isna(row["atr"]) or row["atr"] <= 0:
            i += 1; continue
        entry = float(row["close"]); a0 = float(row["atr"])
        stop = entry - atr_mult*a0; peak = entry
        t = Trade(); j = i+1; end = min(n-1, i+TIMEOUT_BARS); exit_price = None
        while j <= end:
            hi = float(df.iloc[j]["high"]); lo = float(df.iloc[j]["low"])
            aj = float(df.iloc[j]["atr"]) if not pd.isna(df.iloc[j]["atr"]) else a0
            if lo <= stop:
                exit_price = stop; t.outcome = "TRAIL_STOP"; t.exit_i = j; break
            if hi > peak:
                peak = hi; stop = max(stop, peak - atr_mult*aj)
            j += 1
        if exit_price is None:
            t.exit_i = end; exit_price = float(df.iloc[end]["close"]); t.outcome = "TIMEOUT"
        t.pnl_pct = (exit_price/entry - 1)*100; t.bars = t.exit_i - i
        res.trades.append(t); i = t.exit_i + 1
    return res

def verdict(r):
    if r.n < 5: return "INSUFICIENTE"
    if r.pf >= 1.5 and r.win_rate >= 40: return "APROVADO"
    if r.pf >= 1.2: return "LIMITROFE"
    return "REPROVADO"

def table(results):
    print(f"\n{'='*92}\nBREAKOUT + TREND (EMA9>21>50 & close>max(N) & RSI>50 | trailing 2.5xATR)\n{'='*92}")
    print(f"{'Ativo':<11}{'Trades':>7}{'WR%':>7}{'PF':>8}{'Exp%':>8}{'Ret%':>9}{'MDD%':>8}{'Best%':>8}{'Bars':>6}  Veredito")
    print("-"*92)
    for r in sorted(results, key=lambda x: x.pf, reverse=True):
        pf = "inf" if r.pf == float("inf") else f"{r.pf:.2f}"
        print(f"{r.symbol:<11}{r.n:>7}{r.win_rate:>7.1f}{pf:>8}{r.exp:>8.3f}{r.total:>9.2f}{r.mdd:>8.2f}{r.best:>8.2f}{r.avg_bars:>6.0f}  {verdict(r)}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--lookback", type=int, default=BREAKOUT_LOOKBACK_DEF)
    p.add_argument("--atr", type=float, default=ATR_MULT_DEF)
    a = p.parse_args()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()]
    print(f"\nBACKTEST BREAKOUT/TREND — {a.days}d — {TIMEFRAME} — breakout {a.lookback} velas | trailing {a.atr}xATR")
    print("(HYPE = alvo | BTC/ETH/SOL/LINK = controle)")
    res = []
    for s in syms:
        df = fetch_ohlcv(s, a.days)
        if df is None or len(df) < 250: continue
        res.append(run_bt(enrich(df, a.lookback), s, a.atr))
    table(res)
    aprov = [r.symbol for r in res if verdict(r) == "APROVADO"]
    print(f"\nAPROVADOS (PF>=1.5 & WR>=40%): {aprov or 'nenhum'}")

if __name__ == "__main__":
    main()
