"""📈 11/6 14시 — k1106_portexec2(2차: 예약 종가판 s1_c1 흔들기·비용·해별): 💼 기본 포트의 🔄 월말 흐름도 「한국에서 할 수 있는 체결」로 + 날짜별 분해(과적합 확인)
  12시 k1106_exectime3(🎯)와 같은 run() 틀 · 💼 = S&P 47.5·나스닥 47.5·금 5 / 하락 31.5·31.5·금 11 + 변동성 맞춤(목표 15·아래 30%) + 🧭 추세 칸 주차
  판: 신호 앞당김 s0·s1 × 체결 c0(같은 종가, 한국 불가)·o1(다음 날 시가 23:30)·c1(다음 날 종가) · 흐름 없음 c0·o1·c1
  분해: (흐름 판 − 흐름 없음) 하루 수익 차이를 「달 끝에서 몇째 날(0=마지막)」·「다음 달 첫째~셋째 날」로 나눠 앞/뒤 평균 bp·t
  대조: 마지막 날(rfe 0) 신호를 끈 판 · 흔들기 K4·K6·문턱 0.4·0.6 · 비용 0.25% · 🎯 도 분해만 같이
→ market/lab/k1106_portexec2.json
"""
from __future__ import annotations
import datetime as dt, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from src.conc_bt import SECT, START, IS_END, OOS_START, regimes
from k1011_size import load, seg
from src.kick_ideas_bt import ydl, cash_daily, trend_run, TREND_U
from k1028_qflow import drifts, make, rfe, G_CONC, RD_CONC, G_PORT, RD_PORT
from k1106_exectime3 import run, KEYS

OUT = Path("market/lab/k1106_portexec2.json")
A = math.sqrt(252) * 100


def tstat(x):
    x = x.dropna()
    if len(x) < 5 or x.std() == 0:
        return {"n": int(len(x)), "bp": 0.0, "t": 0.0, "sum": 0.0}
    return {"n": int(len(x)), "bp": round(float(x.mean()) * 1e4, 2), "t": round(float(x.mean() / x.std() * math.sqrt(len(x))), 2),
            "sum": round(float(x.sum()) * 100, 2)}


def main():
    C = load()
    px = ydl(["^IRX", "IEF", "SPY", "QQQ", "GLD"] + TREND_U, start="2006-01-01")
    irx = px.pop("^IRX")["close"]
    C["IEF"] = px.pop("IEF")["close"].reindex(C.index).ffill()
    O = {}
    for k in ["SPY", "QQQ", "GLD"]:
        O[k] = px.pop(k)
    C["TLT"] = px["TLT"]["close"].reindex(C.index).ffill()
    O["TLT"] = px["TLT"]
    allidx = pd.DatetimeIndex(sorted(set().union(*[set(px[s].index) for s in TREND_U if s in px])))
    cdl = cash_daily(irx, allidx)
    common = max(px[s].index[0] for s in TREND_U if s in px)
    reg = regimes(C["SPY"], C[[t for t in SECT if t in C.columns]])["A"].reindex(C.index).fillna(False)
    idx = C.index[C.index >= pd.Timestamp(START)]
    spy = C["SPY"].reindex(idx); END = str(idx[-1].date())
    s, _, _ = trend_run({k: px[k] for k in TREND_U if k in px}, cdl, 100, 50, "risk", start=str(common.date()))
    C["TRD"] = (1 + s.reindex(C.index).fillna(0.0)).cumprod()
    DM, DQ = drifts(C)
    msig, mfs = make(C, DM, DQ)
    rv = (0.5 * C["SPY"].pct_change() + 0.5 * C["QQQ"].pct_change()).rolling(20).std() * A
    SC = {"port": (15.0 / rv).clip(upper=1.0, lower=0.30).fillna(1.0), "conc": (22.0 / rv).clip(upper=1.0, lower=0.70).fillna(1.0)}
    GR = {"port": (G_PORT, RD_PORT), "conc": (G_CONC, RD_CONC)}

    ON = pd.DataFrame(0.0, index=C.index, columns=KEYS); ID = pd.DataFrame(0.0, index=C.index, columns=KEYS)
    for k, src in [("SPY", "SPY"), ("QQQ", "QQQ"), ("GLD", "GLD"), ("BND", "TLT")]:
        f = O[src].reindex(C.index)
        on = (f["open"] / f["close"].shift(1) - 1).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-0.3, 0.3)
        cc = C[src].pct_change().fillna(0.0)
        ON[k] = on; ID[k] = (1 + cc) / (1 + on) - 1
    ID["TRD"] = C["TRD"].pct_change().fillna(0.0)

    out = {"at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "from": START, "to": END}
    z = pd.Series(0.0, index=C.index)
    res, navs = {}, {}

    def go(nm, base, a_, f_, m, cost=0.001):
        G, Rd = GR[base]
        nav, td = run(C, ON, ID, reg, idx, SC[base], a_, f_, G, Rd, m, cost)
        a = seg(nav, spy, START, IS_END, td); b = seg(nav, spy, OOS_START, END, td)
        res[nm] = {"is": a, "oos": b}; navs[nm] = nav
        print(nm, a["cagr"], b["cagr"], b["mdd"], b["turn"], flush=True)

    def sh(a, k):
        return a.shift(-k).fillna(0.0)
    for base in ("port", "conc"):
        go(f"{base}_noflow_c1", base, z, z, "c1")
        go(f"{base}_noflow_c1_c25", base, z, z, "c1", 0.0025)
        go(f"{base}_s1_c1", base, sh(msig, 1), sh(mfs, 1), "c1")
        go(f"{base}_s0_c1", base, msig, mfs, "c1")
        go(f"{base}_s1_c1_c25", base, sh(msig, 1), sh(mfs, 1), "c1", 0.0025)
        r0 = rfe(C.index) == 0
        go(f"{base}_nolast_s1_c1", base, sh(msig.where(~r0, 0.0), 1), sh(mfs.where(~r0, 0.0), 1), "c1")
        for K_, th, f in ((4, 0.005, .6), (6, 0.005, .6), (5, 0.004, .6), (5, 0.006, .6), (5, 0.005, .48), (5, 0.005, .72)):
            s2, f2 = make(C, DM, DQ, K=K_, th=th, f=f)
            go(f"{base}_shake_K{K_}_th{th}_f{f}_s1_c1", base, sh(s2, 1), sh(f2, 1), "c1")
    # 해별(뒤 구간) 차이: 예약 종가판 − 흐름 없음
    yr = {}
    for base in ("port", "conc"):
        a = navs[f"{base}_s1_c1"]; b = navs[f"{base}_noflow_c1"]; o = {}
        for y in range(2009, idx[-1].year + 1):
            m = a.index.year == y
            if m.sum() > 20:
                pa = a[a.index < a[m].index[0]].iloc[-1]; pb = b[b.index < b[m].index[0]].iloc[-1]
                o[y] = round(((a[m].iloc[-1] / pa) - (b[m].iloc[-1] / pb)) * 100, 2)
        yr[base] = o
        print("해별", base, o, flush=True)
    out["res"] = res; out["yr_diff"] = yr
    out["note"] = "s1_c1 = 하루 먼저 알고(이틀 전 종가 쏠림) 그날 밤 예약 종가 체결 · 변동성·국면도 다음 날 종가(현실) · ETF 만 · 레버리지 없음 · 매수 추천 아님"
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
