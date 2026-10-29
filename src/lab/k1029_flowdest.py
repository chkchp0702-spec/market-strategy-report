"""📈 10/29 10시 2번 — 🔄 월말 흐름(적용 중) 「주식을 덜어낼 때 어디로 옮기나」 (어제 16시 계획 ②)
  지금: 넘침 신호(연기금이 주식 팔 차례) → 💼 주식 칸 60% 를 TLT 로. 2026 올해 4·9월 이 쪽에서 −1.7·−1.8%p.
  비교: TLT · IEF · GLD · BIL(현금) · UUP(달러) · TLT½+GLD½ · TLT½+UUP½ — 모자람 쪽(주식으로)은 그대로
  기준점 = 지금 실제 💼(월말 흐름 TLT 판) · 앞 2008-07~16 / 뒤 2017~ · 하루 늦은 체결 · 회전 × 0.1% · 흔들기(K4/6·th 0.4/0.6·f 0.48/0.72)
→ market/lab/k1029_flowdest.json
"""
from __future__ import annotations
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_rebalflow4 import sig_lag
from k1029_volctl import core_run2

OUT = Path("market/lab/k1029_flowdest.json")


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    for t in ("TLT", "UUP"):
        C[t] = px[t]["close"].reindex(C.index).ffill()
    C["TG"] = (1 + 0.5 * C["TLT"].pct_change().fillna(0) + 0.5 * C["GLD"].pct_change().fillna(0)).cumprod()
    C["TU"] = (1 + 0.5 * C["TLT"].pct_change().fillna(0) + 0.5 * C["UUP"].pct_change().fillna(0)).cumprod()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    sc = (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0)
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END}

    def go(dest="TLT", K=5, th=0.005, f=0.6):
        sig = sig_lag(C, K, th, 2)
        fs = pd.Series(f, index=C.index); fs[sig == 0] = 0.0
        nav, td = core_run2(C, reg, idx, sc, sig, fs, dest)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        d = nav.pct_change().fillna(0)
        o["y"] = {y: round(((1 + d[d.index.year == y]).prod() - 1) * 100, 2) for y in range(2008, idx[-1].year + 1)}
        return o

    def dlt(a, b):
        r = {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                 "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2)} for p in ("is", "oos")}
        r["y"] = {y: round(b["y"][y] - a["y"][y], 2) for y in a["y"]}
        return r
    base = {}
    res = {}
    for nm, kw in {"main": {}, "K4": dict(K=4), "K6": dict(K=6), "th0.4": dict(th=0.004), "th0.6": dict(th=0.006),
                   "f0.48": dict(f=0.48), "f0.72": dict(f=0.72)}.items():
        base[nm] = go("TLT", **kw)
        res[nm] = {}
        for dest in ("IEF", "GLD", "BIL", "UUP", "TG", "TU"):
            o = go(dest, **kw)
            res[nm][dest] = dlt(base[nm], o)
            print(nm, dest, {p: res[nm][dest][p] for p in ("is", "oos")}, "2026", res[nm][dest]["y"][idx[-1].year], flush=True)
    out["B_TLT"] = {k: base["main"][k] for k in ("is", "oos")}
    out["res"] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
