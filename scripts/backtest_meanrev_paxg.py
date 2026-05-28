#!/usr/bin/env python3
"""
backtest_meanrev_paxg.py — Backtest MEAN-REVERSION (LONG-only).

Tese: ativos de baixa volatilidade / reversao a media (ex.: PAXG/ouro)
respondem a REVERSAO, nao a momentum (MACD/EMA falham neles).

ENTRADA (compra) — confluencia (E):
  1. RSI(14) < RSI_OVERSOLD           (default 30)
  2. close <= banda inferior Bollinger (SMA20 - 2*std)

SAIDA:
  - Alvo : close >= SMA20 (banda media) -> "voltou a media"
  - Stop : entry - 2.5*ATR              -> protege contra "faca caindo"
  - Timeout: 48 candles                 -> nao reverteu, sai a mercado

Controle cientifico: rode tambem em BTC/ETH para confirmar que reversao
NAO funciona em cripto de tendencia (esperado: PF baixo neles).

Uso:
  python -m scripts.backtest_meanrev_paxg
  python -m scripts.backtest_meanrev_paxg --symbols PAXG/USDT --days 99
  python -m scripts.backtest_meanrev_paxg --rsi 25 --bb-std 2.5
"""
from __future__ import annotations
import argparse, sys, time
from dataclasses import dataclass, field
from typing import List

try:
    import ccxt, pandas as pd, numpy as np
except ImportError as e:
    print(f"[ERRO] dependencia ausente: {e}. pip install ccxt pandas numpy"); sys.exit(1)

# PAXG = alvo principal; BTC/ETH/SOL = controle (cripto de tendencia)
DEFAULT_SYMBOLS = ["PAXG/USDT","BTC/USDT","ETH/USDT","SOL/USDT"]
TIMEFRAME, DEFAULT_DAYS = "1h", 99
EXCHANGES = ["gateio","binance","bybit"]
BB_PERIOD, BB_STD_DEF = 20, 2.0
RSI_OVERSOLD_DEF = 30.0
ATR_STOP_MULT, TIMEOUT_BARS = 2.5, 48
WARMUP, MS_H = 220, 3600*1000

def sma(s,p): return s.rolling(p).mean()
def rsi(s,p=14):
    d=s.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    al=l.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
    rs=ag/al.replace(0,np.nan); return 100-(100/(1+rs))
def atr(df,p=14):
    h,l,c=df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/p,adjust=False,min_periods=p).mean()
def enrich(df, bb_std):
    df=df.copy()
    mid=sma(df["close"],BB_PERIOD); sd=df["close"].rolling(BB_PERIOD).std()
    df["bb_mid"]=mid; df["bb_low"]=mid-bb_std*sd; df["bb_up"]=mid+bb_std*sd
    df["rsi"]=rsi(df["close"]); df["atr"]=atr(df)
    return df

def fetch_ohlcv(symbol, days):
    needed=days*24+WARMUP
    for ex_name in EXCHANGES:
        try:
            ex=getattr(ccxt,ex_name)({"enableRateLimit":True}); ex.load_markets()
            if symbol not in ex.markets: continue
            cursor=ex.milliseconds()-needed*MS_H
            rows=[]; last=None; stalls=0; guard=0
            while len(rows)<needed and guard<20:
                guard+=1
                b=ex.fetch_ohlcv(symbol,TIMEFRAME,since=cursor,limit=1000)
                if not b: break
                rows+=b
                if last is not None and b[-1][0]<=last:
                    stalls+=1
                    if stalls>=2: break
                else: stalls=0
                last=b[-1][0]; cursor=b[-1][0]+MS_H
                time.sleep(ex.rateLimit/1000)
            seen=set(); uniq=[]
            for rr in rows:
                if rr[0] not in seen: seen.add(rr[0]); uniq.append(rr)
            uniq.sort(key=lambda x:x[0])
            if len(uniq)<250: continue
            df=pd.DataFrame(uniq,columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
            span=(uniq[-1][0]-uniq[0][0])/MS_H/24
            print(f"  [{symbol}] {len(df)} candles via {ex_name} (~{span:.0f}d)"); return df
        except Exception as e:
            print(f"  [{symbol}] {ex_name} falhou: {str(e)[:60]}"); continue
    print(f"  [{symbol}] SEM DADOS"); return None

def sig_meanrev(r, rsi_th):
    try:
        if any(pd.isna(r[c]) for c in ("rsi","bb_low","close")): return False
        return r["rsi"]<rsi_th and r["close"]<=r["bb_low"]
    except (KeyError,TypeError): return False

@dataclass
class Trade:
    pnl_pct: float=0.0; outcome: str=""; exit_i: int=-1; bars: int=0
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
    def avg_bars(self): return sum(t.bars for t in self.trades)/self.n if self.n else 0.0
    @property
    def mdd(self):
        eq=peak=mdd=0.0
        for t in self.trades:
            eq+=t.pnl_pct; peak=max(peak,eq); mdd=min(mdd,eq-peak)
        return mdd

def run_bt(df, symbol, rsi_th):
    res=Result(symbol=symbol); i=BB_PERIOD+14; n=len(df)
    while i<n-1:
        row=df.iloc[i]
        if not sig_meanrev(row,rsi_th) or pd.isna(row["atr"]) or row["atr"]<=0:
            i+=1; continue
        entry=float(row["close"]); a=float(row["atr"]); stop=entry-ATR_STOP_MULT*a
        t=Trade(); j=i+1; end=min(n-1,i+TIMEOUT_BARS)
        while j<=end:
            lo=float(df.iloc[j]["low"]); cl=float(df.iloc[j]["close"]); tgt=float(df.iloc[j]["bb_mid"])
            if lo<=stop:
                t.exit_i=j; t.pnl_pct=(stop/entry-1)*100; t.outcome="STOP"; break
            if not pd.isna(tgt) and cl>=tgt:
                t.exit_i=j; t.pnl_pct=(cl/entry-1)*100; t.outcome="TARGET"; break
            j+=1
        if t.outcome=="":
            t.exit_i=end; t.pnl_pct=(float(df.iloc[end]["close"])/entry-1)*100; t.outcome="TIMEOUT"
        t.bars=t.exit_i-i; res.trades.append(t); i=t.exit_i+1
    return res

def verdict(r):
    if r.n<5: return "INSUFICIENTE"
    if r.pf>=1.5 and r.win_rate>=50: return "APROVADO"
    if r.pf>=1.2: return "LIMITROFE"
    return "REPROVADO"

def table(results):
    print(f"\n{'='*84}\nMEAN-REVERSION (RSI<thr & close<=BB_low -> exit SMA20 | stop 2.5xATR)\n{'='*84}")
    print(f"{'Ativo':<11}{'Trades':>7}{'WR%':>7}{'PF':>8}{'Exp%':>8}{'Ret%':>9}{'MDD%':>8}{'Bars':>6}  Veredito")
    print("-"*84)
    for r in sorted(results,key=lambda x:x.pf,reverse=True):
        pf="inf" if r.pf==float("inf") else f"{r.pf:.2f}"
        print(f"{r.symbol:<11}{r.n:>7}{r.win_rate:>7.1f}{pf:>8}{r.exp:>8.3f}{r.total:>9.2f}{r.mdd:>8.2f}{r.avg_bars:>6.0f}  {verdict(r)}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=DEFAULT_DAYS)
    p.add_argument("--symbols",type=str,default=",".join(DEFAULT_SYMBOLS))
    p.add_argument("--rsi",type=float,default=RSI_OVERSOLD_DEF)
    p.add_argument("--bb-std",type=float,default=BB_STD_DEF)
    a=p.parse_args()
    syms=[s.strip() for s in a.symbols.split(",") if s.strip()]
    print(f"\nBACKTEST MEAN-REVERSION — {a.days}d — {TIMEFRAME} — RSI<{a.rsi} & BB({BB_PERIOD},{a.bb_std}sigma)")
    print("(PAXG = alvo | BTC/ETH/SOL = controle: espera-se PF baixo em cripto)")
    res=[]
    for s in syms:
        df=fetch_ohlcv(s,a.days)
        if df is None or len(df)<250: continue
        res.append(run_bt(enrich(df,a.bb_std),s,a.rsi))
    table(res)
    aprov=[r.symbol for r in res if verdict(r)=="APROVADO"]
    print(f"\nAPROVADOS (PF>=1.5 & WR>=50%): {aprov or 'nenhum'}")

if __name__=="__main__":
    main()
