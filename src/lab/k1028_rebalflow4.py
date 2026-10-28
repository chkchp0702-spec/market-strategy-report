"""📈 10/28 14시 — 리밸런싱 흐름 4차: 「하루 늦은 체결」로 다시 (검토자 지적)
  1~3차는 i일 종가까지의 쏠림으로 i일 종가에 바로 갈아탐 = 같은 종가 체결. 실전(전날 종가로 판단 → 다음 날 체결)에 맞게
  쏠림을 하루 더 늦춰(drift.shift(2)) 같은 창(달 마지막 K 거래일)에서 다시 잼. 맞대기·💼 둘 다, 격자 전체 중앙값도.
→ market/lab/k1028_rebalflow4.json
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
from k1028_rebalflow import core_run

OUT = Path("market/lab/k1028_rebalflow4.json")


def sig_lag(C, K=5, th=0.005, lag=2):
    S = C["SPY"].pct_change().fillna(0.0); B = C["IEF"].pct_change().fillna(0.0)
    idx = C.index
    mon = pd.Series(idx.month, index=idx)
    rfe = mon.groupby((mon != mon.shift()).cumsum()).cumcount(ascending=False)
    win = rfe < K
    drift = pd.Series(0.0, index=idx); ws = wb = 1
    for i, d in enumerate(idx):
        if i == 0 or idx[i - 1].month != d.month:
            ws, wb = 0.6, 0.4
        ws *= 1 + S.iloc[i]; wb *= 1 + B.iloc[i]
        drift.iloc[i] = ws / (ws + wb) - 0.6
    prev = drift.shift(lag).fillna(0.0)
    out = pd.Series(0.0, index=idx)
    out[win & (prev > th)] = 1.0; out[win & (prev < -th)] = -1.0
    return out


def edge(C, sig, a, b, bond="IEF"):
    r = (C["SPY"].pct_change() - C[bond].pct_change()).fillna(0.0)
    m = (sig.index >= a) & (sig.index <= b) & (sig != 0)
    x = (-sig[m] * r[m]) * 1e4
    if len(x) < 5:
        return {"n": int(len(x))}
    return {"n": int(len(x)), "bp": round(float(x.mean()), 1), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2)}


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
    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "to": END}
    # 맞대기: 같은 종가(lag1) vs 하루 늦게(lag2)
    ls = {}
    for lag in (1, 2):
        for K in (3, 5):
            sg = sig_lag(C, K=K, lag=lag)
            ls[f"lag{lag}_K{K}"] = {"is": edge(C, sg, START, IS_END), "oos": edge(C, sg, OOS_START, END),
                                   "is_TLT": edge(C, sg, START, IS_END, "TLT"), "oos_TLT": edge(C, sg, OOS_START, END, "TLT")}
            print("LS", lag, K, ls[f"lag{lag}_K{K}"], flush=True)
    out["ls"] = ls
    SG = {}

    def go(K=5, th=0.005, f=0.0, fb=None, bond="TLT", sym=True, lag=2, tgt=15.0, floor=0.30):
        k = (K, th, lag)
        if k not in SG:
            SG[k] = sig_lag(C, K, th, lag)
        sc = (tgt / rv).clip(upper=1.0, lower=floor).fillna(1.0)
        nav, td = core_run(C, reg, idx, sc, SG[k], f, bond, sym, fb=fb)
        return {"is": seg(nav, spy, START, IS_END, td), "oos": seg(nav, spy, OOS_START, END, td)}

    def dlt(a, b):
        return {p: {"cagr": round(b[p]["cagr"] - a[p]["cagr"], 2), "mdd": round(b[p]["mdd"] - a[p]["mdd"], 2),
                    "sharpe": round(b[p]["sharpe"] - a[p]["sharpe"], 2)} for p in ("is", "oos")}

    B0 = go(); out["B0"] = B0
    res = {}
    for K in (3, 5):
        for f in (0.3, 0.6):
            for bond in ("IEF", "TLT"):
                for side in ("sym", "buy", "sell"):
                    kw = dict(K=K, f=f, bond=bond)
                    if side == "buy":
                        kw.update(fb=0.0)
                    elif side == "sell":
                        kw.update(f=0.0, fb=f, sym=False)
                    o = go(**kw); nm = f"K{K}_f{f}_{bond}_{side}"
                    res[nm] = {"d": dlt(B0, o), "turn_oos": o["oos"]["turn"]}
                    print(nm, res[nm], flush=True)
    out["grid_lag2"] = res
    oos = sorted(v["d"]["oos"]["cagr"] for v in res.values()); iss = sorted(v["d"]["is"]["cagr"] for v in res.values())
    out["median"] = {"is": iss[len(iss) // 2], "oos": oos[len(oos) // 2], "oos_pos": f"{sum(1 for x in oos if x > 0)}/{len(oos)}"}
    best = max(res, key=lambda k: res[k]["d"]["is"]["sharpe"])
    out["is_pick"] = {"name": best, **res[best]}
    print("MEDIAN", out["median"], "PICK", best, res[best], flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
