#!/usr/bin/env python3
"""
backtest_super_agressivo.py — Backtest do perfil SUPER AGRESSIVO (LONG-only).

Regras de ENTRADA (LONG), no candle FECHADO:
  1. EMA9 > EMA21 > EMA50            (tendencia de alta empilhada)
  2. MACD line > MACD signal         (forca compradora; vale mesmo abaixo de zero)
  3. 40 <= RSI <= 69                 (sem sobrecompra extrema)

Saida: ATR — SL = entry - 1.5*ATR | TP = entry + 3.0*ATR (R:R 1:2),
       timeout de 48 candles. Anti-spam: 1 posicao por vez por ativo.

--compare tambem roda o gatilho MACD-only (Fase A) lado a lado.

Uso:
  python -m scripts.backtest_super_agressivo --compare
  python -m scripts.backtest_super_agressivo --days 90 --symbols LINK/USDT,HYPE/USDT
"""
from __future__ import annotations
import argparse, sys, time
from dataclasses import dataclass, field
from typing import List

try:
    import ccxt, pandas as pd, numpy as np
except ImportError as e:
    print(f"[ERRO] dependencia ausente: {e}. pip install ccxt pandas numpy"); sys.exit(1)

WATCHLIST = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT",
             "LINK/USDT","HYPE/USDT","AAVE/USDT","TRX/USDT","PAXG/USDT"]
TIMEFRAME, DEFAULT_DAYS = "1h", 90
EXCHANGES = ["gateio","binance","bybit"]
ATR_SL_MULT, ATR_TP_MULT, TIMEOUT_BARS = 1.5, 3.0, 48
RSI_MIN, RSI_MAX = 40.0, 69.0
WARMUP = 220                      # candles extras p/ EMA200 estabilizar
MS_H = 3600*1000

def ema(s, span): return s.ewm(span=span, adjust=False).mean()
def rsi(s, p=14):
    d=s.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    al=l.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    rs=ag/al.replace(0,np.nan); return 100-(100/(1+rs))
def macd(s,f=12,sl=26,sig=9):
    m=ema(s,f)-ema(s,sl); return m, ema(m,sig)
def atr(df,p=14):
    h,l,c=df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
def enrich(df):
    df=df.copy()
    df["ema9"],df["ema21"],df["ema50"],df["ema200"]=ema(df["close"],9),ema(df["close"],21),ema(df["close"],50),ema(df["close"],200)
    df["rsi"]=rsi(df["close"]); df["macd"],df["macd_signal"]=macd(df["close"]); df["atr"]=atr(df)
    return df

def fetch_ohlcv(symbol, days):
    """Paginacao robusta: muitas exchanges limitam ~1000/req (gateio devolve 999).
    Para SO quando o cursor nao avanca ou o alvo e atingido — nunca por len(batch)."""
    needed = days*24 + WARMUP
    for ex_name in EXCHANGES:
        try:
            ex=getattr(ccxt,ex_name)({"enableRateLimit":True}); ex.load_markets()
            if symbol not in ex.markets: continue
            cursor = ex.milliseconds() - needed*MS_H
            rows=[]; last_ts=None; stalls=0; guard=0
            while len(rows) < needed and guard < 20:
                guard+=1
                batch=ex.fetch_ohlcv(symbol,TIMEFRAME,since=cursor,limit=1000)
                if not batch: break
                rows += batch
                new_cursor = batch[-1][0] + MS_H
                if last_ts is not None and batch[-1][0] <= last_ts:
                    stalls += 1
                    if stalls >= 2: break          # API parou de avancar
                else:
                    stalls = 0
                last_ts = batch[-1][0]
                cursor = new_cursor
                time.sleep(ex.rateLimit/1000)
            seen=set(); uniq=[]
            for rr in rows:
                if rr[0] not in seen: seen.add(rr[0]); uniq.append(rr)
            uniq.sort(key=lambda x:x[0])
            if len(uniq) < 250: continue
            df=pd.DataFrame(uniq,columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
            df=df.reset_index(drop=True)
            span=(uniq[-1][0]-uniq[0][0])/MS_H/24
            print(f"  [{symbol}] {len(df)} candles via {ex_name} (~{span:.0f}d)"); return df
        except Exception as e:
            print(f"  [{symbol}] {ex_name} falhou: {str(e)[:60]}"); continue
    print(f"  [{symbol}] SEM DADOS"); return None

def sig_super(r):
    try:
        if any(pd.isna(r[c]) for c in ("ema9","ema21","ema50","macd","macd_signal","rsi")): return False
        return (r["ema9"]>r["ema21"]>r["ema50"] and r["macd"]>r["macd_signal"] and RSI_MIN<=r["rsi"]<=RSI_MAX)
    except (KeyError,TypeError): return False
def sig_macd(prev,r):
    try:
        if any(pd.isna(x) for x in (prev["macd"],prev["macd_signal"],r["macd"],r["macd_signal"],r["close"],r["ema200"],r["rsi"])): return False
        cr=prev["macd"]<=prev["macd_signal"] and r["macd"]>r["macd_signal"]
        return cr and r["close"]>r["ema200"] and 40.0<=r["rsi"]<=70.0
    except (KeyError,TypeError): return False

@dataclass
class Trade:
    pnl_pct: float=0.0; outcome: str=""; exit_i: int=-1
@dataclass
class Result:
    symbol: str; trades: List[Trade]=field(default_factory=list)
    @property
    def n(self): return len(self.trades)
    @property
    def wins(self): return sum(1 for t in self.trades if t.pnl_pct>0)
    @property
    def win_rate(self): return 100*self.wins/self.n if self.n else 0.0
    @property
    def gw(self): return sum(t.pnl_pct for t in self.trades if t.pnl_pct>0)
    @property
    def gl(self): return abs(sum(t.pnl_pct for t in self.trades if t.pnl_pct<0))
    @property
    def pf(self): return self.gw/self.gl if self.gl>0 else float("inf")
    @property
    def total(self): return sum(t.pnl_pct for t in self.trades)
    @property
    def exp(self): return self.total/self.n if self.n else 0.0
    @property
    def mdd(self):
        eq=peak=mdd=0.0
        for t in self.trades:
            eq+=t.pnl_pct; peak=max(peak,eq); mdd=min(mdd,eq-peak)
        return mdd

def run_bt(df, symbol, mode):
    res=Result(symbol=symbol); i=200; n=len(df)
    while i<n-1:
        row,prev=df.iloc[i],df.iloc[i-1]
        fire=sig_super(row) if mode=="super" else sig_macd(prev,row)
        if not fire or pd.isna(row["atr"]) or row["atr"]<=0: i+=1; continue
        entry=float(row["close"]); a=float(row["atr"])
        stop,tp=entry-ATR_SL_MULT*a, entry+ATR_TP_MULT*a
        t=Trade(); j=i+1; end=min(n-1,i+TIMEOUT_BARS)
        while j<=end:
            hi,lo=float(df.iloc[j]["high"]),float(df.iloc[j]["low"])
            if lo<=stop: t.exit_i=j; t.pnl_pct=(stop/entry-1)*100; t.outcome="LOSS"; break
            if hi>=tp:   t.exit_i=j; t.pnl_pct=(tp/entry-1)*100; t.outcome="WIN"; break
            j+=1
        if t.outcome=="":
            t.exit_i=end; t.pnl_pct=(float(df.iloc[end]["close"])/entry-1)*100; t.outcome="TIMEOUT"
        res.trades.append(t); i=t.exit_i+1
    return res

def verdict(r):
    if r.n<5: return "INSUFICIENTE"
    if r.pf>=1.5 and r.win_rate>=45: return "APROVADO"
    if r.pf>=1.2: return "LIMITROFE"
    return "REPROVADO"

def table(title, results):
    print(f"\n{'='*80}\n{title}\n{'='*80}")
    print(f"{'Ativo':<11}{'Trades':>7}{'WR%':>7}{'PF':>8}{'Exp%':>8}{'Ret%':>9}{'MDD%':>8}  Veredito")
    print("-"*80)
    agg=Result(symbol="TOTAL")
    for r in sorted(results,key=lambda x:x.pf,reverse=True):
        pf="inf" if r.pf==float("inf") else f"{r.pf:.2f}"
        print(f"{r.symbol:<11}{r.n:>7}{r.win_rate:>7.1f}{pf:>8}{r.exp:>8.3f}{r.total:>9.2f}{r.mdd:>8.2f}  {verdict(r)}")
        agg.trades+=r.trades
    pf="inf" if agg.pf==float("inf") else f"{agg.pf:.2f}"
    print("-"*80)
    print(f"{'AGREGADO':<11}{agg.n:>7}{agg.win_rate:>7.1f}{pf:>8}{agg.exp:>8.3f}{agg.total:>9.2f}{agg.mdd:>8.2f}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=DEFAULT_DAYS)
    p.add_argument("--symbols",type=str,default=",".join(WATCHLIST))
    p.add_argument("--compare",action="store_true")
    a=p.parse_args()
    syms=[s.strip() for s in a.symbols.split(",") if s.strip()]
    print(f"\nBACKTEST SUPER AGRESSIVO — {a.days}d — {TIMEFRAME} — {len(syms)} ativos")
    sup,mac=[],[]
    for s in syms:
        df=fetch_ohlcv(s,a.days)
        if df is None or len(df)<250: continue
        df=enrich(df); sup.append(run_bt(df,s,"super"))
        if a.compare: mac.append(run_bt(df,s,"macd"))
    table("PERFIL SUPER AGRESSIVO (EMA9>21>50 + MACD>signal + RSI 40-69)", sup)
    if a.compare and mac: table("REFERENCIA — MACD-only (Fase A)", mac)
    aprov=[r.symbol for r in sup if verdict(r)=="APROVADO"]
    print(f"\nAPROVADOS (PF>=1.5 & WR>=45%): {aprov or 'nenhum'}")

if __name__=="__main__":
    main()
