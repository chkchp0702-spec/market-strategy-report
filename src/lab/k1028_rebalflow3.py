"""📈 10/28 14시 — 리밸런싱 흐름 3차: 「주식 모자람 → 주식 쪽」만(사는 쪽만) 판 · 해마다 · 같은 변동성 비교
  k1028_rebalflow2 에서 뒤 구간 성과 대부분이 「사는 쪽」(이번 달 주식이 채권보다 덜 오름 → 마지막 주 SPY 하루 +36bp)에서 나옴
  → 💼 위에: buy = 사는 쪽만(금·추세 칸 f 만큼을 마지막 5거래일 동안 주식으로) / sym = 양쪽(1차 고른 것)
→ market/lab/k1028_rebalflow3.json
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
from k1028_rebalflow import signals, core_run

OUT = Path("market/lab/k1028_rebalflow3.json")


def main():
    C = load()
    px = ydl(["^IRX", "IEF"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"]
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx)
    END = str(idx[-1].date())
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * math.sqrt(252) * 100
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    SG = {}

    def go(K=5, th=0.005, f=0.0, fb=None, bond="TLT", sym=True, tgt=15.0, floor=0.30):
        k = (K, th)
        if k not in SG:
            SG[k] = signals(C, "cal", K=K, th=th)
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, SG[k], f, bond, sym, fb=fb)
        o = {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}
        yr = {}
        for y in range(2009, idx[-1].year + 1):
            a = nav[nav.index.year == y]
            if len(a) > 20:
                yr[y] = round((a.iloc[-1] / nav[nav.index < a.index[0]].iloc[-1] - 1) * 100, 1)
        o["yr"] = yr
        return o

    def dlt(a, b):
        return {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                    "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2), "vol": round(b[p]["vol"] - a[p]["vol"], 1)} for p in ("is", "oos")}

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END}
    B0 = go(); out["B0"] = B0
    V = {"sym_f0.6": dict(f=0.6), "buy_f0.6": dict(f=0.6, fb=0.0), "buy_f0.48": dict(f=0.48, fb=0.0),
         "buy_f0.72": dict(f=0.72, fb=0.0), "buy_f1.0": dict(f=1.0, fb=0.0), "buy_f0.6_th0.4": dict(f=0.6, fb=0.0, th=0.004),
         "buy_f0.6_th0.6": dict(f=0.6, fb=0.0, th=0.006), "buy_f0.6_K4": dict(f=0.6, fb=0.0, K=4), "buy_f0.6_K6": dict(f=0.6, fb=0.0, K=6),
         "sell_f0.6": dict(f=0.0, fb=0.6, sym=False)}
    res = {}
    for nm, kw in V.items():
        o = go(**kw); o["d"] = dlt(B0, o); res[nm] = o
        yd = {y: round(o["yr"][y] - B0["yr"][y], 1) for y in o["yr"]}
        o["yr_d"] = yd; o["yr_pos"] = f"{sum(1 for v in yd.values() if v > 0)}/{len(yd)}"
        print(nm, o["d"], o["yr_pos"], o["is"]["turn"], o["oos"]["turn"], flush=True)
    for nm, kw in {"tgt12": dict(tgt=12.0), "tgt18": dict(tgt=18.0), "floor24": dict(floor=0.24), "floor36": dict(floor=0.36)}.items():
        for v in ("buy_f0.6", "sym_f0.6"):
            a = go(**kw); b = go(**{**V[v], **kw}); res[f"{v}|{nm}"] = {"d": dlt(a, b)}
            print(v, nm, res[f"{v}|{nm}"]["d"], flush=True)
    # 같은 변동성: 묶음 OOS 변동성을 B0 와 맞춘 목표
    for v in ("buy_f0.6", "sym_f0.6"):
        t2 = 15.0 * B0["oos"]["vol"] / res[v]["oos"]["vol"]
        m = go(**{**V[v], "tgt": round(t2, 2)}); res[v + "|samevol"] = {"tgt": round(t2, 2), "d": dlt(B0, m)}
        print(v, "samevol", t2, res[v + "|samevol"]["d"], flush=True)
    out["res"] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
